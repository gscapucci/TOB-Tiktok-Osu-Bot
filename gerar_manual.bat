@echo off
rem Gera o "Guia de uso - Leitor de Chat.pdf", instalando antes o que faltar.
cd /d "%~dp0"
call "%~dp0instalar.bat"
if errorlevel 1 (
    pause
    exit /b 1
)
"%PY%" gerar_manual.py
pause
