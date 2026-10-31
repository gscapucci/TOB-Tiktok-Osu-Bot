@echo off
rem Gera o LeitorChat.exe a partir do leitor_chat.py, instalando antes o que faltar.
cd /d "%~dp0"
call "%~dp0instalar.bat"
if errorlevel 1 (
    pause
    exit /b 1
)
echo Gerando o LeitorChat.exe, isso leva um ou dois minutos...
"%PY%" -m PyInstaller --noconfirm --onefile --console --name LeitorChat --collect-all TikTokLive --collect-all edge_tts --hidden-import comtypes.client --workpath build --specpath build --distpath dist leitor_chat.py
if errorlevel 1 (
    echo.
    echo *** Deu erro ao gerar o exe.
) else (
    rmdir /s /q build 2>nul
    echo.
    echo Pronto: dist\LeitorChat.exe atualizado.
)
pause
