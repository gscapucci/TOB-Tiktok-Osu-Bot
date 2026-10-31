@echo off
rem Confere e instala tudo o que os scripts do projeto precisam:
rem   1. o Python (instala o 3.13 pelo winget, se não tiver)
rem   2. as bibliotecas do requirements.txt (só se faltar alguma)
rem Os outros .bat chamam este com "call instalar.bat" e depois usam "%PY%".
chcp 65001 >nul
cd /d "%~dp0"

set "PY="
call :achar_python
if defined PY goto bibliotecas

echo Python não encontrado. Instalando o Python 3.13, isso pode levar alguns minutos...
winget --version >nul 2>&1
if errorlevel 1 goto sem_winget
winget install -e --id Python.Python.3.13 --scope user --silent --accept-package-agreements --accept-source-agreements
call :achar_python
if not defined PY goto sem_python
echo Python instalado.
echo.

:bibliotecas
rem só confere se as bibliotecas existem, sem carregar (bem mais rápido que importar)
"%PY%" -c "import importlib.util as u, sys; sys.exit(any(u.find_spec(m) is None for m in ['TikTokLive', 'edge_tts', 'comtypes', 'PyInstaller', 'reportlab']))" >nul 2>&1
if not errorlevel 1 exit /b 0
echo Instalando as bibliotecas necessárias. Só acontece na primeira vez...
"%PY%" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto erro_pip
echo Bibliotecas instaladas.
echo.
exit /b 0


:achar_python
rem "python" pode ser só o atalho da Microsoft Store, então testa se ele roda de verdade
for /f "delims=" %%i in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "PY=%%i"
if defined PY exit /b 0
for /f "delims=" %%i in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PY=%%i"
if defined PY exit /b 0
rem logo depois de instalar, o Python ainda não está no PATH desta janela
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
exit /b 0

:sem_winget
echo.
echo *** Não consegui instalar o Python sozinho: o winget não está disponível neste Windows.
echo *** Instale o Python pelo site que vai abrir agora. Na instalação, marque a opção
echo *** "Add python.exe to PATH". Depois rode este script de novo.
start "" "https://www.python.org/downloads/"
exit /b 1

:sem_python
echo.
echo *** A instalação do Python não terminou. Feche esta janela, abra de novo e tente mais uma vez.
echo *** Se continuar, instale pelo site https://www.python.org/downloads/
echo *** marcando a opção "Add python.exe to PATH".
exit /b 1

:erro_pip
echo.
echo *** Não consegui instalar as bibliotecas. Confira a internet e tente de novo.
exit /b 1
