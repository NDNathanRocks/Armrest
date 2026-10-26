<#
.SYNOPSIS
    Upgrade test required before every release (plan.md section 12, rule 4).

.DESCRIPTION
    Installs an OLD published installer silently into a throwaway folder, starts the app, installs the NEW
    installer over it, and checks: the version changed, the same folder was reused, the running app was closed
    and started again, the user's data was kept, and the uninstaller keeps user data by default.

    Since 0.5.0 (the CouchJarvis -> Armrest rename) it also checks that Armrest.exe replaced CouchJarvis.exe,
    that the data folders moved whole to Armrest (room.json, config.env and the Edge profile unchanged, a note
    left in the old folder), that the startup entry was renamed, and that the app holds both single-instance
    names.

    The test never uses your real data: APPDATA and LOCALAPPDATA point at a sandbox under -Work, seeded with an
    old-style CouchJarvis install, for everything it starts. Your real CouchJarvis folders are also held open
    for the whole run, so nothing can move them, and checked afterwards. Run it on a PC (or Windows Sandbox /
    VM) with no Armrest installed: the installers share one registry entry, so it refuses to run when one is
    registered.

.PARAMETER OldInstaller
    The previously published CouchJarvis-Setup.exe (download it from the GitHub release).

.PARAMETER OldVersion
    The version of -OldInstaller (default 0.2.0). Run the test from 0.2.0 and from the last release.

.PARAMETER NewInstaller
    The candidate installer\dist\Armrest-Setup.exe.

.PARAMETER Work
    A SHORT scratch folder (Windows rejects very long install paths), e.g. $env:LOCALAPPDATA\cjt.

.EXAMPLE
    .\scripts\test_installer_upgrade.ps1 -OldInstaller C:\temp\Setup-0.4.0.exe -OldVersion 0.4.0 -NewInstaller .\installer\dist\Armrest-Setup.exe -Work $env:LOCALAPPDATA\cjt
#>
param(
    [Parameter(Mandatory)][string]$OldInstaller,
    [string]$OldVersion = '0.2.0',
    [Parameter(Mandatory)][string]$NewInstaller,
    [Parameter(Mandatory)][string]$Work
)
$ErrorActionPreference = 'Stop'
$key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{7B1E3C52-5A9D-4B5E-9C1A-2F4D8E6A0C31}_is1'
$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo '.venv\Scripts\python.exe'
$OldInstaller = (Resolve-Path -LiteralPath $OldInstaller).Path
$NewInstaller = (Resolve-Path -LiteralPath $NewInstaller).Path
New-Item -ItemType Directory -Force -Path $Work | Out-Null
$Work = (Resolve-Path -LiteralPath $Work).Path
$app = Join-Path $Work 'app'
$results = [ordered]@{}
function Check($name, $ok, $detail = '') { $results[$name] = if ($ok) { "PASS $detail" } else { "FAIL $detail" } }
function Hash($p) { if (Test-Path -LiteralPath $p) { (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash } else { 'absent' } }
# Run a program and wait for that process only (not for anything it starts), with a time limit.
function Run($file, $arguments, $limitSeconds = 180) {
    $p = Start-Process -FilePath $file -ArgumentList $arguments -PassThru
    if (-not $p.WaitForExit($limitSeconds * 1000)) { $p.Kill(); return -999 }
    return $p.ExitCode
}
function Stop-App { Get-Process -Name Armrest, CouchJarvis -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue }

if (Test-Path -LiteralPath $key) { throw 'An install is already registered on this PC: refusing to touch it.' }
if (Get-Process -Name _unins, unins000 -ErrorAction SilentlyContinue) {
    throw 'An uninstaller is still running (maybe waiting on a dialog). Answer No / close it first: a Yes deletes your settings.'
}
if (Get-Process -Name Armrest, CouchJarvis -ErrorAction SilentlyContinue) { throw 'Quit Armrest / CouchJarvis first.' }
if (Test-Path -LiteralPath $app) { throw "$app exists: use a fresh -Work folder." }

# Your real folders (from Windows, not from the environment), and handles that keep them from being renamed.
$realRoaming = [Environment]::GetFolderPath('ApplicationData')
$realLocal = [Environment]::GetFolderPath('LocalApplicationData')
$realRoom = Join-Path $realRoaming 'CouchJarvis\room.json'
$realRoomBefore = Hash $realRoom
$realNew = @((Join-Path $realRoaming 'Armrest'), (Join-Path $realLocal 'Armrest')) | Where-Object { -not (Test-Path -LiteralPath $_) }
$holds = @()
foreach ($dir in (Join-Path $realRoaming 'CouchJarvis'), (Join-Path $realLocal 'CouchJarvis')) {
    # any one open file blocks the rename (files Edge has locked cannot be opened: try the next)
    foreach ($file in @(Get-ChildItem -LiteralPath $dir -Recurse -File -ErrorAction SilentlyContinue)) {
        try { $holds += [IO.File]::Open($file.FullName, 'Open', 'Read', 'ReadWrite'); break } catch { continue }
    }
}

# The sandbox: an old-style install's data, with settings that keep the app off the relay and off your TV browser.
$sandRoaming = Join-Path $Work 'Roaming'
$sandLocal = Join-Path $Work 'Local'
$oldData = Join-Path $sandRoaming 'CouchJarvis'
$oldLocal = Join-Path $sandLocal 'CouchJarvis'
$newData = Join-Path $sandRoaming 'Armrest'
$newLocal = Join-Path $sandLocal 'Armrest'
New-Item -ItemType Directory -Force -Path $oldData, (Join-Path $oldLocal 'edge-profile\Default\Network') | Out-Null
& $python -c "import sys; sys.path.insert(0, r'$repo\pc-daemon'); from pathlib import Path; from room import RoomStore; s = RoomStore(Path(r'$oldData\room.json')); s.load_or_create(); s.set_room_key('k' * 64)"
if ($LASTEXITCODE -ne 0) { throw 'could not create the sandbox room.json' }
@(
    '# an old (CouchJarvis) settings file'
    'CJ_RELAY_WS_URL=ws://127.0.0.1:9/never'
    'CJ_EDGE_PATH=C:\no-such-folder\msedge.exe'
    'CJ_CDP_PORT=9339'
    'CJ_LAN_PORT=8799'
) | Set-Content -LiteralPath (Join-Path $oldData 'config.env') -Encoding ascii
Set-Content -LiteralPath (Join-Path $oldLocal 'edge-profile\Default\Network\Cookies') -Value 'signed in to the streaming sites'
$room = Join-Path $oldData 'room.json'
$roomBefore = Hash $room
$configBefore = Hash (Join-Path $oldData 'config.env')
$cookiesBefore = Hash (Join-Path $oldLocal 'edge-profile\Default\Network\Cookies')
$savedEnv = @{ APPDATA = $env:APPDATA; LOCALAPPDATA = $env:LOCALAPPDATA }
$env:APPDATA = $sandRoaming
$env:LOCALAPPDATA = $sandLocal

try {
    # 1. install the published old version into a throwaway folder
    $code = Run $OldInstaller "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /DIR=`"$app`" /LOG=`"$Work\old.log`""
    Check 'old installer exit code 0' ($code -eq 0) "($code)"
    $old = (Get-ItemProperty -LiteralPath $key).DisplayVersion
    Check 'old version registered' ($old -eq $OldVersion) $old
    $oldExe = Join-Path $app 'CouchJarvis.exe'
    Check 'old build is CouchJarvis.exe' (Test-Path -LiteralPath $oldExe)
    $oldDefaults = Get-Content -LiteralPath (Join-Path $app '_internal\installer\defaults.env') -Raw
    Check 'old build has the old defaults' ($oldDefaults -match 'CJ_STT_DEVICE=')
    $oldRun = (Get-ItemProperty -LiteralPath $runKey -ErrorAction SilentlyContinue).CouchJarvis
    Check 'old startup entry exists' ($oldRun -like "*$app*") $oldRun

    # a running copy (a windowless background process, like the real app) must be stopped by the update
    $running = Start-Process -FilePath $oldExe -ArgumentList '--dry-run' -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 5
    Check 'the old app is running before the update' (-not $running.HasExited)

    # 2. install the new build over it, without naming a folder (it must reuse the old one)
    $code = Run $NewInstaller "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /LOG=`"$Work\new.log`""
    Check 'new installer exit code 0' ($code -eq 0) "($code)"
    $new = (Get-ItemProperty -LiteralPath $key).DisplayVersion
    Check 'new version registered' ($new -match '^\d+\.\d+\.\d+$' -and $new -ne $OldVersion) $new
    $loc = (Get-ItemProperty -LiteralPath $key).InstallLocation.TrimEnd('\')
    Check 'updated in place (same folder)' ($loc -eq $app) $loc
    Check 'Armrest.exe installed' (Test-Path -LiteralPath (Join-Path $app 'Armrest.exe'))
    Check 'CouchJarvis.exe removed' (-not (Test-Path -LiteralPath $oldExe))
    $newDefaults = Get-Content -LiteralPath (Join-Path $app '_internal\installer\defaults.env') -Raw
    Check 'new defaults are in place' ($newDefaults -match 'ARMREST_STT_DEVICE=auto')
    Check 'the old running copy was closed' ($running.HasExited)
    $runs = Get-ItemProperty -LiteralPath $runKey -ErrorAction SilentlyContinue
    Check 'startup entry renamed' (($runs.Armrest -like "*$app\Armrest.exe*") -and -not $runs.CouchJarvis) $runs.Armrest
    Start-Sleep -Seconds 10
    $relaunched = @(Get-Process -Name Armrest -ErrorAction SilentlyContinue)
    Check 'a silent update starts the app again' ($relaunched.Count -ge 1) "($($relaunched.Count) process)"
    Check 'no CouchJarvis process left' (@(Get-Process -Name CouchJarvis -ErrorAction SilentlyContinue).Count -eq 0)
    & $python -c "import ctypes, sys; k = ctypes.windll.kernel32; sys.exit(0 if all(k.OpenMutexW(0x100000, False, n) for n in ('Local\\ArmrestDaemon', 'Local\\CouchJarvisDaemon')) else 1)"
    Check 'the app holds both single-instance names' ($LASTEXITCODE -eq 0)
    $second = Start-Process -FilePath (Join-Path $app 'Armrest.exe') -PassThru -WindowStyle Hidden
    Check 'a second launch exits (single instance)' ($second.WaitForExit(20000)) "(exit $($second.ExitCode))"
    Stop-App
    Start-Sleep -Seconds 3

    # 3. the data moved whole, unchanged
    Check 'room.json moved unchanged' ((Hash (Join-Path $newData 'room.json')) -eq $roomBefore)
    Check 'config.env moved unchanged' ((Hash (Join-Path $newData 'config.env')) -eq $configBefore)
    Check 'Edge profile moved (sign-ins kept)' ((Hash (Join-Path $newLocal 'edge-profile\Default\Network\Cookies')) -eq $cookiesBefore)
    foreach ($dir in $oldData, $oldLocal) {
        $left = @(Get-ChildItem -LiteralPath $dir -Force -ErrorAction SilentlyContinue | ForEach-Object Name)
        Check "only the note left in $(Split-Path -Leaf (Split-Path -Parent $dir))\CouchJarvis" (($left -join ',') -eq 'MOVED_TO_ARMREST.txt') ($left -join ',')
    }
    $programs = Join-Path $realRoaming 'Microsoft\Windows\Start Menu\Programs'
    $links = @(Get-ChildItem -Recurse -Path $programs -Filter 'Armrest.lnk' -ErrorAction SilentlyContinue)
    Check 'one Start-menu shortcut' ($links.Count -eq 1) "($($links.Count))"
    $shell = New-Object -ComObject WScript.Shell
    Check 'the shortcut opens Armrest.exe' (($links.Count -ge 1) -and ($shell.CreateShortcut($links[0].FullName).TargetPath -like '*\Armrest.exe'))
    $oldLinks = @(Get-ChildItem -Recurse -Path $programs -Filter 'Couch Jarvis*.lnk' -ErrorAction SilentlyContinue)
    Check 'the 0.x shortcuts (old name) are gone' ($oldLinks.Count -eq 0) "($($oldLinks.Count))"

    # 4. uninstall (the prompt to delete settings defaults to No) and confirm the data is still there
    $unins = Get-ChildItem -LiteralPath $app -Filter 'unins*.exe' | Select-Object -First 1
    $code = Run $unins.FullName "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /LOG=`"$Work\unins.log`"" 120
    Start-Sleep -Seconds 3
    if ($code -ne 0 -and (Test-Path -LiteralPath "$Work\unins.log")) {
        Write-Host '--- last lines of the uninstall log ---'
        Get-Content -LiteralPath "$Work\unins.log" -Tail 12 | ForEach-Object { Write-Host $_ }
    }
    Check 'uninstall exit code 0' ($code -eq 0) "($code)"
    Check 'uninstall removed the registration' (-not (Test-Path -LiteralPath $key))
    Check 'uninstall removed the startup entry' (-not (Get-ItemProperty -LiteralPath $runKey -ErrorAction SilentlyContinue).Armrest)
    Check 'uninstall kept room.json' ((Hash (Join-Path $newData 'room.json')) -eq $roomBefore)
    Check 'uninstall kept config.env' ((Hash (Join-Path $newData 'config.env')) -eq $configBefore)
}
catch { $results['SCRIPT ERROR'] = "FAIL $($_.Exception.Message)" }
finally {
    Stop-App
    Get-Process -Name _unins -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    $env:APPDATA = $savedEnv.APPDATA
    $env:LOCALAPPDATA = $savedEnv.LOCALAPPDATA
    foreach ($h in $holds) { $h.Dispose() }
    foreach ($name in 'Armrest', 'CouchJarvis') {  # a startup entry left by a failed run would point into the sandbox
        $value = (Get-ItemProperty -LiteralPath $runKey -ErrorAction SilentlyContinue).$name
        if ($value -like "*$Work*") { Remove-ItemProperty -LiteralPath $runKey -Name $name -ErrorAction SilentlyContinue }
    }
}
Check 'your real room.json untouched' ((Hash $realRoom) -eq $realRoomBefore)
Check 'no real Armrest folder created' (@($realNew | Where-Object { Test-Path -LiteralPath $_ }).Count -eq 0)
$results.GetEnumerator() | ForEach-Object { '{0,-46} {1}' -f $_.Key, $_.Value }
"FAILED CHECKS: $(@($results.Values | Where-Object { $_ -like 'FAIL*' }).Count)"
