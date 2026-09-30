@echo off
title Push Maxflow to GitHub
echo ============================================================
echo   Uploading Maxflow Project to GitHub
echo   Repository: https://github.com/RajRikame007/Maxflow-Quotation-Generator-.git
echo ============================================================
echo.

cd /d "%~dp0"
set "PATH=C:\Program Files\Git\cmd;C:\Program Files\Git\ucrt64\bin;%PATH%"

git push -u origin main

echo.
if %errorlevel% equ 0 (
    echo ============================================================
    echo   SUCCESS! All project files uploaded to GitHub successfully!
    echo ============================================================
) else (
    echo ============================================================
    echo   If prompted, sign in via browser or paste a GitHub Token.
    echo ============================================================
)
pause
