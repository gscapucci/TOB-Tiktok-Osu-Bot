@echo off
rem Confere e instala tudo o que os scripts do projeto precisam:
rem   1. o Python (instala o 3.13 pelo winget, se não tiver)
rem   2. as bibliotecas do requirements.txt (só se faltar alguma)
rem   3. o tosu, em tosu\tosu.exe (só se não tiver; depois ele mesmo se atualiza)
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
"%PY%" -c "import importlib.util as u, sys; sys.exit(any(u.find_spec(m) is None for m in ['TikTokLive', 'edge_tts', 'comtypes', 'PyInstaller', 'reportlab', 'packaging']))" >nul 2>&1
if not errorlevel 1 goto tosu
echo Instalando as bibliotecas necessárias. Só acontece na primeira vez...
"%PY%" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto erro_pip
echo Bibliotecas instaladas.
echo.

:tosu
if exist "tosu\tosu.exe" exit /b 0
echo Baixando o tosu (lê os dados do osu!). Só acontece na primeira vez, são uns 50 MB...
rem pega a versão mais recente para Windows nas releases oficiais: github.com/tosuapp/tosu
rem (o zip vai para dentro de tosu\ e não para o %TEMP%, que pode ter acento no nome do usuário)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol = 'Tls12'; $r = Invoke-RestMethod 'https://api.github.com/repos/tosuapp/tosu/releases/latest' -Headers @{ 'User-Agent' = 'LeitorChat' }; $a = $r.assets | Where-Object { $_.name -like 'tosu-windows-*.zip' } | Select-Object -First 1; if (-not $a) { throw 'a release não tem o arquivo para Windows' }; New-Item -ItemType Directory -Force 'tosu' | Out-Null; $z = 'tosu\download.zip'; Invoke-WebRequest $a.browser_download_url -OutFile $z -UseBasicParsing; Expand-Archive -LiteralPath $z -DestinationPath 'tosu' -Force; Remove-Item -LiteralPath $z; Set-Content -LiteralPath 'tosu\VERSAO.txt' $r.tag_name; Write-Host ('tosu ' + $r.tag_name + ' instalado.')"
if errorlevel 1 goto erro_tosu
if not exist "tosu\tosu.exe" goto erro_tosu
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

:erro_tosu
rem sem o tosu o chat funciona igual, só os comandos do osu! não respondem: por isso não para tudo
echo.
echo *** Não consegui baixar o tosu. O chat funciona normal, mas !np, !pp e os avisos do osu! não.
echo *** Baixe o "tosu-windows" em https://github.com/tosuapp/tosu/releases e coloque o
echo *** tosu.exe dentro da pasta "tosu", ao lado deste arquivo. Ou tente de novo depois.
echo.
exit /b 0
