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

# Self check: the scanner must detect the standard harmless antivirus test file, otherwise "clean" means nothing.
$probe = Join-Path $env:RUNNER_TEMP "scanner_selfcheck"
if (-not $env:RUNNER_TEMP) { $probe = Join-Path $env:TEMP "scanner_selfcheck" }
New-Item -ItemType Directory -Force $probe | Out-Null
$testFile = Join-Path $probe "selfcheck.txt"
try { [IO.File]::WriteAllText($testFile, ('X5O!P%@AP[4\PZX54(P^)7CC)7}$' + 'EICAR-STANDARD-ANTIVIRUS-' + 'TEST-FILE!$H+H*')) } catch { Write-Host "selfcheck write: $($_.Exception.Message)" }
$sc = Invoke-Scan $probe
Write-Host "=== Scanner self check exit code $($sc.Code) (2 = works)"
if ($sc.Code -ne 2) { Write-Host $sc.Text; Write-Host "SELF CHECK FAILED - Defender is not really scanning on this runner"; if ($FailOnThreat) { exit 1 } }
Remove-Item -Recurse -Force $probe -ErrorAction SilentlyContinue

$found = $false
$root = (Resolve-Path $Folder).Path
foreach ($zip in Get-ChildItem $root -Filter *.zip | Sort-Object Name) {
  Write-Host ""
  Write-Host "=================== $($zip.Name)"
  # Mark of the Web, as a browser download from GitHub would have.
  Set-Content -Path $zip.FullName -Stream Zone.Identifier -Value "[ZoneTransfer]`r`nZoneId=3`r`nReferrerUrl=https://github.com/`r`nHostUrl=https://github.com/"
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
