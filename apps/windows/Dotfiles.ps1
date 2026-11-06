param(
    [string]$Distro = '',
    [string]$Repository = '',
    [switch]$Install,
    [switch]$NoOpen,
    [switch]$Stop
)
$ErrorActionPreference = 'Stop'
function Invoke-DotfilesWsl([string[]]$Arguments) {
    $quoted = foreach ($value in $Arguments) {
        if ($value -and $value -notmatch '[\s"]') { $value; continue }
        '"' + [regex]::Replace([regex]::Replace($value, '(\\*)"', '$1$1\"'), '(\\+)$', '$1$1') + '"'
    }
    $start = New-Object System.Diagnostics.ProcessStartInfo
    $start.FileName = (Get-Command wsl.exe).Source
    $start.Arguments = $quoted -join ' '
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $start.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    $start.EnvironmentVariables['WSL_UTF8'] = '1'
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $start
    $null = $process.Start()
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    if (-not $process.WaitForExit(60000)) { $process.Kill(); throw 'WSL did not respond within 60 seconds.' }
    $result = $stdout.Result
    $errorText = $stderr.Result
    $exitCode = $process.ExitCode
    $process.Dispose()
    if ($exitCode -ne 0) { throw ('WSL command failed: ' + $errorText + $result) }
    return $result.Trim()
}

try {
    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { throw 'WSL is required. Install WSL with Ubuntu first.' }
    $wslArgs = @()
    if ($Distro) { $wslArgs += @('--distribution', $Distro) }
    if (-not $Repository) {
        $windowsRepo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
        if ($windowsRepo -match '^\\\\(?:wsl\.localhost|wsl\$)\\([^\\]+)\\(.*)$') {
            if ($Distro -and $Distro -ne $Matches[1]) { throw 'The chosen distribution differs from the repository distribution.' }
            $Distro = $Matches[1]
            $Repository = '/' + $Matches[2].Replace('\','/')
            $wslArgs = @('--distribution',$Distro)
        } else {
            $converted = Invoke-DotfilesWsl ($wslArgs + @('--exec','wslpath','-a','-u',$windowsRepo))
            $Repository = ($converted | Out-String).Trim()
        }
    }
    if (-not $Repository.StartsWith('/')) { throw 'Repository must be an absolute Linux path.' }
    if ($Install) {
        $shell = New-Object -ComObject WScript.Shell
        $folder = Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs'
        New-Item -ItemType Directory -Force -Path $folder | Out-Null
        # A process launch passes separate quoted arguments; never interpolate Linux paths into shell code.
        $escapedScript = $PSCommandPath.Replace('"','')
        $arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $escapedScript + '" -Repository "' + $Repository.Replace('"','') + '"'
        if ($Distro) { $arguments += ' -Distro "' + $Distro.Replace('"','') + '"' }
        foreach ($location in @((Join-Path $folder 'Dotfiles.lnk'), (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Dotfiles.lnk'))) {
            $shortcut = $shell.CreateShortcut($location)
            $shortcut.TargetPath = Join-Path $PSHOME 'powershell.exe'
            $shortcut.Arguments = $arguments
            $shortcut.WorkingDirectory = $PSScriptRoot
            $shortcut.Description = 'Dotfiles settings for WSL'
            $shortcut.IconLocation = (Join-Path $PSScriptRoot 'AppIcon.ico')
            $shortcut.WindowStyle = 7
            $shortcut.Save()
        }
        Write-Output 'Dotfiles shortcuts installed in Start menu and Desktop.'
        return
    }
    $action = 'launch'
    if ($Stop) { $action = 'stop' }
    $output = Invoke-DotfilesWsl ($wslArgs + @('--exec','python3',"$Repository/bin/desktop.py",$action,'--no-open'))
    if ($Stop) { Write-Output $output; return }
    $url = (($output -split "`n") | Where-Object { $_ -match '^http://127\.0\.0\.1:\d+/$' } | Select-Object -Last 1)
    if (-not $url) { throw 'The dashboard did not return a local URL.' }
    # Confirm Windows can reach WSL before opening a window.
    $reachable = $false
    for ($attempt=0; $attempt -lt 20; $attempt++) {
        try { $null = Invoke-WebRequest -UseBasicParsing -Uri ($url + 'api/desktop') -TimeoutSec 2; $reachable=$true;break } catch { Start-Sleep -Milliseconds 250 }
    }
    if (-not $reachable) { throw 'Windows cannot reach the WSL dashboard. Check WSL localhost forwarding, then reopen Dotfiles.' }
    if ($NoOpen) { Write-Output $url;return }
    $browsers = @(
        (Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'),
        (Join-Path $env:ProgramFiles 'Microsoft\Edge\Application\msedge.exe'),
        (Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'),
        (Join-Path $env:LOCALAPPDATA 'Google\Chrome\Application\chrome.exe')
    )
    $browser = $browsers | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($browser) { Start-Process -FilePath $browser -ArgumentList @("--app=$url", '--window-size=1440,960') }
    else { Start-Process $url }
} catch {
    if ($NoOpen) { Write-Error $_;exit 1 }
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show($_.Exception.Message, 'Dotfiles') | Out-Null
    exit 1
}
