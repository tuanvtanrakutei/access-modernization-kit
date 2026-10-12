param(
  [Parameter(Mandatory = $true)][string]$Database,
  [string]$Backends = "",
  [Parameter(Mandatory = $true)][string]$Requests,
  [Parameter(Mandatory = $true)][string]$Out,
  [int]$Rows = 20
)
# Reads the first rows of each requested record source from a DISPOSABLE copy, for the
# runtime mockup (A91). Called by collect_mockup_data.py, which makes the copies; never
# point this at an original. Links whose target file has the same name as a supplied
# backend copy are re-pointed at that copy first, so a join through a link resolves.
$ErrorActionPreference = 'Stop'
$requestList = Get-Content -Raw -Encoding UTF8 -LiteralPath $Requests | ConvertFrom-Json
$engine = New-Object -ComObject DAO.DBEngine.36
$db = $engine.OpenDatabase($Database, $false, $false)
$relinked = New-Object System.Collections.Generic.List[string]
$backendFiles = @($Backends.Split(';') | Where-Object { $_ })
foreach ($table in $db.TableDefs) {
  $connect = [string]$table.Connect
  if (-not $connect) { continue }
  $index = $connect.ToUpper().IndexOf('DATABASE=')
  if ($index -lt 0) { continue }
  $leaf = Split-Path ($connect.Substring($index + 9)) -Leaf
  foreach ($backend in $backendFiles) {
    if ((Split-Path $backend -Leaf) -eq $leaf) {
      $table.Connect = ';DATABASE=' + $backend
      $table.RefreshLink()
      $relinked.Add($table.Name)
    }
  }
}

function Convert-Value($value) {
  if ($null -eq $value -or $value -is [System.DBNull]) { return $null }
  if ($value -is [datetime]) { return $value.ToString('s') }
  if ($value -is [byte[]]) { return '(binary)' }
  return $value
}

$results = [ordered]@{}
foreach ($request in $requestList) {
  $entry = [ordered]@{ columns = @(); rows = @(); total = $null; error = '' }
  try {
    $rs = $db.OpenRecordset([string]$request.source, 4)
    $columns = @()
    for ($i = 0; $i -lt $rs.Fields.Count; $i++) { $columns += [string]$rs.Fields.Item($i).Name }
    $entry.columns = $columns
    $list = New-Object System.Collections.Generic.List[object]
    $count = 0
    while (-not $rs.EOF -and $count -lt $Rows) {
      $row = [ordered]@{}
      for ($i = 0; $i -lt $rs.Fields.Count; $i++) { $row[$columns[$i]] = Convert-Value $rs.Fields.Item($i).Value }
      $list.Add($row)
      $count++
      $rs.MoveNext()
    }
    # How many rows the screen holds in all, for its record count: a snapshot's
    # RecordCount is exact once it has been moved to the end.
    if ($rs.EOF -and $count -eq 0) { $entry.total = 0 }
    else { if (-not $rs.EOF) { $rs.MoveLast() }; $entry.total = $rs.RecordCount }
    $rs.Close()
    $entry.rows = $list.ToArray()
  } catch {
    $entry.error = $_.Exception.Message
  }
  $results[[string]$request.key] = $entry
}
$db.Close()
$payload = [ordered]@{ relinked = $relinked.ToArray(); results = $results }
[System.IO.File]::WriteAllText($Out, ($payload | ConvertTo-Json -Depth 8), (New-Object System.Text.UTF8Encoding $false))
