param(
  [Parameter(Mandatory = $true)][string]$Database,
  [string]$Backends = "",
  [Parameter(Mandatory = $true)][string]$Requests,
  [Parameter(Mandatory = $true)][string]$OutDir,
  [Parameter(Mandatory = $true)][string]$Out,
  [ValidateSet('auto', 'keep', 'strip')][string]$Code = 'auto'
)
# Opens every form of a DISPOSABLE copy in the view it opens in, as an operator would see
# it, captures the Access window with any pop-up form drawn where it sits, and reads each
# control's runtime properties (A93). Called by capture_runtime_view.py, which makes the
# copies; never point this at an original.
#
# On a host whose Access cannot load the application's VBA, a form with a module is
# cancelled on opening. With -Code auto that is detected on the first such form and every
# form's code-behind is removed on the copy (SaveAsText / LoadFromText); the result says so,
# and which opening procedures went with it.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class AkRun {
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int hh, bool r);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  public delegate bool EnumProc(IntPtr h, IntPtr p);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc f, IntPtr p);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  // The other visible top-level windows of the process: a pop-up form is one of them.
  public static System.Collections.Generic.List<IntPtr> Others(IntPtr main) {
    uint mine; GetWindowThreadProcessId(main, out mine);
    var found = new System.Collections.Generic.List<IntPtr>();
    EnumWindows(delegate (IntPtr h, IntPtr p) {
      uint pid; GetWindowThreadProcessId(h, out pid);
      if (pid == mine && h != main && IsWindowVisible(h)) { found.Add(h); }
      return true;
    }, IntPtr.Zero);
    return found;
  }
}
"@
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$log = New-Object System.Collections.Generic.List[string]
# PowerShell 5.1 hands a parsed JSON array on as one object; foreach enumerates it.
$parsed = ConvertFrom-Json (Get-Content -Raw -Encoding UTF8 -LiteralPath $Requests)
$forms = @(foreach ($item in $parsed) { $item })

# The copy: no start-up form (its code is not what is being captured), and every link whose
# target has the name of a supplied backend re-pointed at that backend's copy.
$dao = New-Object -ComObject DAO.DBEngine.36
$db = $dao.OpenDatabase($Database)
try { $db.Properties.Delete('StartupForm'); $log.Add('STARTUP removed') } catch { $log.Add('STARTUP none') }
$backendFiles = @($Backends.Split(';') | Where-Object { $_ })
foreach ($table in $db.TableDefs) {
  $connect = [string]$table.Connect
  $index = $connect.ToUpper().IndexOf('DATABASE=')
  if ($index -lt 0) { continue }
  $leaf = Split-Path ($connect.Substring($index + 9)) -Leaf
  foreach ($backend in $backendFiles) {
    if ((Split-Path $backend -Leaf) -eq $leaf) {
      $table.Connect = ';DATABASE=' + $backend
      $table.RefreshLink()
      $log.Add("RELINK`t" + $table.Name)
    }
  }
}
$db.Close()

$app = New-Object -ComObject Access.Application
try { $app.AutomationSecurity = 1 } catch { }
$app.Visible = $true
$h = [IntPtr]$app.hWndAccessApp()
[AkRun]::ShowWindow($h, 1) | Out-Null
[AkRun]::MoveWindow($h, 0, 0, 1280, 900, $true) | Out-Null
$app.OpenCurrentDatabase($Database, $false)
try {

function Ev([string]$e) { try { $v = $app.Eval($e); if ($null -eq $v) { return $null } return "$v" } catch { return '#ERR' } }

function Strip-Code([string]$name, [string]$file) {
  # Byte level: the text is in the database's code page, whose trail bytes never fall on
  # CR or LF, so only ASCII markers are matched.
  $ascii = [System.Text.Encoding]::ASCII
  $app.SaveAsText(2, $name, $file)
  $bytes = [System.IO.File]::ReadAllBytes($file)
  $out = New-Object System.IO.MemoryStream
  $start = 0; $changed = $false
  for ($i = 0; $i -lt $bytes.Length - 1; $i++) {
    if ($bytes[$i] -eq 13 -and $bytes[$i + 1] -eq 10) {
      $line = if ($i -gt $start) { $bytes[$start..($i - 1)] } else { @() }
      $start = $i + 2; $i++
      $text = if ($line.Length) { $ascii.GetString($line) } else { '' }
      if ($text -match '^CodeBehindForm') { $changed = $true; break }
      if ($text -match '^\s*(HasModule|Checksum)\b' -or $text -match '="\[Event Procedure\]"') { $changed = $true; continue }
      if ($line.Length) { $out.Write($line, 0, $line.Length) }
      $out.WriteByte(13); $out.WriteByte(10)
    }
  }
  if (-not $changed) { return $false }
  [System.IO.File]::WriteAllBytes($file, $out.ToArray())
  $app.DoCmd.DeleteObject(2, $name)
  $app.LoadFromText(2, $name, $file)
  return $true
}

# Can this host run the forms' code? Try the first form that has a module.
$strip = $Code -eq 'strip'
if ($Code -eq 'auto') {
  $probe = $forms | Where-Object { $_.has_module } | Select-Object -First 1
  if ($probe) {
    try {
      $app.DoCmd.OpenForm([string]$probe.name, [int]$probe.view)
      $app.DoCmd.Close(2, [string]$probe.name, 2)
      $log.Add('VBA loads')
    } catch {
      $strip = $true
      $log.Add("VBA does not load`t" + $_.Exception.Message)
    }
  }
}
if ($strip) {
  $k = 0
  foreach ($f in $forms) {
    if (-not $f.has_module) { continue }
    $k++
    try {
      if (Strip-Code ([string]$f.name) (Join-Path $env:TEMP ("ak-runtime-strip-$k.txt"))) { $log.Add("STRIPPED`t" + $f.name) }
    } catch { $log.Add("STRIPFAIL`t" + $f.name + "`t" + $_.Exception.Message) }
  }
}

function Save-Window([string]$path) {
  $r = New-Object AkRun+RECT
  [AkRun]::GetWindowRect($h, [ref]$r) | Out-Null
  $bmp = New-Object System.Drawing.Bitmap ($r.R - $r.L), ($r.B - $r.T)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $dc = $g.GetHdc()
  [AkRun]::PrintWindow($h, $dc, 2) | Out-Null
  $g.ReleaseHdc($dc)
  # A pop-up form is its own window, outside the Access window: draw it where it sits.
  foreach ($o in [AkRun]::Others($h)) {
    $q = New-Object AkRun+RECT
    [AkRun]::GetWindowRect($o, [ref]$q) | Out-Null
    $w = $q.R - $q.L; $hh = $q.B - $q.T
    if ($w -lt 20 -or $hh -lt 20) { continue }
    $pop = New-Object System.Drawing.Bitmap $w, $hh
    $pg = [System.Drawing.Graphics]::FromImage($pop)
    $pdc = $pg.GetHdc(); [AkRun]::PrintWindow($o, $pdc, 2) | Out-Null; $pg.ReleaseHdc($pdc); $pg.Dispose()
    $g.DrawImage($pop, $q.L - $r.L, $q.T - $r.T); $pop.Dispose()
  }
  $g.Dispose()
  $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
}

$FORM_KEYS = 'DefaultView', 'CurrentView', 'AllowEdits', 'AllowAdditions', 'AllowDeletions', 'RecordSelectors',
             'NavigationButtons', 'ScrollBars', 'DividingLines', 'PopUp', 'Modal', 'InsideHeight', 'InsideWidth',
             'RecordsetClone.RecordCount'
$CONTROL_KEYS = 'Visible', 'Enabled', 'Locked', 'BackColor', 'BackStyle', 'ForeColor', 'FontBold', 'FontSize',
                'SpecialEffect', 'BorderStyle', 'Left', 'Top', 'Width', 'Height', 'FormatConditions.Count'
$results = New-Object System.Collections.Generic.List[object]
$index = 0
foreach ($f in $forms) {
  $index++
  $name = [string]$f.name
  $entry = [ordered]@{ name = $name; file = ''; view = [int]$f.view; form = [ordered]@{}; controls = @(); error = '' }
  try {
    $app.DoCmd.OpenForm($name, [int]$f.view)
    Start-Sleep -Milliseconds 1200
    # The file name is an index: a production name can hold characters a file name cannot.
    $entry.file = 'form-{0:D3}.png' -f $index
    Save-Window (Join-Path $OutDir $entry.file)
    $p = "[Forms]![$name]"
    foreach ($k in $FORM_KEYS) { $entry.form[$k] = Ev "$p.$k" }
    $controls = New-Object System.Collections.Generic.List[object]
    foreach ($c in @($f.controls)) {
      $row = [ordered]@{ name = [string]$c }
      foreach ($k in $CONTROL_KEYS) { $row[$k] = Ev "$p![$c].$k" }
      $controls.Add($row)
    }
    $entry.controls = $controls.ToArray()
    $log.Add(("OK`tform`t{0}`t{1}" -f $name, $entry.file))
    $app.DoCmd.Close(2, $name, 2)
  } catch {
    $entry.error = $_.Exception.Message
    $log.Add(("FAIL`tform`t{0}`t{1}" -f $name, $_.Exception.Message))
    try { $app.DoCmd.Close(2, $name, 2) } catch { }
  }
  $results.Add($entry)
}
} finally {
  # Whatever failed, Access closes: a copy left open keeps its lock file, and the caller's
  # temporary folder cannot be removed.
  try { $app.CloseCurrentDatabase() } catch { }
  try { $app.Quit() } catch { }
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null
}
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllLines((Join-Path $OutDir 'capture-log.txt'), $log, $utf8)
[System.IO.File]::WriteAllText($Out, (ConvertTo-Json -InputObject @{ stripped = $strip; forms = $results.ToArray() } -Depth 8), $utf8)
