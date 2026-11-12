@echo off
setlocal
cd /d "%~dp0"
title Aula CyT - Servidor para celular y tablet

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

set HOST=0.0.0.0
set PORT=5000

echo.
echo Iniciando Aula CyT para tu red local...
echo.
echo IMPORTANTE:
echo  - En el celular o tablet abre la direccion "Desde tu celular" que aparece abajo.
echo  - La computadora y el celular deben estar en la misma red Wi-Fi.
echo  - Si Windows pregunta por el Firewall, permite el acceso en redes privadas.
echo.
python app.py

goto :eof

:error
echo.
echo Ocurrio un error. Revisa que Python 3 este instalado y que tengas conexion a internet.
pause
