@echo off
chcp 65001 >nul
title VetCare - resetar dados
cd /d "%~dp0"

echo.
echo  Isto apaga todos os dados e recria os dados de demonstracao.
echo  Feche o sistema (a janela do iniciar.bat) antes de continuar.
echo.
pause

if not exist ".venv\Scripts\python.exe" (
    echo  Rode o iniciar.bat pelo menos uma vez antes.
    pause
    exit /b 1
)
del /q vetcare.db vetcare.db-wal vetcare.db-shm 2>nul
".venv\Scripts\python.exe" -m vetcare.dados_exemplo

echo.
echo  Pronto! Agora abra o iniciar.bat.
pause
