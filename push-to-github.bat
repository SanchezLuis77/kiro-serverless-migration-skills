@echo off
echo ===================================================================
echo PUSHING SKILL 01 TO GITHUB
echo ===================================================================
echo.

cd /d "c:\Users\USUARIO\Documents\TG-MAESTRIA\kiro-serverless-migration-skills"

echo Current directory:
cd

echo.
echo Commit to push:
git log --oneline -1

echo.
echo Remote repository:
git remote -v

echo.
echo ===================================================================
echo EXECUTING GIT PUSH...
echo ===================================================================
echo.

git push origin main

echo.
echo ===================================================================
if %ERRORLEVEL% EQU 0 (
    echo ? PUSH SUCCESSFUL!
    echo ===================================================================
    echo.
    echo Verifying...
    git log --oneline origin/main -1
    echo.
    echo Visit: https://github.com/SanchezLuis77/kiro-serverless-migration-skills
) else (
    echo ? PUSH FAILED - Error code: %ERRORLEVEL%
    echo ===================================================================
    echo.
    echo Please check:
    echo   1. Internet connection
    echo   2. GitHub authentication
    echo   3. Repository permissions
    echo.
    echo Alternative: Use GitHub Desktop or VSCode
)

echo.
pause
