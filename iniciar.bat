@echo off
rem Abre o leitor do chat pelo leitor_chat.py, instalando antes o que faltar.
cd /d "%~dp0"
call "%~dp0instalar.bat"
if errorlevel 1 (
    pause
    exit /b 1
)
"%PY%" leitor_chat.py
pause
