param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $root
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
if (-not [Environment]::Is64BitOperatingSystem) { throw 'Can Windows 10/11 64-bit.' }
$runtime = Join-Path $root '.runtime'
New-Item -ItemType Directory -Path $runtime -Force | Out-Null
$manifest = Get-Content -LiteralPath (Join-Path $root 'downloads.json') -Raw | ConvertFrom-Json
function Install-Portable($spec, [string]$folder, [string]$check) {
    $dest = Join-Path $runtime $folder
    if (Test-Path -LiteralPath (Join-Path $dest $check)) { return }
    $zip = Join-Path $runtime "$folder.zip"
    Write-Host "Dang tai $($spec.name)..."
    if (-not (Test-Path -LiteralPath $zip) -or (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ne $spec.sha256) {
        Invoke-WebRequest -UseBasicParsing -Uri $spec.url -OutFile $zip
    }
    if ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ne $spec.sha256) { throw "SHA256 khong khop: $folder. Hay tai lai." }
    Expand-Archive -LiteralPath $zip -DestinationPath $dest -Force
    if (-not (Test-Path -LiteralPath (Join-Path $dest $check))) { throw "Giai nen that bai: $folder" }
}
Install-Portable $manifest.python 'python' 'python.exe'
Install-Portable $manifest.adb 'adb' 'platform-tools\adb.exe'
Write-Host 'Dang mo CleanupTV. Giu cua so nay; Ctrl+C de dung.'
$appArgs = @('-I', (Join-Path $root 'app.py'))
if (-not $NoBrowser) { $appArgs += '--open' }
& (Join-Path $runtime 'python\python.exe') @appArgs
exit $LASTEXITCODE
