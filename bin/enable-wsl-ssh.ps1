# Run in an elevated Windows PowerShell after configuring the WSL SSH server.
# Re-run after the WSL IP changes. This does not configure the router.
# Example: .\bin\enable-wsl-ssh.ps1 -ListenAddress <LAN-IP>
#Requires -RunAsAdministrator
param(
    [Parameter(Mandatory = $true)]
    [System.Net.IPAddress]$ListenAddress,
    [string]$Distribution = 'Ubuntu-24.04',
    [ValidateRange(1, 65535)][int]$Port = 2222
)
$ErrorActionPreference = 'Stop'
$wslExe = "$env:WINDIR\System32\wsl.exe"
$netshExe = "$env:WINDIR\System32\netsh.exe"
$route = & $wslExe -d $Distribution -- ip -4 -j address show eth0
if ($LASTEXITCODE -ne 0) { throw 'Unable to read WSL network address.' }
$wslAddress = (($route | ConvertFrom-Json).addr_info |
    Where-Object { $_.family -eq 'inet' } | Select-Object -First 1).local
if (-not $wslAddress) { throw 'No IPv4 address found on WSL eth0.' }
if (-not (Get-NetIPAddress -IPAddress $ListenAddress.IPAddressToString -ErrorAction SilentlyContinue)) {
    throw 'ListenAddress is not assigned to this Windows PC.'
}
if (-not (Test-NetConnection -ComputerName $wslAddress -Port $Port -InformationLevel Quiet)) {
    throw 'WSL SSH server is not reachable. No forwarding rule was changed.'
}
Start-Service iphlpsvc
& $netshExe interface portproxy add v4tov4 `
    "listenaddress=$ListenAddress" "listenport=$Port" `
    "connectaddress=$wslAddress" "connectport=$Port"
if ($LASTEXITCODE -ne 0) { throw 'Unable to configure Windows port forwarding.' }
$ruleName = "Dotfiles-WSL-SSH-$Port"
Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -Name $ruleName -DisplayName "WSL SSH TCP $Port" `
    -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port `
    -LocalAddress $ListenAddress.IPAddressToString -Profile Any | Out-Null
Write-Output "Windows ${ListenAddress}:$Port -> WSL ${wslAddress}:$Port"
Write-Output 'Router port forwarding is still required for internet access.'
