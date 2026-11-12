@echo off
setlocal
cd /d "%~dp0"
title Aula CyT - Servidor local

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo Creando entorno virtual de Python...
    py -m venv .venv
    if errorlevel 1 goto error
)

call ".venv\Scripts\activate.bat"

echo.
echo Instalando o verificando dependencias...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r requirements.txt
if errorlevel 1 goto error

echo.
echo Iniciando Aula CyT...
echo Cuando aparezca la direccion, abrela en el navegador.
echo Para detener el servidor presiona Ctrl + C.
echo.
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:5000'"
python app.py

goto :eof

:error
echo.
echo Ocurrio un error. Revisa que Python 3 este instalado y que tengas conexion a internet.
pause
