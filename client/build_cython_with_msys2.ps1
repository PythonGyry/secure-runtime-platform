# Build Cython extensions using MSYS2 MinGW (alternative to MSVC)
# Run from project root: .\client\build_cython_with_msys2.ps1

$msys2Paths = @(
    "C:\msys64\mingw64\bin",
    "C:\msys32\mingw64\bin",
    "$env:USERPROFILE\msys64\mingw64\bin",
    "$env:USERPROFILE\scoop\apps\msys2\current\mingw64\bin"
)

$mingwBin = $null
foreach ($p in $msys2Paths) {
    if (Test-Path (Join-Path $p "gcc.exe")) {
        $mingwBin = $p
        break
    }
}

if (-not $mingwBin) {
    Write-Host "MSYS2 MinGW not found. Install: pacman -S mingw-w64-x86_64-gcc" -ForegroundColor Yellow
    exit 1
}

$env:PATH = "$mingwBin;$env:PATH"
$env:CC = "gcc"
$env:CYTHON_USE_MSVC = "0"

$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if ($root -ne (Get-Location).Path) { Set-Location $root }

Write-Host "Using MinGW from: $mingwBin" -ForegroundColor Green
python setup_cython_bootstrap.py build_ext --inplace --compiler=mingw32
exit $LASTEXITCODE
