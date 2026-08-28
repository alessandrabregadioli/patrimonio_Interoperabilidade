@echo off
setlocal
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo Criando ambiente virtual...
    python -m venv venv
)

echo Instalando dependencias...
"venv\Scripts\python.exe" -m pip install -r requirements.txt

echo.
echo Sistema disponivel localmente em http://127.0.0.1:5000
echo Pela VPN, utilize http://IP_DA_VPN:5000
echo.
"venv\Scripts\python.exe" app.py

endlocal
