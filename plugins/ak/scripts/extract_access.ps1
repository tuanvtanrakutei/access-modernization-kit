[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Snapshot,
    [Parameter(Mandatory = $true)][string]$DatabaseId,
    [Parameter(Mandatory = $true)][string]$SessionId,
    [Parameter(Mandatory = $true)][string]$OutputDir,
    [string]$PasswordEnvironment = '',
    # Which runtime to drive, declared rather than inferred. COM resolves a bare
    # ProgId to whichever Office registered itself last; a version-qualified one
    # ('Access.Application.11') pins the install the caller actually means.
    [string]$AccessProgId = 'Access.Application',
    [string]$DaoProgId = 'DAO.DBEngine.36',
    # Skip the Access host entirely and keep only the DAO tier.
    [switch]$SkipObjectExport,
    # Do not register forms, reports, macros, modules or queries at all. Use this when an
    # imported export of the same database supplies them: without it both adapters
    # describe the same objects and the bundle counts every one of them twice.
    [switch]$SkipObjectInventory,
    # Show the Access host so an operator can dismiss dialogs it raises. A database
    # whose VBA project has a broken reference throws a modal "Error in loading DLL"
    # while opening - before any macro runs, so AutomationSecurity cannot prevent it -
    # and a hidden host then waits forever on a dialog nobody can see. This makes the
    # attended run possible instead of leaving the objects unexportable.
    [switch]$VisibleHost
)

$ErrorActionPreference = 'Stop'

function Get-NameDigest([string]$Name) {
    $sha1 = [System.Security.Cryptography.SHA1]::Create()
    try {
        $digest = $sha1.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($Name))
    } finally {
        $sha1.Dispose()
    }
    return (-join ($digest[0..3] | ForEach-Object { $_.ToString('x2') }))
}

function Get-SafeName([string]$Name) {
    # Keep the object's real name. NTFS stores Japanese filenames perfectly well, and
    # an earlier version replaced every non-[A-Za-z0-9_.-] character with an
    # underscore - which turned an entire Japanese application into unreadable
    # `_______-84e869a1.txt` files and forced a hash suffix to undo the collisions the
    # sanitize had just created. Only characters Windows genuinely forbids in a file
    # name are replaced, and the digest is appended solely when the name had to be
    # altered or truncated, so it can no longer collide.
    $illegal = [regex]::Escape(-join [System.IO.Path]::GetInvalidFileNameChars())
    $sanitized = ($Name -replace "[$illegal]", '_')
    $altered = $sanitized -ne $Name
    if ([string]::IsNullOrWhiteSpace($sanitized)) {
        $sanitized = 'object'
        $altered = $true
    }
    # Leave headroom under the 255-character path component limit for the extension
    # and any digest suffix.
    if ($sanitized.Length -gt 120) {
        $sanitized = $sanitized.Substring(0, 120)
        $altered = $true
    }
    # A trailing dot or space is legal in the string but not on disk.
    $trimmed = $sanitized.TrimEnd('.', ' ')
    if ($trimmed -ne $sanitized) {
        $sanitized = if ([string]::IsNullOrEmpty($trimmed)) { 'object' } else { $trimmed }
        $altered = $true
    }
    # CON, PRN, NUL, COM1 and friends cannot be used as a file name on Windows even
    # with an extension, so a query legitimately named one of them needs the suffix.
    if ($sanitized -match '^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$') { $altered = $true }
    if ($altered) { return ('{0}-{1}' -f $sanitized, (Get-NameDigest $Name)) }
    return $sanitized
}

function Redact-Connection([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) { return '' }
    $redacted = $Value -replace '(?i)(PWD|PASSWORD|TOKEN|SECRET|API[_-]?KEY)\s*=\s*[^;]*', '$1=<REDACTED>'
    return $redacted -replace '(?i)(UID|USER ID)\s*=\s*[^;]*', '$1=<REDACTED>'
}

function Scrub-Export([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $text = Get-Content -Raw -LiteralPath $Path
    $text = Redact-Connection $text
    Set-Content -LiteralPath $Path -Value $text -Encoding UTF8
}

function Get-DbProperty($Database, [string]$Name) {
    try { return [string]$Database.Properties.Item($Name).Value } catch { return '' }
}

function Add-Component($List, [string]$Kind, [string]$Name, [string]$SourcePath, [string]$Container, [hashtable]$Metadata, [string]$Text = '') {
    $id = ('{0}:{1}:{2}' -f $DatabaseId, $Kind, $Name)
    $component = [ordered]@{
        id = $id
        kind = $Kind
        name = $Name
        container = $Container
        module_hint = $Container
        source_paths = @($SourcePath)
        depends_on = @()
        metadata = $Metadata
    }
    # Code records travel with their text so the bundle can write real content
    # instead of an empty file next to a correct-looking inventory entry.
    if (-not [string]::IsNullOrEmpty($Text)) { $component['text'] = $Text }
    [void]$List.Add($component)
}

$snapshotPath = (Resolve-Path -LiteralPath $Snapshot).Path
# Hash the snapshot before Access opens it. Access keeps the file handle for a
# moment after Quit(), so hashing at the end raced the release and threw
# FileReadError, killing the script before it could write access-extraction.json
# and taking every collected warning with it. Opening the database also mutates
# it (lock bookkeeping, AutoExec), so the pre-open digest is the one that
# actually matches the source the caller handed us.
$snapshotHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $snapshotPath).Hash.ToLowerInvariant()
$root = [System.IO.Path]::GetFullPath($OutputDir)
$directories = @('forms', 'reports', 'macros', 'vba', 'queries', 'schema')
New-Item -ItemType Directory -Path $root -Force | Out-Null
foreach ($directory in $directories) {
    New-Item -ItemType Directory -Path (Join-Path $root $directory) -Force | Out-Null
}

$components = [System.Collections.ArrayList]::new()
$warnings = [System.Collections.ArrayList]::new()
$tables = [System.Collections.ArrayList]::new()
$relations = [System.Collections.ArrayList]::new()
$references = [System.Collections.ArrayList]::new()
$application = $null
$automationUsed = $false
$skippedTables = 0
$skippedQueries = 0
$macroNames = [System.Collections.Generic.HashSet[string]]::new()
$database = $null
$status = 'EXTRACTED'
$databasePassword = if ([string]::IsNullOrWhiteSpace($PasswordEnvironment)) { '' } else { [Environment]::GetEnvironmentVariable($PasswordEnvironment) }
if (-not [string]::IsNullOrWhiteSpace($PasswordEnvironment) -and $null -eq $databasePassword) {
    throw "Password environment variable is not set: $PasswordEnvironment"
}

$isAdp = [System.IO.Path]::GetExtension($snapshotPath).ToLowerInvariant() -eq '.adp'
$objectIndex = @{}
$projectContext = [ordered]@{
    access_version = ''
    process_bitness = if ([IntPtr]::Size -eq 8) { '64-bit' } else { '32-bit' }
    file_format = [System.IO.Path]::GetExtension($snapshotPath).TrimStart('.').ToLowerInvariant()
    startup_form = ''
    startup_show_db_window = ''
    autoexec_present = $false
    conditional_compilation_constants = ''
    references = $references
}

# Reads everything the Jet layer knows: schema, queries, and the object inventory.
# Called with a DAO Database, which can come from DAO itself or, for an ADP, from
# the Access host.
function Read-JetLayer($Database) {
    foreach ($table in $Database.TableDefs) {
        # Every Access database carries MSys* system tables whose definitions the DAO
        # account cannot read ("no read definitions permission for table or query
        # 'MSysACEs'"). They are Access's own bookkeeping, never business schema, so
        # they are skipped rather than reported as failures.
        $tableName = [string]$table.Name
        if ($tableName -like 'MSys*') { continue }
        # Temporary/work tables Access leaves behind, excluded by the same rule this
        # package's own exporter applies in tools/ExportAccessObjects.bas.
        if ($tableName -like '~*') { $script:skippedTables++; continue }
        # Read the link metadata first. A table linked to a missing external file
        # throws when its fields are enumerated, and those are exactly the tables that
        # define the application's boundary - losing them loses the boundary evidence
        # Phase 1 depends on.
        $connect = ''
        $sourceTableName = ''
        try {
            $connect = Redact-Connection ([string]$table.Connect)
            $sourceTableName = [string]$table.SourceTableName
        } catch {}
        $linked = -not [string]::IsNullOrWhiteSpace($connect)
        # One unreadable table must never abort the whole extraction. Before this
        # guard a single failure ended the run at that table and silently dropped
        # every later table plus all queries, forms, reports and modules.
        try {
            $fields = @()
            foreach ($field in $table.Fields) {
                $fields += [ordered]@{ name = [string]$field.Name; type = [int]$field.Type; size = [int]$field.Size; required = [bool]$field.Required }
            }
            $indexes = @()
            foreach ($index in $table.Indexes) {
                $indexFields = @()
                foreach ($indexField in $index.Fields) { $indexFields += [string]$indexField.Name }
                $indexes += [ordered]@{ name = [string]$index.Name; primary = [bool]$index.Primary; unique = [bool]$index.Unique; fields = $indexFields }
            }
            # Access creates an ImportErrors table for every failed import, and a
            # long-lived application accumulates hundreds of them: this frontend
            # carried 210 against 21 real tables, which would have inflated the
            # bundle's own table inventory tenfold. They are identified by shape -
            # exactly Error(Text)/Field(Text)/Row(Long) - not by name, because the
            # name is localized and one legitimate table here also matched the
            # Japanese word for "error". Same rule as tools/ExportAccessObjects.bas.
            if ($fields.Count -eq 3 -and $fields[0].type -eq 10 -and $fields[1].type -eq 10 -and $fields[2].type -eq 4) {
                $script:skippedTables++
            } else {
                [void]$tables.Add([ordered]@{ name = $tableName; source_table_name = $sourceTableName; connect = $connect; attributes = [int]$table.Attributes; fields = $fields; indexes = $indexes; read_error = '' })
                # connect belongs on the component too. The bundle builds its linked-table
                # records from components, not from the tables array, so omitting it left the
                # boundary half-recorded: source_table_name gave the file or table name while
                # the location it lives in - here a mapped L: drive every linked table in the
                # application depends on - reached the bundle only inside an error sentence.
                Add-Component $components 'table' $tableName 'schema/tables.json' 'data' @{ linked = $linked; source_table_name = $sourceTableName; connect = $connect }
            }
        } catch {
            $script:status = 'PARTIAL'
            $reason = [string]$_.Exception.Message
            [void]$warnings.Add(('Could not read table {0}: {1}' -f $tableName, $reason))
            # Keep the identity and link target even when the definition is unreadable,
            # so an unreachable interface is recorded as a known boundary rather than
            # vanishing from the inventory.
            [void]$tables.Add([ordered]@{ name = $tableName; source_table_name = $sourceTableName; connect = $connect; attributes = 0; fields = @(); indexes = @(); read_error = $reason })
            Add-Component $components 'table' $tableName 'schema/tables.json' 'data' @{ linked = $linked; source_table_name = $sourceTableName; connect = $connect; read_error = $reason }
        }
    }
    foreach ($relation in $Database.Relations) {
        try {
            $relationFields = @()
            foreach ($field in $relation.Fields) { $relationFields += [ordered]@{ name = [string]$field.Name; foreign_name = [string]$field.ForeignName } }
            [void]$relations.Add([ordered]@{ name = [string]$relation.Name; table = [string]$relation.Table; foreign_table = [string]$relation.ForeignTable; attributes = [int]$relation.Attributes; fields = $relationFields })
        } catch {
            $script:status = 'PARTIAL'
            [void]$warnings.Add(('Could not read a relation: {0}' -f $_.Exception.Message))
        }
    }
    foreach ($query in $Database.QueryDefs) {
        $queryName = '?'
        try { $queryName = [string]$query.Name } catch {}
        # Access generates hidden ~sq_* queries to back form and report record
        # sources. They are not authored objects, and this package's own exporter
        # skips them; including them doubled this frontend's query count.
        if ($queryName.StartsWith('~')) {
            $script:skippedQueries++
            continue
        }
        # An imported export carries the query SQL too, so "object inventory" covers
        # queries as well. Registering them here as well doubled the bundle's own
        # access_sql count.
        if ($SkipObjectInventory) { continue }
        try {
            $safe = Get-SafeName $queryName
            $relative = "queries/$safe.sql"
            $queryText = Redact-Connection ([string]$query.SQL)
            Set-Content -LiteralPath (Join-Path $root $relative) -Value $queryText -Encoding UTF8
            # The bundle's code sections carry the text inline, so a component that
            # only points at a sibling file assembles into an empty record.
            Add-Component $components 'query' $queryName $relative 'queries' @{ connect = Redact-Connection ([string]$query.Connect); returns_records = [bool]$query.ReturnsRecords } $queryText
        } catch {
            $script:status = 'PARTIAL'
            [void]$warnings.Add(('Could not read query {0}: {1}' -f $queryName, $_.Exception.Message))
        }
    }
    # DAO's own containers list every form, report, macro and module by name. That is
    # the whole object inventory without starting the Access host - so a database
    # whose VBA project will not load still yields a complete inventory, and only the
    # exported definition text is missing.
    foreach ($container in @(
        @{ Name = 'Forms'; Kind = 'form'; Folder = 'forms' },
        @{ Name = 'Reports'; Kind = 'report'; Folder = 'reports' },
        @{ Name = 'Scripts'; Kind = 'macro'; Folder = 'macros' },
        @{ Name = 'Modules'; Kind = 'module'; Folder = 'vba' }
    )) {
        try {
            foreach ($document in $Database.Containers($container.Name).Documents) {
                $name = [string]$document.Name
                # Still noted, because project_context reports whether an AutoExec
                # macro exists and that is a real startup fact either way.
                if ($container.Kind -eq 'macro') { [void]$macroNames.Add($name) }
                if ($SkipObjectInventory) { continue }
                $component = [ordered]@{
                    id = ('{0}:{1}:{2}' -f $DatabaseId, $container.Kind, $name)
                    kind = $container.Kind
                    name = $name
                    container = $container.Folder
                    module_hint = $container.Folder
                    source_paths = @()
                    depends_on = @()
                    metadata = @{ definition_exported = $false }
                }
                [void]$components.Add($component)
                $objectIndex[($container.Kind + '|' + $name)] = $component
            }
        } catch {
            $script:status = 'PARTIAL'
            [void]$warnings.Add(('Could not list the {0} container: {1}' -f $container.Name, $_.Exception.Message))
        }
    }
    $projectContext['startup_form'] = Get-DbProperty $Database 'StartupForm'
    $projectContext['startup_show_db_window'] = Get-DbProperty $Database 'StartupShowDBWindow'
    $projectContext['conditional_compilation_constants'] = Get-DbProperty $Database 'Conditional Compilation Arguments'
    $projectContext['autoexec_present'] = $macroNames.Contains('AutoExec')
}

function Write-Extraction {
    $tables | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $root 'schema/tables.json') -Encoding UTF8
    $relations | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $root 'schema/relations.json') -Encoding UTF8
    $generatedAt = [DateTime]::UtcNow.ToString('o')
    $componentIndex = [ordered]@{ schema_version = '2.1'; app_id = $DatabaseId; generated_at = $generatedAt; components = $components }
    $componentIndex | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath (Join-Path $root 'component-index.json') -Encoding UTF8
    $hash = $snapshotHash
    $result = [ordered]@{
        schema_version = '2.1'
        database_id = $DatabaseId
        session_id = $SessionId
        source = [ordered]@{ path = '<ORIGINAL_REDACTED_BY_ADAPTER>'; format = [System.IO.Path]::GetExtension($snapshotPath).TrimStart('.').ToLowerInvariant(); sha256 = $hash }
        snapshot = [ordered]@{ path = $snapshotPath; sha256 = $hash }
        status = $status
        runtime = [ordered]@{
            adapter = 'extract_access.ps1'
            access_automation = $automationUsed
            runtime_tested = $true
            # Which tier produced what, so a consumer can tell a names-only inventory
            # from one carrying exported definitions.
            dao_tier = [ordered]@{ prog_id = $DaoProgId; used = $daoUsed }
            object_export_tier = [ordered]@{ prog_id = $AccessProgId; used = $automationUsed; skipped = [bool]$SkipObjectExport }
        }
        project_context = $projectContext
        components = $components
        # Field and index detail travels with the result, not only in schema/tables.json.
        # The bundle adapter normalizes from this record alone, so detail left behind in
        # a sibling file could never reach databases.fields / databases.indexes, and the
        # capabilities Phase 1 requires stayed permanently unreachable.
        tables = $tables
        warnings = $warnings
    }
    $result | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath (Join-Path $root 'access-extraction.json') -Encoding UTF8
}

# ---- Tier 1: DAO, read-only. No Access host means no AutoExec, no VBA project
# load, and therefore none of the modal dialogs that can stall an unattended run.
$daoEngine = $null
$daoUsed = $false
if (-not $isAdp) {
    try {
        $daoEngine = New-Object -ComObject $DaoProgId
        $database = if ([string]::IsNullOrEmpty($databasePassword)) {
            $daoEngine.OpenDatabase($snapshotPath, $false, $true)
        } else {
            $daoEngine.OpenDatabase($snapshotPath, $false, $true, (';PWD=' + $databasePassword))
        }
        $daoUsed = $true
        Read-JetLayer $database
    } catch {
        $status = 'PARTIAL'
        [void]$warnings.Add(('DAO tier failed ({0}): {1}' -f $DaoProgId, $_.Exception.Message))
    } finally {
        if ($null -ne $database) { try { $database.Close() } catch {} ; $database = $null }
        if ($null -ne $daoEngine) { try { [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($daoEngine) } catch {} ; $daoEngine = $null }
    }
}

# A silent exclusion reads as "this is everything there was", so say what was
# dropped and why.
if ($skippedTables -gt 0) {
    [void]$warnings.Add(('Excluded {0} non-model tables: Access temporary (~*) and auto-generated ImportErrors tables.' -f $skippedTables))
}
if ($skippedQueries -gt 0) {
    [void]$warnings.Add(('Excluded {0} Access-generated hidden queries (~*) backing form and report record sources.' -f $skippedQueries))
}

# Persist what the DAO tier produced before starting a host that may hang. The
# caller's timeout kills this process outright, so anything written only at the end
# would be lost along with a complete, usable schema inventory.
Write-Extraction

# ---- Tier 2: the Access host, needed only to export object definition text and to
# read VBA references. It is allowed to fail without costing the DAO tier's results.
if ($SkipObjectExport) {
    [void]$warnings.Add('Object definition export was skipped; the inventory carries names only.')
}
$hostPidsBefore = @(Get-Process MSACCESS -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
if (-not $SkipObjectExport) {
try {
    $application = New-Object -ComObject $AccessProgId
    $application.Visible = [bool]$VisibleHost
    if ($VisibleHost) {
        [void]$warnings.Add('Access host ran visible: an operator may have dismissed dialogs, so this run is attended and not reproducible unattended.')
    }
    # Record which Access processes this run started. A hung host has to be
    # killable by the caller, and only these PIDs are ours - an Access instance the
    # operator opened by hand must never be touched.
    $ourPids = @(Get-Process MSACCESS -ErrorAction SilentlyContinue | Where-Object { $hostPidsBefore -notcontains $_.Id } | ForEach-Object { $_.Id })
    if ($ourPids.Count -gt 0) {
        [ordered]@{ session_id = $SessionId; pids = $ourPids } | ConvertTo-Json -Compress | Set-Content -LiteralPath (Join-Path $root 'access-host.json') -Encoding UTF8
    }
    # Opening a database runs its AutoExec macro and startup VBA. On a real
    # application that code hit an error and dropped into the VBA debugger's break
    # mode - invisible, because the host is hidden - and the extraction hung forever.
    # Asking for macros to be force-disabled is worth doing, but do not rely on it:
    # measured against Access 2003, the property is accepted without error and the
    # startup VBA still executes, because it governs macro security for documents
    # opened by automation rather than Access's own startup path. The defences that
    # actually hold are the DAO tier (no host at all), the timeout, and -VisibleHost
    # for a database that genuinely needs an operator.
    try { $application.AutomationSecurity = 3 } catch { [void]$warnings.Add(('Could not force-disable automation macros: {0}' -f $_.Exception.Message)) }
    if ($isAdp) {
        $application.OpenAccessProject($snapshotPath, $false)
    } else {
        if ([string]::IsNullOrEmpty($databasePassword)) {
            $application.OpenCurrentDatabase($snapshotPath, $false)
        } else {
            $application.OpenCurrentDatabase($snapshotPath, $false, $databasePassword)
        }
    }
    # An ADP has no Jet file for the DAO tier to open, so its schema has to come
    # through the host. For an MDB the DAO tier already did this work.
    if (-not $daoUsed) {
        try { $database = $application.CurrentDb() } catch { [void]$warnings.Add('DAO CurrentDb is unavailable; ADP/server metadata may require a separate SQL Server export.') }
        if ($null -ne $database) { Read-JetLayer $database }
    }

    $exports = @(
        @{ Collection = $application.CurrentProject.AllForms; Type = 2; Folder = 'forms'; Kind = 'form' },
        @{ Collection = $application.CurrentProject.AllReports; Type = 3; Folder = 'reports'; Kind = 'report' },
        @{ Collection = $application.CurrentProject.AllMacros; Type = 4; Folder = 'macros'; Kind = 'macro' },
        @{ Collection = $application.CurrentProject.AllModules; Type = 5; Folder = 'vba'; Kind = 'module' }
    )
    foreach ($export in $exports) {
        foreach ($object in $export.Collection) {
            $name = [string]$object.Name
            $safe = Get-SafeName $name
            $relative = ('{0}/{1}.txt' -f $export.Folder, $safe)
            $target = Join-Path $root $relative
            try {
                $application.SaveAsText([int]$export.Type, $name, $target)
                Scrub-Export $target
                # The DAO tier already registered this object by name. Attach the
                # exported definition to that entry instead of adding a duplicate;
                # only an object DAO could not see needs a fresh component.
                $key = ([string]$export.Kind) + '|' + $name
                if ($objectIndex.ContainsKey($key)) {
                    $objectIndex[$key]['source_paths'] = @($relative)
                    $objectIndex[$key]['metadata']['definition_exported'] = $true
                    # Modules land in the bundle's code section, which carries text
                    # inline. Forms and reports only feed an inventory, so their
                    # definition stays on disk rather than bloating the result.
                    if ($export.Kind -eq 'module') {
                        try { $objectIndex[$key]['text'] = [string](Get-Content -Raw -LiteralPath $target) } catch {}
                    }
                } else {
                    Add-Component $components ([string]$export.Kind) $name $relative ([string]$export.Folder) @{ definition_exported = $true }
                }
            } catch {
                $status = 'PARTIAL'
                [void]$warnings.Add(('Failed to export {0} {1}: {2}' -f $export.Kind, $name, $_.Exception.Message))
            }
        }
    }
    try {
        foreach ($reference in $application.References) {
            [void]$references.Add([ordered]@{ name = [string]$reference.Name; guid = [string]$reference.Guid; major = [int]$reference.Major; minor = [int]$reference.Minor; full_path = [string]$reference.FullPath; broken = [bool]$reference.IsBroken })
        }
    } catch { [void]$warnings.Add(('Could not enumerate VBA references: {0}' -f $_.Exception.Message)) }

    $projectContext['access_version'] = [string]$application.Version
} catch {
    # A failed host no longer costs the DAO tier its results: schema, queries and the
    # object inventory survive, and only the exported definition text is missing.
    $status = if ($daoUsed) { 'PARTIAL' } else { 'BLOCKED' }
    [void]$warnings.Add(('Access host failed ({0}): {1}' -f $AccessProgId, $_.Exception.Message))
} finally {
    if ($application -ne $null) {
        # Record whether automation ran before releasing the RCW. Touching
        # $application afterwards - even a $null comparison - throws
        # InvalidComObjectException and aborts the run just before the result
        # file is written.
        $automationUsed = $true
        try { $application.CloseCurrentDatabase() } catch {}
        try { $application.Quit() } catch {}
        try { [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($application) } catch {}
        $application = $null
    }
}
}
Write-Extraction
if ($status -eq 'BLOCKED') { exit 2 }
exit 0
