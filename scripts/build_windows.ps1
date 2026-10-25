$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
if ($env:OS -ne "Windows_NT") { throw "Build Windows binaries on Windows." }
python -m pip install ".[dev]"
if ($LASTEXITCODE) { throw "Dependency installation failed" }
python -m pytest
if ($LASTEXITCODE) { throw "Tests failed" }
python -m PyInstaller --noconfirm --clean --onedir --windowed --name AssetFlow --collect-all assetflow launch.py
if ($LASTEXITCODE) { throw "Build failed" }
Copy-Item LICENSE,README.md -Destination dist/AssetFlow
Write-Host "Build ready in dist/AssetFlow. Review docs/WINDOWS.md before distribution."
