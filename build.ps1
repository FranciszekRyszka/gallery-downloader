# Build Gallery Downloader into a single-file Windows .exe.
#
# Usage:  right-click > Run with PowerShell, or:  ./build.ps1
# Output: dist/GalleryDownloader.exe  (double-click to run; no Python needed)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "Installing build dependencies..." -ForegroundColor Cyan
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

Write-Host "Building GalleryDownloader.exe..." -ForegroundColor Cyan
python -m PyInstaller --noconfirm --clean GalleryDownloader.spec

$exe = Join-Path $PSScriptRoot "dist\GalleryDownloader.exe"
if (Test-Path $exe) {
    Write-Host "`nDone. Executable: $exe" -ForegroundColor Green
} else {
    Write-Error "Build finished but $exe was not found."
}
