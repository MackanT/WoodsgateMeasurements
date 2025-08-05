param(
    [string]$db_name,
    [string]$local_ip,
    [string]$external_ip,
    [int]$local_port,
    [string]$rpi_user,
    [string]$config = "config.yml"
)

# Helper: YAML parsing (requires PowerShell 7+ and PowerShell-Yaml module)
function Import-Yaml {
    param([string]$Path)
    if (!(Get-Command ConvertFrom-Yaml -ErrorAction SilentlyContinue)) {
        Write-Host "ConvertFrom-Yaml not found. Attempting to install PowerShell-Yaml module..."
        try {
            Install-Module -Name powershell-yaml -Force -Scope CurrentUser -AllowClobber -ErrorAction Stop
            Import-Module powershell-yaml -Force
        } catch {
            Write-Error "Failed to install PowerShell-Yaml. Please install manually: Install-Module -Name powershell-yaml"
            exit 1
        }
    }
    Get-Content $Path -Raw | ConvertFrom-Yaml
}

# Default config
$default_config = @{
    rpi_user = "your_rpi_username_here"
    local_ip = "192.168.x.x"
    external_ip = "xxx.xxx.xxx.xxx"
    local_port = 22
    db_name = "data.db"
}

# Load config if needed
$use_config = $false
foreach ($key in 'db_name','local_ip','external_ip','local_port','rpi_user') {
    if (-not (Get-Variable $key -ValueOnly)) {
        $use_config = $true
        Write-Host "[!] Argument '$key' is missing"
    }
}

if ($use_config) {
    if (-not (Test-Path $config)) {
        $default_config | ConvertTo-Yaml | Set-Content $config
        Write-Host "Template config created at '$config'. Please fill it out!"
        exit 1
    }
    $cfg = Import-Yaml $config
    foreach ($key in $default_config.Keys) {
        if (-not (Get-Variable $key -ValueOnly)) {
            Set-Variable -Name $key -Value $cfg.$key
        }
    }
}

# Print config
foreach ($key in 'db_name','local_ip','external_ip','local_port','rpi_user') {
    Write-Host ("-${key}: " + (Get-Variable $key -ValueOnly))
}

# Get local IP
function Get-LocalIP {
    $s = New-Object Net.Sockets.Socket ([Net.Sockets.AddressFamily]::InterNetwork, [Net.Sockets.SocketType]::Dgram, [Net.Sockets.ProtocolType]::Udp)
    $s.Connect('8.8.8.8', 80)
    $ip = $s.LocalEndPoint.Address.ToString()
    $s.Close()
    return $ip
}

function Is-SameNetwork($my_ip, $rpi_local_ip) {
    $my_net = ($my_ip -replace '\.\d+$','.0')
    $rpi_net = ($rpi_local_ip -replace '\.\d+$','.0')
    return $my_net -eq $rpi_net
}

$my_ip = Get-LocalIP
if (Is-SameNetwork $my_ip $local_ip) {
    Write-Host "User is on same network as RPI, using Local IP."
    $ip = $local_ip
} else {
    Write-Host "User is not on same network as RPI, using Tailscale IP."
    $ip = $external_ip
}

# Check SSH key
$ssh_key = Join-Path $HOME ".ssh/id_ed25519"
if (-not (Test-Path $ssh_key)) {
    Write-Host "SSH key not found. Please generate one with `ssh-keygen` and add it to your RPi, see readme for more info"
    exit 1
}

# Run SCP
$scpArgs = @(
    "-P", $local_port,
    "-o", "StrictHostKeyChecking=no",
    "$($rpi_user)@$($ip):/home/admin/Documents/5400_data.db",
    $db_name
)
Write-Host "Starting download.... This may take a few minutes depending on connection!"

$output = & scp @scpArgs 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Command failed!"
    Write-Host $output
    exit $LASTEXITCODE
} else {
    Write-Host "Success!"
}