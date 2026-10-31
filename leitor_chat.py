"""
Leitor de chat da live do TikTok em voz alta (pt-BR).

Uso:
    python leitor_chat.py seu_usuario
    (sem o @; a live precisa estar AO VIVO quando você rodar)

Comandos do chat (as respostas são faladas):
    Todo mundo:  !comandos  !mensagens  !top  !copiar <texto>
    Você e MODERADORES:  !mudo  !voltar  !limpar  !velocidade <-10 a 10>  !volume <0 a 100>
                         !apelido <usuário> <apelido>
                         !voz <francisca, antonio, maria...>  !nomes  !bloquear <palavra>
                         !desbloquear <palavra>  !ligar <comando>  !desligar <comando>
                         !avisos <mapa ou recorde>  !espera <segundos>  !tamanho <letras>  !fila <mensagens>
    Só você:  !mod <usuário>  !desmod <usuário>
    (o que estes comandos mudam fica gravado no config.json)

Pedidos de mapas do osu! (a fila fica salva em pedidos.txt):
    Todo mundo:  !pedir <link ou nome do mapa>  !pedidos
    Você e MODERADORES:  !proximo (abre no navegador)  !fecharpedidos
                         !abrirpedidos  !zerarpedidos  !limitepedidos <número>
                         !filapedidos (liga/desliga a fila: desligada, cada pedido vai direto para o osu!)

osu! (o tosu abre sozinho, se estiver na pasta tosu):  !np (mapa atual)  !pp  !rank  !recorde
    e avisos automáticos de mapa novo (AVISAR_MAPA) e de recorde de PP da live (AVISAR_RECORDE)

Sem live: rode com o usuário "teste" e digite as mensagens do chat na janela.

Configurações: pelo config.json ou pela página http://localhost:8765 (WEB_PORTA),
    que muda tudo na hora, sem reabrir o programa.
"""

import csv
import http.server
import ipaddress
import os
import queue
import re
import subprocess
import sys
import threading
import time
import json
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timedelta, timezone

from TikTokLive import TikTokLiveClient
from TikTokLive.events import CommentEvent, ConnectEvent, DisconnectEvent, JoinEvent

# ---------------- Configurações ----------------
# Estes são os valores padrão. Para mudar, use a página de configurações ou edite o
# config.json ao lado do programa (ele é criado sozinho na primeira vez que o programa abre).
# Vozes disponíveis (as neurais precisam de internet e soam mais naturais):
#   "pt-BR-FranciscaNeural"           feminina
#   "pt-BR-ThalitaMultilingualNeural" feminina
#   "pt-BR-AntonioNeural"             masculina
#   "pt-PT-RaquelNeural"              feminina (Portugal)
#   "pt-PT-DuarteNeural"              masculina (Portugal)
#   "windows"                         voz Maria do Windows (funciona offline)
VOZ = "pt-BR-FranciscaNeural"
VELOCIDADE = 1          # -10 (lento) a 10 (rápido)
VOLUME = 100            # 0 a 100
LER_NOME = True         # falar "Fulano disse: ..." antes da mensagem
TAMANHO_MAXIMO = 200    # corta mensagens muito longas
FILA_MAXIMA = 15        # se o chat estiver muito rápido, descarta as mais antigas
PALAVRAS_BLOQUEADAS = []  # ex.: ["spam", "palavrão"]

# Comandos do chat (veja a lista completa em tratar_comando)
PREFIXO = "!"
MODERADORES = []        # usuários (sem @) que podem usar os comandos de moderação, além de você
ESPERA_COMANDO = 15     # segundos que cada pessoa espera entre um comando e outro
PEDIDOS_MAXIMOS = 30    # tamanho máximo da fila de pedidos de mapas do osu!
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
# ------------------------------------------------

fila: "queue.Queue[str]" = queue.Queue()

# ---------------- Registro de quem entrou / mensagens ----------------
# Pasta do programa: ao lado do .exe quando empacotado, senão ao lado deste arquivo
PASTA = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
PASTA_REGISTROS = os.path.join(PASTA, "registros")
ARQUIVO_CONFIG = os.path.join(PASTA, "config.json")

# nome no config.json -> variável aqui do programa
OPCOES = {nome.lower(): nome for nome in (
    "VOZ", "VELOCIDADE", "VOLUME", "LER_NOME", "TAMANHO_MAXIMO", "FILA_MAXIMA", "PALAVRAS_BLOQUEADAS",
    "PREFIXO", "MODERADORES", "ESPERA_COMANDO", "PEDIDOS_MAXIMOS", "FILA_PEDIDOS", "COMANDOS_DESATIVADOS",
    "TOSU_URL", "AVISAR_MAPA", "AVISAR_RECORDE", "OSU_USUARIO", "OSU_IRC_SENHA", "WEB_PORTA", "WEB_REDE_LOCAL")}
SECRETAS = ("osu_irc_senha",)  # ficam só no config.json: a página nunca mostra nem muda
LIMITES = {"VELOCIDADE": (-10, 10), "VOLUME": (0, 100), "TAMANHO_MAXIMO": (1, None), "FILA_MAXIMA": (1, None),
           "ESPERA_COMANDO": (0, None), "PEDIDOS_MAXIMOS": (1, None), "WEB_PORTA": (0, 65535)}


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
    for aviso in avisos:
        print(f"*** {aviso}")
    return avisos


def aplicar_config(config: dict) -> list:
    """Confere e aplica as opções (do config.json ou da página). Devolve os avisos do que não deu."""
    avisos = []
    for chave, valor in config.items():
        nome = OPCOES.get(chave.lower())
        if nome is None:
            avisos.append(f"não conheço a opção \"{chave}\" (escrita errada?). Ignorando.")
            continue
        atual = globals()[nome]
        esperado = type(atual)
        # em Python True/False também contam como número; aqui não podem
        ok = isinstance(valor, esperado) and not (esperado is int and isinstance(valor, bool))
        if ok and esperado is list:
            ok = all(isinstance(x, str) for x in valor)
        if not ok:
            avisos.append(f"\"{chave}\" deveria ser {TIPOS.get(esperado, esperado.__name__)}. "
                          f"Mantive: {json.dumps(atual, ensure_ascii=False)}")
            continue
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
    # versão nova com opções novas: acrescenta só elas, com o valor padrão, sem mexer no resto.
    # Com algum aviso não grava, para não apagar o que a pessoa ainda precisa corrigir.
    novas = [chave for chave in OPCOES if chave not in {c.lower() for c in config}]
    if novas and not avisos:
        try:
            salvar_config()
            print(f"Opções novas no config.json (com o valor padrão): {', '.join(novas)}\n")
        except OSError:
            pass


TIPOS = {bool: "true ou false", int: "um número inteiro (sem vírgula)", str: "um texto entre aspas", list: "uma lista entre [ ]"}
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


def tocar_mp3(caminho: str):
    """Toca um mp3 usando o player nativo do Windows (MCI) e espera terminar."""
    import ctypes
    mci = ctypes.windll.winmm.mciSendStringW
    mci(f'open "{caminho}" type mpegvideo alias fala', None, 0, None)
    mci(f"setaudio fala volume to {VOLUME * 10}", None, 0, None)
    mci("play fala wait", None, 0, None)
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


def narrador():
    """Thread que fala as mensagens da fila, uma de cada vez.
    VOZ, VELOCIDADE e VOLUME são lidos a cada fala, para valer o que mudar durante a live."""
    import asyncio
    import tempfile
    import edge_tts

    caminho = os.path.join(tempfile.gettempdir(), "tiktok_fala.mp3")
    sapi = None  # só criada se a voz "windows" for usada
    while True:
        texto = fila.get()
        try:
            if VOZ == "windows":
                if sapi is None:
                    sapi = voz_windows()
                sapi.Rate = VELOCIDADE
                sapi.Volume = VOLUME
                sapi.Speak(texto)
            else:
                taxa = f"{VELOCIDADE * 10:+d}%"
                asyncio.run(edge_tts.Communicate(texto, VOZ, rate=taxa).save(caminho))
                tocar_mp3(caminho)
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


def falar(texto: str):
    """Coloca na fila de fala; se o chat estiver muito rápido, descarta as mais antigas."""
    while fila.qsize() >= FILA_MAXIMA:
        try:
            fila.get_nowait()
        except queue.Empty:
            break
    fila.put(texto)


def limpar_fila():
    while True:
        try:
            fila.get_nowait()
        except queue.Empty:
            return


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
    """Link do beatmap, se a pessoa mandou um; senão, a busca do osu! com o que ela escreveu."""
    m = re.search(r"osu\.ppy\.sh/\S+", texto)
    if m:
        return "https://" + m.group(0)
    return "https://osu.ppy.sh/beatmapsets?q=" + urllib.parse.quote(texto)


def mandar_no_osu(texto: str) -> str:
    """Manda uma mensagem privada para você mesmo no chat do osu!, pelo IRC (irc.ppy.sh).
    Devolve "" se deu certo, senão o motivo."""
    import socket
    nick = OSU_USUARIO.strip().replace(" ", "_")  # no IRC do osu! os espaços do nome viram _
    try:
        with socket.create_connection(("irc.ppy.sh", 6667), timeout=10) as s:
            def enviar(linha):
                s.sendall((linha + "\r\n").encode("utf-8"))
            enviar(f"PASS {OSU_IRC_SENHA.strip()}")
            enviar(f"NICK {nick}")
            enviar(f"USER {nick} 0 * :{nick}")
            resto, fim = b"", time.time() + 15
            while time.time() < fim:
                dados = s.recv(4096)
                if not dados:
                    return "o osu! fechou a conexão (nome ou senha de IRC errados?)"
                resto += dados
                *linhas, resto = resto.split(b"\r\n")
                for linha in linhas:
                    partes = linha.decode("utf-8", "replace").split()
                    if partes[:1] == ["PING"]:
                        enviar("PONG " + " ".join(partes[1:]))
                    elif partes[1:2] == ["464"]:
                        return "o osu! recusou a senha de IRC"
                    elif partes[1:2] == ["001"]:  # entrou
                        enviar(f"PRIVMSG {nick} :{texto}")
                        time.sleep(1)  # sair na mesma hora às vezes perde a mensagem
                        enviar("QUIT")
                        return ""
            return "o osu! demorou demais para responder"
    except OSError as e:
        return f"não consegui conectar no chat do osu! ({e})"


trava_irc = threading.Lock()  # um envio de cada vez: duas conexões juntas com o mesmo nome se atrapalham


def abrir_pedido(p: dict, navegador: bool = True):
    """Manda o pedido no seu chat do osu! (se configurado). Senão, ou se der erro: abre no navegador
    (!proximo) ou só deixa o link na janela (fila desligada, para não abrir o navegador no meio do mapa)."""
    if OSU_USUARIO.strip() and OSU_IRC_SENHA.strip():
        # no chat do osu!, [link texto] vira o texto clicável. Colchetes no texto quebrariam o link.
        rotulo = "abrir o mapa" if "osu.ppy.sh" in p["texto"] else p["texto"]
        limpo = lambda t: re.sub(r"[\[\]\r\n]", "", t)
        with trava_irc:
            erro = mandar_no_osu(f"Pedido de {limpo(p['nome'])}: [{p['url']} {limpo(rotulo)}]")
        if not erro:
            print("  (mandado no seu chat do osu!)")
            return
        if not navegador:
            print(f"*** {erro}. O link do pedido está logo acima.")
            return
        print(f"*** {erro}. Abrindo no navegador.")
    elif not navegador:
        print("  (para os pedidos irem para o osu!, preencha osu_usuario e osu_irc_senha no config.json)")
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

COMANDOS_PUBLICOS = ["np", "pp", "rank", "recorde", "pedir", "pedidos", "mensagens", "top", "copiar"]
COMANDOS_MOD = ["mudo", "voltar", "limpar", "apelido", "velocidade", "volume", "voz", "nomes", "bloquear",
                "desbloquear", "ligar", "desligar", "avisos", "espera", "tamanho", "fila",
                "proximo", "fecharpedidos", "abrirpedidos", "zerarpedidos", "limitepedidos", "filapedidos"]
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
PROTEGIDOS = ("ligar", "desligar")  # se desligar estes pelo chat, não daria para religar pelo chat


def desativado(cmd: str) -> bool:
    return APELIDOS_COMANDO.get(cmd, cmd) in [c.lstrip(PREFIXO).lower() for c in COMANDOS_DESATIVADOS]


FALADO = {"proximo": "próximo", "fecharpedidos": "fechar pedidos", "abrirpedidos": "abrir pedidos",
          "zerarpedidos": "zerar pedidos", "limitepedidos": "limite pedidos",
          "filapedidos": "fila pedidos"}  # como a voz fala cada comando

# !voz francisca -> nome da voz no config
VOZES = {"francisca": "pt-BR-FranciscaNeural", "thalita": "pt-BR-ThalitaMultilingualNeural",
         "antonio": "pt-BR-AntonioNeural", "antônio": "pt-BR-AntonioNeural", "raquel": "pt-PT-RaquelNeural",
         "duarte": "pt-PT-DuarteNeural", "maria": "windows", "windows": "windows"}

# comandos que mudam um número: comando -> (opção do config, o que a voz responde)
NUMERICOS = {
    "velocidade": ("velocidade", "Velocidade {}."),
    "volume": ("volume", "Volume {}."),
    "espera": ("espera_comando", "Agora cada pessoa espera {} segundos entre um comando e outro."),
    "tamanho": ("tamanho_maximo", "Vou ler até {} letras de cada mensagem."),
    "fila": ("fila_maxima", "A fila de fala agora guarda até {} mensagens."),
    "limitepedidos": ("pedidos_maximos", "A fila de pedidos agora aceita até {}."),
}


def ajuda(lista, titulo: str) -> str:
    nomes = [FALADO.get(c, c) for c in lista if not desativado(c)]
    if not nomes:
        return "Nenhum comando ligado."
    texto = ", ".join(nomes[:-1]) + " e " + nomes[-1] if len(nomes) > 1 else nomes[0]
    return f"{titulo}: {texto}. Use com exclamação, por exemplo: exclamação {nomes[0]}."


def tratar_comando(user, nome: str, texto: str, dono: str) -> bool:
    """Executa um comando do chat. Retorna True se era um comando (e não deve ser lido)."""
    global pausado, pedidos_abertos
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
    eh_mod = eh_dono or uid in [m.lstrip("@").lower() for m in MODERADORES]

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
            if any(p.lower() in apelido.lower() for p in PALAVRAS_BLOQUEADAS):
                falar("Esse apelido não pode.")
                return True
            salvar_apelido(alvo, apelido)
            falar(f"Beleza, agora vou chamar {alvo} de {apelido}.")
            return True
        if cmd in NUMERICOS:
            chave, resposta = NUMERICOS[cmd]
            try:
                n = int(arg)
            except ValueError:
                falar(f"Use: exclamação {FALADO.get(cmd, cmd)} e um número.")
                return True
            mudar_config({chave: n})  # fora do limite, usa o limite mais próximo
            falar(resposta.format(globals()[OPCOES[chave]]))
            return True
        if cmd == "voz":
            voz = VOZES.get(arg.lower()) or next((v for v in VOZES.values() if v.lower() == arg.lower()), None)
            if not voz:
                falar("Vozes: Francisca, Thalita, Antonio, Raquel, Duarte e Maria, que funciona sem internet. "
                      "Use: exclamação voz e o nome.")
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
            if alvo not in TODOS_COMANDOS:
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
    if cmd != "comandos" and cmd not in COMANDOS_PUBLICOS:
        return False
    agora = time.time()
    if not eh_mod and agora - ultimo_comando.get(uid, 0) < ESPERA_COMANDO:
        return True  # anti-spam: ignora calado
    ultimo_comando[uid] = agora
    if pausado:
        return True

    if cmd == "comandos":
        falar(ajuda(COMANDOS_MOD + (COMANDOS_DONO if eh_dono else []), "Comandos de moderação") if eh_mod
              else ajuda(COMANDOS_PUBLICOS, "Comandos"))
    elif cmd == "mensagens":
        with trava:
            n = pessoas.get(user.unique_id, {}).get("mensagens", 0)
        falar(f"{nome}, você mandou {n} {'mensagem' if n == 1 else 'mensagens'} nesta live.")
    elif cmd == "top":
        with trava:
            top = sorted(pessoas.items(), key=lambda kv: -kv[1]["mensagens"])[:3]
        apelidos = carregar_apelidos()
        nomes = [f"{apelidos.get(u.lower(), p['nome'])}, com {p['mensagens']}"
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
        meu = next((i for i, p in enumerate(pedidos, 1) if p["uid"] == uid), None)
        if not pedidos_abertos:
            falar(f"{nome}, os pedidos estão fechados agora.")
        elif not arg:
            falar(f"{nome}, manda o link ou o nome do mapa depois do comando.")
        elif not FILA_PEDIDOS:  # sem fila: vai direto para o chat do osu!, sem a voz anunciar
            if any(p.lower() in arg.lower() for p in PALAVRAS_BLOQUEADAS):
                falar(f"{nome}, esse pedido não pode.")
                return True
            p = {"uid": uid, "nome": nome, "texto": arg, "url": link_do_pedido(arg)}
            print(f"[pedido de {nome}: {arg}]\n  {p['url']}")
            threading.Thread(target=abrir_pedido, args=(p, False), daemon=True).start()
        elif meu:
            falar(f"{nome}, você já tem um pedido na fila, na posição {meu}.")
        elif len(pedidos) >= PEDIDOS_MAXIMOS:
            falar(f"{nome}, a fila de pedidos está cheia.")
        elif any(p.lower() in arg.lower() for p in PALAVRAS_BLOQUEADAS):
            falar(f"{nome}, esse pedido não pode.")
        else:
            pedidos.append({"uid": uid, "nome": nome, "texto": arg, "url": link_do_pedido(arg)})
            salvar_pedidos()
            print(f"[novo pedido de {nome}: {arg}]")
            falar(f"Pedido de {nome} anotado, posição {len(pedidos)}.")
    elif cmd == "pedidos" and not FILA_PEDIDOS:
        falar("A fila de pedidos está desligada: os pedidos vão direto para o osu." +
              ("" if pedidos_abertos else " Os pedidos estão fechados."))
    elif cmd == "pedidos":
        meu = next((i for i, p in enumerate(pedidos, 1) if p["uid"] == uid), None)
        n = len(pedidos)
        texto = "Não tem pedidos na fila." if n == 0 else \
            f"Tem {n} {'pedido' if n == 1 else 'pedidos'} na fila."
        if meu:
            texto += f" O seu é o número {meu}."
        if not pedidos_abertos:
            texto += " Os pedidos estão fechados."
        falar(texto)
    elif cmd == "copiar":
        if not arg:
            falar(f"{nome}, escreve o que quer copiar depois do comando.")
            return True
        try:
            copiar_texto(arg)  # texto original, sem cortar links
            print(f"[copiado de {nome}: {arg}]")
            falar(f"Copiei a mensagem de {nome}.")
        except OSError as e:
            print(f"[não deu para copiar: {e}]")
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
        return {"config": config, "comandos": TODOS_COMANDOS,
                "apelidos": APELIDOS_COMANDO}

    def do_GET(self):
        if not self.host_ok():
            return self.responder(403, "text/plain; charset=utf-8", b"acesso negado")
        if self.path == "/":
            self.responder(200, "text/html; charset=utf-8", PAGINA.encode("utf-8"))
        elif self.path == "/api/config":
            self.responder_json(self.dados_da_pagina())
        else:
            self.responder(404, "text/plain; charset=utf-8", b"nada aqui")

    def do_POST(self):
        # exigir JSON faz o navegador barrar envios vindos de outros sites
        if not self.host_ok() or self.path != "/api/config" or \
                not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return self.responder(403, "text/plain; charset=utf-8", b"acesso negado")
        try:
            dados = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8"))
            if not isinstance(dados, dict):
                raise ValueError
        except (ValueError, UnicodeDecodeError):
            return self.responder_json({"erro": "dados inválidos"}, 400)
        dados = {k: v for k, v in dados.items() if k.lower() not in SECRETAS}
        print("[configurações alteradas pela página]")
        avisos = mudar_config(dados)
        self.responder_json({"avisos": avisos, **self.dados_da_pagina()})


def ip_local() -> str:
    """IP deste PC na rede local (o que o celular usa para abrir a página)."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("8.8.8.8", 80))  # não envia nada, só descobre por qual placa de rede sairia
            return s.getsockname()[0]
        except OSError:
            return "IP-deste-PC"


def iniciar_pagina():
    if not WEB_PORTA:
        return
    endereco = "0.0.0.0" if WEB_REDE_LOCAL else "127.0.0.1"
    try:
        servidor = http.server.ThreadingHTTPServer((endereco, WEB_PORTA), PaginaConfig)
    except OSError:
        print(f"*** Não consegui abrir a página de configurações na porta {WEB_PORTA} (outro programa usando?).\n"
              f"*** Troque \"web_porta\" no config.json para outro número, por exemplo 8766.\n")
        return
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    print(f"Página de configurações: http://localhost:{WEB_PORTA}")
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
input[type=text], input[type=number], select, textarea { width: 100%; padding: 8px; border: 1px solid var(--borda);
  border-radius: 6px; background: var(--fundo); color: inherit; font: inherit; }
textarea { min-height: 72px; resize: vertical; }
label.check { display: flex; gap: 8px; align-items: flex-start; }
label.check input { margin-top: 4px; }
.faixa { display: flex; gap: 10px; align-items: center; }
.faixa input { flex: 1; }
.faixa output { min-width: 3ch; text-align: right; font-variant-numeric: tabular-nums; }
.cmds { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 4px 12px; margin-top: 8px; }
.cmds label { font-weight: 400; margin: 0; display: flex; gap: 6px; align-items: center; }
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
    <h2>Voz</h2>
    <label for="voz">Voz</label>
    <select id="voz">
      <option value="pt-BR-FranciscaNeural">Francisca (feminina)</option>
      <option value="pt-BR-ThalitaMultilingualNeural">Thalita (feminina)</option>
      <option value="pt-BR-AntonioNeural">Antonio (masculina)</option>
      <option value="pt-PT-RaquelNeural">Raquel (feminina, Portugal)</option>
      <option value="pt-PT-DuarteNeural">Duarte (masculina, Portugal)</option>
      <option value="windows">Maria do Windows (funciona sem internet)</option>
    </select>
    <label for="velocidade">Velocidade</label>
    <div class="faixa"><input type="range" id="velocidade" min="-10" max="10" step="1"><output for="velocidade"></output></div>
    <label for="volume">Volume</label>
    <div class="faixa"><input type="range" id="volume" min="0" max="100" step="1"><output for="volume"></output></div>
  </section>

  <section>
    <h2>Leitura do chat</h2>
    <label class="check"><input type="checkbox" id="ler_nome"><span>Falar o nome antes da mensagem<small>"Fulano disse: ..."</small></span></label>
    <label for="tamanho_maximo">Tamanho máximo da mensagem<small>Letras; o resto é cortado.</small></label>
    <input type="number" id="tamanho_maximo" min="1">
    <label for="fila_maxima">Tamanho da fila de fala<small>Se o chat estiver rápido demais, as mensagens mais antigas são puladas.</small></label>
    <input type="number" id="fila_maxima" min="1">
    <label for="palavras_bloqueadas">Palavras bloqueadas<small>Uma por linha. Mensagens com elas não são lidas.</small></label>
    <textarea id="palavras_bloqueadas"></textarea>
  </section>

  <section>
    <h2>Comandos</h2>
    <label for="prefixo">Prefixo<small>O símbolo antes dos comandos.</small></label>
    <input type="text" id="prefixo" maxlength="5">
    <label for="moderadores">Moderadores<small>Usuários do TikTok, sem @, um por linha. Podem usar os comandos de moderação.</small></label>
    <textarea id="moderadores"></textarea>
    <label for="espera_comando">Espera entre comandos (segundos)<small>Anti-spam: quanto cada pessoa espera entre um comando e outro.</small></label>
    <input type="number" id="espera_comando" min="0">
    <label>Comandos ligados<small>Desmarque para desligar um comando.</small></label>
    <div class="cmds" id="cmds"></div>
  </section>

  <section>
    <h2>Pedidos de mapas</h2>
    <label for="pedidos_maximos">Tamanho máximo da fila de pedidos</label>
    <input type="number" id="pedidos_maximos" min="1">
    <label class="check"><input type="checkbox" id="fila_pedidos"><span>Usar fila de pedidos<small>Desligado: cada pedido vai direto
      para o seu chat do osu! (precisa do nome e da senha de IRC) e a voz não anuncia.</small></span></label>
  </section>

  <section>
    <h2>osu!</h2>
    <label class="check"><input type="checkbox" id="avisar_mapa"><span>Avisar mapa novo<small>Fala "Agora: Artista - Música" quando você começa um mapa.</small></span></label>
    <label class="check"><input type="checkbox" id="avisar_recorde"><span>Avisar recorde de PP da live</span></label>
    <label for="tosu_url">Endereço do tosu<small>Só mude se tiver mudado no tosu.</small></label>
    <input type="text" id="tosu_url">
    <label for="osu_usuario">Seu nome no osu!<small>Com ele e a senha de IRC, o !proximo manda o pedido no seu chat do osu!.
      A senha de IRC fica só no config.json (osu_irc_senha), por segurança esta página não mostra.</small></label>
    <input type="text" id="osu_usuario">
  </section>

  <section>
    <h2>Esta página</h2>
    <p class="sub" style="margin:4px 0 0">Estas duas só valem quando o programa abre de novo.</p>
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
const LISTAS = ["palavras_bloqueadas", "moderadores"];
let comandos = [], apelidos = {}, chaves = [];

function status(texto, erro) {
  $("status").textContent = texto;
  $("status").className = erro ? "erro" : "";
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
  $("cmds").replaceChildren(...comandos.map(cmd => {
    const l = document.createElement("label"), i = document.createElement("input");
    i.type = "checkbox"; i.value = cmd; i.checked = !desligados.has(cmd);
    l.append(i, c.prefixo + cmd);
    return l;
  }));
  atualizarFaixas();
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

async function salvar() {
  status("Salvando...");
  try {
    const r = await fetch("/api/config", {method: "POST", headers: {"Content-Type": "application/json"},
                                          body: JSON.stringify(coletar())});
    const d = await r.json();
    if (!r.ok) throw new Error(d.erro || r.status);
    preencher(d);
    if (d.avisos.length) status("Salvo, mas: " + d.avisos.join(" "), true);
    else status("Salvo! Já está valendo.");
  } catch (e) {
    status("Não consegui salvar. O programa está aberto?", true);
  }
}

document.addEventListener("input", e => { if (e.target.type === "range") atualizarFaixas(); });
$("salvar").onclick = salvar;
$("recarregar").onclick = carregar;
carregar();
</script>
</body>
</html>
"""


def processar_comentario(user, comentario: str, dono: str):
    """Um comentário do chat: comando ou mensagem para ler em voz alta."""
    nome = user.nick_name or user.unique_id
    nome = carregar_apelidos().get((user.unique_id or "").lower(), nome)
    msg = limpar(comentario)
    print(f"{nome}: {comentario}")
    registrar(user, mensagem=True)
    if tratar_comando(user, nome, comentario.strip(), dono):
        return
    if pausado or not msg or any(p.lower() in msg.lower() for p in PALAVRAS_BLOQUEADAS):
        return
    falar(f"{nome} disse: {msg}" if LER_NOME else msg)


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


def main():
    carregar_config()
    iniciar_pagina()
    abrir_tosu()
    acertar_inicio()
    salvar_pedidos()  # a fila começa vazia: o pedidos.txt não pode continuar mostrando a da live anterior
    if len(sys.argv) > 1:
        usuario = sys.argv[1]
    else:
        usuario = input("Seu usuário do TikTok (sem @): ")
    usuario = usuario.strip().lstrip("@")
    if usuario.lower() in ("teste", "--teste"):
        threading.Thread(target=narrador, daemon=True).start()
        threading.Thread(target=vigia_osu, daemon=True).start()
        return modo_teste()

    os.makedirs(PASTA_REGISTROS, exist_ok=True)
    arquivo = os.path.join(PASTA_REGISTROS, f"live_{datetime.now():%Y-%m-%d_%H-%M}.csv")

    threading.Thread(target=narrador, daemon=True).start()
    threading.Thread(target=salvador_automatico, args=(arquivo,), daemon=True).start()
    threading.Thread(target=vigia_osu, daemon=True).start()
    client = TikTokLiveClient(unique_id=f"@{usuario}")

    @client.on(JoinEvent)
    async def ao_entrar(event: JoinEvent):
        registrar(event.user)

    @client.on(ConnectEvent)
    async def ao_conectar(event: ConnectEvent):
        print(f"Conectado à live de @{usuario}! Lendo o chat...\n")
        fila.put("Conectado ao chat da live.")

    @client.on(DisconnectEvent)
    async def ao_desconectar(event: DisconnectEvent):
        print("Desconectado da live.")

    @client.on(CommentEvent)
    async def ao_comentar(event: CommentEvent):
        if comentario_repetido_ou_antigo(event):
            return
        processar_comentario(event.user, event.comment or "", usuario)

    print(f"Conectando a @{usuario}... (Ctrl+C para sair)")
    erro = False
    try:
        # sem o lote de mensagens recentes que o TikTok manda ao conectar (seriam lidas de novo)
        client.run(process_connect_events=False)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"\nErro: {e}\nVerifique se o usuário está certo e se a live está ao vivo.")
        erro = True
    finally:
        try:
            salvar(arquivo)
        except PermissionError:
            print("Feche a planilha no Excel para salvar a versão final.")
        if pessoas:
            print(f"\nRegistro salvo em: {arquivo}")
    if erro or getattr(sys, "frozen", False):  # no .exe a janela fecharia sem dar tempo de ler
        input("Pressione Enter para sair...")


if __name__ == "__main__":
    main()
