@echo off
setlocal
chcp 65001 >nul
title VetCare
cd /d "%~dp0"

echo.
echo  ===== VetCare =====
echo  Pasta: %cd%
echo.

if not exist "requirements.txt" (
    echo  ERRO: este arquivo precisa ficar na mesma pasta do requirements.txt.
    goto :fim
)

rem ---------------------------------------------------------------
rem 1) Ambiente virtual ja existe? Usa ele.
rem ---------------------------------------------------------------
if exist ".venv\Scripts\python.exe" goto :dependencias

rem ---------------------------------------------------------------
rem 2) Procura um Python de verdade (o launcher "py" primeiro;
rem    o "python" do Windows pode ser so um atalho para a Store)
rem ---------------------------------------------------------------
set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY (
    python -c "import sys" >nul 2>&1 && set "PY=python"
)

if not defined PY (
    echo  Python nao encontrado. Tentando instalar automaticamente...
    winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
    echo.
    echo  Se a instalacao terminou, FECHE esta janela e abra o iniciar.bat de novo.
    echo  Se nao funcionou, instale pelo site python.org marcando "Add python.exe to PATH".
    goto :fim
)

echo  Preparando o ambiente (so na primeira vez)...
%PY% -m venv .venv
if errorlevel 1 (
    echo  ERRO ao criar o ambiente virtual.
    goto :fim
)

:dependencias
rem ---------------------------------------------------------------
rem 3) Garante as bibliotecas (instala se faltar alguma)
rem ---------------------------------------------------------------
".venv\Scripts\python.exe" -c "import starlette, uvicorn, jwt" >nul 2>&1
if errorlevel 1 (
    echo  Instalando bibliotecas, precisa de internet...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo  ERRO ao instalar as bibliotecas. Verifique a internet e tente de novo.
        goto :fim
    )
)

rem ---------------------------------------------------------------
rem 4) Dados de demonstracao na primeira vez
rem ---------------------------------------------------------------
if not exist "vetcare.db" ".venv\Scripts\python.exe" -m vetcare.dados_exemplo

rem ---------------------------------------------------------------
rem 5) Sobe o sistema e abre o navegador
rem ---------------------------------------------------------------
start "" cmd /c "timeout /t 4 >nul & start http://127.0.0.1:8000"
echo.
echo  Sistema em http://127.0.0.1:8000
echo  Login: admin@vetcare.local  /  Admin@123
echo  Para desligar, feche esta janela.
echo.
".venv\Scripts\python.exe" -m vetcare

:fim
echo.
pause
