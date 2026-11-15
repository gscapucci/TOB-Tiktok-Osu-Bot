"""
Leitor de chat da live do TikTok em voz alta (pt-BR).

Uso:
    python leitor_chat.py seu_usuario
    (sem o @; fica guardado no config.json. Se a live não começou ou cair, ele espera e volta sozinho)

Comandos do chat (as respostas são faladas):
    Todo mundo:  !comandos  !mensagens  !top  !sons
                 e os comandos de som do config.json ("sons": {"ai": "ai.mp3"} -> !ai)
    Você e MODERADORES:  !mudo  !voltar  !limpar  !velocidade <-10 a 10>  !volume <0 a 100>
                         !apelido <usuário> <apelido>  !copiar <texto>
                         !voz <francisca, antonio, maria...>  !nomes  !bloquear <palavra>
                         !desbloquear <palavra>  !silenciar <nome ou usuário>  !liberar <nome ou usuário>
                         !ligar <comando>  !desligar <comando>
                         !avisos <mapa ou recorde>  !espera <segundos>  !tamanho <letras>  !fila <mensagens>
                         !esperasom <segundos>
    Só você:  !mod <usuário>  !desmod <usuário>
    (o que estes comandos mudam fica gravado no config.json)

Pedidos de mapas do osu! (a fila fica salva em pedidos.txt):
    Todo mundo:  !pedir <link, nome, código do set ou d + código da dificuldade>  !pedidos  !cancelar
    Você e MODERADORES:  !proximo (abre no navegador)  !remover <posição>  !fecharpedidos
                         !abrirpedidos  !zerarpedidos  !limitepedidos <número>  !porpessoa <número>
                         !filapedidos (liga/desliga a fila: desligada, cada pedido vai direto para o osu!)

osu! (o tosu abre sozinho, se estiver na pasta tosu):  !np (mapa atual)  !pp  !rank  !recorde
    e avisos automáticos de mapa novo (AVISAR_MAPA) e de recorde de PP da live (AVISAR_RECORDE)

Sem live: rode com o usuário "teste" e digite as mensagens do chat na janela.

Configurações: pelo config.json ou pela página http://localhost:8765 (WEB_PORTA),
    que muda tudo na hora, sem reabrir o programa.
"""

import atexit
import base64
import csv
import http.server
import ipaddress
import os
import re
import subprocess
import sys
import threading
import time
import json
import urllib.parse
import urllib.request
import webbrowser
from collections import deque
from datetime import datetime, timedelta, timezone

from TikTokLive import TikTokLiveClient
from TikTokLive.client.errors import UserNotFoundError, UserOfflineError
from TikTokLive.events import CommentEvent, ConnectEvent, DisconnectEvent, JoinEvent

# ---------------- Configurações ----------------
# Estes são os valores padrão. Para mudar, use a página de configurações ou edite o
# config.json ao lado do programa (ele é criado sozinho na primeira vez que o programa abre).
TIKTOK_USUARIO = ""     # seu usuário do TikTok, sem @ (perguntado e guardado na primeira vez)

# Vozes disponíveis (as neurais precisam de internet e soam mais naturais):
#   "pt-BR-FranciscaNeural"           feminina
#   "pt-BR-ThalitaMultilingualNeural" feminina
#   "pt-BR-AntonioNeural"             masculina
#   "pt-PT-RaquelNeural"              feminina (Portugal)
#   "pt-PT-DuarteNeural"              masculina (Portugal)
#   "en-US-AvaMultilingualNeural"     feminina, EUA, fala português com sotaque
#   "en-US-EmmaMultilingualNeural"    feminina, EUA, fala português com sotaque
#   "en-US-BrianMultilingualNeural"   masculina, EUA, fala português com sotaque
#   "en-AU-WilliamMultilingualNeural" masculina, Austrália, fala português com sotaque
#   "fr-FR-VivienneMultilingualNeural" feminina, França, fala português com sotaque
#   "fr-FR-RemyMultilingualNeural"    masculina, França, fala português com sotaque
#   "de-DE-SeraphinaMultilingualNeural" feminina, Alemanha, fala português com sotaque
#   "de-DE-FlorianMultilingualNeural" masculina, Alemanha, fala português com sotaque
#   "it-IT-GiuseppeMultilingualNeural" masculina, Itália, fala português com sotaque
#   "ko-KR-HyunsuMultilingualNeural"  masculina, Coreia, fala português com sotaque
#   "windows"                         voz Maria do Windows (funciona offline)
VOZ = "pt-BR-FranciscaNeural"
VELOCIDADE = 1          # -10 (lento) a 10 (rápido)
VOLUME = 100            # 0 a 100
LER_NOME = True         # falar "Fulano disse: ..." antes da mensagem
TAMANHO_MAXIMO = 200    # corta mensagens muito longas
FILA_MAXIMA = 15        # se o chat estiver muito rápido, descarta as mais antigas
PALAVRAS_BLOQUEADAS = []  # ex.: ["spam", "palavrão"]
USUARIOS_SILENCIADOS = []  # usuários (sem @) que a voz não lê e cujos comandos são ignorados

# Comandos do chat (veja a lista completa em tratar_comando)
PREFIXO = "!"
MODERADORES = []        # usuários (sem @) que podem usar os comandos de moderação, além de você
ESPERA_COMANDO = 15     # segundos que cada pessoa espera entre um comando e outro
ESPERA_SOM = 10         # depois de um som (!ai), segundos até o chat poder tocar outro
# comandos de som: "comando": {"arquivo": "arquivo da pasta sons" (aceita caminho completo), "volume": 0 a 100}.
# O volume do som é uma parte do volume geral (100 = igual à voz). No config.json também vale só "comando": "arquivo".
# Os arquivos destes vêm no zip.
SONS = {"ai": {"arquivo": "ai-ai-ai.mp3", "volume": 100},
        "ban": {"arquivo": "banido_FzWiL58.mp3", "volume": 100},
        "banido": {"arquivo": "banido_FzWiL58.mp3", "volume": 100},
        "quecano": {"arquivo": "metal-pipe-clang.mp3", "volume": 100},
        "cano": {"arquivo": "metal-pipe-clang.mp3", "volume": 100},
        "zap": {"arquivo": "som-do-zap-zap-estourado.mp3", "volume": 100},
        "fah": {"arquivo": "fahhhhhhhhhhhhhh.mp3", "volume": 100}}
PEDIDOS_MAXIMOS = 30    # tamanho máximo da fila de pedidos de mapas do osu!
PEDIDOS_POR_PESSOA = 1  # quantos pedidos cada pessoa pode ter na fila ao mesmo tempo (0 = sem limite)
FILA_PEDIDOS = True     # False: cada !pedir vai direto para o seu chat do osu!, sem fila e sem a voz anunciar
COMANDOS_DESATIVADOS = []  # comandos desligados, sem o "!". ex.: ["copiar", "top"]

# osu! (precisa do tosu aberto junto com o jogo)
TOSU_URL = "http://127.0.0.1:24050/json/v2"
AVISAR_MAPA = True      # falar "Agora: Artista - Música" quando você começa a jogar um mapa novo
AVISAR_RECORDE = True   # falar quando você bate o recorde de PP da live
# Chat do osu!: com os dois preenchidos, o !proximo manda o pedido no seu chat do osu! em vez de abrir o
# navegador. A senha NÃO é a da conta: é a de IRC, em osu.ppy.sh > Configurações > Legacy API.
OSU_USUARIO = ""        # seu nome no osu!
OSU_IRC_SENHA = ""

# Página de configurações (estas duas só valem quando o programa abre de novo)
WEB_PORTA = 8765        # http://localhost:8765 ; 0 desliga a página
WEB_REDE_LOCAL = False  # True: abre também no celular/outro PC da mesma rede (qualquer um nela pode mexer)
ABRIR_PAGINA = True     # abrir a página no navegador quando o programa começa
# ------------------------------------------------

# O que a voz vai falar. Respostas e avisos passam na frente do chat: quem usou um comando
# não pode esperar a fila inteira de mensagens, nem ter a resposta descartada por elas.
fila_avisos = deque()   # textos
fila_chat = deque()     # (usuário em minúsculo, texto)
tem_fala = threading.Condition()

# ---------------- Registro de quem entrou / mensagens ----------------
# Pasta do programa: ao lado do .exe quando empacotado, senão ao lado deste arquivo
PASTA = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
PASTA_REGISTROS = os.path.join(PASTA, "registros")
ARQUIVO_CONFIG = os.path.join(PASTA, "config.json")
PASTA_SONS = os.path.join(PASTA, "sons")  # onde ficam os arquivos dos SONS (a página grava aqui)

# nome no config.json -> variável aqui do programa
OPCOES = {nome.lower(): nome for nome in (
    "TIKTOK_USUARIO", "VOZ", "VELOCIDADE", "VOLUME", "LER_NOME", "TAMANHO_MAXIMO", "FILA_MAXIMA", "PALAVRAS_BLOQUEADAS",
    "USUARIOS_SILENCIADOS", "PREFIXO", "MODERADORES", "ESPERA_COMANDO", "ESPERA_SOM", "SONS", "PEDIDOS_MAXIMOS", "PEDIDOS_POR_PESSOA", "FILA_PEDIDOS", "COMANDOS_DESATIVADOS",
    "TOSU_URL", "AVISAR_MAPA", "AVISAR_RECORDE", "OSU_USUARIO", "OSU_IRC_SENHA", "WEB_PORTA", "WEB_REDE_LOCAL", "ABRIR_PAGINA")}
OPCOES_ANTIGAS = ("janela_pedidos",)  # opções de versões anteriores: ignoradas sem aviso
SECRETAS = ("osu_irc_senha",)  # a página nunca mostra: só diz se tem uma salva e deixa trocar
LIMITES = {"VELOCIDADE": (-10, 10), "VOLUME": (0, 100), "TAMANHO_MAXIMO": (1, None), "FILA_MAXIMA": (1, None),
           "ESPERA_COMANDO": (0, None), "ESPERA_SOM": (0, None), "PEDIDOS_MAXIMOS": (1, None), "PEDIDOS_POR_PESSOA": (0, None), "WEB_PORTA": (0, 65535)}


def config_atual() -> dict:
    return {chave: globals()[nome] for chave, nome in OPCOES.items()}


def salvar_config():
    with open(ARQUIVO_CONFIG, "w", encoding="utf-8") as f:
        json.dump(config_atual(), f, ensure_ascii=False, indent=2)


trava_config = threading.Lock()  # o chat e a página podem mudar as configurações ao mesmo tempo


def mudar_config(mudancas: dict) -> list:
    """Aplica as mudanças (do chat ou da página) e grava no config.json. Devolve os avisos."""
    with trava_config:
        avisos = aplicar_config(mudancas)
        try:
            salvar_config()
        except OSError as e:
            avisos.append(f"mudei agora, mas não consegui gravar o config.json ({e}).")
    esquecer_silenciados()
    for aviso in avisos:
        print(f"*** {aviso}")
    return avisos


def aplicar_config(config: dict) -> list:
    """Confere e aplica as opções (do config.json ou da página). Devolve os avisos do que não deu."""
    avisos = []
    for chave, valor in config.items():
        nome = OPCOES.get(chave.lower())
        if nome is None:
            if chave.lower() in OPCOES_ANTIGAS:
                continue
            avisos.append(f"não conheço a opção \"{chave}\" (escrita errada?). Ignorando.")
            continue
        atual = globals()[nome]
        esperado = type(atual)
        # em Python True/False também contam como número; aqui não podem
        ok = isinstance(valor, esperado) and not (esperado is int and isinstance(valor, bool))
        if ok and esperado is list:
            ok = all(isinstance(x, str) for x in valor)
        if ok and esperado is dict and nome != "SONS":  # os sons são conferidos em conferir_sons
            ok = all(isinstance(k, str) and isinstance(v, str) for k, v in valor.items())
        if not ok:
            avisos.append(f"\"{chave}\" deveria ser {TIPOS.get(esperado, esperado.__name__)}. "
                          f"Mantive: {json.dumps(atual, ensure_ascii=False)}")
            continue
        if nome == "TIKTOK_USUARIO":
            valor = valor.strip().lstrip("@")
        if nome == "SONS":
            valor, avisos_sons = conferir_sons(valor)
            avisos += avisos_sons
        if nome == "PREFIXO" and not valor.strip():
            avisos.append(f"\"{chave}\" não pode ficar vazio. Mantive: {json.dumps(atual, ensure_ascii=False)}")
            continue
        if nome in LIMITES:
            menor, maior = LIMITES[nome]
            ajustado = max(menor, valor) if maior is None else max(menor, min(maior, valor))
            if ajustado != valor:
                avisos.append(f"\"{chave}\" vai de {menor} a {maior if maior is not None else 'quanto quiser'}. "
                              f"Usei {ajustado}.")
                valor = ajustado
        globals()[nome] = valor
    return avisos


def carregar_config():
    """Lê o config.json (criando com os valores padrão se não existir)."""
    if not os.path.exists(ARQUIVO_CONFIG):
        salvar_config()
        print(f"Criei o arquivo de configurações: {ARQUIVO_CONFIG}\n")
        return
    try:
        with open(ARQUIVO_CONFIG, encoding="utf-8-sig") as f:
            config = json.load(f)
        if not isinstance(config, dict):
            raise ValueError("o arquivo precisa começar com { e terminar com }")
    except (ValueError, UnicodeDecodeError) as e:
        if isinstance(e, json.JSONDecodeError):
            print(f"*** ERRO no config.json, perto da linha {e.lineno}, coluna {e.colno}.\n"
                  f"*** Confira: true/false em minúsculo, textos entre aspas, vírgula entre os itens\n"
                  f"*** e nenhuma vírgula depois do último item.")
        else:
            print(f"*** ERRO no config.json: {e}")
        print("*** Usando as configurações padrão. Corrija o arquivo e abra o programa de novo.\n")
        return
    avisos = aplicar_config(config)
    for aviso in avisos:
        print(f"*** config.json: {aviso}")
    for aviso in sons_configurados()[1]:
        print(f"*** som {aviso}")
    # versão nova com opções novas: acrescenta só elas, com o valor padrão, sem mexer no resto.
    # Com algum aviso não grava, para não apagar o que a pessoa ainda precisa corrigir.
    novas = [chave for chave in OPCOES if chave not in {c.lower() for c in config}]
    # sons no jeito antigo ("ai": "ai.mp3") são regravados com o volume, para a pessoa ver onde mudar
    sons_antigos = any(isinstance(v, str) for c, sons in config.items() if c.lower() == "sons"
                       and isinstance(sons, dict) for v in sons.values())
    if (novas or sons_antigos) and not avisos:
        try:
            salvar_config()
            if novas:
                print(f"Opções novas no config.json (com o valor padrão): {', '.join(novas)}\n")
            if sons_antigos:
                print("Os sons do config.json agora têm \"volume\" (de 0 a 100) ao lado do arquivo.\n")
        except OSError:
            pass


TIPOS = {bool: "true ou false", int: "um número inteiro (sem vírgula)", str: "um texto entre aspas", list: "uma lista entre [ ]",
         dict: "uma lista de \"nome\": \"valor\" entre { }"}
pessoas = {}  # unique_id -> {"nome", "entrou", "mensagens"}
trava = threading.Lock()
mudou = False


def registrar(user, mensagem=False):
    global mudou
    if user is None or not user.unique_id:
        return
    with trava:
        p = pessoas.setdefault(user.unique_id, {
            "nome": user.nick_name or user.unique_id,
            "entrou": datetime.now().strftime("%H:%M:%S"),
            "mensagens": 0,
        })
        if mensagem:
            p["mensagens"] += 1
        mudou = True


DIAS_REGISTROS = 7  # planilhas de live mais antigas que isso são apagadas quando o programa abre


def apagar_registros_antigos():
    """Apaga as planilhas live_DATA_HORA.csv de mais de DIAS_REGISTROS dias (pela data no nome).
    Outros arquivos que você puser na pasta registros não são mexidos."""
    limite = datetime.now() - timedelta(days=DIAS_REGISTROS)
    apagados = 0
    try:
        nomes = os.listdir(PASTA_REGISTROS)
    except OSError:
        return
    for nome in nomes:
        m = re.fullmatch(r"live_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2})\.csv", nome)
        if not m:
            continue
        try:
            if datetime.strptime(m.group(1), "%Y-%m-%d_%H-%M") < limite:
                os.remove(os.path.join(PASTA_REGISTROS, nome))
                apagados += 1
        except (ValueError, OSError):  # data estranha no nome, ou a planilha aberta no Excel: fica para a próxima
            pass
    if apagados:
        print(f"[apaguei {apagados} {'registro' if apagados == 1 else 'registros'} de mais de {DIAS_REGISTROS} dias]")


def salvar(arquivo):
    """Salva a planilha (abre no Excel), ordenada por quem mais mandou mensagem."""
    global mudou
    with trava:
        if not mudou:
            return
        linhas = sorted(pessoas.items(), key=lambda kv: -kv[1]["mensagens"])
        mudou = False
    with open(arquivo, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Usuário", "Nome", "Entrou às", "Mensagens"])
        for uid, p in linhas:
            w.writerow([f"@{uid}", p["nome"], p["entrou"], p["mensagens"]])


def salvador_automatico(arquivo):
    while True:
        time.sleep(5)
        try:
            salvar(arquivo)
        except PermissionError:
            pass  # arquivo aberto no Excel; tenta de novo depois


def tocar_mp3(caminho: str, enquanto=None, volume=100):
    """Toca um mp3 (ou wav) com o player nativo do Windows (MCI) e espera terminar.
    enquanto: chamada sem parar durante o som (o narrador usa para já baixar a próxima fala).
    volume: de 0 a 100, uma parte do VOLUME geral (os sons do chat têm o volume de cada um)."""
    import ctypes
    mci = ctypes.windll.winmm.mciSendStringW
    if mci(f'open "{caminho}" type mpegvideo alias fala', None, 0, None):
        raise OSError(f"não consegui abrir {os.path.basename(caminho)}")
    try:
        mci(f"setaudio fala volume to {round(VOLUME * volume / 10)}", None, 0, None)
        if enquanto is None:
            mci("play fala wait", None, 0, None)
            return
        mci("play fala", None, 0, None)
        estado = ctypes.create_unicode_buffer(32)
        while True:
            enquanto()
            if mci("status fala mode", estado, 32, None) or estado.value not in ("playing", "seeking"):
                break
            time.sleep(0.05)
    finally:
        mci("close fala", None, 0, None)


def voz_windows():
    """Prepara a voz Maria do Windows (SAPI), que funciona offline."""
    import comtypes.client
    comtypes.CoInitialize()
    voz = comtypes.client.CreateObject("SAPI.SpVoice")
    for v in voz.GetVoices():
        if "pt-BR" in v.GetDescription() or "Maria" in v.GetDescription():
            voz.Voice = v
            break
    return voz


ESPERA_VOZ_NEURAL = 10  # segundos que uma fala pode levar para vir da internet antes de desistir (normal: 1 a 2)
PAUSA_VOZ_NEURAL = 60   # depois de uma falha, segundos sem tentar a voz neural (cada tentativa pode demorar)


def apagar_arquivo(caminho: str):
    try:
        os.remove(caminho)
    except OSError:
        pass


def narrador():
    """Thread que fala as mensagens da fila, uma de cada vez.
    Enquanto uma fala toca, a próxima da fila já vai sendo baixada, para não ter espera entre elas.
    VOZ, VELOCIDADE e VOLUME são lidos a cada fala, para valer o que mudar durante a live.
    Se a voz neural falhar, a mensagem sai na voz do Windows, e a neural é tentada de novo depois."""
    import asyncio
    import glob
    import itertools
    import tempfile
    from concurrent.futures import ThreadPoolExecutor
    import edge_tts
    from edge_tts.exceptions import NoAudioReceived

    pasta = tempfile.gettempdir()
    for velho in glob.glob(os.path.join(pasta, "tiktok_fala*.mp3")):  # sobras de quando o programa fechou falando
        apagar_arquivo(velho)
    numeros = itertools.count()
    baixador = ThreadPoolExecutor(max_workers=2, thread_name_prefix="voz")
    preparadas = {}  # (texto, voz, velocidade) -> a fala sendo baixada (ou já baixada) antes da vez dela
    sapi = None  # só criada se a voz do Windows for usada
    tentar_neural_em = 0.0  # até esta hora a voz neural falhou há pouco: usa a do Windows direto
    em_reserva = False      # já avisou que está na voz do Windows

    def falar_windows(frase: str):
        nonlocal sapi
        if sapi is None:
            sapi = voz_windows()
        sapi.Rate = VELOCIDADE
        sapi.Volume = VOLUME
        sapi.Speak(frase)

    def baixar(texto: str, voz: str, taxa: str) -> str:
        caminho = os.path.join(pasta, f"tiktok_fala_{next(numeros)}.mp3")
        try:
            asyncio.run(asyncio.wait_for(edge_tts.Communicate(texto, voz, rate=taxa).save(caminho),
                                         ESPERA_VOZ_NEURAL))
        except BaseException:
            apagar_arquivo(caminho)
            raise
        return caminho

    def chave(texto: str) -> tuple:
        return texto, VOZ, f"{VELOCIDADE * 10:+d}%"

    def descartar(fala):
        """Fala baixada antes da hora que não vai mais ser usada (a voz mudou, ou o !limpar apagou a fila)."""
        if not fala.cancel():
            fala.add_done_callback(lambda f: f.exception() is None and apagar_arquivo(f.result()))

    def preparar_proxima():
        """Chamada enquanto uma fala toca: já baixa a próxima da fila. Uma resposta que chega no meio
        passa na frente, e é ela que passa a ser baixada."""
        if VOZ == "windows" or time.time() < tentar_neural_em:
            return
        with tem_fala:
            proxima = fila_avisos[0] if fila_avisos else fila_chat[0][1] if fila_chat else None
        if not isinstance(proxima, str) or chave(proxima) in preparadas:
            return
        while len(preparadas) >= 3:  # guarda poucas: a fila muda o tempo todo
            descartar(preparadas.pop(next(iter(preparadas))))
        preparadas[chave(proxima)] = baixador.submit(baixar, *chave(proxima))

    while True:
        texto = proxima_fala()
        try:
            if isinstance(texto, tuple):  # ("som", arquivo, volume): um !ai, por exemplo
                tocar_mp3(texto[1], preparar_proxima, texto[2])
                continue
            if VOZ == "windows" or time.time() < tentar_neural_em:
                falar_windows(texto)
                continue
            fala = preparadas.pop(chave(texto), None) or baixador.submit(baixar, *chave(texto))
            try:
                caminho = fala.result()
            except NoAudioReceived:
                # o serviço respondeu, mas o texto não tem nada para falar (só símbolos, por exemplo)
                print(f"[nada para falar em: {texto}]")
                continue
            except Exception as e:
                # sem internet ou serviço fora do ar: a mensagem não se perde, sai na voz do Windows
                tentar_neural_em = time.time() + PAUSA_VOZ_NEURAL
                for f in preparadas.values():  # as já baixadas vão sair na voz do Windows
                    descartar(f)
                preparadas.clear()
                if not em_reserva:
                    em_reserva = True
                    print(f"*** A voz da internet falhou ({type(e).__name__}: {e}). Usando a voz do Windows "
                          f"e tentando de novo a cada {PAUSA_VOZ_NEURAL} segundos.")
                    falar_windows("A voz da internet falhou. Vou usar a voz do Windows.")
                falar_windows(texto)
                continue
            if em_reserva:
                em_reserva = False
                print("[a voz da internet voltou]")
            try:
                tocar_mp3(caminho, preparar_proxima)
            finally:
                apagar_arquivo(caminho)
        except Exception as e:
            print(f"[erro na voz: {e}]")


ARQUIVO_APELIDOS = os.path.join(PASTA, "apelidos.txt")


def carregar_apelidos() -> dict:
    """Lê apelidos.txt a cada mensagem, para valer mesmo se editado durante a live."""
    apelidos = {}
    try:
        with open(ARQUIVO_APELIDOS, encoding="utf-8-sig") as f:
            for linha in f:
                linha = linha.strip()
                if not linha or linha.startswith("#") or "=" not in linha:
                    continue
                usuario, apelido = linha.split("=", 1)
                apelidos[usuario.strip().lstrip("@").lower()] = apelido.strip()
    except (FileNotFoundError, UnicodeDecodeError):
        pass
    return apelidos


def limpar(texto: str) -> str:
    texto = re.sub(r"https?://\S+", "link", texto)
    texto = re.sub(r"(.)\1{4,}", r"\1\1\1", texto)  # "kkkkkkkkk" -> "kkk"
    return texto[:TAMANHO_MAXIMO].strip()


def tem_palavra_bloqueada(texto: str) -> bool:
    return any(p.lower() in texto.lower() for p in PALAVRAS_BLOQUEADAS)


def nome_para_falar(nome: str) -> str:
    """O nome do TikTok também é lido em voz alta e aparece na fila: com palavra bloqueada, não sai."""
    return "Alguém" if tem_palavra_bloqueada(nome) else nome


def falar(texto):
    """Resposta ou aviso: passa na frente do chat. Com respostas demais, descarta as mais antigas."""
    with tem_fala:
        while len(fila_avisos) >= FILA_MAXIMA:
            fila_avisos.popleft()
        fila_avisos.append(texto)
        tem_fala.notify()


def tocar_som(som: dict):
    """Som de um comando (!ai), {"caminho", "volume"}: entra na fila como as respostas, para não tocar por cima da voz."""
    falar(("som", som["caminho"], som["volume"]))


def falar_chat(uid: str, texto: str):
    """Mensagem do chat; se o chat estiver muito rápido, descarta as mais antigas."""
    with tem_fala:
        while len(fila_chat) >= FILA_MAXIMA:
            fila_chat.popleft()
        fila_chat.append((uid, texto))
        tem_fala.notify()


def proxima_fala():
    """Espera ter algo para falar e devolve: primeiro as respostas e os avisos, depois o chat.
    Um som vem como ("som", arquivo, volume); o resto é o texto."""
    with tem_fala:
        while not fila_avisos and not fila_chat:
            tem_fala.wait()
        return fila_avisos.popleft() if fila_avisos else fila_chat.popleft()[1]


def limpar_fila():
    with tem_fala:
        fila_avisos.clear()
        fila_chat.clear()


def lista_silenciados() -> set:
    return {u.strip().lstrip("@").lower() for u in USUARIOS_SILENCIADOS}


def esquecer_silenciados():
    """Tira da fila o que os silenciados já tinham mandado, senão a voz continuaria lendo por um tempo."""
    silenciados = lista_silenciados()
    with tem_fala:
        restantes = [m for m in fila_chat if m[0] not in silenciados]
        fila_chat.clear()
        fila_chat.extend(restantes)


def salvar_apelido(uid: str, apelido: str):
    """Grava (ou troca) o apelido da pessoa no apelidos.txt."""
    linhas = []
    try:
        with open(ARQUIVO_APELIDOS, encoding="utf-8-sig") as f:
            linhas = [l for l in f.read().splitlines()
                      if l.split("=", 1)[0].strip().lstrip("@").lower() != uid]
    except FileNotFoundError:
        pass
    linhas.append(f"{uid} = {apelido}")
    with open(ARQUIVO_APELIDOS, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")


def copiar_texto(texto: str):
    """Copia o texto para a área de transferência do Windows (o mesmo do Ctrl+C)."""
    import ctypes
    from ctypes import wintypes
    k32, u32 = ctypes.windll.kernel32, ctypes.windll.user32
    k32.GlobalAlloc.restype = wintypes.HGLOBAL
    k32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    k32.GlobalLock.restype = wintypes.LPVOID
    k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    u32.SetClipboardData.restype = wintypes.HANDLE
    u32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    dados = texto.encode("utf-16-le") + b"\0\0"
    for _ in range(10):  # outro programa pode estar usando a área de transferência
        if u32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        raise OSError("área de transferência ocupada")
    try:
        u32.EmptyClipboard()
        h = k32.GlobalAlloc(0x0002, len(dados))  # GMEM_MOVEABLE
        ctypes.memmove(k32.GlobalLock(h), dados, len(dados))
        k32.GlobalUnlock(h)
        u32.SetClipboardData(13, h)  # CF_UNICODETEXT
    finally:
        u32.CloseClipboard()


# ---------------- Pedidos de mapas do osu! ----------------
ARQUIVO_PEDIDOS = os.path.join(PASTA, "pedidos.txt")
pedidos = []            # [{"uid", "nome", "texto", "url"}], na ordem em que chegaram
pedidos_abertos = True  # !fecharpedidos / !abrirpedidos


def link_do_pedido(texto: str) -> str:
    """Link do beatmap, se a pessoa mandou um link ou código; senão, a busca do osu! com o que ela escreveu.
    Código: só o número ou "s" + número = set (beatmapsets/123); "d" ou "b" + número = uma dificuldade
    específica (beatmaps/123), o "b" como nos links osu.ppy.sh/b/123 do site."""
    m = re.search(r"osu\.ppy\.sh/\S+", texto)
    if m:
        return "https://" + m.group(0)
    m = re.fullmatch(r"([dbs]?)\s*(\d+)", texto.strip(), re.IGNORECASE)
    if m:
        return f"https://osu.ppy.sh/{'b' if m.group(1).lower() in ('d', 'b') else 's'}/{m.group(2)}"
    # s=any: a busca do site, sem isso, só mostra mapas com placar (ranqueados, loved...)
    return "https://osu.ppy.sh/beatmapsets?q=" + urllib.parse.quote(texto) + "&s=any"


# Chat do osu! pelo IRC (irc.ppy.sh). Entra uma vez, no primeiro envio, e fica conectado até o programa
# fechar: entrar e sair a cada pedido são muitos logins seguidos na sua conta, e o osu! pode te deslogar.
irc = None              # a conexão aberta (None = desconectado)
irc_nick = ""           # com que nome ela entrou
irc_senha = ""          # e com que senha
irc_ultimo_envio = 0.0
trava_irc = threading.Lock()  # um envio de cada vez


def fechar_irc():
    global irc
    if irc is not None:
        try:
            irc.sendall(b"QUIT\r\n")
            irc.close()
        except OSError:
            pass
        irc = None


def conectar_irc(nick: str) -> str:
    """Entra no IRC do osu! (com a trava_irc já pega). Devolve "" se entrou, senão o motivo."""
    global irc, irc_nick, irc_senha
    import socket
    try:
        s = socket.create_connection(("irc.ppy.sh", 6667), timeout=10)
    except OSError as e:
        return f"não consegui conectar no chat do osu! ({e})"
    try:
        def enviar(linha):
            s.sendall((linha + "\r\n").encode("utf-8"))
        enviar(f"PASS {OSU_IRC_SENHA.strip()}")
        enviar(f"NICK {nick}")
        enviar(f"USER {nick} 0 * :{nick}")
        resto, fim = b"", time.time() + 15
        while time.time() < fim:
            dados = s.recv(4096)
            if not dados:
                s.close()
                return "o osu! fechou a conexão (nome ou senha de IRC errados?)"
            resto += dados
            *linhas, resto = resto.split(b"\r\n")
            for linha in linhas:
                partes = linha.decode("utf-8", "replace").split()
                if partes[:1] == ["PING"]:
                    enviar("PONG " + " ".join(partes[1:]))
                elif partes[1:2] == ["464"]:
                    s.close()
                    return "o osu! recusou a senha de IRC"
                elif partes[1:2] == ["001"]:  # entrou
                    s.settimeout(None)
                    irc, irc_nick, irc_senha = s, nick, OSU_IRC_SENHA.strip()
                    threading.Thread(target=ouvir_irc, args=(s,), daemon=True).start()
                    print("[conectado ao chat do osu!]")
                    return ""
        s.close()
        return "o osu! demorou demais para responder"
    except OSError as e:
        s.close()
        return f"não consegui conectar no chat do osu! ({e})"


def ouvir_irc(s):
    """Thread que responde aos PINGs do osu! (sem isso ele derruba a conexão) e percebe quando ela cai."""
    global irc
    resto = b""
    try:
        while True:
            dados = s.recv(4096)
            if not dados:
                break
            resto += dados
            *linhas, resto = resto.split(b"\r\n")
            for linha in linhas:
                if linha.startswith(b"PING"):
                    s.sendall(b"PONG" + linha[4:] + b"\r\n")
    except OSError:
        pass
    with trava_irc:
        if irc is not s:
            return  # fechada de propósito (fechar_irc)
        irc = None  # o próximo envio conecta de novo
    print("[a conexão com o chat do osu! caiu; volta sozinha no próximo pedido]")


def mandar_no_osu(texto: str) -> str:
    """Manda uma mensagem privada para você mesmo no chat do osu!. Devolve "" se deu certo, senão o motivo."""
    global irc_ultimo_envio
    nick = OSU_USUARIO.strip().replace(" ", "_")  # no IRC do osu! os espaços do nome viram _
    with trava_irc:
        if irc is not None and (irc_nick, irc_senha) != (nick, OSU_IRC_SENHA.strip()):
            # trocou o nome ou a senha na página: entra de novo com os novos
            fechar_irc()
        for _ in range(2):  # se a conexão tinha caído sem avisar, entra de novo e tenta mais uma vez
            if irc is None:
                erro = conectar_irc(nick)
                if erro:
                    return erro
            espera = irc_ultimo_envio + 1 - time.time()  # o osu! limita mensagens seguidas demais
            if espera > 0:
                time.sleep(espera)
            try:
                irc.sendall(f"PRIVMSG {nick} :{texto}\r\n".encode("utf-8"))
                irc_ultimo_envio = time.time()
                return ""
            except OSError:
                fechar_irc()
        return "não consegui mandar no chat do osu!"


def guardar_pedido(p: dict):
    """Fila desligada e o pedido não chegou ao osu!: guarda na fila para não se perder (sem o limite da
    fila nem o de um por pessoa, porque a pessoa já foi atendida). Sai com o !proximo."""
    pedidos.append(p)
    salvar_pedidos()
    if not pausado:
        falar(f"Pedido de {p['nome']} guardado na fila: não consegui mandar para o osu.")


def abrir_pedido(p: dict, navegador: bool = True):
    """Manda o pedido no seu chat do osu! (se configurado). Senão, ou se der erro: abre no navegador
    (!proximo) ou guarda na fila (fila desligada, para não abrir o navegador no meio do mapa)."""
    if OSU_USUARIO.strip() and OSU_IRC_SENHA.strip():
        # no chat do osu!, [link texto] vira o texto clicável. Colchetes no texto quebrariam o link.
        rotulo = p["texto"] if "beatmapsets?q=" in p["url"] else "abrir o mapa"  # link ou código: sem texto útil
        limpo = lambda t: re.sub(r"[\[\]\r\n]", "", t)
        erro = mandar_no_osu(f"Pedido de {limpo(p['nome'])}: [{p['url']} {limpo(rotulo)}]")
        if not erro:
            print("  (mandado no seu chat do osu!)")
            return
        if not navegador:
            print(f"*** {erro}. Guardei o pedido na fila: ele sai com o {PREFIXO}proximo.")
            guardar_pedido(p)
            return
        print(f"*** {erro}. Abrindo no navegador.")
    elif not navegador:
        print(f"  (guardei na fila: ele sai com o {PREFIXO}proximo. Para os pedidos irem direto para o osu!, "
              "preencha o nome e a senha de IRC na página de configurações)")
        guardar_pedido(p)
        return
    webbrowser.open(p["url"])


def salvar_pedidos():
    """Mantém o pedidos.txt atualizado, para você ver a fila durante a live."""
    try:
        with open(ARQUIVO_PEDIDOS, "w", encoding="utf-8") as f:
            for i, p in enumerate(pedidos, 1):
                f.write(f"{i}. {p['nome']} (@{p['uid']}): {p['texto']}\n   {p['url']}\n")
    except OSError:
        pass


# ---------------- osu! via tosu ----------------
osu = None              # últimos dados do tosu (None = tosu fechado)
JOGANDO = 2             # número do estado "play" no tosu
recorde = None          # melhor jogada da live: {"pp", "mapa", "mods"}
INICIO = datetime.now(timezone.utc)  # scores e mensagens de antes disto não contam (acertado em acertar_inicio)


def acertar_inicio():
    """Acerta o INICIO pela hora da internet: com o relógio do computador errado, todas as
    mensagens e scores pareceriam de antes (ou de depois) de o programa abrir."""
    global INICIO
    from email.utils import parsedate_to_datetime
    try:
        pedido = urllib.request.Request("https://www.tiktok.com", method="HEAD",
                                        headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(pedido, timeout=5) as r:
            internet = parsedate_to_datetime(r.headers["Date"])
    except Exception:
        return  # sem internet não tem TikTok nem voz mesmo; fica o relógio do computador
    diferenca = internet - datetime.now(timezone.utc)
    INICIO += diferenca
    if abs(diferenca) > timedelta(minutes=2):
        minutos = round(diferenca.total_seconds() / 60)
        print(f"[o relógio do computador está {abs(minutos)} minutos "
              f"{'atrasado' if minutos > 0 else 'adiantado'}: usando a hora da internet]")


def abrir_tosu():
    """Abre o tosu\\tosu.exe, se ele estiver na pasta e ainda não estiver aberto."""
    exe = os.path.join(PASTA, "tosu", "tosu.exe")
    if not os.path.exists(exe):
        print("[tosu não encontrado na pasta tosu: os comandos do osu! não vão responder]")
        return
    try:
        # em bytes: a resposta vem acentuada ("INFORMAÇÕES: ...") numa codificação que muda de PC para PC
        lista = subprocess.run(["tasklist", "/fi", "imagename eq tosu.exe", "/fo", "csv", "/nh"],
                               capture_output=True, timeout=10).stdout.decode("ascii", "ignore")
    except (OSError, subprocess.SubprocessError):
        lista = ""
    if "tosu.exe" in lista.lower():
        return  # já está aberto (por você ou por outra vez que o programa abriu)
    try:
        # janela própria: o Ctrl+C daqui não fecha o tosu, e o que ele escreve não se mistura com o chat
        subprocess.Popen([exe], cwd=os.path.dirname(exe), creationflags=subprocess.CREATE_NEW_CONSOLE)
        print("[tosu aberto]")
    except OSError as e:
        print(f"*** Não consegui abrir o tosu ({e}). Abra o tosu\\tosu.exe na mão.")


def numero(n, casas=0) -> str:
    """Formata no jeito brasileiro: 124519 -> 124.519, 6.55 -> 6,6."""
    return f"{n:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def descrever_mapa(d) -> str:
    b = d["beatmap"]
    texto = f"{b['artist']} - {b['title']}, dificuldade {b['version']}, " \
            f"{numero(b['stats']['stars']['total'], 1)} estrelas"
    mods = d["play"]["mods"]["name"] if d["state"]["number"] == JOGANDO else ""
    return texto + (f", com {separar_mods(mods)}" if mods else "")


def separar_mods(mods: str) -> str:
    """'HDDT' -> 'HD DT', para a voz soletrar cada mod."""
    return " ".join(mods[i:i + 2] for i in range(0, len(mods), 2))


def score_desta_live(criado) -> bool:
    """Se o score foi feito depois que o programa abriu (um score antigo do ranking também abre a
    tela de resultado). Data que não dá para ler conta como desta live, para o recorde não parar."""
    try:
        data = datetime.fromisoformat(str(criado).replace("Z", "+00:00"))
    except ValueError:
        return True
    if data.tzinfo is None:
        data = data.astimezone()  # sem fuso: hora do computador
    return data >= INICIO - timedelta(minutes=1)  # folga para o relógio do servidor do osu!


def vigia_osu():
    """Thread que lê o tosu a cada 2 segundos: avisa mapa novo e recorde de PP da live."""
    global osu, recorde
    ultimo_mapa = None
    jogado = None           # id do último mapa jogado, até o resultado dele ser contado
    ultimo_resultado = None
    while True:
        try:
            with urllib.request.urlopen(TOSU_URL, timeout=2) as r:
                osu = json.loads(r.read().decode("utf-8"))
            res = osu["resultsScreen"]
            if osu["state"]["number"] == JOGANDO:
                jogado = osu["beatmap"]["id"]
            # sem o id do mapa na chave: se você troca de mapa ainda na tela de resultado, o tosu
            # recalcula o PP do resultado antigo no mapa novo, e isso não pode virar recorde
            chave = (res["score"], res["createdAt"])
            # a tela de resultado só aparece quando você passa o mapa (fail não conta). Só vale a do
            # mapa que você acabou de jogar: trocou de mapa antes do PP aparecer, o PP já é do outro
            if "result" in osu["state"]["name"].lower() and res["score"] and chave != ultimo_resultado \
                    and osu["beatmap"]["id"] == jogado and score_desta_live(res["createdAt"]):
                pp = res["pp"]["current"]
                if pp > 0:
                    ultimo_resultado = chave  # só depois que o tosu calculou o PP
                    jogado = None
                if pp > 0 and (recorde is None or pp > recorde["pp"]):
                    recorde = {"pp": pp, "mapa": osu["beatmap"]["title"], "mods": res["mods"]["name"]}
                    com = f", com {separar_mods(recorde['mods'])}" if recorde["mods"] else ""
                    print(f"[recorde da live: {pp:.0f} PP em {recorde['mapa']}{com}]")
                    if AVISAR_RECORDE and not pausado:
                        falar(f"Novo recorde da live! {numero(pp)} PP em {recorde['mapa']}{com}.")
            if osu["state"]["number"] == JOGANDO and osu["beatmap"]["id"] != ultimo_mapa:
                ultimo_mapa = osu["beatmap"]["id"]
                print(f"[mapa: {descrever_mapa(osu)}]\n  https://osu.ppy.sh/b/{ultimo_mapa}")
                if AVISAR_MAPA and not pausado:
                    falar("Agora: " + descrever_mapa(osu) + ".")
        except Exception:
            osu = None
        time.sleep(2)


# ---------------- Comandos do chat ----------------
pausado = False         # !mudo / !voltar
ultimo_comando = {}     # unique_id -> horário do último comando (anti-spam)

COMANDOS_PUBLICOS = ["np", "pp", "rank", "recorde", "pedir", "pedidos", "cancelar", "mensagens", "top", "sons"]
# !copiar é só de mods: com ele, qualquer um trocaria o seu Ctrl+C por um texto malicioso sem você perceber
COMANDOS_MOD = ["mudo", "voltar", "limpar", "apelido", "copiar", "velocidade", "volume", "voz", "nomes", "bloquear",
                "desbloquear", "silenciar", "liberar", "ligar", "desligar", "avisos", "espera", "tamanho", "fila",
                "esperasom", "proximo", "remover", "fecharpedidos", "abrirpedidos", "zerarpedidos", "limitepedidos", "porpessoa", "filapedidos"]
COMANDOS_DONO = ["mod", "desmod"]  # só você: se um mod pudesse criar mods, qualquer um daria acesso a qualquer um
# atalhos: !vol 70 é o mesmo que !volume 70. Desligar um comando desliga os atalhos dele também.
APELIDOS_COMANDO = {
    "ajuda": "comandos", "cmd": "comandos", "mapa": "np", "rec": "recorde", "msg": "mensagens",
    "ap": "apelido",
    "vel": "velocidade", "vol": "volume", "bl": "bloquear", "dbl": "desbloquear",
    "próximo": "proximo", "prox": "proximo", "próx": "proximo",
    "fechar": "fecharpedidos", "abrir": "abrirpedidos", "zerar": "zerarpedidos", "limite": "limitepedidos",
}
TODOS_COMANDOS = ["comandos"] + COMANDOS_PUBLICOS + COMANDOS_MOD + COMANDOS_DONO
# o que cada comando faz (mostrado na página de configurações)
DESCRICAO_COMANDO = {
    "comandos": "Fala a lista de comandos ligados. Para você e os mods, fala os de moderação; !comandos chat fala os de todo mundo e !comandos todos fala tudo.",
    "np": "Fala o mapa que você está jogando: música, dificuldade, estrelas e mods.",
    "pp": "Fala quanto PP vale o SS do mapa atual com os mods selecionados, e também com 98% e 95%.",
    "rank": "Fala o seu rank global, o PP e a precisão.",
    "recorde": "Fala o maior PP que você fez nesta live e em qual mapa.",
    "pedir": "Pede um mapa: pelo link, pelo nome, pelo código do set (123456 ou s123456) ou da dificuldade (d1234567 ou b1234567). Pelo nome, a busca mostra mapas de qualquer status, ranqueados ou não.",
    "pedidos": "Fala quantos pedidos tem na fila e a posição de quem perguntou.",
    "cancelar": "Tira da fila o pedido de quem usou o comando. Serve para corrigir um pedido errado.",
    "mensagens": "Fala quantas mensagens a pessoa mandou nesta live.",
    "top": "Fala as 3 pessoas que mais mandaram mensagem na live.",
    "sons": "Fala a lista de sons. Cada som é um comando, como !ai; você cria os sons mais abaixo, em Sons.",
    "copiar": "Copia o texto para o seu Ctrl+C. Só você e os mods podem usar, para ninguém trocar o que você copiou.",
    "mudo": "Para de ler o chat e apaga o que estava esperando. Respostas e avisos também param, mas os pedidos de mapas continuam entrando na fila.",
    "voltar": "Volta a ler o chat depois do !mudo.",
    "limpar": "Apaga as mensagens que estavam esperando para serem lidas.",
    "apelido": "Dá um apelido para alguém (ex.: apelido fulano Aninha). A voz passa a chamar a pessoa assim.",
    "velocidade": "Muda a velocidade da voz, de -10 a 10.",
    "volume": "Muda o volume da voz, de 0 a 100.",
    "voz": "Troca a voz: francisca, thalita, antonio, raquel, duarte ou maria. Com sotaque de gringo: ava, emma, brian, william, "
           "vivienne, remy, seraphina, florian, giuseppe ou hyunsu. Sem nome, fala a lista.",
    "nomes": "Liga ou desliga o \"Fulano disse:\" antes das mensagens.",
    "bloquear": "Bloqueia uma palavra: mensagens com ela não são lidas em voz alta.",
    "desbloquear": "Desbloqueia uma palavra.",
    "silenciar": "A voz para de ler uma pessoa e os comandos dela são ignorados. Aceita o nome que aparece no chat ou o usuário. Não vale para você e os mods.",
    "liberar": "Tira alguém dos silenciados.",
    "ligar": "Religa um comando desligado (nome sem o símbolo).",
    "desligar": "Desliga um comando (nome sem o símbolo). O ligar e o desligar não podem ser desligados pelo chat.",
    "avisos": "Com mapa ou recorde, liga ou desliga esse aviso. Sozinho, fala como os avisos estão.",
    "espera": "Muda quantos segundos cada pessoa espera entre um comando e outro (anti-spam).",
    "esperasom": "Muda quantos segundos o chat espera entre um som e outro.",
    "tamanho": "Muda quantas letras de cada mensagem são lidas.",
    "fila": "Muda quantas mensagens podem ficar esperando a voz.",
    "proximo": "Manda o próximo pedido no seu chat do osu! (ou abre no navegador) e fala de quem é.",
    "remover": "Tira da fila o pedido daquela posição (ex.: remover 3), sem abrir o mapa.",
    "fecharpedidos": "Para de aceitar pedidos.",
    "abrirpedidos": "Volta a aceitar pedidos.",
    "zerarpedidos": "Apaga a fila de pedidos inteira.",
    "limitepedidos": "Muda o tamanho máximo da fila de pedidos.",
    "porpessoa": "Muda quantos pedidos cada pessoa pode ter na fila ao mesmo tempo (0 = sem limite). Não vale para você e os mods.",
    "filapedidos": "Liga ou desliga a fila. Desligada, cada pedido vai direto para o seu chat do osu!; se não conseguir mandar, ele fica guardado na fila.",
    "mod": "Torna alguém moderador (usuário do TikTok, sem @).",
    "desmod": "Tira alguém dos moderadores.",
}
PROTEGIDOS = ("ligar", "desligar")  # se desligar estes pelo chat, não daria para religar pelo chat


def desativado(cmd: str) -> bool:
    return APELIDOS_COMANDO.get(cmd, cmd) in [c.lstrip(PREFIXO).lower() for c in COMANDOS_DESATIVADOS]


FALADO = {"proximo": "próximo", "fecharpedidos": "fechar pedidos", "abrirpedidos": "abrir pedidos",
          "zerarpedidos": "zerar pedidos", "limitepedidos": "limite pedidos", "porpessoa": "por pessoa",
          "filapedidos": "fila pedidos", "esperasom": "espera som"}  # como a voz fala cada comando

# !voz francisca -> nome da voz no config
VOZES = {"francisca": "pt-BR-FranciscaNeural", "thalita": "pt-BR-ThalitaMultilingualNeural",
         "antonio": "pt-BR-AntonioNeural", "antônio": "pt-BR-AntonioNeural", "raquel": "pt-PT-RaquelNeural",
         "duarte": "pt-PT-DuarteNeural", "maria": "windows", "windows": "windows",
         # vozes de outros países: falam português com sotaque
         "ava": "en-US-AvaMultilingualNeural", "emma": "en-US-EmmaMultilingualNeural",
         "brian": "en-US-BrianMultilingualNeural", "william": "en-AU-WilliamMultilingualNeural",
         "vivienne": "fr-FR-VivienneMultilingualNeural", "remy": "fr-FR-RemyMultilingualNeural",
         "seraphina": "de-DE-SeraphinaMultilingualNeural", "florian": "de-DE-FlorianMultilingualNeural",
         "giuseppe": "it-IT-GiuseppeMultilingualNeural", "hyunsu": "ko-KR-HyunsuMultilingualNeural"}

# comandos que mudam um número: comando -> (opção do config, o que a voz responde)
NUMERICOS = {
    "velocidade": ("velocidade", "Velocidade {}."),
    "volume": ("volume", "Volume {}."),
    "espera": ("espera_comando", "Agora cada pessoa espera {} segundos entre um comando e outro."),
    "esperasom": ("espera_som", "Agora o chat espera {} segundos entre um som e outro."),
    "tamanho": ("tamanho_maximo", "Vou ler até {} letras de cada mensagem."),
    "fila": ("fila_maxima", "A fila de fala agora guarda até {} mensagens."),
    "limitepedidos": ("pedidos_maximos", "A fila de pedidos agora aceita até {}."),
    "porpessoa": ("pedidos_por_pessoa", "Agora cada pessoa pode ter até {} pedidos na fila."),
}


# ---------------- Sons: comandos que tocam um áudio (SONS no config.json) ----------------
EXTENSOES_SOM = (".mp3", ".wav")
TAMANHO_MAXIMO_SOM = 5 * 1024 * 1024  # arquivo que a página aceita (5 MB já é um áudio bem longo)
ultimo_som = 0.0  # horário do último som que o chat tocou (para o ESPERA_SOM)


def nome_de_som(texto: str) -> str:
    """'Ai Que Susto' -> 'aiquesusto': o nome vira comando, então fica minúsculo, sem espaços nem símbolos."""
    return re.sub(r"\W", "", texto.lower())


def nome_reservado(nome: str) -> bool:
    """Nome de um comando do programa: o comando ganha do som."""
    return nome in TODOS_COMANDOS or nome in APELIDOS_COMANDO


def conferir_sons(sons: dict) -> tuple:
    """Arruma os nomes dos comandos de som ("!Ai" -> "ai") e tira os que não dão. Cada som pode vir como
    "arquivo" ou {"arquivo": "...", "volume": 0 a 100}. Devolve (sons arrumados no segundo jeito, avisos)."""
    limpos, avisos = {}, []
    for comando, valor in sons.items():
        nome = nome_de_som(comando.lstrip(PREFIXO))
        arquivo, volume = valor, 100
        if isinstance(valor, dict):
            arquivo, volume = valor.get("arquivo", ""), valor.get("volume", 100)
            if not isinstance(volume, (int, float)) or isinstance(volume, bool):
                avisos.append(f"o volume do som \"{comando}\" deveria ser um número de 0 a 100. Usei 100.")
                volume = 100
            elif not 0 <= volume <= 100:
                avisos.append(f"o volume do som \"{comando}\" vai de 0 a 100. Usei {max(0, min(100, round(volume)))}.")
            volume = max(0, min(100, round(volume)))
        if not isinstance(arquivo, str):
            avisos.append(f"o som \"{comando}\" deveria ser \"arquivo\" ou "
                          f"{{\"arquivo\": \"...\", \"volume\": 100}}. Ignorei.")
        elif not nome or not arquivo.strip():
            avisos.append(f"o som \"{comando}\" precisa de um nome (letras ou números) e de um arquivo. Ignorei.")
        elif nome_reservado(nome):
            avisos.append(f"\"{comando}\" já é um comando do programa: dê outro nome para esse som. Ignorei.")
        elif nome in limpos:
            avisos.append(f"o som \"{comando}\" aparece duas vezes. Usei o primeiro.")
        else:
            limpos[nome] = {"arquivo": arquivo.strip(), "volume": volume}
    return limpos, avisos


def caminho_do_som(arquivo: str) -> str:
    """Só o nome do arquivo = está na pasta sons; senão, o caminho completo que a pessoa escreveu."""
    return arquivo if os.path.isabs(arquivo) else os.path.join(PASTA_SONS, arquivo)


def sons_configurados() -> tuple:
    """Devolve ({comando: {"caminho", "volume"}}, [avisos dos sons cujo arquivo não existe]).
    O arquivo é conferido a cada vez: se a pessoa colocar o arquivo durante a live, já vale."""
    sons, faltando = {}, []
    for nome, som in SONS.items():
        caminho = caminho_do_som(som["arquivo"])
        if os.path.isfile(caminho):
            sons[nome] = {"caminho": caminho, "volume": som["volume"]}
        else:
            faltando.append(f"{PREFIXO}{nome}: não achei o arquivo {som['arquivo']}")
    return sons, faltando


def sons_disponiveis() -> dict:
    return sons_configurados()[0]



def ajuda(lista, titulo: str) -> str:
    nomes = [FALADO.get(c, c) for c in lista if not desativado(c)]
    if not nomes:
        return "Nenhum comando ligado."
    texto = ", ".join(nomes[:-1]) + " e " + nomes[-1] if len(nomes) > 1 else nomes[0]
    return f"{titulo}: {texto}. Use com exclamação, por exemplo: exclamação {nomes[0]}."


def eh_moderador(uid: str, dono: str) -> bool:
    return uid == dono.lower() or uid in [m.lstrip("@").lower() for m in MODERADORES]


def silenciado(uid: str, dono: str) -> bool:
    return uid in lista_silenciados() and not eh_moderador(uid, dono)


def achar_pessoa(texto: str) -> tuple:
    """O usuário de quem o mod citou, pelo @ ou pelo nome que aparece no chat (o mod só vê o nome).
    Devolve (usuário em minúsculo ou "", visto nesta live ou nos apelidos, tem mais de uma pessoa com o nome)."""
    alvo = texto.strip().lstrip("@").lower()
    apelidos = carregar_apelidos()
    with trava:
        vistos = {uid.lower(): p["nome"] for uid, p in pessoas.items()}
    if alvo in vistos or alvo in apelidos:
        return alvo, True, False
    achados = {uid for uid, nome in vistos.items() if nome.lower() == alvo}
    achados |= {uid for uid, apelido in apelidos.items() if apelido.lower() == alvo}
    if len(achados) > 1:
        return "", False, True
    if achados:
        return achados.pop(), True, False
    return ("" if " " in alvo else alvo), False, False


def tratar_comando(user, nome: str, texto: str, dono: str) -> bool:
    """Executa um comando do chat. Retorna True se era um comando (e não deve ser lido)."""
    global pausado, pedidos_abertos, ultimo_som
    if not texto.startswith(PREFIXO):
        return False
    partes = texto[len(PREFIXO):].split(maxsplit=1)
    if not partes:
        return False
    cmd = partes[0].lower()
    arg = partes[1].strip() if len(partes) > 1 else ""
    uid = (user.unique_id or "").lower()
    if cmd in ("fechar", "abrir", "zerar", "limite") and arg.lower() == "pedidos" or \
            cmd == "limite" and arg.lower().startswith("pedidos "):
        cmd, arg = cmd + "pedidos", arg[len("pedidos"):].strip()  # aceita "!fechar pedidos" com espaço
    cmd = APELIDOS_COMANDO.get(cmd, cmd)
    if desativado(cmd):
        return True  # comando desligado em COMANDOS_DESATIVADOS: ignora calado
    eh_dono = uid == dono.lower()
    eh_mod = eh_moderador(uid, dono)

    # --- só você (o dono da live) ---
    if eh_dono and cmd in ("mod", "desmod"):
        alvo = arg.lstrip("@").lower()
        if not alvo or " " in alvo:
            falar(f"Use: exclamação {cmd} e o usuário do TikTok, sem arroba.")
            return True
        mods = [m for m in MODERADORES if m.lstrip("@").lower() != alvo]
        if cmd == "mod":
            mudar_config({"moderadores": mods + [alvo]})
            falar(f"{alvo} agora é moderador.")
        elif len(mods) == len(MODERADORES):
            falar(f"{alvo} não estava na lista de moderadores.")
        else:
            mudar_config({"moderadores": mods})
            falar(f"{alvo} não é mais moderador.")
        return True

    # --- moderação (só você e os MODERADORES) ---
    if eh_mod:
        if cmd == "mudo":
            pausado = True
            limpar_fila()
            print("[leitura pausada]")
            return True
        if cmd == "voltar":
            pausado = False
            falar("Voltei a ler o chat.")
            return True
        if cmd == "limpar":
            limpar_fila()
            print("[fila de fala limpa]")
            return True
        if cmd == "apelido":  # só mods: se o chat escolhesse o próprio apelido, a voz falaria qualquer coisa
            partes = arg.split(maxsplit=1)
            apelido = limpar(partes[1])[:30] if len(partes) > 1 else ""
            if not apelido:
                falar("Use: exclamação apelido, o usuário do TikTok sem arroba e o apelido.")
                return True
            alvo = partes[0].lstrip("@").lower()
            if tem_palavra_bloqueada(apelido):
                falar("Esse apelido não pode.")
                return True
            salvar_apelido(alvo, apelido)
            falar(f"Beleza, agora vou chamar {alvo} de {apelido}.")
            return True
        if cmd == "copiar":
            if not arg:
                falar("Escreve o que quer copiar depois do comando.")
                return True
            try:
                copiar_texto(arg)  # texto original, sem cortar links
                print(f"[copiado de {nome}: {arg}]")
                falar(f"Copiei a mensagem de {nome}.")
            except OSError as e:
                print(f"[não deu para copiar: {e}]")
            return True
        if cmd in ("silenciar", "liberar"):
            if not arg:
                falar(f"Use: exclamação {cmd} e o nome ou o usuário da pessoa.")
                return True
            alvo, visto, repetido = achar_pessoa(arg)
            if repetido:
                falar("Tem mais de uma pessoa com esse nome. Use o usuário do TikTok, sem arroba.")
                return True
            # a voz nunca repete quem é: o nome da pessoa pode ser justamente o problema
            outros = [u for u in USUARIOS_SILENCIADOS if u.strip().lstrip("@").lower() != alvo]
            if cmd == "liberar":
                if not alvo or len(outros) == len(USUARIOS_SILENCIADOS):
                    falar("Essa pessoa não estava silenciada.")
                    return True
                mudar_config({"usuarios_silenciados": outros})
                print(f"[liberado: @{alvo}]")
                falar("Pessoa liberada.")
                return True
            if not alvo:
                falar("Não achei essa pessoa nesta live. Use o usuário do TikTok, sem arroba.")
            elif eh_moderador(alvo, dono):
                falar("Você e os moderadores não podem ser silenciados.")
            else:
                mudar_config({"usuarios_silenciados": outros + [alvo]})
                print(f"[silenciado: @{alvo}]")
                falar("Pessoa silenciada." if visto else
                      "Não vi essa pessoa nesta live, mas silenciei esse usuário. Confira se está certo.")
            return True
        if cmd in NUMERICOS:
            chave, resposta = NUMERICOS[cmd]
            try:
                n = int(arg)
            except ValueError:
                falar(f"Use: exclamação {FALADO.get(cmd, cmd)} e um número.")
                return True
            mudar_config({chave: n})  # fora do limite, usa o limite mais próximo
            valor = globals()[OPCOES[chave]]
            if cmd == "porpessoa" and valor in (0, 1):
                resposta = "Agora cada pessoa pode pedir quantos mapas quiser." if valor == 0 else \
                    "Agora cada pessoa pode ter um pedido na fila."
            falar(resposta.format(valor))
            return True
        if cmd == "voz":
            voz = VOZES.get(arg.lower()) or next((v for v in VOZES.values() if v.lower() == arg.lower()), None)
            if not voz:
                falar("Vozes: Francisca, Thalita, Antonio, Raquel, Duarte e Maria, que funciona sem internet. "
                      "Com sotaque de gringo: Ava, Emma, Brian, William, Vivienne, Remy, Seraphina, Florian, "
                      "Giuseppe e Hyunsu. Use: exclamação voz e o nome.")
                return True
            mudar_config({"voz": voz})
            falar("Voz trocada.")
            return True
        if cmd == "nomes":
            mudar_config({"ler_nome": not LER_NOME})
            falar("Vou ler os nomes." if LER_NOME else "Não vou mais ler os nomes.")
            return True
        if cmd in ("bloquear", "desbloquear"):
            palavra = arg.lower()
            if not palavra:
                falar(f"Use: exclamação {cmd} e a palavra.")
                return True
            outras = [p for p in PALAVRAS_BLOQUEADAS if p.lower() != palavra]
            if cmd == "bloquear":
                mudar_config({"palavras_bloqueadas": outras + [palavra]})
                print(f"[palavra bloqueada: {arg}]")  # não fala a palavra, ela pode ser um palavrão
            elif len(outras) == len(PALAVRAS_BLOQUEADAS):
                falar("Essa palavra não estava bloqueada.")
            else:
                mudar_config({"palavras_bloqueadas": outras})
                print(f"[palavra desbloqueada: {arg}]")
                falar("Palavra desbloqueada.")
            return True
        if cmd in ("ligar", "desligar"):
            alvo = arg.lstrip(PREFIXO).lower()
            alvo = APELIDOS_COMANDO.get(alvo, alvo)
            if alvo not in TODOS_COMANDOS and alvo not in sons_disponiveis():
                falar(f"Use: exclamação {cmd} e o nome de um comando, sem a exclamação.")
                return True
            if alvo in PROTEGIDOS:
                falar(f"O {alvo} não pode ser desligado pelo chat.")
                return True
            outros = [c for c in COMANDOS_DESATIVADOS
                      if APELIDOS_COMANDO.get(c.lstrip(PREFIXO).lower(), c.lstrip(PREFIXO).lower()) != alvo]
            mudar_config({"comandos_desativados": outros + ([alvo] if cmd == "desligar" else [])})
            falado = FALADO.get(alvo, alvo)
            falar(f"Comando {falado} desligado." if cmd == "desligar" else f"Comando {falado} ligado.")
            return True
        if cmd == "avisos":
            qual = {"mapa": "avisar_mapa", "recorde": "avisar_recorde"}.get(arg.lower())
            if not qual:
                falar(f"Aviso de mapa {'ligado' if AVISAR_MAPA else 'desligado'}, aviso de recorde "
                      f"{'ligado' if AVISAR_RECORDE else 'desligado'}. "
                      "Use: exclamação avisos mapa, ou exclamação avisos recorde, para ligar ou desligar.")
                return True
            mudar_config({qual: not globals()[OPCOES[qual]]})
            ligado = globals()[OPCOES[qual]]
            falar(f"Aviso de {arg.lower()} {'ligado' if ligado else 'desligado'}.")
            return True
        if cmd == "proximo":
            if not pedidos:
                falar("Não tem nenhum pedido na fila.")
                return True
            p = pedidos.pop(0)
            salvar_pedidos()
            threading.Thread(target=abrir_pedido, args=(p,), daemon=True).start()  # o IRC leva uns segundos
            print(f"[pedido de {p['nome']}: {p['texto']}]\n  {p['url']}")
            falar(f"Próximo pedido, de {p['nome']}. Faltam {len(pedidos)}.")
            return True
        if cmd == "remover":
            try:
                p = pedidos.pop(int(arg) - 1) if int(arg) > 0 else None
            except (ValueError, IndexError):
                p = None
            if not p:
                falar(f"Use: exclamação remover e a posição na fila. Tem {len(pedidos)} na fila.")
                return True
            salvar_pedidos()
            print(f"[pedido removido, de {p['nome']}: {p['texto']}]")
            falar(f"Pedido de {p['nome']} removido. Faltam {len(pedidos)}.")
            return True
        if cmd in ("fecharpedidos", "abrirpedidos"):
            pedidos_abertos = cmd == "abrirpedidos"
            falar("Pedidos abertos!" if pedidos_abertos else "Pedidos fechados.")
            return True
        if cmd == "filapedidos":
            mudar_config({"fila_pedidos": not FILA_PEDIDOS})
            falar("Fila de pedidos ligada." if FILA_PEDIDOS else
                  "Fila de pedidos desligada: os pedidos vão direto para o chat do osu.")
            return True
        if cmd == "zerarpedidos":
            pedidos.clear()
            salvar_pedidos()
            falar("Fila de pedidos zerada.")
            return True

    if cmd in COMANDOS_MOD or cmd in COMANDOS_DONO:
        return True  # comando de moderação vindo de quem não pode: ignora calado

    # --- comandos de todo mundo ---
    sons = sons_disponiveis()
    if cmd != "comandos" and cmd not in COMANDOS_PUBLICOS and cmd not in sons:
        return False
    agora = time.time()
    if cmd in sons and not eh_mod and agora - ultimo_som < ESPERA_SOM:
        return True  # outro som tocou há pouco: ignora calado (e a pessoa não perde a vez dela)
    # cancelar o próprio pedido não espera nem conta como comando: quem errou o pedido corrige logo.
    # Não vira spam porque, para cancelar de novo, a pessoa precisa de outro !pedir, e esse espera.
    # com mais de um pedido, o cancelar tira o mais recente
    pedido_meu = next((i for i in reversed(range(len(pedidos))) if pedidos[i]["uid"] == uid), None) \
        if cmd == "cancelar" else None
    if pedido_meu is None:
        if not eh_mod and agora - ultimo_comando.get(uid, 0) < ESPERA_COMANDO:
            return True  # anti-spam: ignora calado
        ultimo_comando[uid] = agora
    # no mudo a voz fica calada, mas os pedidos não podem se perder
    if pausado and cmd not in ("pedir", "cancelar"):
        return True
    # no mudo, a resposta aparece só na janela
    dizer = (lambda frase: print(f"  (no mudo, não falei: {frase})")) if pausado else falar

    if cmd in sons:
        ultimo_som = agora
        print(f"[som {PREFIXO}{cmd}, de {nome}]")
        tocar_som(sons[cmd])
        return True
    if cmd == "comandos":
        # mods: "!comandos" = moderação, "!comandos chat" = os de todo mundo, "!comandos todos" = tudo
        qual = arg.lower() if eh_mod else ""
        moderacao = COMANDOS_MOD + (COMANDOS_DONO if eh_dono else [])
        if qual in ("todos", "tudo"):
            falar(ajuda(COMANDOS_PUBLICOS + moderacao, "Todos os comandos"))
        elif qual in ("chat", "publicos", "públicos"):
            falar(ajuda(COMANDOS_PUBLICOS, "Comandos de todo mundo"))
        elif eh_mod:
            falar(ajuda(moderacao, "Comandos de moderação") +
                  " Os de todo mundo: exclamação comandos chat. Todos: exclamação comandos todos.")
        else:
            falar(ajuda(COMANDOS_PUBLICOS, "Comandos"))
    elif cmd == "sons":
        nomes = [n for n in sons if not desativado(n)]
        if not nomes:
            falar("Ainda não tem nenhum som.")
        else:
            lista = ", ".join(nomes[:-1]) + " e " + nomes[-1] if len(nomes) > 1 else nomes[0]
            falar(f"Sons: {lista}. Use com exclamação, por exemplo: exclamação {nomes[0]}.")
    elif cmd == "mensagens":
        with trava:
            n = pessoas.get(user.unique_id, {}).get("mensagens", 0)
        falar(f"{nome}, você mandou {n} {'mensagem' if n == 1 else 'mensagens'} nesta live.")
    elif cmd == "top":
        with trava:
            top = sorted((kv for kv in pessoas.items() if not silenciado(kv[0].lower(), dono)),
                         key=lambda kv: -kv[1]["mensagens"])[:3]
        apelidos = carregar_apelidos()
        nomes = [f"{nome_para_falar(apelidos.get(u.lower(), p['nome']))}, com {p['mensagens']}"
                 for u, p in top if p["mensagens"]]
        falar("Quem mais falou: " + "; ".join(nomes) + "." if nomes else "Ninguém falou ainda.")
    elif cmd == "recorde":
        if recorde:
            com = f", com {separar_mods(recorde['mods'])}" if recorde["mods"] else ""
            falar(f"O recorde da live é {numero(recorde['pp'])} PP em {recorde['mapa']}{com}.")
        else:
            falar("Ainda não tem recorde nesta live.")
    elif cmd in ("np", "pp", "rank"):
        d = osu
        if not d:
            falar("Não consegui ver o osu agora.")
        elif cmd == "np":
            falar("Agora: " + descrever_mapa(d) + ".")
            print(f"  https://osu.ppy.sh/b/{d['beatmap']['id']}")
        elif cmd == "pp":
            pp = d["performance"]["accuracy"]  # o tosu já calcula com os mods selecionados
            mods = d["play"]["mods"]["name"]
            com = f"com {separar_mods(mods)}" if mods else "sem mods"
            falar(f"SS {com} vale {numero(pp['100'])} PP. "
                  f"Com 98 por cento, {numero(pp['98'])}, e com 95, {numero(pp['95'])}.")
        else:
            p = d["profile"]
            falar(f"{p['name']} está em número {numero(p['globalRank'])} no mundo, "
                  f"com {numero(p['pp'])} PP e {numero(p['accuracy'], 2)} por cento de precisão.")
    elif cmd == "pedir":
        meus = [i for i, p in enumerate(pedidos, 1) if p["uid"] == uid]  # posições dos pedidos da pessoa
        no_limite = PEDIDOS_POR_PESSOA and not eh_mod and len(meus) >= PEDIDOS_POR_PESSOA
        if not pedidos_abertos:
            dizer(f"{nome}, os pedidos estão fechados agora.")
        elif not arg:
            dizer(f"{nome}, manda o link, o nome ou o código do mapa depois do comando.")
        elif not FILA_PEDIDOS:  # sem fila: vai direto para o chat do osu!, sem a voz anunciar
            if tem_palavra_bloqueada(arg):
                dizer(f"{nome}, esse pedido não pode.")
                return True
            p = {"uid": uid, "nome": nome, "texto": arg, "url": link_do_pedido(arg)}
            print(f"[pedido de {nome}: {arg}]\n  {p['url']}")
            threading.Thread(target=abrir_pedido, args=(p, False), daemon=True).start()
        elif no_limite and len(meus) == 1:
            dizer(f"{nome}, você já tem um pedido na fila, na posição {meus[0]}.")
        elif no_limite:  # o limite pode ter baixado com a pessoa já tendo mais pedidos que ele
            dizer(f"{nome}, você já tem {len(meus)} pedidos na fila, e o máximo por pessoa é {PEDIDOS_POR_PESSOA}.")
        elif len(pedidos) >= PEDIDOS_MAXIMOS:
            dizer(f"{nome}, a fila de pedidos está cheia.")
        elif tem_palavra_bloqueada(arg):
            dizer(f"{nome}, esse pedido não pode.")
        else:
            pedidos.append({"uid": uid, "nome": nome, "texto": arg, "url": link_do_pedido(arg)})
            salvar_pedidos()
            print(f"[novo pedido de {nome}: {arg}]")
            dizer(f"Pedido de {nome} anotado, posição {len(pedidos)}.")
    elif cmd == "cancelar":
        if pedido_meu is None:
            dizer(f"{nome}, você não tem pedido na fila.")
        else:
            p = pedidos.pop(pedido_meu)
            salvar_pedidos()
            print(f"[pedido cancelado por {nome}: {p['texto']}]")
            falta = 0 if eh_mod else ESPERA_COMANDO - (agora - ultimo_comando.get(uid, 0))
            dizer(f"{nome}, pedido cancelado." +
                  (f" Pode pedir de novo em {int(falta) + 1} segundos." if falta > 0 else ""))
    elif cmd == "pedidos" and not FILA_PEDIDOS:
        n = len(pedidos)  # os que não conseguiram ir para o osu! e ficaram guardados
        falar("A fila de pedidos está desligada: os pedidos vão direto para o osu." +
              (f" Tem {n} {'guardado' if n == 1 else 'guardados'} na fila." if n else "") +
              ("" if pedidos_abertos else " Os pedidos estão fechados."))
    elif cmd == "pedidos":
        meus = [str(i) for i, p in enumerate(pedidos, 1) if p["uid"] == uid]
        n = len(pedidos)
        texto = "Não tem pedidos na fila." if n == 0 else \
            f"Tem {n} {'pedido' if n == 1 else 'pedidos'} na fila."
        if len(meus) == 1:
            texto += f" O seu é o número {meus[0]}."
        elif meus:
            texto += f" Os seus são os números {', '.join(meus[:-1])} e {meus[-1]}."
        if not pedidos_abertos:
            texto += " Os pedidos estão fechados."
        falar(texto)
    return True


# ---------------- Página de configurações ----------------
class PaginaConfig(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # não enche a janela com cada acesso à página

    def host_ok(self) -> bool:
        """Só aceita quem acessa pelo IP ou por localhost: impede que um site qualquer aberto
        no navegador se passe pela página e mude as configurações."""
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
        if host == "localhost":
            return True
        try:
            ipaddress.ip_address(host)
            return True
        except ValueError:
            return False

    def responder(self, codigo: int, tipo: str, corpo: bytes):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def responder_json(self, dados, codigo=200):
        self.responder(codigo, "application/json; charset=utf-8",
                       json.dumps(dados, ensure_ascii=False).encode("utf-8"))

    def dados_da_pagina(self) -> dict:
        config = {k: v for k, v in config_atual().items() if k not in SECRETAS}
        atalhos = {}
        for atalho, cmd in APELIDOS_COMANDO.items():
            atalhos.setdefault(cmd, []).append(atalho)

        def grupo(titulo, cmds):
            return {"titulo": titulo, "comandos": [{"cmd": c, "descricao": DESCRICAO_COMANDO.get(c, ""),
                                                    "atalhos": atalhos.get(c, [])} for c in cmds]}
        sons, faltando = sons_configurados()
        grupos = [grupo("Todo mundo", ["comandos"] + COMANDOS_PUBLICOS),
                  grupo("Você e os moderadores", COMANDOS_MOD),
                  grupo("Só você", COMANDOS_DONO)]
        if sons:
            grupos.append({"titulo": "Sons (todo mundo)", "comandos": [
                {"cmd": n, "descricao": f"Toca {SONS[n]['arquivo']}.", "atalhos": []} for n in sons]})
        return {"config": config, "comandos": TODOS_COMANDOS, "apelidos": APELIDOS_COMANDO, "grupos": grupos,
                "sons": [{"nome": n, "arquivo": s["arquivo"], "volume": s["volume"], "existe": n in sons}
                         for n, s in SONS.items()],
                "sons_faltando": faltando, "senha_salva": bool(OSU_IRC_SENHA.strip())}

    def mexer_nos_sons(self, d: dict):
        """Página: tocar, apagar, adicionar ou mudar o volume de um som. Devolve (resposta, código)."""
        acao = d.get("acao")
        nome = nome_de_som(str(d.get("nome", "")))
        if acao in ("tocar", "apagar", "volume") and nome not in SONS:
            return {"erro": "Não achei esse som. Clique em Recarregar."}, 404
        if acao == "tocar":
            som = sons_disponiveis().get(nome)
            if not som:
                return {"erro": f"Não achei o arquivo {SONS[nome]['arquivo']} na pasta sons."}, 404
            tocar_som(som)
            return {"mensagem": f"Tocando {PREFIXO}{nome}."}, 200
        if acao == "volume":
            volume = d.get("volume")
            if not isinstance(volume, int) or isinstance(volume, bool) or not 0 <= volume <= 100:
                return {"erro": "O volume vai de 0 a 100."}, 400
            mudar_config({"sons": {**SONS, nome: {**SONS[nome], "volume": volume}}})
            print(f"[volume do som {PREFIXO}{nome}: {volume}, pela página]")
            return {"mensagem": f"Volume do {PREFIXO}{nome}: {volume}.", **self.dados_da_pagina()}, 200
        if acao == "apagar":
            arquivo = SONS[nome]["arquivo"]
            mudar_config({"sons": {n: s for n, s in SONS.items() if n != nome}})
            print(f"[som {PREFIXO}{nome} apagado pela página]")
            mensagem = f"Som {PREFIXO}{nome} apagado."
            # o arquivo só vai embora se for da pasta sons e nenhum outro som usar
            if not os.path.isabs(arquivo) and arquivo not in (s["arquivo"] for s in SONS.values()):
                try:
                    os.remove(caminho_do_som(arquivo))
                except FileNotFoundError:
                    pass
                except OSError:
                    mensagem += f" O arquivo {arquivo} ficou na pasta sons (talvez estivesse tocando)."
            return {"mensagem": mensagem, **self.dados_da_pagina()}, 200
        if acao != "adicionar":
            return {"erro": "dados inválidos"}, 400
        ext = str(d.get("extensao", "")).lower()
        if not nome:
            return {"erro": "Dê um nome ao som, com letras ou números."}, 400
        if len(nome) > 20:
            return {"erro": "Nome comprido demais: use até 20 letras."}, 400
        if nome_reservado(nome):
            return {"erro": f"{PREFIXO}{nome} já é um comando do programa. Escolha outro nome."}, 400
        if nome in SONS:
            return {"erro": f"Já tem um som {PREFIXO}{nome}. Apague o antigo antes, ou use outro nome."}, 400
        if ext not in EXTENSOES_SOM:
            return {"erro": "Use um arquivo .mp3 ou .wav."}, 400
        try:
            conteudo = base64.b64decode(str(d.get("arquivo", "")), validate=True)
        except ValueError:
            return {"erro": "O arquivo chegou estragado. Tente de novo."}, 400
        if not conteudo:
            return {"erro": "O arquivo está vazio."}, 400
        if len(conteudo) > TAMANHO_MAXIMO_SOM:
            return {"erro": "Arquivo grande demais: o limite é 5 MB."}, 400
        arquivo = nome + ext
        numero = 2
        while os.path.exists(caminho_do_som(arquivo)):  # não estraga um arquivo que já estava na pasta
            arquivo = f"{nome}_{numero}{ext}"
            numero += 1
        try:
            os.makedirs(PASTA_SONS, exist_ok=True)
            with open(caminho_do_som(arquivo), "xb") as saida:
                saida.write(conteudo)
        except OSError as e:
            return {"erro": f"Não consegui gravar o arquivo ({e})."}, 500
        mudar_config({"sons": {**SONS, nome: {"arquivo": arquivo, "volume": 100}}})
        print(f"[som {PREFIXO}{nome} criado pela página]")
        return {"mensagem": f"Pronto: {PREFIXO}{nome} já funciona no chat.", **self.dados_da_pagina()}, 200

    def do_GET(self):
        caminho = urllib.parse.urlsplit(self.path).path.rstrip("/") or "/"
        # a fila só mostra o que já aparece na live, então aceita qualquer nome (o LIVE Studio
        # recusa "localhost" e precisa de um como localtest.me, que aponta para este computador)
        if not self.host_ok() and caminho not in ("/pedidos", "/api/pedidos"):
            return self.responder(403, "text/plain; charset=utf-8", b"acesso negado")
        if caminho == "/":
            self.responder(200, "text/html; charset=utf-8", PAGINA.encode("utf-8"))
        elif caminho == "/api/config":
            self.responder_json(self.dados_da_pagina())
        elif caminho == "/pedidos":
            self.responder(200, "text/html; charset=utf-8", PAGINA_PEDIDOS.encode("utf-8"))
        elif caminho == "/api/pedidos":
            # só o que aparece na tela: nome e pedido (o @ e o link ficam de fora)
            self.responder_json({"pedidos": [{"nome": x["nome"], "texto": x["texto"]} for x in list(pedidos)],
                                 "abertos": pedidos_abertos, "fila": FILA_PEDIDOS, "prefixo": PREFIXO})
        else:
            self.responder(404, "text/plain; charset=utf-8", b"nada aqui")

    def do_POST(self):
        # exigir JSON faz o navegador barrar envios vindos de outros sites
        if not self.host_ok() or self.path not in ("/api/config", "/api/sons") or \
                not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return self.responder(403, "text/plain; charset=utf-8", b"acesso negado")
        try:
            tamanho = int(self.headers.get("Content-Length", 0))
            if tamanho > TAMANHO_MAXIMO_SOM * 2:  # o arquivo vem em base64, que ocupa 4/3 do tamanho
                return self.responder_json({"erro": "Arquivo grande demais: o limite é 5 MB."}, 413)
            dados = json.loads(self.rfile.read(tamanho).decode("utf-8"))
            if not isinstance(dados, dict):
                raise ValueError
        except (ValueError, UnicodeDecodeError):
            return self.responder_json({"erro": "dados inválidos"}, 400)
        if self.path == "/api/sons":
            return self.responder_json(*self.mexer_nos_sons(dados))
        # senha em branco = continua a que já está salva (a página nunca recebe a senha para mandar de volta)
        dados = {k: v for k, v in dados.items()
                 if k.lower() not in SECRETAS or (isinstance(v, str) and v.strip())}
        print("[configurações alteradas pela página]")
        avisos = mudar_config(dados)
        self.responder_json({"avisos": avisos, **self.dados_da_pagina()})


PAGINA_PEDIDOS = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fila de pedidos</title>
<style>
/* fundo transparente (fonte de link do LIVE Studio, fonte de navegador do OBS); a caixa escura
   deixa o texto legível em cima do jogo */
html, body { margin: 0; background: transparent; }
body { font: 700 26px/1.3 system-ui, "Segoe UI", sans-serif; color: #fff; overflow: hidden; padding: 8px; }
#painel { display: inline-block; min-width: 14em; max-width: calc(100vw - 16px); box-sizing: border-box;
  padding: 12px 18px 14px; text-shadow: 1px 1px 2px #000; background: rgba(0, 0, 0, .85); border-radius: 14px; }
h1 { font-size: 1.1em; margin: 0 0 6px; color: #fff; }
h1 small { font-size: .65em; color: #fff; font-weight: 600; }
ol { margin: 0; padding: 0; list-style: none; }
li { display: flex; gap: .45em; align-items: baseline; padding: 3px 0; }
.pos { color: #fff; min-width: 1.6em; font-variant-numeric: tabular-nums; }
.mapa { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 22em; }
.quem { font-size: .7em; color: #fff; font-weight: 600; white-space: nowrap; }
.vazio, .mais { font-size: .75em; color: #fff; font-weight: 600; }
ol:not(:empty) + #extra { margin-top: 6px; }  /* separa o "Peça com !pedir" da lista */
</style>
</head>
<body>
<div id="painel">
<h1>Pedidos <small id="estado"></small></h1>
<ol id="lista"></ol>
<div id="extra"></div>
</div>
<script>
const params = new URLSearchParams(location.search);
const MAX = Math.max(1, parseInt(params.get("max")) || 5);
const $ = id => document.getElementById(id);

function el(tag, classe, texto) {
  const e = document.createElement(tag);
  e.className = classe; e.textContent = texto;
  return e;
}

async function atualizar() {
  let d;
  try {
    d = await (await fetch("/api/pedidos", {cache: "no-store"})).json();
  } catch (e) {
    return;  // programa fechado: mantém o que estava na tela e tenta de novo
  }
  const n = d.pedidos.length;
  $("estado").textContent = !d.fila ? (n ? `(${n} ${n === 1 ? "guardado" : "guardados"})` : "(direto no osu!)") :
    !d.abertos ? "(fechados)" : n ? `(${n})` : "";
  $("lista").replaceChildren(...d.pedidos.slice(0, MAX).map((p, i) => {
    const li = document.createElement("li");
    const mapa = /^d?\\s*\\d+$/i.test(p.texto.trim()) ? "#" + p.texto.trim() : p.texto;
    li.append(el("span", "pos", (i + 1) + "."), el("span", "mapa", mapa), el("span", "quem", p.nome));
    return li;
  }));
  // como pedir fica sempre à vista enquanto os pedidos estão abertos, com ou sem gente na fila
  $("extra").replaceChildren(...[
    n > MAX ? el("div", "mais", `+ ${n - MAX} na fila`) : null,
    d.abertos ? el("div", "vazio", `Peça com ${d.prefixo}pedir <link, nome ou código>`) : null,
  ].filter(Boolean));
}

atualizar();
setInterval(atualizar, 2000);
</script>
</body>
</html>
"""


def ip_local() -> str:
    """IP deste PC na rede local (o que o celular usa para abrir a página)."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("8.8.8.8", 80))  # não envia nada, só descobre por qual placa de rede sairia
            return s.getsockname()[0]
        except OSError:
            return "IP-deste-PC"


pagina_iniciada = False


def iniciar_pagina():
    global pagina_iniciada
    if not WEB_PORTA or pagina_iniciada:
        return
    pagina_iniciada = True
    endereco = "0.0.0.0" if WEB_REDE_LOCAL else "127.0.0.1"
    try:
        servidor = http.server.ThreadingHTTPServer((endereco, WEB_PORTA), PaginaConfig)
    except OSError:
        print(f"*** Não consegui abrir a página de configurações na porta {WEB_PORTA} (outro programa usando?).\n"
              f"*** Troque \"web_porta\" no config.json para outro número, por exemplo 8766.\n")
        return
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    print(f"Página de configurações: http://localhost:{WEB_PORTA}")
    print(f"Fila de pedidos (fonte de link no LIVE Studio): http://localtest.me:{WEB_PORTA}/pedidos")
    if ABRIR_PAGINA:
        webbrowser.open(f"http://localhost:{WEB_PORTA}")
    if WEB_REDE_LOCAL:
        print(f"  no celular ou outro PC da mesma rede: http://{ip_local()}:{WEB_PORTA}")
    print()


PAGINA = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Leitor de Chat</title>
<style>
:root { color-scheme: light dark; --fundo: #f3f3f6; --cartao: #fff; --texto: #1d1d22; --suave: #666a75;
        --borda: #d9dbe1; --destaque: #e0245e; --erro: #c62828; }
@media (prefers-color-scheme: dark) {
  :root { --fundo: #16161a; --cartao: #212127; --texto: #ececf1; --suave: #9a9ca8; --borda: #36363e; --erro: #ef6c6c; }
}
* { box-sizing: border-box; }
body { margin: 0; font: 15px/1.45 system-ui, "Segoe UI", sans-serif; background: var(--fundo); color: var(--texto); }
main { max-width: 720px; margin: 0 auto; padding: 16px 16px 110px; }
h1 { font-size: 22px; margin: 8px 0 4px; }
.sub { color: var(--suave); margin: 0 0 16px; }
section { background: var(--cartao); border: 1px solid var(--borda); border-radius: 10px; padding: 14px 16px; margin-bottom: 14px; }
h2 { font-size: 16px; margin: 0 0 4px; }
label { display: block; margin: 12px 0 4px; font-weight: 600; }
small { display: block; color: var(--suave); font-weight: 400; }
input[type=text], input[type=password], input[type=number], select, textarea { width: 100%; padding: 8px; border: 1px solid var(--borda);
  border-radius: 6px; background: var(--fundo); color: inherit; font: inherit; }
textarea { min-height: 72px; resize: vertical; }
label.check { display: flex; gap: 8px; align-items: flex-start; }
.passos { border: 1px solid var(--borda); border-radius: 8px; padding: 10px 14px; margin: 6px 0 10px; }
.passos ol { margin: 6px 0; padding-left: 22px; }
.passos li { margin: 6px 0; }
.passos li small { display: block; margin-top: 4px; }
label.check input { margin-top: 4px; }
.faixa { display: flex; gap: 10px; align-items: center; }
.faixa input { flex: 1; }
.faixa output { min-width: 3ch; text-align: right; font-variant-numeric: tabular-nums; }
.cmds h3 { font-size: 14px; margin: 14px 0 2px; color: var(--suave); text-transform: uppercase; letter-spacing: .04em; }
.cmds label { font-weight: 400; margin: 0; display: flex; gap: 8px; align-items: flex-start; padding: 6px 0;
  border-top: 1px solid var(--borda); }
.cmds label input { margin-top: 4px; }
.cmds code { font-weight: 700; font-size: 15px; }
.cmds .atalhos { color: var(--suave); font-size: 13px; }
.som { display: flex; gap: 8px; align-items: center; padding: 6px 0; border-top: 1px solid var(--borda); }
.som span { flex: 1; min-width: 0; overflow-wrap: anywhere; }
.som button { padding: 5px 12px; }
.som .vol { display: flex; gap: 6px; align-items: center; flex: 0 1 170px; min-width: 110px; margin: 0; font-weight: 400; }
.som .vol input { flex: 1; min-width: 0; }
.som .vol output { min-width: 3ch; text-align: right; font-variant-numeric: tabular-nums; font-size: 13px; }
@media (max-width: 520px) { .som { flex-wrap: wrap; } .som span { flex-basis: 100%; } .som .vol { flex: 1 1 auto; } }
.novo { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.novo input[type=text] { flex: 1 1 140px; width: auto; }
.novo input[type=file] { flex: 1 1 200px; min-width: 0; }
.barra { position: fixed; left: 0; right: 0; bottom: 0; background: var(--cartao); border-top: 1px solid var(--borda);
  padding: 12px 16px; display: flex; gap: 10px; align-items: center; justify-content: center; flex-wrap: wrap; }
button { font: inherit; padding: 9px 18px; border-radius: 6px; border: 1px solid var(--borda); background: var(--fundo);
  color: inherit; cursor: pointer; }
button.principal { background: var(--destaque); border-color: var(--destaque); color: #fff; font-weight: 600; }
#status { color: var(--suave); flex: 1 1 260px; max-width: 420px; }
#status.erro { color: var(--erro); }
</style>
</head>
<body>
<main>
  <h1>Leitor de Chat</h1>
  <p class="sub">Ao salvar, as mudanças já valem na live e ficam gravadas no config.json.</p>

  <section>
    <h2>Link da fila de pedidos</h2>
    <div class="passos">
      <b>Para mostrar a fila na live, só uma vez:</b>
      <ol>
        <li>Clique em <b>Copiar o link da fila</b>: <button type="button" id="copiar_link">Copiar o link da fila</button>
          <small><code id="link_studio"></code> · <a href="/pedidos" target="_blank">ver a fila agora</a></small></li>
        <li>No TikTok LIVE Studio, adicione uma fonte de <b>link</b> (página da web) e cole com <b>Ctrl+V</b>.</li>
        <li>Arraste e ajuste o tamanho da fila na tela. Pronto: nas próximas lives ela aparece sozinha.</li>
      </ol>
      <small>Não precisa abrir nada: a fila aparece no LIVE Studio enquanto o programa estiver aberto.
        No OBS: fonte de navegador com <code id="link_pedidos"></code>. <code>?max=3</code> no fim mostra só os 3 primeiros.</small>
    </div>
  </section>

  <section>
    <h2>Live</h2>
    <label for="tiktok_usuario">Seu usuário do TikTok<small>Sem o @. Se o programa estiver pedindo o usuário, entra na hora; senão, vale quando ele abre de novo.</small></label>
    <input type="text" id="tiktok_usuario" autocomplete="off" spellcheck="false">
  </section>

  <section>
    <h2>Voz</h2>
    <label for="voz">Voz<small>Quem lê o chat. As neurais precisam de internet e soam mais naturais. No chat: !voz antonio.</small></label>
    <select id="voz">
      <option value="pt-BR-FranciscaNeural">Francisca (feminina)</option>
      <option value="pt-BR-ThalitaMultilingualNeural">Thalita (feminina)</option>
      <option value="pt-BR-AntonioNeural">Antonio (masculina)</option>
      <option value="pt-PT-RaquelNeural">Raquel (feminina, Portugal)</option>
      <option value="pt-PT-DuarteNeural">Duarte (masculina, Portugal)</option>
      <option value="windows">Maria do Windows (funciona sem internet)</option>
      <option value="en-US-AvaMultilingualNeural">Ava (feminina, EUA, sotaque de gringo)</option>
      <option value="en-US-EmmaMultilingualNeural">Emma (feminina, EUA, sotaque de gringo)</option>
      <option value="en-US-BrianMultilingualNeural">Brian (masculina, EUA, sotaque de gringo)</option>
      <option value="en-AU-WilliamMultilingualNeural">William (masculina, Austrália, sotaque de gringo)</option>
      <option value="fr-FR-VivienneMultilingualNeural">Vivienne (feminina, França, sotaque de gringo)</option>
      <option value="fr-FR-RemyMultilingualNeural">Remy (masculina, França, sotaque de gringo)</option>
      <option value="de-DE-SeraphinaMultilingualNeural">Seraphina (feminina, Alemanha, sotaque de gringo)</option>
      <option value="de-DE-FlorianMultilingualNeural">Florian (masculina, Alemanha, sotaque de gringo)</option>
      <option value="it-IT-GiuseppeMultilingualNeural">Giuseppe (masculina, Itália, sotaque de gringo)</option>
      <option value="ko-KR-HyunsuMultilingualNeural">Hyunsu (masculina, Coreia, sotaque de gringo)</option>
    </select>
    <label for="velocidade">Velocidade<small>De -10 (bem lenta) a 10 (bem rápida). No chat: !velocidade 5 ou !vel 5.</small></label>
    <div class="faixa"><input type="range" id="velocidade" min="-10" max="10" step="1"><output for="velocidade"></output></div>
    <label for="volume">Volume<small>Volume da voz, de 0 a 100. No chat: !volume 70 ou !vol 70.</small></label>
    <div class="faixa"><input type="range" id="volume" min="0" max="100" step="1"><output for="volume"></output></div>
  </section>

  <section>
    <h2>Leitura do chat</h2>
    <label class="check"><input type="checkbox" id="ler_nome"><span>Falar o nome antes da mensagem<small>Ligado: "Fulano disse: mensagem". Desligado: só a mensagem. No chat: !nomes.</small></span></label>
    <label for="tamanho_maximo">Tamanho máximo da mensagem<small>Quantas letras de cada mensagem são lidas; o resto é cortado. No chat: !tamanho 150.</small></label>
    <input type="number" id="tamanho_maximo" min="1">
    <label for="fila_maxima">Tamanho da fila de fala<small>Quantas mensagens podem esperar a voz. Se o chat passar disso, as mais antigas são puladas para a voz não ficar atrasada. No chat: !fila 10.</small></label>
    <input type="number" id="fila_maxima" min="1">
    <label for="palavras_bloqueadas">Palavras bloqueadas<small>Uma por linha. Mensagens com elas não são lidas em voz alta, e pedidos com elas são recusados. No chat: !bloquear palavra.</small></label>
    <textarea id="palavras_bloqueadas"></textarea>
    <label for="usuarios_silenciados">Pessoas silenciadas<small>Usuários do TikTok, sem @, um por linha. A voz não lê essas pessoas e os comandos delas são ignorados. Não vale para você e os mods. No chat: !silenciar nome e !liberar nome.</small></label>
    <textarea id="usuarios_silenciados"></textarea>
  </section>

  <section>
    <h2>Comandos</h2>
    <label for="prefixo">Prefixo<small>O símbolo que marca um comando no começo da mensagem (o "!" de !pedir). Só muda por aqui ou pelo config.json.</small></label>
    <input type="text" id="prefixo" maxlength="5">
    <label for="moderadores">Moderadores<small>Usuários do TikTok, sem @, um por linha. Podem usar os comandos de moderação e não têm a espera entre comandos. No chat (só você): !mod usuario.</small></label>
    <textarea id="moderadores"></textarea>
    <label for="espera_comando">Espera entre comandos (segundos)<small>Anti-spam: quanto cada pessoa espera entre um comando e outro. Comandos a mais são ignorados. Não vale para você e os mods. No chat: !espera 10.</small></label>
    <input type="number" id="espera_comando" min="0">
    <label>Comandos ligados<small>Desmarque para desligar um comando (e os atalhos dele). Desligado, ele é
      ignorado em silêncio e sai do !comandos.</small></label>
    <div class="cmds" id="cmds"></div>
  </section>

  <section>
    <h2>Sons</h2>
    <p class="sub" style="margin:4px 0 0">Cada som vira um comando que todo mundo pode usar: o som <b>ai</b> toca com
      <code>!ai</code>. O <code>!sons</code> fala a lista. No mudo, os sons não tocam. A barrinha de cada som é o volume dele
      (100 = igual ao volume da voz): muda na hora e fica no config.json.</p>
    <div id="lista_sons"></div>
    <small id="sons_faltando" style="color:var(--erro)"></small>
    <label for="som_nome">Novo som<small>O nome do comando (só letras e números) e um arquivo .mp3 ou .wav de até 5 MB.
      O arquivo vai para a pasta <b>sons</b>, ao lado do programa, e o som fica no config.json, em "sons".</small></label>
    <div class="novo">
      <input type="text" id="som_nome" placeholder="ex.: ai" maxlength="20" autocomplete="off" spellcheck="false">
      <input type="file" id="som_arquivo" accept=".mp3,.wav,audio/mpeg,audio/wav">
      <button type="button" id="som_adicionar">Adicionar</button>
    </div>
    <label for="espera_som">Espera entre sons (segundos)<small>Depois de um som, o chat espera isso para tocar outro; os que chegarem antes são ignorados. Não vale para você e os mods. No chat: !esperasom 5.</small></label>
    <input type="number" id="espera_som" min="0">
  </section>

  <section>
    <h2>Pedidos de mapas</h2>
    <label for="pedidos_maximos">Tamanho máximo da fila de pedidos<small>Com a fila cheia, novos pedidos são recusados. No chat: !limitepedidos 20.</small></label>
    <input type="number" id="pedidos_maximos" min="1">
    <label for="pedidos_por_pessoa">Pedidos por pessoa<small>Quantos pedidos cada pessoa pode ter na fila ao mesmo tempo. 0 = sem limite. Não vale para você e os mods. No chat: !porpessoa 2.</small></label>
    <input type="number" id="pedidos_por_pessoa" min="0">
    <label class="check"><input type="checkbox" id="fila_pedidos"><span>Usar fila de pedidos<small>Desligado: cada pedido vai direto
      para o seu chat do osu! (precisa do nome e da senha de IRC) e a voz não anuncia. No chat: !filapedidos.</small></span></label>
  </section>

  <section>
    <h2>osu!</h2>
    <label class="check"><input type="checkbox" id="avisar_mapa"><span>Avisar mapa novo<small>Fala "Agora: Artista - Música" quando você começa um mapa. No chat: !avisos mapa.</small></span></label>
    <label class="check"><input type="checkbox" id="avisar_recorde"><span>Avisar recorde de PP da live<small>Fala quando você bate o maior PP desta live. No chat: !avisos recorde.</small></span></label>
    <label for="tosu_url">Endereço do tosu<small>De onde o programa lê os dados do osu! (!np, !pp, !rank, avisos). Só mude se tiver mudado no tosu.</small></label>
    <input type="text" id="tosu_url">
    <label for="osu_usuario">Seu nome no osu!<small>Com ele e a senha de IRC, o !proximo manda o pedido no seu chat do osu!.
</small></label>
    <input type="text" id="osu_usuario" autocomplete="off">
    <label for="osu_irc_senha">Senha de IRC do osu!<small>Não é a senha da conta: é a de osu.ppy.sh &gt; Configurações &gt;
      Legacy API. Por segurança a página nunca mostra a senha salva; deixe em branco para manter a atual.</small></label>
    <input type="password" id="osu_irc_senha" autocomplete="new-password" spellcheck="false">
    <small id="senha_estado"></small>
  </section>

  <section>
    <h2>Esta página</h2>
    <p class="sub" style="margin:4px 0 0">Estas valem quando o programa abre de novo.</p>
    <label class="check"><input type="checkbox" id="abrir_pagina"><span>Abrir esta página sozinha<small>Abre no navegador quando o programa começa.</small></span></label>
    <label for="web_porta">Porta<small>0 desliga a página.</small></label>
    <input type="number" id="web_porta" min="0" max="65535">
    <label class="check"><input type="checkbox" id="web_rede_local"><span>Abrir na rede local<small>Para mexer pelo celular. Qualquer pessoa no mesmo Wi-Fi também vai conseguir.</small></span></label>
  </section>
</main>

<div class="barra">
  <span id="status" role="status"></span>
  <button type="button" id="recarregar">Recarregar</button>
  <button type="button" class="principal" id="salvar">Salvar</button>
</div>

<script>
const $ = id => document.getElementById(id);
const LISTAS = ["palavras_bloqueadas", "usuarios_silenciados", "moderadores"];
let comandos = [], apelidos = {}, chaves = [];
let base = {};  // como a página estava quando recebeu os dados: o que difere disto é o que a pessoa mudou

function status(texto, erro) {
  $("status").textContent = texto;
  $("status").className = erro ? "erro" : "";
}

function el(tag, classe, texto) {
  const e = document.createElement(tag);
  if (classe) e.className = classe;
  if (texto) e.textContent = texto;
  return e;
}

function mostrarSons(d) {
  const p = d.config.prefixo;
  $("lista_sons").replaceChildren(...(d.sons.length ? d.sons.map(s => {
    const linha = el("div", "som"), texto = el("span"), tocar = el("button", "", "Tocar"), apagar = el("button", "", "Apagar");
    tocar.type = apagar.type = "button";
    texto.append(el("code", "", p + s.nome), el("small", "", s.arquivo + (s.existe ? "" : " (arquivo não encontrado)")));
    const vol = el("label", "vol"), barra = el("input"), valor = el("output", "", String(s.volume));
    barra.type = "range"; barra.min = 0; barra.max = 100; barra.value = s.volume;
    barra.setAttribute("aria-label", "Volume do " + p + s.nome);
    barra.oninput = () => valor.textContent = barra.value;
    barra.onchange = () => sons({acao: "volume", nome: s.nome, volume: Number(barra.value)});
    vol.append(barra, valor);
    tocar.onclick = () => sons({acao: "tocar", nome: s.nome});
    apagar.onclick = () => confirm("Apagar o som " + p + s.nome + "?") && sons({acao: "apagar", nome: s.nome});
    linha.append(texto, vol, tocar, apagar);
    return linha;
  }) : [el("small", "", "Nenhum som ainda.")]));
  $("sons_faltando").textContent = d.sons_faltando.length ? "Estes não tocam, porque o arquivo não está na pasta sons: " +
    d.sons_faltando.join("; ") + "." : "";
}

// tocar, apagar, adicionar ou mudar o volume de um som. Devolve true se deu certo.
async function sons(pedido) {
  try {
    const r = await fetch("/api/sons", {method: "POST", headers: {"Content-Type": "application/json"},
                                        body: JSON.stringify(pedido)});
    const d = await r.json();
    if (!r.ok) { status(d.erro || "Não deu certo.", true); return false; }
    if (d.sons) {
      // a lista de sons muda na hora; o resto só se não tiver nada esperando o Salvar
      if (Object.keys(mudancas(base)).length) mostrarSons(d);
      else preencher(d);
    }
    status(d.mensagem);
    return true;
  } catch (e) {
    status("Não consegui falar com o programa. Ele está aberto?", true);
    return false;
  }
}

function adicionarSom() {
  const arquivo = $("som_arquivo").files[0];
  if (!arquivo) return status("Escolha um arquivo .mp3 ou .wav.", true);
  const ponto = arquivo.name.lastIndexOf(".");
  const nome = $("som_nome").value.trim() || arquivo.name.slice(0, ponto);
  const leitor = new FileReader();
  leitor.onload = async () => {
    status("Enviando...");
    const ok = await sons({acao: "adicionar", nome, extensao: arquivo.name.slice(ponto),
                           arquivo: leitor.result.split(",")[1] || ""});
    if (ok) { $("som_nome").value = ""; $("som_arquivo").value = ""; }
  };
  leitor.readAsDataURL(arquivo);
}

function atualizarFaixas() {
  document.querySelectorAll(".faixa").forEach(f => f.querySelector("output").textContent = f.querySelector("input").value);
}

function preencher(d) {
  comandos = d.comandos; apelidos = d.apelidos;
  const c = d.config;
  chaves = Object.keys(c);
  const voz = $("voz");
  if (![...voz.options].some(o => o.value === c.voz)) voz.add(new Option(c.voz, c.voz));
  for (const k of chaves) {
    const el = $(k);
    if (!el) continue;
    if (el.type === "checkbox") el.checked = c[k];
    else if (LISTAS.includes(k)) el.value = c[k].join("\\n");
    else el.value = c[k];
  }
  const desligados = new Set(c.comandos_desativados.map(x => {
    x = x.replace(/^!+/, "").toLowerCase();
    return apelidos[x] || x;
  }));
  $("cmds").replaceChildren(...d.grupos.flatMap(g => [el("h3", "", g.titulo), ...g.comandos.map(x => {
    const l = el("label"), i = el("input"), texto = el("span");
    i.type = "checkbox"; i.value = x.cmd; i.checked = !desligados.has(x.cmd);
    texto.append(el("code", "", c.prefixo + x.cmd));
    if (x.atalhos.length) texto.append(" ", el("span", "atalhos", "(atalho: " + x.atalhos.map(a => c.prefixo + a).join(", ") + ")"));
    texto.append(el("small", "", x.descricao));
    l.append(i, texto);
    return l;
  })]));
  mostrarSons(d);
  $("osu_irc_senha").value = "";
  $("osu_irc_senha").placeholder = d.senha_salva ? "•••••••• (salva)" : "";
  $("senha_estado").textContent = d.senha_salva ? "Tem uma senha salva." : "Nenhuma senha salva ainda.";
  atualizarFaixas();
  base = coletar();
}

function coletar() {
  const c = {};
  for (const k of chaves) {
    const el = $(k);
    if (!el) continue;
    if (el.type === "checkbox") c[k] = el.checked;
    else if (LISTAS.includes(k)) c[k] = el.value.split("\\n").map(s => s.trim()).filter(Boolean);
    else if (el.type === "number" || el.type === "range") c[k] = Number(el.value);
    else c[k] = el.value;
  }
  const senha = $("osu_irc_senha").value.trim();
  if (senha) c.osu_irc_senha = senha;
  c.comandos_desativados = [...document.querySelectorAll("#cmds input")].filter(i => !i.checked).map(i => i.value);
  return c;
}

async function carregar() {
  try {
    const r = await fetch("/api/config");
    preencher(await r.json());
    status("");
  } catch (e) {
    status("Não consegui falar com o programa. Ele está aberto?", true);
  }
}

// só o que a pessoa mudou nesta página: uma aba aberta há horas não pode desfazer o que o chat mudou
function mudancas(atual) {
  const c = coletar(), m = {};
  const comando = x => { x = x.replace(/^!+/, "").toLowerCase(); return apelidos[x] || x; };
  for (const k of Object.keys(c)) {
    if (JSON.stringify(c[k]) === JSON.stringify(base[k])) continue;
    if (!Array.isArray(c[k])) { m[k] = c[k]; continue; }
    // lista: aplica o que entrou e o que saiu em cima da lista de agora, que o chat pode ter mudado
    const chave = k === "comandos_desativados" ? comando : x => x.toLowerCase();
    const antes = new Set(base[k].map(chave)), depois = new Set(c[k].map(chave));
    const ficam = atual[k].filter(x => antes.has(chave(x)) ? depois.has(chave(x)) : true);
    const tem = new Set(ficam.map(chave));
    m[k] = ficam.concat(c[k].filter(x => !antes.has(chave(x)) && !tem.has(chave(x))));
  }
  return m;
}

async function salvar() {
  status("Salvando...");
  try {
    const m = mudancas((await (await fetch("/api/config")).json()).config);
    if (!Object.keys(m).length) {
      await carregar();
      return status("Nada para salvar: você não mudou nada aqui.");
    }
    const r = await fetch("/api/config", {method: "POST", headers: {"Content-Type": "application/json"},
                                          body: JSON.stringify(m)});
    const d = await r.json();
    if (!r.ok) throw new Error(d.erro || r.status);
    preencher(d);
    if (d.avisos.length) status("Salvo, mas: " + d.avisos.join(" "), true);
    else status("Salvo! Já está valendo.");
  } catch (e) {
    status("Não consegui salvar. O programa está aberto?", true);
  }
}

// ao voltar para a aba, mostra o que o chat mudou enquanto isso (sem apagar o que a pessoa está editando)
addEventListener("focus", async () => {
  if (Object.keys(mudancas(base)).length) return;
  try {
    preencher(await (await fetch("/api/config")).json());
  } catch (e) {}
});

document.addEventListener("input", e => { if (e.target.type === "range") atualizarFaixas(); });
$("link_pedidos").textContent = location.origin + "/pedidos";
$("link_studio").textContent = "http://localtest.me:" + (location.port || 80) + "/pedidos";
$("copiar_link").onclick = async () => {
  const link = $("link_studio").textContent;
  try {
    await navigator.clipboard.writeText(link);
    status("Link copiado. Agora cole no LIVE Studio com Ctrl+V.");
  } catch (e) {
    getSelection().selectAllChildren($("link_studio"));
    status("Não consegui copiar sozinho: o link ficou selecionado, aperte Ctrl+C.", true);
  }
};
$("salvar").onclick = salvar;
$("som_adicionar").onclick = adicionarSom;
$("recarregar").onclick = carregar;
carregar();
</script>
</body>
</html>
"""


def processar_comentario(user, comentario: str, dono: str):
    """Um comentário do chat: comando ou mensagem para ler em voz alta."""
    nome = user.nick_name or user.unique_id
    uid = (user.unique_id or "").lower()
    nome = carregar_apelidos().get(uid, nome)
    msg = limpar(comentario)
    registrar(user, mensagem=True)
    if silenciado(uid, dono):
        print(f"{nome} (silenciado): {comentario}")
        return
    print(f"{nome}: {comentario}")
    nome = nome_para_falar(nome)
    if tratar_comando(user, nome, comentario.strip(), dono):
        return
    if pausado or not msg or tem_palavra_bloqueada(msg):
        return
    falar_chat(uid, f"{nome} disse: {msg}" if LER_NOME else msg)


lidos = set()  # ids das mensagens já lidas: se a conexão cai e volta, o TikTok pode mandar de novo


def comentario_repetido_ou_antigo(event) -> bool:
    """Mensagem que já foi lida, ou que foi escrita antes de o programa abrir."""
    common = getattr(event, "common", None)
    msg_id = getattr(common, "msg_id", 0)
    if msg_id:
        if msg_id in lidos:
            return True
        lidos.add(msg_id)
    criada = getattr(common, "create_time", 0) or 0
    if criada > 10 ** 11:  # o TikTok manda em milissegundos
        criada /= 1000
    # folga de 1 minuto para o relógio do computador não bater certinho com o do TikTok
    return 0 < criada < INICIO.timestamp() - 60


def modo_teste():
    """Simula o chat sem live: cada linha digitada vira um comentário."""
    from types import SimpleNamespace
    dono = "voce"
    print("MODO DE TESTE: sem live, o que você digitar aqui entra como mensagem do chat.\n"
          "  oi                -> mensagem sua (você é o dono: pode usar os comandos de moderação)\n"
          "  Fulano: oi        -> mensagem de outra pessoa, chamada Fulano\n"
          "  sair (ou Ctrl+C)  -> fecha\n"
          "Atenção: apelidos e pedidos ficam gravados de verdade (apelidos.txt e pedidos.txt).\n")
    falar("Modo de teste ligado.")
    while True:
        try:
            linha = input().strip()
        except (EOFError, KeyboardInterrupt):
            break
        if linha.lower() == "sair":
            break
        if not linha:
            continue
        m = re.match(r"(\w+):\s+(.+)", linha)  # "Fulano: oi" (links como https://... não entram aqui)
        nome, texto = (m.group(1), m.group(2)) if m else ("Você", linha)
        uid = nome.lower() if m else dono
        processar_comentario(SimpleNamespace(unique_id=uid, nick_name=nome), texto, dono)


ESPERA_LIVE_OFFLINE = 30   # segundos entre uma tentativa e outra enquanto a live não começa
ESPERA_RECONEXAO = (5, 10, 20, 40, 60)  # depois de um erro: espera cada vez mais, até 60s


def tecla_em(segundos: int, texto: str) -> str:
    """Mostra o texto com a contagem ({} = segundos que faltam) e devolve a tecla apertada, em minúsculo
    ("" se o tempo acabou). Fora de uma janela do Windows não espera."""
    try:
        import msvcrt
    except ImportError:
        return ""
    if not sys.stdin.isatty():
        return ""
    fim = time.time() + segundos
    tecla = ""
    while (falta := fim - time.time()) > 0 and not tecla:
        print("\r" + texto.format(int(falta) + 1) + " ", end="", flush=True)
        if msvcrt.kbhit():
            tecla = msvcrt.getwch().lower()
        else:
            time.sleep(0.05)
    print("\n")
    return tecla


def escolher_usuario() -> str:
    """Usuário do TikTok: o da linha de comando, senão o guardado no config.json, senão pergunta (e guarda)."""
    if len(sys.argv) > 1:
        return sys.argv[1].strip().lstrip("@")
    if TIKTOK_USUARIO:
        tecla = tecla_em(5, f"Entrando na live de @{TIKTOK_USUARIO} em {{}}s... "
                            f"(T = testar sem live, U = trocar de usuário)")
        if tecla == "t":
            return "teste"
        if tecla != "u":
            return TIKTOK_USUARIO
    # a página abre já aqui, para dar para digitar o usuário nela também
    anterior = TIKTOK_USUARIO
    iniciar_pagina()
    usuario = ""
    while not usuario:
        usuario = ler_usuario(anterior)
    if usuario.lower() not in ("teste", "--teste") and usuario != TIKTOK_USUARIO:
        mudar_config({"tiktok_usuario": usuario})
    if usuario.lower() not in ("teste", "--teste"):
        print("Guardei o usuário: da próxima vez o programa já entra direto.\n")
    return usuario


def ler_usuario(anterior: str) -> str:
    """Pergunta o usuário aqui e, ao mesmo tempo, fica de olho na página de configurações:
    o que for preenchido primeiro vale. Fora de uma janela do Windows, só pergunta aqui."""
    pergunta = "Seu usuário do TikTok (sem @"
    pergunta += ", aqui ou na página de configurações): " if pagina_iniciada else "): "
    try:
        import msvcrt
    except ImportError:
        msvcrt = None
    if msvcrt is None or not sys.stdin.isatty():
        return input(pergunta).strip().lstrip("@")
    print(pergunta, end="", flush=True)
    digitado = ""
    while True:
        if TIKTOK_USUARIO and TIKTOK_USUARIO != anterior:  # salvo pela página
            print(f"\r{pergunta}{TIKTOK_USUARIO}{' ' * max(0, len(digitado) - len(TIKTOK_USUARIO))}")
            print("(preenchido na página de configurações)")
            return TIKTOK_USUARIO
        if not msvcrt.kbhit():
            time.sleep(0.05)
            continue
        c = msvcrt.getwch()
        if c in ("\x00", "\xe0"):  # setas e outras teclas especiais: vêm em dois pedaços, ignora
            msvcrt.getwch()
        elif c == "\x03":
            raise KeyboardInterrupt
        elif c in ("\r", "\n"):
            print()
            return digitado.strip().lstrip("@")
        elif c == "\x08":
            if digitado:
                digitado = digitado[:-1]
                print("\b \b", end="", flush=True)
        elif c.isprintable():
            digitado += c
            print(c, end="", flush=True)


def esperar(segundos: float):
    """Espera mostrando a contagem na mesma linha (Ctrl+C interrompe)."""
    fim = time.time() + segundos
    while (falta := fim - time.time()) > 0:
        print(f"\r  tentando de novo em {int(falta) + 1:>2}s... (Ctrl+C para sair) ", end="", flush=True)
        time.sleep(min(1, falta))
    print("\r" + " " * 50 + "\r", end="", flush=True)


def ficar_na_live(client, usuario: str):
    """Conecta e, se a live ainda não começou ou a conexão cair, fica tentando de novo até a pessoa fechar."""
    erros = 0          # erros seguidos (para esperar cada vez mais)
    ultimo_aviso = ""  # não repete a mesma mensagem a cada tentativa
    while True:
        try:
            # sem o lote de mensagens recentes que o TikTok manda ao conectar (seriam lidas de novo)
            client.run(process_connect_events=False)
            # voltou sem erro: a conexão terminou (queda ou fim da live); o aviso já saiu no DisconnectEvent
            espera, aviso, erros = ESPERA_RECONEXAO[0], "", 0
        except KeyboardInterrupt:
            return
        except UserOfflineError:
            espera, erros = ESPERA_LIVE_OFFLINE, 0
            aviso = f"@{usuario} não está ao vivo agora. Assim que a live começar, eu conecto sozinho."
        except UserNotFoundError:
            espera, erros = ESPERA_LIVE_OFFLINE, 0
            aviso = (f"Não achei a live de @{usuario}. Se o usuário estiver errado, troque na página de\n"
                     f"  configurações ou em \"tiktok_usuario\" no config.json e abra o programa de novo.\n"
                     f"  (Quem nunca fez live também cai aqui: é só começar a live.)")
        except Exception as e:
            espera = ESPERA_RECONEXAO[min(erros, len(ESPERA_RECONEXAO) - 1)]
            erros += 1
            aviso = f"Não consegui conectar à live ({type(e).__name__}: {e})."
        if aviso and aviso != ultimo_aviso:
            print(aviso)
        ultimo_aviso = aviso
        try:
            if client.connected:  # garante que a próxima tentativa começa do zero
                client._asyncio_loop.run_until_complete(client.disconnect())
        except Exception:
            pass
        try:
            esperar(espera)
        except KeyboardInterrupt:
            print()
            return


def main():
    carregar_config()
    os.makedirs(PASTA_SONS, exist_ok=True)  # para a pessoa achar onde pôr os sons
    # antes de abrir o navegador e o tosu: as janelas deles roubam o foco e o T/U (ou o usuário
    # digitado na primeira vez) iria para elas em vez desta janela
    usuario = escolher_usuario()
    iniciar_pagina()
    abrir_tosu()
    acertar_inicio()
    atexit.register(fechar_irc)  # sai do chat do osu! direitinho ao fechar
    salvar_pedidos()  # a fila começa vazia: o pedidos.txt não pode continuar mostrando a da live anterior
    if usuario.lower() in ("teste", "--teste"):
        threading.Thread(target=narrador, daemon=True).start()
        threading.Thread(target=vigia_osu, daemon=True).start()
        return modo_teste()

    os.makedirs(PASTA_REGISTROS, exist_ok=True)
    apagar_registros_antigos()
    arquivo =os.path.join(PASTA_REGISTROS, f"live_{datetime.now():%Y-%m-%d_%H-%M}.csv")

    threading.Thread(target=narrador, daemon=True).start()
    threading.Thread(target=salvador_automatico, args=(arquivo,), daemon=True).start()
    threading.Thread(target=vigia_osu, daemon=True).start()
    client = TikTokLiveClient(unique_id=f"@{usuario}")
    ja_conectou = False

    @client.on(JoinEvent)
    async def ao_entrar(event: JoinEvent):
        registrar(event.user)

    @client.on(ConnectEvent)
    async def ao_conectar(event: ConnectEvent):
        nonlocal ja_conectou
        if ja_conectou:
            print(f"Voltei para a live de @{usuario}! Lendo o chat...\n")
            falar("Voltei a ler o chat da live.")
        else:
            print(f"Conectado à live de @{usuario}! Lendo o chat...\n")
            falar("Conectado ao chat da live.")
        ja_conectou = True

    @client.on(DisconnectEvent)
    async def ao_desconectar(event: DisconnectEvent):
        print("Caiu a conexão com a live (ou a live acabou). Tentando voltar...")
        falar("Caiu a conexão com a live. Tentando voltar.")

    @client.on(CommentEvent)
    async def ao_comentar(event: CommentEvent):
        if comentario_repetido_ou_antigo(event):
            return
        processar_comentario(event.user, event.comment or "", usuario)

    print(f"Conectando a @{usuario}... (Ctrl+C para sair)")
    try:
        ficar_na_live(client, usuario)
    finally:
        try:
            salvar(arquivo)
        except PermissionError:
            print("Feche a planilha no Excel para salvar a versão final.")
        if pessoas:
            print(f"\nRegistro salvo em: {arquivo}")
    if getattr(sys, "frozen", False):  # no .exe a janela fecharia sem dar tempo de ler
        input("Pressione Enter para sair...")

if __name__ == "__main__":
    main()
