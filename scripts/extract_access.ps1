[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Snapshot,
    [Parameter(Mandatory = $true)][string]$DatabaseId,
    [Parameter(Mandatory = $true)][string]$SessionId,
    [Parameter(Mandatory = $true)][string]$OutputDir,
    [string]$PasswordEnvironment = ''
)

$ErrorActionPreference = 'Stop'

function Get-SafeName([string]$Name) {
    return ($Name -replace '[^A-Za-z0-9_.-]', '_')
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

function Add-Component($List, [string]$Kind, [string]$Name, [string]$SourcePath, [string]$Container, [hashtable]$Metadata) {
    $id = ('{0}:{1}:{2}' -f $DatabaseId, $Kind, $Name)
    [void]$List.Add([ordered]@{
        id = $id
        kind = $Kind
        name = $Name
        container = $Container
        module_hint = $Container
        source_paths = @($SourcePath)
        depends_on = @()
        metadata = $Metadata
    })
}

$snapshotPath = (Resolve-Path -LiteralPath $Snapshot).Path
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
$database = $null
$status = 'EXTRACTED'
$databasePassword = if ([string]::IsNullOrWhiteSpace($PasswordEnvironment)) { '' } else { [Environment]::GetEnvironmentVariable($PasswordEnvironment) }
if (-not [string]::IsNullOrWhiteSpace($PasswordEnvironment) -and $null -eq $databasePassword) {
    throw "Password environment variable is not set: $PasswordEnvironment"
}

try {
    $application = New-Object -ComObject Access.Application
    $application.Visible = $false
    if ([System.IO.Path]::GetExtension($snapshotPath).ToLowerInvariant() -eq '.adp') {
        $application.OpenAccessProject($snapshotPath, $false)
    } else {
        if ([string]::IsNullOrEmpty($databasePassword)) {
            $application.OpenCurrentDatabase($snapshotPath, $false)
        } else {
            $application.OpenCurrentDatabase($snapshotPath, $false, $databasePassword)
        }
    }
    try { $database = $application.CurrentDb() } catch { [void]$warnings.Add('DAO CurrentDb is unavailable; ADP/server metadata may require a separate SQL Server export.') }

    if ($database -ne $null) {
        foreach ($table in $database.TableDefs) {
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
            $connect = Redact-Connection ([string]$table.Connect)
            $item = [ordered]@{ name = [string]$table.Name; source_table_name = [string]$table.SourceTableName; connect = $connect; attributes = [int]$table.Attributes; fields = $fields; indexes = $indexes }
            [void]$tables.Add($item)
            Add-Component $components 'table' ([string]$table.Name) 'schema/tables.json' 'data' @{ linked = -not [string]::IsNullOrWhiteSpace($connect); source_table_name = [string]$table.SourceTableName }
        }
        foreach ($relation in $database.Relations) {
            $relationFields = @()
            foreach ($field in $relation.Fields) { $relationFields += [ordered]@{ name = [string]$field.Name; foreign_name = [string]$field.ForeignName } }
            [void]$relations.Add([ordered]@{ name = [string]$relation.Name; table = [string]$relation.Table; foreign_table = [string]$relation.ForeignTable; attributes = [int]$relation.Attributes; fields = $relationFields })
        }
        foreach ($query in $database.QueryDefs) {
            $safe = Get-SafeName ([string]$query.Name)
            $relative = "queries/$safe.sql"
            $queryText = Redact-Connection ([string]$query.SQL)
            Set-Content -LiteralPath (Join-Path $root $relative) -Value $queryText -Encoding UTF8
            Add-Component $components 'query' ([string]$query.Name) $relative 'queries' @{ connect = Redact-Connection ([string]$query.Connect); returns_records = [bool]$query.ReturnsRecords }
        }
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
                Add-Component $components ([string]$export.Kind) $name $relative ([string]$export.Folder) @{}
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

    $projectContext = [ordered]@{
        access_version = [string]$application.Version
        process_bitness = if ([IntPtr]::Size -eq 8) { '64-bit' } else { '32-bit' }
        file_format = [System.IO.Path]::GetExtension($snapshotPath).TrimStart('.').ToLowerInvariant()
        startup_form = if ($database -ne $null) { Get-DbProperty $database 'StartupForm' } else { '' }
        startup_show_db_window = if ($database -ne $null) { Get-DbProperty $database 'StartupShowDBWindow' } else { '' }
        autoexec_present = @($application.CurrentProject.AllMacros | Where-Object { $_.Name -eq 'AutoExec' }).Count -gt 0
        conditional_compilation_constants = if ($database -ne $null) { Get-DbProperty $database 'Conditional Compilation Arguments' } else { '' }
        references = $references
    }
} catch {
    $status = 'BLOCKED'
    $projectContext = [ordered]@{ file_format = [System.IO.Path]::GetExtension($snapshotPath).TrimStart('.').ToLowerInvariant() }
    [void]$warnings.Add(('Access automation failed: {0}' -f $_.Exception.Message))
} finally {
    if ($application -ne $null) {
        try { $application.CloseCurrentDatabase() } catch {}
        try { $application.Quit() } catch {}
        try { [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($application) } catch {}
    }
}

$tables | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $root 'schema/tables.json') -Encoding UTF8
$relations | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $root 'schema/relations.json') -Encoding UTF8
$generatedAt = [DateTime]::UtcNow.ToString('o')
$componentIndex = [ordered]@{ schema_version = '2.1'; app_id = $DatabaseId; generated_at = $generatedAt; components = $components }
$componentIndex | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath (Join-Path $root 'component-index.json') -Encoding UTF8
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $snapshotPath).Hash.ToLowerInvariant()
$result = [ordered]@{
    schema_version = '2.1'
    database_id = $DatabaseId
    session_id = $SessionId
    source = [ordered]@{ path = '<ORIGINAL_REDACTED_BY_ADAPTER>'; format = [System.IO.Path]::GetExtension($snapshotPath).TrimStart('.').ToLowerInvariant(); sha256 = $hash }
    snapshot = [ordered]@{ path = $snapshotPath; sha256 = $hash }
    status = $status
    runtime = [ordered]@{ adapter = 'extract_access.ps1'; access_automation = $application -ne $null; runtime_tested = $true }
    project_context = $projectContext
    components = $components
    warnings = $warnings
}
$result | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath (Join-Path $root 'access-extraction.json') -Encoding UTF8
if ($status -eq 'BLOCKED') { exit 2 }
exit 0
