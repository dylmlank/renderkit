@echo off
setlocal
cd /d "%~dp0"

echo === RenderKit (Blender add-on) ===
echo.

set "ADDON=%~dp0blender_addon\renderkit_panel.py"
set "BLENDER="

REM Find newest Blender under "Blender Foundation"
for /f "delims=" %%D in ('dir /b /ad /o-n "C:\Program Files\Blender Foundation\Blender*" 2^>nul') do (
    if exist "C:\Program Files\Blender Foundation\%%D\blender.exe" (
        set "BLENDER=C:\Program Files\Blender Foundation\%%D\blender.exe"
        goto found
    )
)

REM Fallback locations
if exist "C:\Program Files\Blender Foundation\Blender\blender.exe" set "BLENDER=C:\Program Files\Blender Foundation\Blender\blender.exe"

:found
if not defined BLENDER (
    echo Blender not found under "C:\Program Files\Blender Foundation".
    echo Edit this script and set BLENDER to your blender.exe path.
    pause
    exit /b 1
)

echo Using Blender: %BLENDER%
echo Registering RenderKit panel on startup...
echo Look for the "RenderKit" tab in the 3D viewport sidebar (press N).
echo.

start "" "%BLENDER%" --python "%ADDON%"
