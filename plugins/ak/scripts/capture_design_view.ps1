param(
  [Parameter(Mandatory = $true)][string]$Database,
  [Parameter(Mandatory = $true)][string]$OutDir
)
# Captures every form and report of a DISPOSABLE copy in design view. Design view runs
# no event code, and the copy's startup form is removed first, so nothing the
# application does on open runs either. Called by capture_design_view.py, which makes
# the copy; never point this at an original.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class AkWin {
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
}
"@
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$log = New-Object System.Collections.Generic.List[string]

$dao = New-Object -ComObject DAO.DBEngine.36
$db = $dao.OpenDatabase($Database)
try { $db.Properties.Delete('StartupForm'); $log.Add('STARTUP removed') } catch { $log.Add('STARTUP none') }
$forms = @(); $reports = @()
foreach ($d in $db.Containers.Item('Forms').Documents) { $forms += $d.Name }
foreach ($d in $db.Containers.Item('Reports').Documents) { $reports += $d.Name }
$db.Close()

$app = New-Object -ComObject Access.Application
try { $app.AutomationSecurity = 3 } catch { }
$app.Visible = $true
$app.OpenCurrentDatabase($Database, $false)
$h = [IntPtr]$app.hWndAccessApp()
[AkWin]::ShowWindow($h, 3) | Out-Null

function Save-Window([string]$path) {
  $r = New-Object AkWin+RECT
  [AkWin]::GetWindowRect($h, [ref]$r) | Out-Null
  $bmp = New-Object System.Drawing.Bitmap ($r.R - $r.L), ($r.B - $r.T)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $dc = $g.GetHdc()
  [AkWin]::PrintWindow($h, $dc, 2) | Out-Null
  $g.ReleaseHdc($dc); $g.Dispose()
  $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
}

$index = 0
foreach ($kind in @('form', 'report')) {
  $names = if ($kind -eq 'form') { $forms } else { $reports }
  foreach ($n in $names) {
    $index++
    try {
      if ($kind -eq 'form') { $app.DoCmd.OpenForm($n, 1) } else { $app.DoCmd.OpenReport($n, 1) }
      $app.DoCmd.Maximize()
      Start-Sleep -Milliseconds 1200
      # The file name is an index: a production name can hold characters a file name
      # cannot. capture-log.txt maps each index to the object it shows.
      $file = '{0}-{1:D3}.png' -f $kind, $index
      Save-Window (Join-Path $OutDir $file)
      $log.Add(("OK`t{0}`t{1}`t{2}" -f $kind, $n, $file))
      if ($kind -eq 'form') { $app.DoCmd.Close(2, $n, 2) } else { $app.DoCmd.Close(3, $n, 2) }
    } catch {
      $log.Add(("FAIL`t{0}`t{1}`t{2}" -f $kind, $n, $_.Exception.Message))
    }
  }
}
$app.CloseCurrentDatabase()
$app.Quit()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null
[System.IO.File]::WriteAllLines((Join-Path $OutDir 'capture-log.txt'), $log, (New-Object System.Text.UTF8Encoding $false))
