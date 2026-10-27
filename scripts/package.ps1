$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$dist = Join-Path $root 'dist'
New-Item -ItemType Directory -Path $dist -Force | Out-Null
$stage = Join-Path $dist ('stage-' + [Guid]::NewGuid().ToString('N'))
$package = Join-Path $stage 'CleanupTV'
New-Item -ItemType Directory -Path $package -Force | Out-Null
# Explicit allowlist: never package backups, runtime, research or ADB keys.
$files = @('START.bat','app.py','personalize.py','rescue.py','catalog.json','profiles.json','downloads.json','README.md','LICENSE','THIRD_PARTY_NOTICES.md')
foreach ($file in $files) { Copy-Item -LiteralPath (Join-Path $root $file) -Destination $package }
New-Item -ItemType Directory -Path (Join-Path $package 'web') -Force | Out-Null
foreach ($file in @('index.html','app.js','personalize.js','rescue.js','style.css')) {
    Copy-Item -LiteralPath (Join-Path $root "web\$file") -Destination (Join-Path $package 'web')
}
New-Item -ItemType Directory -Path (Join-Path $package 'scripts') -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $root 'scripts\bootstrap.ps1') -Destination (Join-Path $package 'scripts')
New-Item -ItemType Directory -Path (Join-Path $package 'docs') -Force | Out-Null
foreach ($file in @('preview.png','VALIDATION.md','CHANGELOG-0.4.md','CHANGELOG-0.5.md','CHANGELOG-0.6.md')) {
    Copy-Item -LiteralPath (Join-Path $root ('docs\' + $file)) -Destination (Join-Path $package 'docs')
}
New-Item -ItemType Directory -Path (Join-Path $package 'launcher-overlay') -Force | Out-Null
foreach ($file in @('CleanupPreferences.java','CleanupProvider.java','CleanupSettingsActivity.java','CleanupWeatherProvider.java','weather-vi.xml','CleanupMarket.java','CleanupMarketData.java','CleanupMarketDataTest.java')) {
    Copy-Item -LiteralPath (Join-Path $root ('launcher-overlay\' + $file)) -Destination (Join-Path $package 'launcher-overlay')
}
$archive = Join-Path $dist 'CleanupTV-Windows-0.6.0.zip'
Compress-Archive -LiteralPath $package -DestinationPath $archive -Force
Get-FileHash -LiteralPath $archive -Algorithm SHA256
Write-Host "Package: $archive"
