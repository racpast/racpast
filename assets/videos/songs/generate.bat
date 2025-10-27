@echo off
setlocal

:: Set a specific window title for this script's function
title Static Image + Audio to Video Utility

:main
cls
echo =======================================================
echo         Static Image + Audio to Video Utility
echo =======================================================
echo.

:: --- Input File Acquisition ---
set "image_file="
set "audio_file="

echo Please drag and drop the cover image file here, then press Enter:
set /p "image_file="
rem Sanitize the input path by removing quotes if present
set "image_file=%image_file:"=%"

echo.
echo Please drag and drop the audio file here, then press Enter:
set /p "audio_file="
set "audio_file=%audio_file:"=%"
echo.

:: --- Input Validation ---
if not exist "%image_file%" (
    echo [ERROR] The specified image file was not found.
    echo Please restart the script.
    echo.
    pause
    goto main
)
if not exist "%audio_file%" (
    echo [ERROR] The specified audio file was not found.
    echo Please restart the script.
    echo.
    pause
    goto main
)

:: --- Output File Configuration ---
rem Generate a default output filename from the audio input
for %%f in ("%audio_file%") do set "output_name=%%~nf"
set "output_file=%output_name%.mp4"

echo The default output filename is: "%output_file%"
echo To accept this default, press Enter.
echo To specify a different name, enter it now (including .mp4 extension):
set /p "new_output="

if defined new_output (
    set "output_file=%new_output%"
)
echo.
echo Output will be saved to: "%output_file%"
echo =======================================================
echo.
echo Now processing... Please wait.
echo.

:: --- FFmpeg Command Execution ---
ffmpeg -loop 1 -i "%image_file%" -i "%audio_file%" -c:v libx264 -preset ultrafast -tune stillimage -pix_fmt yuv420p -r 1 -vf "scale='iw*min(1,300/iw)':'ih*min(1,300/ih)',scale=300:300:force_original_aspect_ratio=decrease" -c:a copy -shortest "%output_file%"
echo.
echo =======================================================
echo.
echo Process completed successfully.
echo.
echo =======================================================
echo.
pause
exit