@echo off
REM Build Cython extensions using MSYS2 MinGW
REM Run from project root: client\build_cython_with_msys2.bat
REM If gcc not found: Start "MSYS2 MINGW64" from Start Menu, then: pacman -S mingw-w64-x86_64-gcc

set "MINGW_BIN="
if exist "C:\msys64\mingw64\bin\gcc.exe" set "MINGW_BIN=C:\msys64\mingw64\bin"
if exist "C:\msys64\ucrt64\bin\gcc.exe" set "MINGW_BIN=C:\msys64\ucrt64\bin"
if exist "C:\msys32\mingw64\bin\gcc.exe" set "MINGW_BIN=C:\msys32\mingw64\bin"
if exist "%USERPROFILE%\msys64\mingw64\bin\gcc.exe" set "MINGW_BIN=%USERPROFILE%\msys64\mingw64\bin"

if "%MINGW_BIN%"=="" (
    echo MSYS2 found but GCC not installed.
    echo 1. Start "MSYS2 MINGW64" from Start Menu
    echo 2. Run: pacman -S mingw-w64-x86_64-gcc
    echo 3. Then run this script again
    exit /b 1
)

set "PATH=%MINGW_BIN%;%PATH%"
set "CC=gcc"
cd /d "%~dp0.."
python client\cython_prebuild_cleanup.py
if errorlevel 1 exit /b 1
python setup_cython_bootstrap.py build_ext --inplace --compiler=mingw32
exit /b %ERRORLEVEL%
