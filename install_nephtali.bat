@echo off
setlocal
cd /d "%~dp0"

echo Installation de Nephtali...
where python >nul 2>&1
if errorlevel 1 (
  echo Python est introuvable. Installe Python 3.11 ou plus recent, puis relance ce fichier.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creation de l'environnement Python...
  python -m venv .venv
  if errorlevel 1 goto :error
)

.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto :error
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo Installation terminee. Lance Nephtali avec run_app.bat.
pause
exit /b 0

:error
echo.
echo L'installation a echoue. Verifie ta connexion Internet et Python.
pause
exit /b 1
