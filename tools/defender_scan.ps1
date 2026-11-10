# Scans every zip in -Folder with Windows Defender and prints which file is detected.
# Used by .github/workflows/defender-scan.yml and build-desktop.yml (release gate).
# Nothing is removed (-DisableRemediation). Exit code 1 when -FailOnThreat and a threat was found.
param(
  [Parameter(Mandatory = $true)][string]$Folder,
  [switch]$FailOnThreat,
  [switch]$Deep,         # also scan every extracted file one by one when a zip is detected
  [string]$CloudBlockLevel = ""   # e.g. High - diagnosis only (stricter than an ordinary PC)
)
$ErrorActionPreference = "Continue"
$mp = Join-Path $env:ProgramFiles "Windows Defender\MpCmdRun.exe"
if (-not (Test-Path $mp)) { Write-Host "MpCmdRun.exe not found - Defender is not installed on this runner"; if ($FailOnThreat) { exit 1 } else { exit 0 } }

Write-Host "=== Defender state (before)"
try { Start-Service WinDefend -ErrorAction SilentlyContinue } catch {}
Get-Service WinDefend -ErrorAction SilentlyContinue | Format-List Name, Status, StartType
# Same conditions as an ordinary PC: real-time + cloud protection on (cloud block level left at default).
try { Set-MpPreference -DisableRealtimeMonitoring $false -ErrorAction Stop } catch { Write-Host "realtime: $($_.Exception.Message)" }
try { Set-MpPreference -MAPSReporting Advanced -SubmitSamplesConsent NeverSend -ErrorAction Stop } catch { Write-Host "cloud: $($_.Exception.Message)" }
try { Set-MpPreference -DisableArchiveScanning $false -DisableScriptScanning $false -DisableIOAVProtection $false -ErrorAction Stop } catch { Write-Host "prefs: $($_.Exception.Message)" }
# GitHub runners exclude whole drives (C:\, D:\) from Defender - a scan there finds nothing at all.
try { (Get-MpPreference).ExclusionPath | Where-Object { $_ } | ForEach-Object { Remove-MpPreference -ExclusionPath $_ -ErrorAction Stop } } catch { Write-Host "exclusions: $($_.Exception.Message)" }
try { (Get-MpPreference).ExclusionProcess | Where-Object { $_ } | ForEach-Object { Remove-MpPreference -ExclusionProcess $_ -ErrorAction Stop } } catch {}
try { (Get-MpPreference).ExclusionExtension | Where-Object { $_ } | ForEach-Object { Remove-MpPreference -ExclusionExtension $_ -ErrorAction Stop } } catch {}
if ($CloudBlockLevel) { try { Set-MpPreference -CloudBlockLevel $CloudBlockLevel -CloudExtendedTimeout 50 -ErrorAction Stop } catch { Write-Host "cloud level: $($_.Exception.Message)" } }
& $mp -SignatureUpdate | Out-Host
try {
  Get-MpComputerStatus | Format-List AMServiceEnabled, AntivirusEnabled, RealTimeProtectionEnabled, IoavProtectionEnabled, AMProductVersion, AMEngineVersion, AntivirusSignatureVersion, AntivirusSignatureLastUpdated
  Get-MpPreference | Format-List MAPSReporting, CloudBlockLevel, SubmitSamplesConsent, DisableArchiveScanning, ExclusionPath
} catch { Write-Host "status: $($_.Exception.Message)" }

function Invoke-Scan([string]$path) {
  $out = & $mp -Scan -ScanType 3 -File $path -DisableRemediation 2>&1
  $code = $LASTEXITCODE
  return [pscustomobject]@{ Code = $code; Text = ($out | Out-String) }
}

# The path a browser uses for a finished download (IAttachmentExecute::Save -> antivirus "downloaded file" scan).
# Works on a copy, because a blocked file is deleted by this call.
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
[ComImport, Guid("73db1241-1e85-4581-8e4f-a81e1d0f8c57"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IAttachmentExecute {
  [PreserveSig] int SetClientTitle([MarshalAs(UnmanagedType.LPWStr)] string t);
  [PreserveSig] int SetClientGuid(ref Guid g);
  [PreserveSig] int SetLocalPath([MarshalAs(UnmanagedType.LPWStr)] string p);
  [PreserveSig] int SetFileName([MarshalAs(UnmanagedType.LPWStr)] string n);
  [PreserveSig] int SetSource([MarshalAs(UnmanagedType.LPWStr)] string s);
  [PreserveSig] int SetReferrer([MarshalAs(UnmanagedType.LPWStr)] string r);
  [PreserveSig] int CheckPolicy();
  [PreserveSig] int Prompt(IntPtr hwnd, int prompt, out int action);
  [PreserveSig] int Save();
}
public static class DownloadScan {
  public static string Run(string path, string url) {
    var t = Type.GetTypeFromCLSID(new Guid("4125dd96-e03a-4103-8f70-e0597d803b9c"));
    var a = (IAttachmentExecute)Activator.CreateInstance(t);
    var g = new Guid("2676A9A2-D919-4FEE-9187-152100393AB2");
    a.SetClientGuid(ref g);
    a.SetLocalPath(path);
    a.SetSource(url);
    a.SetReferrer("https://github.com/");
    int hr = a.Save();
    Marshal.ReleaseComObject(a);
    return "0x" + hr.ToString("X8");
  }
}
"@
function Invoke-DownloadScan([string]$path, [string]$url) {
  $copy = Join-Path (Split-Path $path) ("dl_" + (Split-Path $path -Leaf))
  Copy-Item $path $copy -Force
  try { $hr = [DownloadScan]::Run($copy, $url) } catch { $hr = "error: $($_.Exception.Message)" }
  Start-Sleep -Seconds 2
  $left = Test-Path $copy
  if ($left) { Remove-Item $copy -Force -ErrorAction SilentlyContinue }
  return [pscustomobject]@{ Result = $hr; Kept = $left }
}

# Self check: the scanner must detect the standard harmless antivirus test file, otherwise "clean" means nothing.
$probe = Join-Path $env:RUNNER_TEMP "scanner_selfcheck"
if (-not $env:RUNNER_TEMP) { $probe = Join-Path $env:TEMP "scanner_selfcheck" }
New-Item -ItemType Directory -Force $probe | Out-Null
$testFile = Join-Path $probe "selfcheck.txt"
try { [IO.File]::WriteAllText($testFile, ('X5O!P%@AP[4\PZX54(P^)7CC)7}$' + 'EICAR-STANDARD-ANTIVIRUS-' + 'TEST-FILE!$H+H*')) } catch { Write-Host "selfcheck write: $($_.Exception.Message)" }
$sc = Invoke-Scan $probe
Write-Host "=== Scanner self check exit code $($sc.Code) (2 = works)"
if ($sc.Code -ne 2) { Write-Host $sc.Text; Write-Host "::warning::Defender self check failed - the scan below proves nothing on this runner" }
Remove-Item -Recurse -Force $probe -ErrorAction SilentlyContinue

$found = $false
$root = (Resolve-Path $Folder).Path
foreach ($zip in Get-ChildItem $root -Filter *.zip | Sort-Object Name) {
  Write-Host ""
  Write-Host "=================== $($zip.Name)"
  # Mark of the Web, as a browser download from GitHub would have.
  Set-Content -Path $zip.FullName -Stream Zone.Identifier -Value "[ZoneTransfer]`r`nZoneId=3`r`nReferrerUrl=https://github.com/`r`nHostUrl=https://github.com/"
  $d = Invoke-DownloadScan $zip.FullName ("https://github.com/kimminkuy70-coder/Para/releases/download/" + $zip.Name)
  Write-Host "download-path scan: result $($d.Result), file kept = $($d.Kept)"
  if ($d.Result -ne "0x00000000" -or -not $d.Kept) { $found = $true }
  $r = Invoke-Scan $zip.FullName
  Write-Host "zip scan exit code $($r.Code) (0 = clean, 2 = threat)"
  Write-Host $r.Text
  $dir = Join-Path $root ($zip.BaseName + "_x")
  Expand-Archive -Path $zip.FullName -DestinationPath $dir -Force
  $r2 = Invoke-Scan $dir
  Write-Host "extracted folder scan exit code $($r2.Code)"
  Write-Host $r2.Text
  if ($r.Code -eq 2 -or $r2.Code -eq 2) {
    $found = $true
    if ($Deep) {
      Write-Host "--- file by file"
      foreach ($f in Get-ChildItem $dir -Recurse -File) {
        $rf = Invoke-Scan $f.FullName
        if ($rf.Code -ne 0) { Write-Host "DETECTED($($rf.Code)) $($f.FullName.Substring($dir.Length))"; Write-Host $rf.Text }
      }
    }
  }
}

Write-Host ""
Write-Host "=== Detections recorded by Defender"
try {
  Get-MpThreatDetection | Sort-Object InitialDetectionTime | ForEach-Object {
    $t = Get-MpThreat -ThreatID $_.ThreatID -ErrorAction SilentlyContinue
    Write-Host ("{0}  {1}  source={2}" -f $_.InitialDetectionTime, $t.ThreatName, $_.DetectionSourceTypeID)
    $_.Resources | ForEach-Object { Write-Host "    $_" }
  }
} catch { Write-Host "detections: $($_.Exception.Message)" }

if ($found) { Write-Host "RESULT: THREAT FOUND"; if ($FailOnThreat) { exit 1 } } else { Write-Host "RESULT: clean" }
exit 0
