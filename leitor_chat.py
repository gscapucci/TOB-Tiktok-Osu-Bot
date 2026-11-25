"""
Leitor de chat da live do TikTok em voz alta (pt-BR).

Uso:
    python leitor_chat.py seu_usuario
    (sem o @; fica guardado no config.json. Se a live não começou ou cair, ele espera e volta sozinho)

Comandos do chat (as respostas são faladas):
    Todo mundo:  !comandos  !mensagens  !top  !sons
                 e os comandos de som do config.json ("sons": {"ai": "ai.mp3"} -> !ai)
    Você e MODERADORES:  !mudo  !voltar  !limpar  !velocidade <-10 a 10>  !volume <0 a 100, +10 ou -10>
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
                         !pedidopresente (liga/desliga: cada presente vale um !pedir)
    Atalhos de teclado (ATALHOS): cada tecla faz o mesmo que um comando no chat, sem sair do jogo.
    Vem com o Ctrl+Alt+N para o !proximo.

osu! (o tosu abre sozinho, se estiver na pasta tosu):  !np (mapa atual)  !pp  !rank  !recorde
    e avisos automáticos de mapa novo (AVISAR_MAPA) e de recorde de PP da live (AVISAR_RECORDE)

Presentes: cada presente da live pode tocar um dos sons ("presentes": {"Rose": "fah"} no config.json).

Sem live: rode com o usuário "teste" e digite as mensagens do chat na janela (#presente Rose simula um presente).

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
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from collections import deque
from datetime import datetime, timedelta, timezone

from TikTokLive import TikTokLiveClient
from TikTokLive.client.errors import UserNotFoundError, UserOfflineError
from TikTokLive.events import CommentEvent, ConnectEvent, DisconnectEvent, GiftEvent, JoinEvent

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
# Servidor que gera a voz neural:
#   "gratis"     Microsoft grátis, sem cadastro (usa a VOZ acima). Falha de vez em quando.
#   "azure"      Microsoft Azure com a SUA chave: as mesmas vozes da VOZ acima, pelo serviço oficial
#   "google"     Google Cloud Text-to-Speech com a SUA chave (voz em VOZ_GOOGLE)
#   "elevenlabs" ElevenLabs com a SUA chave (voz em VOZ_ELEVENLABS)
#   "openai"     OpenAI com a SUA chave (voz em VOZ_OPENAI)
#   "piper"      Piper: grátis, roda no próprio PC, sem internet (voz em VOZ_PIPER). Leve.
#   "kokoro"     Kokoro: grátis, roda no próprio PC, sem internet (voz em VOZ_KOKORO). Soa melhor que o
#                Piper, mas precisa de um PC mais forte.
# Os pagos cobram na conta de quem pôs a chave (todos têm uma cota grátis por mês). As vozes do Piper e do
# Kokoro são baixadas na primeira vez que forem usadas (pasta "vozes", ao lado do programa).
# Se o servidor falhar, a mensagem sai na voz do Windows, como sempre.
SERVIDOR_VOZ = "gratis"
VOZ_PIPER = "faber"     # faber, cadu ou jeff
VOZ_KOKORO = "pf_dora"  # pf_dora (feminina), pm_alex ou pm_santa (masculinas)
CHAVE_AZURE = ""
REGIAO_AZURE = "brazilsouth"  # a região onde o recurso de Fala foi criado no portal da Azure
CHAVE_GOOGLE = ""
VOZ_GOOGLE = "pt-BR-Neural2-A"  # nomes em cloud.google.com/text-to-speech/docs/voices
CHAVE_ELEVENLABS = ""
VOZ_ELEVENLABS = "JBFqnCBsd6RMkjVDRZzb"  # o "Voice ID" da voz, na biblioteca de vozes do site
CHAVE_OPENAI = ""
VOZ_OPENAI = "nova"  # alloy, ash, coral, echo, fable, nova, onyx, sage ou shimmer
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
# comandos de som: "comando": {"arquivo": "arquivo da pasta sons" (aceita caminho completo), "volume": 0 a 100,
# "ligado": true ou false}. O volume do som é uma parte do volume geral (100 = igual à voz).
# No config.json também vale só "comando": "arquivo" (volume 100, ligado).
# Os arquivos destes vêm no zip.
SONS = {"ai": {"arquivo": "ai-ai-ai.mp3", "volume": 100, "ligado": True},
        "ban": {"arquivo": "banido_FzWiL58.mp3", "volume": 100, "ligado": True},
        "banido": {"arquivo": "banido_FzWiL58.mp3", "volume": 100, "ligado": True},
        "quecano": {"arquivo": "metal-pipe-clang.mp3", "volume": 100, "ligado": True},
        "cano": {"arquivo": "metal-pipe-clang.mp3", "volume": 100, "ligado": True},
        "zap": {"arquivo": "som-do-zap-zap-estourado.mp3", "volume": 100, "ligado": True},
        "fah": {"arquivo": "fahhhhhhhhhhhhhh.mp3", "volume": 100, "ligado": True}}
# presentes da live que tocam um dos SONS: "nome do presente": "som". ex.: {"Rose": "fah", "GG": "ai"}
# O nome é o que aparece na janela quando alguém manda o presente (maiúsculas e espaços tanto faz).
PRESENTES = {}
PEDIDOS_MAXIMOS = 30    # tamanho máximo da fila de pedidos de mapas do osu!
PEDIDOS_POR_PESSOA = 1  # quantos pedidos cada pessoa pode ter na fila ao mesmo tempo (0 = sem limite)
FILA_PEDIDOS = True     # False: cada !pedir vai direto para o seu chat do osu!, sem fila e sem a voz anunciar
PEDIR_COM_PRESENTE = False  # True: cada presente que a pessoa manda vale um !pedir (você e os mods não precisam)
PRESENTE_GERAL_LIVES = 0  # lives sem a pessoa pedir até os pedidos dela irem para todo mundo usar (0 = nunca vão)
COMANDOS_DESATIVADOS = []  # comandos desligados, sem o "!". ex.: ["copiar", "top"]
# atalhos de teclado: "tecla": "comando". Cada tecla faz o mesmo que você mandar o comando no chat, mesmo com o
# jogo na frente (só no Windows). O comando pode ter o que vem depois dele ("volume 50") e pode ser um som ("ai").
# Teclas: "ctrl+alt+n", "ctrl+shift+p", "pause", "ctrl+num5", "f13"... O jogo não recebe essas teclas: use as que
# você não usa nele. ex.: {"ctrl+alt+n": "proximo", "ctrl+alt+m": "mudo", "ctrl+alt+cima": "volume +10"}
ATALHOS = {"ctrl+alt+n": "proximo"}

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
    "TIKTOK_USUARIO", "VOZ", "SERVIDOR_VOZ", "CHAVE_AZURE", "REGIAO_AZURE", "CHAVE_GOOGLE", "VOZ_GOOGLE",
    "CHAVE_ELEVENLABS", "VOZ_ELEVENLABS", "CHAVE_OPENAI", "VOZ_OPENAI", "VOZ_PIPER", "VOZ_KOKORO", "VELOCIDADE", "VOLUME", "LER_NOME", "TAMANHO_MAXIMO", "FILA_MAXIMA", "PALAVRAS_BLOQUEADAS",
    "USUARIOS_SILENCIADOS", "PREFIXO", "MODERADORES", "ESPERA_COMANDO", "ESPERA_SOM", "SONS", "PRESENTES", "PEDIDOS_MAXIMOS", "PEDIDOS_POR_PESSOA", "FILA_PEDIDOS", "PEDIR_COM_PRESENTE", "PRESENTE_GERAL_LIVES", "COMANDOS_DESATIVADOS", "ATALHOS",
    "TOSU_URL", "AVISAR_MAPA", "AVISAR_RECORDE", "OSU_USUARIO", "OSU_IRC_SENHA", "WEB_PORTA", "WEB_REDE_LOCAL", "ABRIR_PAGINA")}
OPCOES_ANTIGAS = ("janela_pedidos", "atalho_proximo")  # opções de versões anteriores: ignoradas sem aviso
# (o atalho_proximo virou um dos ATALHOS: carregar_config passa ele para lá)
SECRETAS = ("osu_irc_senha", "chave_azure", "chave_google", "chave_elevenlabs", "chave_openai")  # a página nunca
# mostra: só diz se tem uma salva e deixa trocar
SERVIDORES_VOZ = {"gratis": "Microsoft grátis", "azure": "Azure", "google": "Google", "elevenlabs": "ElevenLabs",
                  "openai": "OpenAI", "piper": "Piper", "kokoro": "Kokoro"}  # servidor -> nome falado
DO_SERVIDOR = {"gratis": "da Microsoft", "azure": "da Azure", "google": "do Google", "elevenlabs": "da ElevenLabs",
               "openai": "da OpenAI", "piper": "do Piper", "kokoro": "do Kokoro"}  # "a chave da Azure", "a voz do Google"
VOZES_LOCAIS = {"piper": ("faber", "cadu", "jeff"), "kokoro": ("pf_dora", "pm_alex", "pm_santa")}
LIMITES = {"VELOCIDADE": (-10, 10), "VOLUME": (0, 100), "TAMANHO_MAXIMO": (1, None), "FILA_MAXIMA": (1, None),
           "ESPERA_COMANDO": (0, None), "ESPERA_SOM": (0, None), "PEDIDOS_MAXIMOS": (1, None), "PEDIDOS_POR_PESSOA": (0, None), "PRESENTE_GERAL_LIVES": (0, None), "WEB_PORTA": (0, 65535)}


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
        mover_sons_desligados()
        try:
            salvar_config()
        except OSError as e:
            avisos.append(f"mudei agora, mas não consegui gravar o config.json ({e}).")
    esquecer_silenciados()
    adiantar_voz_local()
    trocar_atalho()
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
        if nome == "PRESENTES":
            valor, avisos_presentes = conferir_presentes(valor)
            avisos += avisos_presentes
        if nome == "SERVIDOR_VOZ":
            valor = valor.strip().lower()
            if valor not in SERVIDORES_VOZ:
                avisos.append(f"\"{chave}\" vai de: {', '.join(SERVIDORES_VOZ)}. "
                              f"Mantive: {json.dumps(atual, ensure_ascii=False)}")
                continue
        if nome.startswith(("CHAVE_", "REGIAO_", "VOZ_")):
            valor = valor.strip()
        if nome in ("VOZ_PIPER", "VOZ_KOKORO"):
            valor = valor.lower()
            opcoes = VOZES_LOCAIS[nome[4:].lower()]
            if valor not in opcoes:
                avisos.append(f"\"{chave}\" vai de: {', '.join(opcoes)}. "
                              f"Mantive: {json.dumps(atual, ensure_ascii=False)}")
                continue
        if nome == "ATALHOS":
            valor, avisos_atalhos = conferir_atalhos(valor)
            avisos += avisos_atalhos
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
    if any(c.lower() == "atalhos" for c in config):  # depois do resto: os sons podem ter vindo junto
        avisos += atalhos_sem_comando()
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
    # versões antigas tinham só o "atalho_proximo": ele vira um dos "atalhos" ("" = desligado = nenhum atalho)
    antigo = next((c for c in config if c.lower() == "atalho_proximo"), None)
    migrou = antigo is not None and not any(c.lower() == "atalhos" for c in config)
    if migrou:
        tecla = config[antigo]
        config["atalhos"] = {tecla: "proximo"} if isinstance(tecla, str) and tecla.strip() else {}
    avisos = aplicar_config(config)
    sons_movidos = mover_sons_desligados()
    for aviso in avisos:
        print(f"*** config.json: {aviso}")
    for aviso in sons_configurados()[1]:
        print(f"*** som {aviso}")
    for presente, som in PRESENTES.items():
        if som not in SONS:
            print(f"*** presente \"{presente}\": não tem nenhum som {PREFIXO}{som} em \"sons\".")
    # versão nova com opções novas: acrescenta só elas, com o valor padrão, sem mexer no resto.
    # Com algum aviso não grava, para não apagar o que a pessoa ainda precisa corrigir.
    novas = [chave for chave in OPCOES if chave not in {c.lower() for c in config}]
    # sons no jeito antigo ("ai": "ai.mp3") são regravados com o volume, para a pessoa ver onde mudar
    sons_antigos = any(not isinstance(v, dict) or "volume" not in v or "ligado" not in v
                       for c, sons in config.items() if c.lower() == "sons" and isinstance(sons, dict)
                       for v in sons.values())
    if (novas or sons_antigos or sons_movidos or migrou) and not avisos:
        try:
            salvar_config()
            if migrou:
                print("O atalho do próximo pedido agora fica em \"atalhos\" no config.json, junto com os outros "
                      "atalhos de teclado que você quiser criar.\n")
            if novas:
                print(f"Opções novas no config.json (com o valor padrão): {', '.join(novas)}\n")
            if sons_antigos:
                print("Os sons do config.json agora têm \"volume\" (de 0 a 100) e \"ligado\" (true ou false) "
                      "ao lado do arquivo.\n")
            if sons_movidos:
                print(f"Estes sons saíram de comandos_desativados e ficaram com \"ligado\": false: "
                      f"{', '.join(sons_movidos)}\n")
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


DIAS_REGISTROS = 7  # planilhas de live e logs do tosu mais antigos que isso são apagados quando o programa abre


def apagar_antigos(pasta, padrao, formato):
    """Apaga da pasta os arquivos cujo nome bate com o padrão e cuja data no nome (grupo 1, no formato dado) tem
    mais de DIAS_REGISTROS dias. Outros arquivos da pasta não são mexidos. Devolve quantos apagou."""
    limite = datetime.now() - timedelta(days=DIAS_REGISTROS)
    apagados = 0
    try:
        nomes = os.listdir(pasta)
    except OSError:
        return 0
    for nome in nomes:
        m = re.fullmatch(padrao, nome)
        if not m:
            continue
        try:
            if datetime.strptime(m.group(1), formato) < limite:
                os.remove(os.path.join(pasta, nome))
                apagados += 1
        except (ValueError, OSError):  # data estranha no nome, ou o arquivo aberto em outro programa: fica para a próxima
            pass
    return apagados


def apagar_registros_antigos():
    """Apaga as planilhas live_DATA_HORA.csv da pasta registros e os logs "DATA HORA.log" do tosu\\logs (o tosu
    guarda um por vez que abre e nunca apaga; numa live chega a 7 MB) de mais de DIAS_REGISTROS dias."""
    planilhas = apagar_antigos(PASTA_REGISTROS, r"live_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2})\.csv", "%Y-%m-%d_%H-%M")
    logs = apagar_antigos(os.path.join(PASTA, "tosu", "logs"), r"(\d{4}-\d{2}-\d{2} \d{2}-\d{2}-\d{2})\.log",
                          "%Y-%m-%d %H-%M-%S")
    partes = []
    if planilhas:
        partes.append(f"{planilhas} {'registro' if planilhas == 1 else 'registros'}")
    if logs:
        partes.append(f"{logs} {'log' if logs == 1 else 'logs'} do tosu")
    if partes:
        print(f"[apaguei {' e '.join(partes)} de mais de {DIAS_REGISTROS} dias]")


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


ESPERA_VOZ_NEURAL = 5   # segundos que cada tentativa de baixar uma fala pode levar (normal: 1 a 2)
ESPERA_VOZ_PAGA = 10    # o mesmo, nos servidores pagos (alguns demoram um pouco mais para gerar)
TENTATIVAS_VOZ_NEURAL = 3  # o serviço falha à toa de vez em quando: tenta isso tudo antes de ir para a do Windows
PAUSA_VOZ_NEURAL = 60   # depois de uma falha, segundos sem tentar a voz neural (cada tentativa pode demorar)


class ErroDeConta(Exception):
    """O servidor pago recusou por causa da conta (chave errada, sem saldo, cota acabou): tentar de novo
    não adianta, a pessoa precisa conferir a chave ou a conta."""


def voz_em_uso() -> tuple:
    """(servidor, voz) que vai ler a próxima fala. A Maria do Windows vale com as vozes da Microsoft."""
    if SERVIDOR_VOZ in ("gratis", "azure"):
        return ("windows", "") if VOZ == "windows" else (SERVIDOR_VOZ, VOZ)
    return SERVIDOR_VOZ, {"google": VOZ_GOOGLE, "elevenlabs": VOZ_ELEVENLABS, "openai": VOZ_OPENAI,
                          "piper": VOZ_PIPER, "kokoro": VOZ_KOKORO}[SERVIDOR_VOZ]


# ---------------- Vozes que rodam no próprio PC (Piper e Kokoro) ----------------
# As vozes são baixadas na primeira vez que alguém escolhe o servidor (não vão no zip: são grandes).
# Enquanto baixa e carrega, as mensagens saem na voz do Windows.
PASTA_VOZES = os.path.join(PASTA, "vozes")
_PIPER_HF = "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR"
_KOKORO_GH = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
TAMANHO_VOZ_LOCAL = {"piper": "uns 60 MB", "kokoro": "uns 120 MB"}
ESPERA_ABRIR_VOZ_LOCAL = 15  # segundos que a fala espera a voz já baixada abrir (normal: 2 a 5)


class ErroVozLocal(Exception):
    """A voz do PC não conseguiu baixar ou carregar: tentar de novo na hora não adianta."""


class VozPreparando(Exception):
    """A voz do PC ainda está baixando ou carregando: esta mensagem sai na voz do Windows."""


class SemAudio(Exception):
    """O texto não tinha nada para falar (só símbolos, por exemplo)."""


def arquivos_voz_local(servidor: str, voz: str) -> dict:
    """Arquivos que a voz precisa, na pasta vozes -> de onde baixar."""
    if servidor == "piper":  # todas as vozes de pt-BR do Piper são CC0 (uso livre)
        nome = f"pt_BR-{voz}-medium.onnx"
        return {nome: f"{_PIPER_HF}/{voz}/medium/{nome}", nome + ".json": f"{_PIPER_HF}/{voz}/medium/{nome}.json"}
    # o Kokoro tem todas as vozes num arquivo só (modelo Apache 2.0)
    return {"kokoro-v1.0.int8.onnx": f"{_KOKORO_GH}/kokoro-v1.0.int8.onnx",
            "voices-v1.0.bin": f"{_KOKORO_GH}/voices-v1.0.bin"}


def baixar_arquivo(url: str, destino: str):
    temporario = destino + ".baixando"
    pedido = urllib.request.Request(url, headers={"User-Agent": "leitor-chat"})
    try:
        with urllib.request.urlopen(pedido, timeout=30) as r, open(temporario, "wb") as f:
            while bloco := r.read(1 << 20):
                f.write(bloco)
        os.replace(temporario, destino)
    except BaseException:
        apagar_arquivo(temporario)
        raise


def dados_espeak_sem_acento(nome: str, origem: str) -> str:
    """O eSpeak (que as duas usam para saber como se pronuncia cada palavra) não abre a pasta de dados
    se o caminho tiver acento, e muita gente tem acento no nome do usuário do Windows (C:\\Users\\Usuário).
    Dentro do .exe ele também não abre a pasta onde o .exe se desempacota (testado), e quando não abre
    ele FECHA O PROGRAMA. Por isso os dados são sempre copiados, uma vez, para uma pasta só com letras
    simples, e conferidos antes de usar."""
    marca = f"{nome}-{os.path.getsize(os.path.join(origem, 'phontab'))}"  # muda quando a biblioteca muda
    for base in (PASTA_VOZES, os.path.join(os.environ.get("ProgramData", ""), "LeitorChat"),
                 os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"), "LeitorChat")):
        if not base.isascii() or "~" in base or not os.path.isabs(base):
            continue
        destino = os.path.join(base, "espeak", marca)
        if os.path.exists(os.path.join(destino, "phontab")):
            return destino
        try:
            import shutil
            shutil.copytree(origem, destino + ".copiando", dirs_exist_ok=True)
            os.replace(destino + ".copiando", destino)
            return destino
        except OSError:
            continue
    raise ErroVozLocal("não achei uma pasta sem acento para os dados de pronúncia (eSpeak)")


def carregar_voz_local(servidor: str, voz: str):
    """Abre o modelo já baixado. Demora uns segundos, por isso é feito uma vez só."""
    if servidor == "piper":
        from piper import PiperVoice
        from piper.voice import ESPEAK_DATA_DIR
        return PiperVoice.load(os.path.join(PASTA_VOZES, f"pt_BR-{voz}-medium.onnx"),
                               espeak_data_dir=dados_espeak_sem_acento("piper", str(ESPEAK_DATA_DIR)))
    import espeakng_loader
    from kokoro_onnx import EspeakConfig, Kokoro
    return Kokoro(os.path.join(PASTA_VOZES, "kokoro-v1.0.int8.onnx"), os.path.join(PASTA_VOZES, "voices-v1.0.bin"),
                  espeak_config=EspeakConfig(
                      lib_path=espeakng_loader.get_library_path(),
                      data_path=dados_espeak_sem_acento("kokoro", espeakng_loader.get_data_path())))


trava_voz_local = threading.Lock()
vozes_locais = {}      # (servidor, voz) -> (modelo carregado, trava para gerar uma fala de cada vez)
preparando_local = set()
erros_voz_local = {}   # (servidor, voz) -> o que deu errado ao preparar


def chave_voz_local(servidor: str, voz: str) -> tuple:
    return servidor, voz if servidor == "piper" else ""  # o Kokoro carrega todas as vozes juntas


def preparar_voz_local(servidor: str, voz: str):
    """Thread: baixa o que falta e carrega a voz."""
    chave = chave_voz_local(servidor, voz)
    nome = SERVIDORES_VOZ[servidor]
    try:
        arquivos = arquivos_voz_local(servidor, voz)
        faltando = {a: u for a, u in arquivos.items() if not os.path.exists(os.path.join(PASTA_VOZES, a))}
        if faltando:
            print(f"[baixando a voz {voz} do {nome} ({TAMANHO_VOZ_LOCAL[servidor]}), só na primeira vez...]")
            os.makedirs(PASTA_VOZES, exist_ok=True)
            for arquivo, url in faltando.items():
                baixar_arquivo(url, os.path.join(PASTA_VOZES, arquivo))
        modelo = carregar_voz_local(servidor, voz)
        with trava_voz_local:
            vozes_locais[chave] = (modelo, threading.Lock())
        print(f"[voz do {nome} pronta]")
    except ImportError as e:
        with trava_voz_local:
            erros_voz_local[chave] = f"o {nome} não está instalado ({e}). Rode o instalar.bat."
    except Exception as e:
        with trava_voz_local:
            erros_voz_local[chave] = f"não consegui preparar a voz do {nome} ({type(e).__name__}: {e})"
    finally:
        with trava_voz_local:
            preparando_local.discard(chave)


def voz_local(servidor: str, voz: str) -> tuple:
    """A voz já carregada. Se ainda não está, começa a preparar e avisa com VozPreparando."""
    chave = chave_voz_local(servidor, voz)
    with trava_voz_local:
        if chave in vozes_locais:
            return vozes_locais[chave]
        if chave in erros_voz_local:
            raise ErroVozLocal(erros_voz_local.pop(chave))  # a próxima tentativa prepara de novo
        if chave not in preparando_local:
            preparando_local.add(chave)
            threading.Thread(target=preparar_voz_local, args=(servidor, voz), daemon=True,
                             name="preparar voz").start()
    raise VozPreparando()


def adiantar_voz_local():
    """Com o Piper ou o Kokoro escolhido, já começa a baixar e abrir a voz, sem esperar a primeira mensagem."""
    servidor, voz = voz_em_uso()
    if servidor in VOZES_LOCAIS:
        try:
            voz_local(servidor, voz)
        except (VozPreparando, ErroVozLocal):
            pass


def gerar_voz_local(servidor: str, voz: str, texto: str, velocidade: int, caminho: str):
    """Gera a fala no próprio PC e grava um .wav."""
    import wave
    modelo, trava = voz_local(servidor, voz)
    fator = max(0.5, min(2.0, 1 + velocidade / 10))
    with trava:  # o eSpeak não aguenta duas falas ao mesmo tempo, e num PC fraco não ganharia nada
        if servidor == "piper":
            from piper import SynthesisConfig
            with wave.open(caminho, "wb") as w:
                modelo.synthesize_wav(texto, w, syn_config=SynthesisConfig(length_scale=1 / fator))
            with wave.open(caminho) as w:
                if not w.getnframes():
                    raise SemAudio()
            return
        import numpy
        amostras, taxa = modelo.create(texto, voice=voz, speed=fator, lang="pt-br")
    if not len(amostras):
        raise SemAudio()
    with wave.open(caminho, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taxa)
        w.writeframes((numpy.clip(amostras, -1, 1) * 32767).astype("<i2").tobytes())


def pedir_voz_paga(servidor: str, voz: str, texto: str, velocidade: int) -> bytes:
    """Gera a fala num servidor pago, com a chave da pessoa. Devolve o mp3."""
    from xml.sax.saxutils import escape, quoteattr
    fator = 1 + velocidade / 10  # velocidade -10 a 10 -> 0 a 2 vezes a normal
    chave = {"azure": CHAVE_AZURE, "google": CHAVE_GOOGLE, "elevenlabs": CHAVE_ELEVENLABS,
             "openai": CHAVE_OPENAI}[servidor]
    nome, do = SERVIDORES_VOZ[servidor], DO_SERVIDOR[servidor]
    if not chave:
        raise ErroDeConta(f"falta a chave {do} (na página, em Voz, ou \"chave_{servidor}\" no config.json)")
    if not voz:
        raise ErroDeConta(f"falta escolher a voz {do}")
    if servidor == "azure":
        idioma = "-".join(voz.split("-")[:2])
        url = f"https://{REGIAO_AZURE or 'brazilsouth'}.tts.speech.microsoft.com/cognitiveservices/v1"
        corpo = (f"<speak version='1.0' xml:lang={quoteattr(idioma)}><voice name={quoteattr(voz)}>"
                 f"<prosody rate='{velocidade * 10:+d}%'>{escape(texto)}</prosody></voice></speak>").encode("utf-8")
        cabecalhos = {"Ocp-Apim-Subscription-Key": chave, "Content-Type": "application/ssml+xml",
                      "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3", "User-Agent": "leitor-chat"}
    elif servidor == "google":
        url = "https://texttospeech.googleapis.com/v1/text:synthesize?key=" + urllib.parse.quote(chave)
        corpo = json.dumps({"input": {"text": texto},
                            "voice": {"languageCode": "-".join(voz.split("-")[:2]), "name": voz},
                            "audioConfig": {"audioEncoding": "MP3", "speakingRate": max(0.25, min(4.0, fator))}})
        cabecalhos = {"Content-Type": "application/json"}
    elif servidor == "elevenlabs":
        url = (f"https://api.elevenlabs.io/v1/text-to-speech/{urllib.parse.quote(voz, safe='')}"
               "?output_format=mp3_44100_128")
        corpo = json.dumps({"text": texto, "model_id": "eleven_flash_v2_5", "language_code": "pt",
                            "voice_settings": {"speed": max(0.7, min(1.2, 1 + velocidade * 0.03))}})
        cabecalhos = {"xi-api-key": chave, "Content-Type": "application/json", "Accept": "audio/mpeg"}
    else:  # openai
        url = "https://api.openai.com/v1/audio/speech"
        corpo = json.dumps({"model": "tts-1", "input": texto, "voice": voz, "response_format": "mp3",
                            "speed": max(0.25, min(4.0, fator))})
        cabecalhos = {"Authorization": "Bearer " + chave, "Content-Type": "application/json"}
    if isinstance(corpo, str):
        corpo = corpo.encode("utf-8")
    pedido = urllib.request.Request(url, data=corpo, headers=cabecalhos, method="POST")
    try:
        with urllib.request.urlopen(pedido, timeout=ESPERA_VOZ_PAGA) as r:
            dados = r.read()
    except urllib.error.HTTPError as e:
        try:
            detalhe = " ".join(e.read(500).decode("utf-8", "replace").split())
        except Exception:
            detalhe = ""
        if e.code in (401, 402, 403, 429) or (e.code == 400 and servidor == "google" and "API key" in detalhe):
            motivo = {401: "chave errada", 402: "sem saldo", 403: "chave sem permissão ou região errada",
                      429: "limite ou cota da conta acabou"}.get(e.code, "chave errada")
            raise ErroDeConta(f"{nome} recusou ({motivo}). {detalhe[:200]}") from None
        if 400 <= e.code < 500:  # pedido recusado: quase sempre a voz escolhida não existe
            raise ErroDeConta(f"{nome} recusou o pedido (confira o nome da voz \"{voz}\"). {detalhe[:200]}") from None
        raise  # erro do servidor (500...): passa, tenta de novo
    if servidor == "google":
        dados = base64.b64decode(json.loads(dados)["audioContent"])
    if not dados:
        raise OSError(f"{nome} não mandou áudio")
    return dados


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
    for velho in glob.glob(os.path.join(pasta, "tiktok_fala*")):  # sobras de quando o programa fechou falando
        apagar_arquivo(velho)
    numeros = itertools.count()
    baixador = ThreadPoolExecutor(max_workers=2, thread_name_prefix="voz")
    preparadas = {}  # (texto, voz, velocidade) -> a fala sendo baixada (ou já baixada) antes da vez dela
    sapi = None  # só criada se a voz do Windows for usada
    tentar_neural_em = 0.0  # até esta hora a voz neural falhou há pouco: usa a do Windows direto
    em_reserva = False      # já avisou que está na voz do Windows
    avisou_baixando = set()  # vozes do PC que já avisou que estão sendo baixadas

    def falar_windows(frase: str):
        nonlocal sapi
        if sapi is None:
            sapi = voz_windows()
        sapi.Rate = VELOCIDADE
        sapi.Volume = VOLUME
        sapi.Speak(frase)

    def baixar(texto: str, servidor: str, voz: str, velocidade: int) -> str:
        """O serviço grátis da Microsoft falha à toa em cerca de 1 a cada 10 pedidos (conexão recusada,
        resposta vazia, pedido que trava), e na hora seguinte funciona. Por isso tenta algumas vezes antes
        de desistir. Nos pagos também, menos quando o problema é a conta (aí tentar de novo não adianta).
        As do PC (Piper e Kokoro) não dependem de rede, então não adianta tentar de novo."""
        if servidor in VOZES_LOCAIS:
            caminho = os.path.join(pasta, f"tiktok_fala_{next(numeros)}.wav")
            try:
                gerar_voz_local(servidor, voz, texto, velocidade, caminho)
            except BaseException:
                apagar_arquivo(caminho)
                raise
            return caminho
        caminho = os.path.join(pasta, f"tiktok_fala_{next(numeros)}.mp3")
        for tentativa in range(1, TENTATIVAS_VOZ_NEURAL + 1):
            try:
                if servidor == "gratis":
                    asyncio.run(asyncio.wait_for(
                        edge_tts.Communicate(texto, voz, rate=f"{velocidade * 10:+d}%").save(caminho),
                        ESPERA_VOZ_NEURAL))
                else:
                    with open(caminho, "wb") as f:
                        f.write(pedir_voz_paga(servidor, voz, texto, velocidade))
                return caminho
            except BaseException as e:
                apagar_arquivo(caminho)
                sem_letras = isinstance(e, NoAudioReceived) and not any(c.isalnum() for c in texto)
                if tentativa == TENTATIVAS_VOZ_NEURAL or sem_letras or isinstance(e, ErroDeConta) \
                        or not isinstance(e, Exception):
                    raise
                time.sleep(0.3)

    def chave(texto: str) -> tuple:
        return (texto, *voz_em_uso(), VELOCIDADE)

    def conta_atual() -> tuple:
        """Muda quando a pessoa troca o servidor, a voz, a chave ou a região: aí vale tentar de novo na hora."""
        return voz_em_uso(), CHAVE_AZURE, REGIAO_AZURE, CHAVE_GOOGLE, CHAVE_ELEVENLABS, CHAVE_OPENAI

    def usar_windows() -> bool:
        nonlocal tentar_neural_em, ultima_conta
        if conta_atual() != ultima_conta:
            ultima_conta = conta_atual()
            tentar_neural_em = 0.0
        return voz_em_uso()[0] == "windows" or time.time() < tentar_neural_em

    ultima_conta = conta_atual()

    def descartar(fala):
        """Fala baixada antes da hora que não vai mais ser usada (a voz mudou, ou o !limpar apagou a fila)."""
        if not fala.cancel():
            fala.add_done_callback(lambda f: f.exception() is None and apagar_arquivo(f.result()))

    def preparar_proxima():
        """Chamada enquanto uma fala toca: já baixa a próxima da fila. Uma resposta que chega no meio
        passa na frente, e é ela que passa a ser baixada."""
        if usar_windows():
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
            if usar_windows():
                falar_windows(texto)
                continue
            servidor = DO_SERVIDOR[voz_em_uso()[0]]
            fala = preparadas.pop(chave(texto), None) or baixador.submit(baixar, *chave(texto))
            try:
                caminho = fala.result()
            except VozPreparando:
                # a voz do PC ainda está baixando ou abrindo. Só abrindo leva uns segundos: espera.
                # Baixando pode levar minutos: esta sai na do Windows, a próxima tenta de novo.
                atual = chave_voz_local(*voz_em_uso())
                baixando = any(not os.path.exists(os.path.join(PASTA_VOZES, a))
                               for a in arquivos_voz_local(*voz_em_uso()))
                caminho = None
                if not baixando:
                    limite = time.time() + ESPERA_ABRIR_VOZ_LOCAL
                    while caminho is None and time.time() < limite:
                        time.sleep(0.2)
                        try:
                            caminho = baixar(*chave(texto))
                        except VozPreparando:
                            pass
                        except Exception as erro:  # não abriu: esta sai na do Windows
                            print(f"*** A voz {servidor} não funcionou: {erro}")
                            break
                if caminho is None:
                    if baixando and atual not in avisou_baixando:
                        avisou_baixando.add(atual)
                        falar_windows(f"Estou baixando a voz {servidor}. Enquanto isso, vou usar a voz do Windows.")
                    falar_windows(texto)
                    continue
            except (NoAudioReceived, SemAudio):
                # mesmo depois das tentativas o serviço não mandou áudio: ou o texto só tem símbolos,
                # ou o serviço não quis ler este texto. O resto do chat segue na voz de sempre.
                if any(c.isalnum() for c in texto):
                    print(f"[a voz {servidor} não leu, indo na do Windows: {texto}]")
                    falar_windows(texto)
                else:
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
                    if isinstance(e, ErroVozLocal):
                        print(f"*** A voz {servidor} não funcionou: {e}\n*** Usando a voz do Windows e "
                              f"tentando de novo a cada {PAUSA_VOZ_NEURAL} segundos.")
                        falar_windows(f"A voz {servidor} não funcionou. Vou usar a voz do Windows.")
                    elif isinstance(e, ErroDeConta):
                        print(f"*** A voz {servidor} não funcionou: {e}\n*** Usando a voz do Windows e "
                              f"tentando de novo a cada {PAUSA_VOZ_NEURAL} segundos (ou assim que mudar a chave).")
                        falar_windows(f"A voz {servidor} não funcionou. Confira a chave na página. "
                                      "Vou usar a voz do Windows.")
                    else:
                        print(f"*** A voz {servidor} falhou ({type(e).__name__}: {e}). Usando a voz do "
                              f"Windows e tentando de novo a cada {PAUSA_VOZ_NEURAL} segundos.")
                        falar_windows("A voz da internet falhou. Vou usar a voz do Windows.")
                falar_windows(texto)
                continue
            if em_reserva:
                em_reserva = False
                print(f"[a voz {servidor} voltou]")
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
# PEDIR_COM_PRESENTE: quantos pedidos cada pessoa ainda pode fazer. Fica gravado, porque a pessoa pagou:
# se o programa fechar, ou a live acabar antes de ela pedir, o crédito continua lá na próxima.
ARQUIVO_CREDITOS = os.path.join(PASTA, "pedidos_por_presente.json")
creditos = {}           # usuário em minúsculo -> pedidos que a pessoa ainda pode fazer
creditos_gravados = {}  # o que está no arquivo: creditos + os pedidos pagos que ainda estão na fila
# PRESENTE_GERAL_LIVES: os pedidos que ninguém usou vão para o geral, que fica em creditos como se fosse uma
# pessoa (o * não existe em nome de usuário do TikTok). "lotes" guarda em qual live cada um chegou.
GERAL = "*geral*"
CHAVE_LIVES = "*lives*"
lives = {"numero": 0, "sala": "", "lotes": {}}  # lotes: usuário -> {número da live (texto): quantos pedidos}
trava_creditos = threading.RLock()


def carregar_creditos():
    global creditos, creditos_gravados, lives
    try:
        with open(ARQUIVO_CREDITOS, encoding="utf-8") as f:
            dados = json.load(f)
        creditos = {str(u).lower(): n for u, n in dados.items() if isinstance(n, int) and n > 0}
        guardado = dados.get(CHAVE_LIVES)
        if isinstance(guardado, dict):
            lotes = guardado.get("lotes")
            lives = {"numero": int(guardado.get("numero", 0)), "sala": str(guardado.get("sala", "")),
                     "lotes": {u: {str(int(live)): int(n) for live, n in lote.items()}
                               for u, lote in (lotes if isinstance(lotes, dict) else {}).items()}}
        creditos_gravados = dados
        acertar_lotes()
    except FileNotFoundError:
        pass
    except (ValueError, TypeError, OSError, AttributeError) as e:
        print(f"*** Não consegui ler {os.path.basename(ARQUIVO_CREDITOS)} ({e}). Os pedidos por presente "
              f"começam do zero; o arquivo só é regravado no próximo presente.")


def acertar_lotes():
    """Deixa os lotes com a mesma soma dos créditos. O que sobra sem lote (arquivo de uma versão antiga, mexido
    à mão, ou pedido que voltou da fila) conta como desta live; gastou um, todos recomeçam desta."""
    numero = str(lives["numero"])
    for uid in [u for u in lives["lotes"] if u not in creditos]:
        del lives["lotes"][uid]
    for uid, n in creditos.items():
        if uid == GERAL:
            continue
        lote = lives["lotes"].get(uid, {})
        falta = n - sum(lote.values())
        if falta > 0:
            lote[numero] = lote.get(numero, 0) + falta
        elif falta < 0:
            lote = {numero: n}
        lives["lotes"][uid] = lote


def comecou_live(sala) -> int:
    """Conectou numa live. Se for uma nova (cair e voltar, ou reabrir o programa, é a mesma sala), manda para o
    geral os pedidos de quem passou PRESENTE_GERAL_LIVES lives inteiras sem pedir, sem contar a live em que o
    presente chegou. Só contam as lives que começam com o pedido por presente ligado.
    Devolve quantos foram."""
    sala = str(sala or "")
    if not sala or sala == lives["sala"]:
        return 0
    with trava_creditos:
        acertar_lotes()
        lives["sala"] = sala
        total = 0
        if PEDIR_COM_PRESENTE:
            lives["numero"] += 1
        if PEDIR_COM_PRESENTE and PRESENTE_GERAL_LIVES:
            for uid, lote in list(lives["lotes"].items()):
                velhos = [x for x in lote if lives["numero"] - 1 - int(x) >= PRESENTE_GERAL_LIVES]
                n = sum(lote.pop(x) for x in velhos)
                if not n:
                    continue
                total += n
                creditos[uid] -= n
                if not creditos[uid]:
                    del creditos[uid], lives["lotes"][uid]
                print(f"[{n} {'pedido' if n == 1 else 'pedidos'} de @{uid} {'foi' if n == 1 else 'foram'} para o geral]")
            if total:
                creditos[GERAL] = creditos.get(GERAL, 0) + total
        gravar_creditos()
        return total


def renovar_creditos(uid: str):
    """A pessoa fez um pedido: as lives dos que ela ainda tem voltam a contar desta."""
    with trava_creditos:
        if uid in creditos and uid != GERAL:
            lives["lotes"][uid] = {str(lives["numero"]): creditos[uid]}
            gravar_creditos()


def gravar_creditos():
    """Grava os créditos (com a trava_creditos na mão). Um pedido pago que ainda está na fila conta como
    crédito no arquivo: a fila zera ao fechar o programa, e assim a pessoa pode pedir de novo na próxima live."""
    global creditos_gravados
    dados = dict(creditos)
    for p in list(pedidos):
        if p.get("pago"):
            dados[p["pago"]] = dados.get(p["pago"], 0) + 1
    if not dados and not creditos_gravados:
        return
    dados[CHAVE_LIVES] = json.loads(json.dumps(lives))  # uma cópia
    if dados == creditos_gravados:
        return
    try:
        with open(ARQUIVO_CREDITOS, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        creditos_gravados = dados
    except OSError as e:
        print(f"*** Não consegui gravar {os.path.basename(ARQUIVO_CREDITOS)} ({e}).")


def mudar_creditos(uid: str, quanto: int) -> int:
    """Soma (ou tira, com negativo) pedidos da pessoa e grava. Devolve quantos ela tem agora."""
    with trava_creditos:
        n = max(0, creditos.get(uid, 0) + quanto)
        if n:
            creditos[uid] = n
        else:
            creditos.pop(uid, None)
        acertar_lotes()
        gravar_creditos()
        return n


def devolver_credito(p: dict):
    """Pedido pago com presente que saiu da fila sem ser atendido (!cancelar, !remover, !zerarpedidos)."""
    if p.get("pago"):
        mudar_creditos(p["pago"], 1)  # para quem pagou: a pessoa ou o geral


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
    """Mantém o pedidos.txt atualizado, para você ver a fila durante a live (e os créditos dos pedidos pagos)."""
    with trava_creditos:
        gravar_creditos()
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
                "esperasom", "proximo", "remover", "fecharpedidos", "abrirpedidos", "zerarpedidos", "limitepedidos", "porpessoa", "filapedidos",
                "pedidopresente"]
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
    "volume": "Muda o volume da voz, de 0 a 100. Com + ou - na frente, sobe ou desce a partir do volume de agora (volume +10, volume -10).",
    "voz": "Troca a voz: francisca, thalita, antonio, raquel, duarte ou maria. Com sotaque de gringo: ava, emma, brian, william, "
           "vivienne, remy, seraphina, florian, giuseppe ou hyunsu. No Piper: faber, cadu ou jeff. No Kokoro: dora, "
           "alex ou santa. Sem nome, fala a lista.",
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
    "pedidopresente": "Liga ou desliga o pedido por presente: ligado, cada presente que a pessoa manda vale um !pedir. Não vale para você e os mods.",
    "mod": "Torna alguém moderador (usuário do TikTok, sem @).",
    "desmod": "Tira alguém dos moderadores.",
}
PROTEGIDOS = ("ligar", "desligar")  # se desligar estes pelo chat, não daria para religar pelo chat


def desativado(cmd: str) -> bool:
    """Comando desligado em COMANDOS_DESATIVADOS, ou som com "ligado": false em SONS."""
    if cmd in SONS:
        return not SONS[cmd]["ligado"]
    return APELIDOS_COMANDO.get(cmd, cmd) in [c.lstrip(PREFIXO).lower() for c in COMANDOS_DESATIVADOS]


def mover_sons_desligados() -> list:
    """Sons que estão em COMANDOS_DESATIVADOS (de versões anteriores, ou escritos lá à mão) passam a
    ficar desligados no próprio som, que é onde a página e o !ligar mexem. Devolve os que mudaram."""
    global COMANDOS_DESATIVADOS, SONS
    movidos = [c for c in COMANDOS_DESATIVADOS if nome_de_som(c.lstrip(PREFIXO)) in SONS]
    if movidos:
        nomes = {nome_de_som(c.lstrip(PREFIXO)) for c in movidos}
        SONS = {n: {**som, "ligado": som["ligado"] and n not in nomes} for n, som in SONS.items()}
        COMANDOS_DESATIVADOS = [c for c in COMANDOS_DESATIVADOS if c not in movidos]
    return movidos


FALADO = {"proximo": "próximo", "fecharpedidos": "fechar pedidos", "abrirpedidos": "abrir pedidos",
          "zerarpedidos": "zerar pedidos", "limitepedidos": "limite pedidos", "porpessoa": "por pessoa",
          "filapedidos": "fila pedidos", "esperasom": "espera som", "pedidopresente": "pedido presente"}  # como a voz fala cada comando

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
    "arquivo" ou {"arquivo": "...", "volume": 0 a 100, "ligado": true/false}.
    Devolve (sons arrumados no segundo jeito, avisos)."""
    limpos, avisos = {}, []
    for comando, valor in sons.items():
        nome = nome_de_som(comando.lstrip(PREFIXO))
        arquivo, volume, ligado = valor, 100, True
        if isinstance(valor, dict):
            arquivo, volume, ligado = valor.get("arquivo", ""), valor.get("volume", 100), valor.get("ligado", True)
            if not isinstance(ligado, bool):
                avisos.append(f"o \"ligado\" do som \"{comando}\" deveria ser true ou false. Deixei ligado.")
                ligado = True
            if not isinstance(volume, (int, float)) or isinstance(volume, bool):
                avisos.append(f"o volume do som \"{comando}\" deveria ser um número de 0 a 100. Usei 100.")
                volume = 100
            elif not 0 <= volume <= 100:
                avisos.append(f"o volume do som \"{comando}\" vai de 0 a 100. Usei {max(0, min(100, round(volume)))}.")
            volume = max(0, min(100, round(volume)))
        if not isinstance(arquivo, str):
            avisos.append(f"o som \"{comando}\" deveria ser \"arquivo\" ou "
                          f"{{\"arquivo\": \"...\", \"volume\": 100, \"ligado\": true}}. Ignorei.")
        elif not nome or not arquivo.strip():
            avisos.append(f"o som \"{comando}\" precisa de um nome (letras ou números) e de um arquivo. Ignorei.")
        elif nome_reservado(nome):
            avisos.append(f"\"{comando}\" já é um comando do programa: dê outro nome para esse som. Ignorei.")
        elif nome in limpos:
            avisos.append(f"o som \"{comando}\" aparece duas vezes. Usei o primeiro.")
        else:
            limpos[nome] = {"arquivo": arquivo.strip(), "volume": volume, "ligado": ligado}
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


# ---------------- Presentes: um presente da live toca um dos sons (PRESENTES no config.json) ----------------
presentes_vistos = deque(maxlen=30)  # presentes que chegaram desde que o programa abriu (a página sugere)
sequencias = {}  # (usuário, presente) -> (horário, quantos até agora): sequência (combo) que já tocou o som
SEQUENCIA_ESQUECIDA = 60  # sem o aviso de fim da sequência, depois disso ela conta como terminada


def conferir_presentes(presentes: dict) -> tuple:
    """Tira os espaços do nome do presente e arruma o nome do som ("!Fah" -> "fah").
    Devolve (presentes arrumados, avisos)."""
    limpos, avisos, vistos = {}, [], set()
    for presente, som in presentes.items():
        chave, som = nome_de_som(presente), nome_de_som(som.lstrip(PREFIXO))
        if not chave or not som:
            avisos.append(f"o presente \"{presente}\" precisa de um nome e de um som. Ignorei.")
        elif chave in vistos:
            avisos.append(f"o presente \"{presente}\" aparece duas vezes. Usei o primeiro.")
        else:
            vistos.add(chave)
            limpos[presente.strip()] = som
    return limpos, avisos


def presente_configurado(presente: str):
    """O nome como está em PRESENTES ("Rose" acha "rose"), ou None."""
    return next((p for p in PRESENTES if nome_de_som(p) == nome_de_som(presente)), None)


def receber_presente(user, presente: str, id_presente, streaking: bool, quantidade: int, dono: str):
    """Um presente da live: toca o som dele. Numa sequência (combo) o TikTok avisa a cada toque e no
    fim; o som toca só no primeiro aviso, para não virar uma metralhadora."""
    uid = (user.unique_id or "").lower()
    nome = carregar_apelidos().get(uid, user.nick_name or user.unique_id)
    agora = time.time()
    for k in [k for k, (t, _) in sequencias.items() if agora - t > SEQUENCIA_ESQUECIDA]:
        del sequencias[k]
    chave = (uid, id_presente or presente)
    anterior = sequencias.pop(chave, None)
    if streaking:
        sequencias[chave] = (agora, max(quantidade, anterior[1] if anterior else 0))
    # cada aviso da sequência traz o total até ali: conta só os presentes novos
    novos = max(0, quantidade - anterior[1]) if anterior else quantidade
    if PEDIR_COM_PRESENTE and novos and uid:
        n = mudar_creditos(uid, novos)
        print(f"[{nome} pode pedir {n} {'mapa' if n == 1 else 'mapas'}]")
        if n == novos and not pausado and not silenciado(uid, dono):  # antes não podia: avisa como pedir
            falar(f"{nome}, valeu pelo presente! Agora você pode pedir {'um mapa' if n == 1 else f'{n} mapas'} "
                  f"com exclamação pedir.")
    if anterior:  # continuação ou fim de uma sequência que já tocou
        if not streaking and quantidade > 1:
            print(f"[{nome} mandou {quantidade}x {presente}]")
        return
    if presente in presentes_vistos:
        presentes_vistos.remove(presente)
    presentes_vistos.append(presente)
    configurado = presente_configurado(presente)
    som = PRESENTES[configurado] if configurado else None
    if som is None:
        print(f"[presente {presente} de {nome}]")
        return
    if silenciado(uid, dono):
        print(f"[presente {presente} de {nome} (silenciado): o som {PREFIXO}{som} não tocou]")
        return
    if pausado:
        print(f"[presente {presente} de {nome}: no mudo, o som {PREFIXO}{som} não tocou]")
        return
    arquivo = sons_disponiveis().get(som)
    if not arquivo:
        print(f"[presente {presente} de {nome}: não achei o som {PREFIXO}{som} (ou o arquivo dele)]")
        return
    print(f"[presente {presente} de {nome}: som {PREFIXO}{som}]")
    tocar_som(arquivo)



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


trava_proximo = threading.Lock()  # o !proximo do chat e o atalho de teclado ao mesmo tempo


def proximo_pedido():
    """Manda o próximo pedido da fila (o !proximo, também pelos ATALHOS)."""
    with trava_proximo:
        if not pedidos:
            falar("Não tem nenhum pedido na fila.")
            return
        p = pedidos.pop(0)
        salvar_pedidos()
    threading.Thread(target=abrir_pedido, args=(p,), daemon=True).start()  # o IRC leva uns segundos
    print(f"[pedido de {p['nome']}: {p['texto']}]\n  {p['url']}")
    falar(f"Próximo pedido, de {p['nome']}. Faltam {len(pedidos)}.")


# ---------------- Atalhos de teclado (Windows) ----------------
# Cada tecla dos ATALHOS faz o mesmo que você mandar um comando no chat. Ela é registrada no Windows
# (RegisterHotKey): funciona com o osu! ou qualquer outra janela na frente. O Windows entrega a tecla só para
# o programa, então o jogo não a recebe: escolha as que você não usa nele.
MODIFICADORES = {"ctrl": 0x2, "alt": 0x1, "shift": 0x4, "win": 0x8}
TECLAS_ESPECIAIS = {"espaco": 0x20, "enter": 0x0D, "tab": 0x09, "esc": 0x1B, "insert": 0x2D,
                    "delete": 0x2E, "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
                    "cima": 0x26, "baixo": 0x28, "esquerda": 0x25, "direita": 0x27, "pause": 0x13,
                    "scrolllock": 0x91, "printscreen": 0x2C,
                    **{f"f{n}": 0x6F + n for n in range(1, 25)},
                    **{f"num{n}": 0x60 + n for n in range(10)}}
OUTROS_NOMES_TECLA = {"space": "espaco", "espaço": "espaco", "up": "cima", "down": "baixo", "left": "esquerda",
                      "right": "direita"}
WM_HOTKEY, WM_TROCAR_ATALHO = 0x0312, 0x8001  # 0x8001 = WM_APP + 1: aviso nosso para trocar as teclas
id_thread_atalho = None
DONO = ""  # o seu usuário do TikTok: os atalhos mandam os comandos como se fosse você no chat


def nome_do_atalho(texto: str):
    """ "Alt + Ctrl + N" -> "ctrl+alt+n" (sempre do mesmo jeito, para achar teclas repetidas).
    None se não der para entender."""
    *mods, tecla = [p.strip().lower() for p in texto.replace(" ", "").split("+")]
    tecla = OUTROS_NOMES_TECLA.get(tecla, tecla)
    if not tecla or any(m not in MODIFICADORES for m in mods) or len(set(mods)) != len(mods):
        return None
    if not (len(tecla) == 1 and tecla.isascii() and tecla.isalnum()) and tecla not in TECLAS_ESPECIAIS:
        return None
    return "+".join([m for m in MODIFICADORES if m in mods] + [tecla])


def ler_atalho(texto: str) -> tuple:
    """ "ctrl+alt+n" (já passado por nome_do_atalho) -> (modificadores, código da tecla) para o Windows."""
    *mods, tecla = texto.split("+")
    codigo = ord(tecla.upper()) if len(tecla) == 1 else TECLAS_ESPECIAIS[tecla]
    return sum(MODIFICADORES[m] for m in mods), codigo


def comando_do_atalho(texto: str) -> str:
    """ "!vol 50" -> "vol 50": guardado sem o prefixo, para continuar valendo se o PREFIXO mudar."""
    texto = texto.strip()
    if texto.startswith(PREFIXO):
        texto = texto[len(PREFIXO):]
    return texto.lstrip("!").strip()


def conferir_atalhos(atalhos: dict) -> tuple:
    """Confere os ATALHOS do config.json ou da página. Devolve (atalhos, avisos)."""
    certos, avisos = {}, []
    for tecla, comando in atalhos.items():
        nome = nome_do_atalho(tecla)
        if not nome:
            avisos.append(f"atalho \"{tecla}\": não entendi a tecla. Use teclas como ctrl+alt+n, ctrl+shift+p, "
                          "pause ou f13. Ignorei esse atalho.")
            continue
        comando = comando_do_atalho(comando)
        if not comando:
            avisos.append(f"atalho \"{tecla}\": falta o comando, como \"proximo\" ou \"volume 50\". "
                          "Ignorei esse atalho.")
            continue
        if nome in certos:
            avisos.append(f"a tecla {nome} aparece em mais de um atalho. Ficou o último: {PREFIXO}{comando}.")
        certos[nome] = comando
    return certos, avisos


def comando_base(comando: str) -> str:
    """ "vol 50" -> "volume" (o comando de verdade, sem o que vem depois e sem o nome curto)."""
    partes = comando.split(maxsplit=1)
    primeiro = partes[0].lower() if partes else ""
    return APELIDOS_COMANDO.get(primeiro, primeiro)


def atalhos_sem_comando() -> list:
    """Avisos dos ATALHOS que mandam um comando que não existe (escrita errada, ou som que foi apagado)."""
    return [f"o atalho {tecla} manda {PREFIXO}{comando}, mas não existe esse comando nem esse som."
            for tecla, comando in ATALHOS.items()
            if comando_base(comando) not in TODOS_COMANDOS and comando_base(comando) not in SONS]


def usar_atalho(tecla: str, comando: str):
    """Apertaram a tecla: faz o mesmo que você mandar o comando no chat."""
    from types import SimpleNamespace
    print(f"[atalho {tecla}: {PREFIXO}{comando}]")
    cmd = comando_base(comando)
    if desativado(cmd):
        print(f"  ({PREFIXO}{cmd} está desligado: ligue de novo para o atalho funcionar)")
        return
    apelido = carregar_apelidos().get(DONO.lower(), DONO)
    if not tratar_comando(SimpleNamespace(unique_id=DONO, nick_name=DONO), nome_para_falar(apelido),
                          PREFIXO + comando, DONO):
        if cmd in SONS:
            print(f"*** O atalho {tecla} toca o som {PREFIXO}{cmd}, mas o arquivo dele não está na pasta sons.")
        else:
            print(f"*** O atalho {tecla} manda {PREFIXO}{comando}, mas não existe esse comando nem esse som. "
                  "Troque na página ou no config.json (atalhos).")


def vigia_atalho():
    """Espera os ATALHOS. Quando eles mudam (página ou config), mudar_config avisa e ele troca as teclas."""
    global id_thread_atalho
    import ctypes
    from ctypes import wintypes
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    id_thread_atalho = kernel32.GetCurrentThreadId()
    msg = wintypes.MSG()
    user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)  # cria a fila de mensagens desta thread
    registrados = {}  # id no Windows -> (tecla, comando), só os que o Windows aceitou
    valendo = None    # os ATALHOS de quando as teclas foram registradas

    def registrar_atalhos():
        nonlocal valendo
        for i in registrados:
            user32.UnregisterHotKey(None, i)
        registrados.clear()
        valendo = dict(ATALHOS)
        ocupadas = []
        for i, (tecla, comando) in enumerate(valendo.items(), 1):
            mods, codigo = ler_atalho(tecla)
            if user32.RegisterHotKey(None, i, mods | 0x4000, codigo):  # 0x4000: segurar não repete
                registrados[i] = (tecla, comando)
            else:
                ocupadas.append(tecla)
        if registrados:
            print("Atalhos de teclado: " + ", ".join(f"{t} = {PREFIXO}{c}" for t, c in registrados.values()))
        if ocupadas:
            print(f"*** Não consegui usar {'a tecla' if len(ocupadas) == 1 else 'as teclas'} {', '.join(ocupadas)}: "
                  "outro programa já usa. Escolha outra na página ou no config.json (atalhos).")

    registrar_atalhos()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        if msg.message == WM_HOTKEY and msg.wParam in registrados:
            tecla, comando = registrados[msg.wParam]
            try:
                usar_atalho(tecla, comando)
            except Exception as e:  # um erro aqui não pode desligar os atalhos
                print(f"*** Erro no atalho {tecla}: {e}")
        elif msg.message == WM_TROCAR_ATALHO and valendo != ATALHOS:
            registrar_atalhos()


def trocar_atalho():
    if id_thread_atalho:
        import ctypes
        ctypes.windll.user32.PostThreadMessageW(id_thread_atalho, WM_TROCAR_ATALHO, 0, 0)


def iniciar_atalho(dono: str):
    global DONO
    DONO = dono
    if sys.platform == "win32":
        threading.Thread(target=vigia_atalho, daemon=True).start()


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
                n = int(arg.replace(" ", ""))  # "- 10" também vale
            except ValueError:
                falar(f"Use: exclamação {FALADO.get(cmd, cmd)} e um número." +
                      (" Com mais ou menos na frente, sobe ou desce: exclamação volume mais 10." if cmd == "volume" else ""))
                return True
            if cmd == "volume" and arg.strip()[0] in "+-":  # !volume +10 / -10: sobe ou desce a partir do de agora
                n = max(0, min(100, VOLUME + n))  # já no limite: sem o aviso de "vai de 0 a 100"
            mudar_config({chave: n})  # fora do limite, usa o limite mais próximo
            valor = globals()[OPCOES[chave]]
            if cmd == "porpessoa" and valor in (0, 1):
                resposta = "Agora cada pessoa pode pedir quantos mapas quiser." if valor == 0 else \
                    "Agora cada pessoa pode ter um pedido na fila."
            falar(resposta.format(valor))
            return True
        if cmd == "voz":
            if SERVIDOR_VOZ in VOZES_LOCAIS:
                nomes = {v.split("_")[-1]: v for v in VOZES_LOCAIS[SERVIDOR_VOZ]}  # pf_dora -> dora
                voz = nomes.get(arg.lower().strip())
                if not voz:
                    falar(f"Vozes do {SERVIDORES_VOZ[SERVIDOR_VOZ]}: {', '.join(n.title() for n in nomes)}. "
                          "Use: exclamação voz e o nome.")
                    return True
                mudar_config({f"voz_{SERVIDOR_VOZ}": voz})
                falar("Voz trocada.")
                return True
            if SERVIDOR_VOZ not in ("gratis", "azure"):
                falar(f"Agora quem fala é a voz {DO_SERVIDOR[SERVIDOR_VOZ]}. "
                      "Para trocar, use a página de configurações.")
                return True
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
            if alvo not in TODOS_COMANDOS and alvo not in SONS:
                falar(f"Use: exclamação {cmd} e o nome de um comando, sem a exclamação.")
                return True
            if alvo in SONS:
                mudar_config({"sons": {**SONS, alvo: {**SONS[alvo], "ligado": cmd == "ligar"}}})
                falar(f"Som {alvo} {'ligado' if cmd == 'ligar' else 'desligado'}.")
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
            proximo_pedido()
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
            devolver_credito(p)
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
        if cmd == "pedidopresente":
            mudar_config({"pedir_com_presente": not PEDIR_COM_PRESENTE})
            falar("Pedido por presente ligado: cada presente vale um pedido de mapa." if PEDIR_COM_PRESENTE else
                  "Pedido por presente desligado: todo mundo pode pedir.")
            return True
        if cmd == "zerarpedidos":
            for p in pedidos:
                devolver_credito(p)
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
        pagar = PEDIR_COM_PRESENTE and not eh_mod  # gasta um dos pedidos que a pessoa ganhou com presente
        pagador = uid if creditos.get(uid) else GERAL  # sem nenhum dela: usa um do geral
        if not pedidos_abertos:
            dizer(f"{nome}, os pedidos estão fechados agora.")
        elif pagar and not creditos.get(pagador):
            dizer(f"{nome}, para pedir um mapa, mande um presente antes. Cada presente vale um pedido.")
        elif not arg:
            dizer(f"{nome}, manda o link, o nome ou o código do mapa depois do comando.")
        elif not FILA_PEDIDOS:  # sem fila: vai direto para o chat do osu!, sem a voz anunciar
            if tem_palavra_bloqueada(arg):
                dizer(f"{nome}, esse pedido não pode.")
                return True
            p = {"uid": uid, "nome": nome, "texto": arg, "url": link_do_pedido(arg),
                 "pago": pagador if pagar else ""}  # de quem é o crédito gasto
            if pagar:  # foi para o osu!: não volta mais. Se não conseguir ir, fica na fila e vale a regra dela
                mudar_creditos(pagador, -1)
            renovar_creditos(uid)
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
            pedidos.append({"uid": uid, "nome": nome, "texto": arg, "url": link_do_pedido(arg),
                            "pago": pagador if pagar else ""})
            salvar_pedidos()
            sobra = mudar_creditos(pagador, -1) if pagar else 0
            renovar_creditos(uid)
            print(f"[novo pedido de {nome}: {arg}]" + ("" if not pagar else f" (do geral, que ainda tem {sobra})" if pagador == GERAL
                                                          else f" (ainda pode pedir {sobra})"))
            dizer(f"Pedido de {nome} anotado, posição {len(pedidos)}." +
                  (f" Era do geral, que ainda tem {sobra}." if pagar and pagador == GERAL else
                   f" Você ainda pode pedir {sobra}." if sobra else ""))
    elif cmd == "cancelar":
        if pedido_meu is None:
            dizer(f"{nome}, você não tem pedido na fila.")
        else:
            p = pedidos.pop(pedido_meu)
            salvar_pedidos()
            devolver_credito(p)
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
        if PEDIR_COM_PRESENTE and not eh_mod:
            n = creditos.get(uid, 0)
            geral = creditos.get(GERAL, 0)
            if geral:
                texto += f" No geral tem {geral} para qualquer um pedir."
            texto += f" Você pode pedir {n} {'mapa' if n == 1 else 'mapas'}." if n else "" if geral else \
                " Para pedir um mapa, mande um presente: cada presente vale um pedido."
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
        return {"config": config, "comandos": TODOS_COMANDOS, "apelidos": APELIDOS_COMANDO, "grupos": grupos,
                "sons": [{"nome": n, "arquivo": s["arquivo"], "volume": s["volume"], "ligado": s["ligado"],
                          "existe": n in sons}
                         for n, s in SONS.items()],
                "sons_faltando": faltando, "senha_salva": bool(OSU_IRC_SENHA.strip()),
                "salvas": {k: bool(globals()[OPCOES[k]].strip()) for k in SECRETAS},
                "presentes": [{"presente": p, "som": s, "existe": s in SONS} for p, s in PRESENTES.items()],
                "presentes_vistos": [p for p in reversed(presentes_vistos) if not presente_configurado(p)]}

    def mexer_nos_presentes(self, d: dict):
        """Página: escolher o som de um presente (novo ou não), testar ou tirar. Devolve (resposta, código)."""
        acao, presente = d.get("acao"), str(d.get("presente", "")).strip()
        configurado = presente_configurado(presente)
        if acao in ("tocar", "apagar") and not configurado:
            return {"erro": "Não achei esse presente. Clique em Recarregar."}, 404
        if acao == "tocar":
            som = sons_disponiveis().get(PRESENTES[configurado])
            if not som:
                return {"erro": f"Não achei o som {PREFIXO}{PRESENTES[configurado]} (ou o arquivo dele)."}, 404
            tocar_som(som)
            return {"mensagem": f"Tocando o som do {configurado}."}, 200
        if acao == "apagar":
            mudar_config({"presentes": {p: s for p, s in PRESENTES.items() if p != configurado}})
            print(f"[presente {configurado} tirado pela página]")
            return {"mensagem": f"O {configurado} não toca mais som.", **self.dados_da_pagina()}, 200
        if acao != "salvar":
            return {"erro": "dados inválidos"}, 400
        som = nome_de_som(str(d.get("som", "")))
        if not nome_de_som(presente):
            return {"erro": "Escreva o nome do presente, como aparece na janela do programa (ex.: Rose)."}, 400
        if len(presente) > 40:
            return {"erro": "Nome comprido demais."}, 400
        if som not in SONS:
            return {"erro": "Escolha um dos sons. Para um som novo, crie antes em Sons."}, 400
        nome = configurado or presente  # mudar o som de um presente que já está na lista mantém o nome dele
        mudar_config({"presentes": {**PRESENTES, nome: som}})
        print(f"[presente {nome}: som {PREFIXO}{som}, pela página]")
        return {"mensagem": f"Pronto: o {nome} toca {PREFIXO}{som}.", **self.dados_da_pagina()}, 200

    def mexer_nos_sons(self, d: dict):
        """Página: tocar, apagar, adicionar, ligar/desligar ou mudar o volume de um som. Devolve (resposta, código)."""
        acao = d.get("acao")
        nome = nome_de_som(str(d.get("nome", "")))
        if acao in ("tocar", "apagar", "volume", "ligar") and nome not in SONS:
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
        if acao == "ligar":
            ligado = d.get("ligado")
            if not isinstance(ligado, bool):
                return {"erro": "dados inválidos"}, 400
            mudar_config({"sons": {**SONS, nome: {**SONS[nome], "ligado": ligado}}})
            print(f"[som {PREFIXO}{nome} {'ligado' if ligado else 'desligado'} pela página]")
            return {"mensagem": f"Som {PREFIXO}{nome} {'ligado' if ligado else 'desligado'}.",
                    **self.dados_da_pagina()}, 200
        if acao == "apagar":
            arquivo = SONS[nome]["arquivo"]
            de_presentes = [p for p, s in PRESENTES.items() if s == nome]
            mudar_config({"sons": {n: s for n, s in SONS.items() if n != nome},
                          "presentes": {p: s for p, s in PRESENTES.items() if s != nome}})
            print(f"[som {PREFIXO}{nome} apagado pela página]")
            mensagem = f"Som {PREFIXO}{nome} apagado."
            if de_presentes:
                mensagem += f" Estes presentes não tocam mais som: {', '.join(de_presentes)}."
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
        mudar_config({"sons": {**SONS, nome: {"arquivo": arquivo, "volume": 100, "ligado": True}}})
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
                                 "abertos": pedidos_abertos, "fila": FILA_PEDIDOS, "prefixo": PREFIXO,
                                 "presente": PEDIR_COM_PRESENTE,
                                 "geral": creditos.get(GERAL, 0) if PEDIR_COM_PRESENTE else 0})
        else:
            self.responder(404, "text/plain; charset=utf-8", b"nada aqui")

    def do_POST(self):
        # exigir JSON faz o navegador barrar envios vindos de outros sites
        if not self.host_ok() or self.path not in ("/api/config", "/api/sons", "/api/presentes", "/api/testar_voz") or \
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
        if self.path == "/api/presentes":
            return self.responder_json(*self.mexer_nos_presentes(dados))
        if self.path == "/api/testar_voz":
            servidor, _ = voz_em_uso()
            falar("Testando a voz. Um, dois, três.")
            nome = "Maria do Windows" if servidor == "windows" else SERVIDORES_VOZ[servidor]
            return self.responder_json({"mensagem": f"Testando a voz ({nome}). Se der erro, ele aparece na "
                                                    "janela do programa e a voz avisa."})
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
.geral { font-size: .85em; color: #ffd76a; }
.vazio, .mais { font-size: .75em; color: #fff; font-weight: 600; }
.so-geral h1, .so-geral ol { display: none; }
.so-geral #painel { min-width: 0; }
#topo:not(:empty) + ol:not(:empty) { margin-top: 6px; }  /* separa o "Peça com !pedir" da lista */
</style>
</head>
<body>
<div id="painel">
<h1>Pedidos <small id="estado"></small></h1>
<div id="topo"></div>
<ol id="lista"></ol>
<div id="extra"></div>
</div>
<script>
const params = new URLSearchParams(location.search);
const MAX = Math.max(1, parseInt(params.get("max")) || 5);
const SO_GERAL = params.get("so") === "geral";  // só o contador, sem a fila
document.body.classList.toggle("so-geral", SO_GERAL);
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
  const geral = el("div", "geral", `🎁 ${d.geral} ${d.geral === 1 ? "pedido" : "pedidos"} para todo mundo`);
  if (SO_GERAL) {
    $("painel").style.display = d.presente ? "" : "none";
    $("topo").replaceChildren(geral);
    return;
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
  $("extra").replaceChildren(...(n > MAX ? [el("div", "mais", `+ ${n - MAX} na fila`)] : []));
  $("topo").replaceChildren(...[
    d.geral ? geral : null,
    d.abertos ? el("div", "vazio", (d.presente && !d.geral ? "Mande um presente e peça" : "Peça") +
                                   ` com ${d.prefixo}pedir <link, nome ou código>`) : null,
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
[hidden] { display: none !important; }
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
.som > input[type=checkbox] { flex: none; width: auto; margin: 0; }
.som.desligado span, .som.desligado .vol { opacity: .5; }
.som button { padding: 5px 12px; }
.som .vol { display: flex; gap: 6px; align-items: center; flex: 0 1 170px; min-width: 110px; margin: 0; font-weight: 400; }
.som .vol input { flex: 1; min-width: 0; }
.som .vol output { min-width: 3ch; text-align: right; font-variant-numeric: tabular-nums; font-size: 13px; }
@media (max-width: 520px) { .som { flex-wrap: wrap; } .som span { flex-basis: 100%; } .som .vol { flex: 1 1 auto; } }
.atalho { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; padding: 6px 0; border-top: 1px solid var(--borda); }
.atalho input { flex: 1 1 150px; width: auto; min-width: 0; }
.atalho button { padding: 5px 12px; }
.novo { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.novo input[type=text] { flex: 1 1 140px; width: auto; }
.novo input[type=file] { flex: 1 1 200px; min-width: 0; }
.novo select, .som select { flex: 1 1 120px; width: auto; min-width: 0; }
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
        No OBS: fonte de navegador com <code id="link_pedidos"></code>. <code>?max=3</code> no fim mostra só os 3 primeiros.
        <code>?so=geral</code> mostra só quantos pedidos de presente o geral tem, sem a fila.</small>
    </div>
  </section>

  <section>
    <h2>Live</h2>
    <label for="tiktok_usuario">Seu usuário do TikTok<small>Sem o @. Se o programa estiver pedindo o usuário, entra na hora; senão, vale quando ele abre de novo.</small></label>
    <input type="text" id="tiktok_usuario" autocomplete="off" spellcheck="false">
  </section>

  <section>
    <h2>Voz</h2>
    <label for="servidor_voz">Servidor da voz<small>Quem gera a voz. O grátis não precisa de nada, mas falha de vez em quando.
      Nos outros você usa a sua conta e a sua chave, e a cobrança é com você (todos têm uma cota grátis por mês).
      Se o servidor falhar, a mensagem sai na voz do Windows.</small></label>
    <select id="servidor_voz">
      <option value="gratis">Microsoft grátis (sem cadastro)</option>
      <option value="piper">Piper (grátis, no seu PC, sem internet, leve)</option>
      <option value="kokoro">Kokoro (grátis, no seu PC, sem internet, precisa de PC mais forte)</option>
      <option value="azure">Microsoft Azure (sua chave, as mesmas vozes do grátis, mais estável)</option>
      <option value="google">Google Cloud (sua chave)</option>
      <option value="elevenlabs">ElevenLabs (sua chave)</option>
      <option value="openai">OpenAI (sua chave)</option>
    </select>

    <div data-servidor="piper">
      <label for="voz_piper">Voz do Piper<small>Roda no seu PC, então nunca dá erro de rede. Soa um pouco mais robótica que as
        da internet. Na primeira vez a voz é baixada (uns 60 MB cada uma), e enquanto isso sai a voz do Windows. No chat: !voz cadu.</small></label>
      <select id="voz_piper">
        <option value="faber">Faber</option>
        <option value="cadu">Cadu (masculina)</option>
        <option value="jeff">Jeff (masculina)</option>
      </select>
    </div>
    <div data-servidor="kokoro">
      <label for="voz_kokoro">Voz do Kokoro<small>Roda no seu PC, então nunca dá erro de rede, e soa quase tão natural quanto as da
        internet. Mas usa bastante o processador: em PC fraco, ou com o jogo pesado aberto, a voz pode atrasar. Na primeira vez
        as vozes são baixadas (uns 120 MB), e enquanto isso sai a voz do Windows. No chat: !voz alex.</small></label>
      <select id="voz_kokoro">
        <option value="pf_dora">Dora (feminina)</option>
        <option value="pm_alex">Alex (masculina)</option>
        <option value="pm_santa">Santa (masculina)</option>
      </select>
    </div>
    <div data-servidor="azure">
      <label for="chave_azure">Chave da Azure<small>No portal.azure.com, crie um recurso de <b>Fala</b> (Speech) e copie a
        "Chave 1" em Chaves e Ponto de Extremidade.</small></label>
      <input type="password" id="chave_azure" autocomplete="new-password" spellcheck="false">
      <small id="chave_azure_estado"></small>
      <label for="regiao_azure">Região da Azure<small>A que aparece junto da chave, ex.: brazilsouth, eastus.</small></label>
      <input type="text" id="regiao_azure" autocomplete="off" spellcheck="false">
    </div>
    <div data-servidor="google">
      <label for="chave_google">Chave do Google Cloud<small>No console.cloud.google.com, ative a "Cloud Text-to-Speech API" e crie
        uma chave de API em APIs e serviços &gt; Credenciais.</small></label>
      <input type="password" id="chave_google" autocomplete="new-password" spellcheck="false">
      <small id="chave_google_estado"></small>
      <label for="voz_google">Voz do Google<small>O nome da voz, como na lista do Google (cloud.google.com/text-to-speech/docs/voices).
        Pode escrever qualquer uma da lista.</small></label>
      <input type="text" id="voz_google" list="vozes_google" autocomplete="off" spellcheck="false">
      <datalist id="vozes_google">
        <option value="pt-BR-Neural2-A">feminina</option>
        <option value="pt-BR-Neural2-B">masculina</option>
        <option value="pt-BR-Neural2-C">feminina</option>
        <option value="pt-BR-Wavenet-A">feminina</option>
        <option value="pt-BR-Wavenet-B">masculina</option>
        <option value="pt-BR-Standard-A">feminina, mais barata</option>
        <option value="pt-BR-Standard-B">masculina, mais barata</option>
      </datalist>
    </div>
    <div data-servidor="elevenlabs">
      <label for="chave_elevenlabs">Chave da ElevenLabs<small>No elevenlabs.io, em Developers &gt; API Keys.</small></label>
      <input type="password" id="chave_elevenlabs" autocomplete="new-password" spellcheck="false">
      <small id="chave_elevenlabs_estado"></small>
      <label for="voz_elevenlabs">Voice ID da ElevenLabs<small>Na biblioteca de vozes do site, abra a voz e copie o "Voice ID".
        Vale qualquer voz da sua conta, inclusive uma clonada.</small></label>
      <input type="text" id="voz_elevenlabs" autocomplete="off" spellcheck="false">
    </div>
    <div data-servidor="openai">
      <label for="chave_openai">Chave da OpenAI<small>No platform.openai.com, em API keys. A conta precisa ter crédito.</small></label>
      <input type="password" id="chave_openai" autocomplete="new-password" spellcheck="false">
      <small id="chave_openai_estado"></small>
      <label for="voz_openai">Voz da OpenAI</label>
      <select id="voz_openai">
        <option value="nova">Nova (feminina)</option>
        <option value="shimmer">Shimmer (feminina)</option>
        <option value="coral">Coral (feminina)</option>
        <option value="sage">Sage (feminina)</option>
        <option value="alloy">Alloy (neutra)</option>
        <option value="fable">Fable (neutra)</option>
        <option value="echo">Echo (masculina)</option>
        <option value="onyx">Onyx (masculina)</option>
        <option value="ash">Ash (masculina)</option>
      </select>
    </div>
    <small data-servidor="azure google elevenlabs openai">As chaves ficam só no config.json deste PC; a página nunca mostra
      a chave salva. Deixe em branco para manter a atual.</small>

    <div data-servidor="gratis azure">
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
    </div>
    <p style="margin:10px 0 0"><button type="button" id="testar_voz">Testar a voz</button>
      <small style="display:inline">Fala uma frase com o que está salvo.</small></p>
    <label for="velocidade">Velocidade<small>De -10 (bem lenta) a 10 (bem rápida). No chat: !velocidade 5 ou !vel 5.</small></label>
    <div class="faixa"><input type="range" id="velocidade" min="-10" max="10" step="1"><output for="velocidade"></output></div>
    <label for="volume">Volume<small>Volume da voz, de 0 a 100. No chat: !volume 70 ou !vol 70; !vol +10 e !vol -10 sobem e descem.</small></label>
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
      ignorado em silêncio e sai do !comandos. Os sons ligam e desligam logo abaixo, em Sons.</small></label>
    <div class="cmds" id="cmds"></div>
  </section>

  <section>
    <h2>Sons</h2>
    <p class="sub" style="margin:4px 0 0">Cada som vira um comando que todo mundo pode usar: o som <b>ai</b> toca com
      <code>!ai</code>. O <code>!sons</code> fala a lista. No mudo, os sons não tocam. A caixinha liga e desliga o som
      (no chat: !desligar ai), e a barrinha é o volume dele (100 = igual ao volume da voz). Os dois mudam na hora e ficam
      no config.json.</p>
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
    <h2>Presentes</h2>
    <p class="sub" style="margin:4px 0 0">Quando alguém manda um destes presentes na live, toca o som escolhido (um dos
      sons acima). Numa sequência de presentes (combo), o som toca uma vez, no começo. O som do presente não espera o
      tempo entre sons e toca mesmo com a caixinha do som desmarcada (ela vale só para o comando do chat). No mudo, e
      para as pessoas silenciadas, não toca. Fica no config.json, em "presentes".</p>
    <div id="lista_presentes"></div>
    <label for="presente_nome">Novo presente<small>O nome do presente como aparece na janela do programa quando alguém
      manda (ex.: Rose, GG, Finger Heart; maiúsculas e espaços tanto faz). Os que já chegaram nesta live aparecem como
      sugestão ao clicar na caixa.</small></label>
    <div class="novo">
      <input type="text" id="presente_nome" list="presentes_vistos" placeholder="ex.: Rose" maxlength="40" autocomplete="off" spellcheck="false">
      <datalist id="presentes_vistos"></datalist>
      <select id="presente_som" aria-label="Som do novo presente"></select>
      <button type="button" id="presente_adicionar">Adicionar</button>
    </div>
  </section>

  <section>
    <h2>Pedidos de mapas</h2>
    <label for="pedidos_maximos">Tamanho máximo da fila de pedidos<small>Com a fila cheia, novos pedidos são recusados. No chat: !limitepedidos 20.</small></label>
    <input type="number" id="pedidos_maximos" min="1">
    <label for="pedidos_por_pessoa">Pedidos por pessoa<small>Quantos pedidos cada pessoa pode ter na fila ao mesmo tempo. 0 = sem limite. Não vale para você e os mods. No chat: !porpessoa 2.</small></label>
    <input type="number" id="pedidos_por_pessoa" min="0">
    <label class="check"><input type="checkbox" id="fila_pedidos"><span>Usar fila de pedidos<small>Desligado: cada pedido vai direto
      para o seu chat do osu! (precisa do nome e da senha de IRC) e a voz não anuncia. No chat: !filapedidos.</small></span></label>
    <label class="check"><input type="checkbox" id="pedir_com_presente"><span>Pedir só com presente<small>Cada presente
      que a pessoa manda vale um pedido (numa sequência, cada presente conta). Quem pede sem ter mandado presente ouve
      como fazer. Se o pedido sair da fila sem ser atendido (!cancelar, !remover, !zerarpedidos), a pessoa pode pedir de
      novo. Os pedidos que cada um ainda pode fazer ficam guardados em pedidos_por_presente.json, mesmo fechando o
      programa. Não vale para você e os mods. No chat: !pedidopresente.</small></span></label>
    <label for="presente_geral_lives">Lives até ir para o geral<small>Com o pedir só com presente ligado: quem passa esse
      número de lives sem pedir tem os pedidos mandados para o geral, e qualquer um usa com o !pedir. A live em que o
      presente chegou não conta. 0 = nunca vão.</small></label>
    <input type="number" id="presente_geral_lives" min="0">
  </section>

  <section>
    <h2>Atalhos de teclado</h2>
    <p class="sub" style="margin:4px 0 0">Cada tecla faz o mesmo que você mandar um comando no chat, mesmo com o jogo na
      frente: Ctrl+Alt+N para o <code>!proximo</code>, Ctrl+Alt+M para o <code>!mudo</code>, Ctrl+Alt+↑ para o
      <code>!volume +10</code>... Vale qualquer comando, com o que vem depois dele, e também os sons (<code>!ai</code>).
      Para escolher a tecla, clique na caixa da esquerda e aperte; Backspace apaga. O jogo não recebe essas teclas, então
      escolha as que você não usa nele. Só no Windows. Clique em <b>Salvar</b> para valer.</p>
    <div id="lista_atalhos"></div>
    <datalist id="comandos_atalho"></datalist>
    <p style="margin:10px 0 0"><button type="button" id="atalho_adicionar">Novo atalho</button></p>
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
    <small id="osu_irc_senha_estado"></small>
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
const SEGREDOS = ["osu_irc_senha", "chave_azure", "chave_google", "chave_elevenlabs", "chave_openai"];

// mostra só os campos do servidor de voz escolhido
function mostrarServidor() {
  const s = $("servidor_voz").value;
  document.querySelectorAll("[data-servidor]").forEach(e => e.hidden = !e.dataset.servidor.split(" ").includes(s));
}

async function testarVoz() {
  if (Object.keys(mudancas(base)).length) return status("Salve antes de testar: o teste usa o que está salvo.", true);
  await sons({}, "/api/testar_voz");
}
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
    const linha = el("div", s.ligado ? "som" : "som desligado"), texto = el("span"), tocar = el("button", "", "Tocar"),
          apagar = el("button", "", "Apagar"), ligado = el("input");
    ligado.type = "checkbox"; ligado.checked = s.ligado;
    ligado.title = "Ligado"; ligado.setAttribute("aria-label", "Ligar o " + p + s.nome);
    ligado.onchange = async () => {
      if (!await sons({acao: "ligar", nome: s.nome, ligado: ligado.checked})) ligado.checked = !ligado.checked;
    };
    tocar.type = apagar.type = "button";
    texto.append(el("code", "", p + s.nome), el("small", "", s.arquivo + (s.ligado ? "" : " (desligado)") +
      (s.existe ? "" : " (arquivo não encontrado)")));
    const vol = el("label", "vol"), barra = el("input"), valor = el("output", "", String(s.volume));
    barra.type = "range"; barra.min = 0; barra.max = 100; barra.value = s.volume;
    barra.setAttribute("aria-label", "Volume do " + p + s.nome);
    barra.oninput = () => valor.textContent = barra.value;
    barra.onchange = () => sons({acao: "volume", nome: s.nome, volume: Number(barra.value)});
    vol.append(barra, valor);
    tocar.onclick = () => sons({acao: "tocar", nome: s.nome});
    apagar.onclick = () => confirm("Apagar o som " + p + s.nome + "?") && sons({acao: "apagar", nome: s.nome});
    linha.append(ligado, texto, vol, tocar, apagar);
    return linha;
  }) : [el("small", "", "Nenhum som ainda.")]));
  $("sons_faltando").textContent = d.sons_faltando.length ? "Estes não tocam, porque o arquivo não está na pasta sons: " +
    d.sons_faltando.join("; ") + "." : "";
  mostrarPresentes(d);
  // sugestões da caixa do comando dos atalhos: os comandos e os sons
  $("comandos_atalho").replaceChildren(...d.comandos.concat(d.sons.map(s => s.nome)).map(x => new Option(p + x)));
}

// uma linha dos atalhos de teclado: a tecla, o comando e o botão de tirar
function linhaAtalho(tecla, comando) {
  const linha = el("div", "atalho"), t = el("input"), c = el("input"), tirar = el("button", "", "Tirar");
  t.type = c.type = "text";
  t.className = "tecla"; t.readOnly = true; t.value = tecla; t.placeholder = "clique e aperte a tecla";
  t.setAttribute("aria-label", "Tecla do atalho");
  c.className = "comando"; c.value = comando; c.placeholder = "ex.: " + prefixo() + "mudo";
  c.setAttribute("list", "comandos_atalho"); c.autocomplete = "off"; c.spellcheck = false;
  c.setAttribute("aria-label", "Comando do atalho");
  tirar.type = "button";
  tirar.onclick = () => linha.remove();
  linha.append(t, c, tirar);
  return linha;
}

function prefixo() { return base.prefixo || $("prefixo").value || "!"; }

function mostrarAtalhos(d) {
  $("lista_atalhos").replaceChildren(...Object.entries(d.config.atalhos).map(([t, c]) => linhaAtalho(t, d.config.prefixo + c)));
}

// os atalhos como vão para o config.json; as linhas sem tecla ou sem comando ficam de fora
function lerAtalhos() {
  const a = {};
  for (const l of $("lista_atalhos").children) {
    const t = l.querySelector(".tecla").value, c = l.querySelector(".comando").value.trim();
    if (t && c) a[t] = c;
  }
  return a;
}

// o que impede de salvar os atalhos, ou "" se estiver tudo certo
function problemaNosAtalhos() {
  const vistas = new Set();
  for (const l of $("lista_atalhos").children) {
    const t = l.querySelector(".tecla").value, c = l.querySelector(".comando").value.trim();
    if (!t && c) return "Falta a tecla do atalho " + c + ": clique na caixa da esquerda e aperte a tecla.";
    if (t && !c) return "Falta o comando do atalho " + t + " (ex.: " + prefixo() + "mudo).";
    if (vistas.has(t)) return "A tecla " + t + " está em mais de um atalho. Escolha outra ou tire um deles.";
    if (t) vistas.add(t);
  }
  return "";
}

// caixa de escolher o som de um presente
function escolhaDeSom(d, atual) {
  const s = el("select");
  if (!d.sons.length) s.add(new Option("(crie um som antes)", ""));
  for (const x of d.sons) s.add(new Option(d.config.prefixo + x.nome, x.nome));
  if (atual && !d.sons.some(x => x.nome === atual)) s.add(new Option(d.config.prefixo + atual + " (não existe)", atual));
  if (atual) s.value = atual;
  return s;
}

function mostrarPresentes(d) {
  $("lista_presentes").replaceChildren(...(d.presentes.length ? d.presentes.map(x => {
    const linha = el("div", x.existe ? "som" : "som desligado"), texto = el("span"), som = escolhaDeSom(d, x.som),
          tocar = el("button", "", "Testar"), apagar = el("button", "", "Tirar");
    tocar.type = apagar.type = "button";
    texto.append(el("b", "", x.presente));
    if (!x.existe) texto.append(el("small", "", "Esse som não existe mais: escolha outro."));
    som.setAttribute("aria-label", "Som do presente " + x.presente);
    som.onchange = async () => {
      if (!await sons({acao: "salvar", presente: x.presente, som: som.value}, "/api/presentes")) som.value = x.som;
    };
    tocar.onclick = () => sons({acao: "tocar", presente: x.presente}, "/api/presentes");
    apagar.onclick = () => confirm("O " + x.presente + " não vai mais tocar som. Tirar?") &&
      sons({acao: "apagar", presente: x.presente}, "/api/presentes");
    linha.append(texto, som, tocar, apagar);
    return linha;
  }) : [el("small", "", "Nenhum presente toca som ainda.")]));
  const escolhido = $("presente_som").value;
  $("presente_som").replaceWith(Object.assign(escolhaDeSom(d, ""), {id: "presente_som"}));
  if (d.sons.some(x => x.nome === escolhido)) $("presente_som").value = escolhido;
  $("presente_som").setAttribute("aria-label", "Som do novo presente");
  $("presentes_vistos").replaceChildren(...d.presentes_vistos.map(p => new Option(p, p)));
}

async function adicionarPresente() {
  const presente = $("presente_nome").value.trim();
  if (!presente) return status("Escreva o nome do presente (ex.: Rose).", true);
  if (await sons({acao: "salvar", presente, som: $("presente_som").value}, "/api/presentes")) $("presente_nome").value = "";
}

// tocar, apagar, adicionar, ligar/desligar ou mudar o volume de um som (ou mexer num presente,
// com url = "/api/presentes"). Devolve true se deu certo.
async function sons(pedido, url = "/api/sons") {
  try {
    const r = await fetch(url, {method: "POST", headers: {"Content-Type": "application/json"},
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
  mostrarAtalhos(d);
  for (const [k, salva] of Object.entries(d.salvas)) {
    $(k).value = "";
    $(k).placeholder = salva ? "•••••••• (salva)" : "";
    const qual = k === "osu_irc_senha" ? "senha" : "chave";
    $(k + "_estado").textContent = salva ? "Tem uma " + qual + " salva." : "Nenhuma " + qual + " salva ainda.";
  }
  atualizarFaixas();
  mostrarServidor();
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
  for (const k of SEGREDOS) {
    const valor = $(k).value.trim();
    if (valor) c[k] = valor;
  }
  c.comandos_desativados = [...document.querySelectorAll("#cmds input")].filter(i => !i.checked).map(i => i.value);
  c.atalhos = lerAtalhos();
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
  const problema = problemaNosAtalhos();
  if (problema) return status(problema, true);
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
// atalhos de teclado: a caixa da tecla grava a tecla apertada ("ctrl+alt+n"), no mesmo jeito do config.json
const TECLAS_ATALHO = {" ": "espaco", "Enter": "enter", "Insert": "insert", "Delete": "delete", "Home": "home",
  "End": "end", "PageUp": "pageup", "PageDown": "pagedown", "ArrowUp": "cima", "ArrowDown": "baixo",
  "ArrowLeft": "esquerda", "ArrowRight": "direita", "Pause": "pause", "ScrollLock": "scrolllock"};
$("lista_atalhos").addEventListener("keydown", e => {
  if (!e.target.classList.contains("tecla") || e.key === "Tab") return;  // Tab: deixa sair da caixa pelo teclado
  e.preventDefault();
  if (["Backspace", "Escape"].includes(e.key)) { e.target.value = ""; return; }
  if (["Control", "Alt", "Shift", "Meta", "AltGraph"].includes(e.key)) return;  // espera a tecla de verdade
  let tecla = /^F([1-9]|1[0-9]|2[0-4])$/.test(e.key) ? e.key.toLowerCase()
    : /^Numpad[0-9]$/.test(e.code) ? "num" + e.code.slice(6)
    : /^Key[A-Z]$/.test(e.code) ? e.code.slice(3).toLowerCase()
    : /^Digit[0-9]$/.test(e.code) ? e.code.slice(5)
    : TECLAS_ATALHO[e.key];
  if (!tecla) return;
  const mods = [e.ctrlKey && "ctrl", e.altKey && "alt", e.shiftKey && "shift", e.metaKey && "win"].filter(Boolean);
  e.target.value = [...mods, tecla].join("+");
  e.target.dispatchEvent(new Event("input", {bubbles: true}));
});
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
$("atalho_adicionar").onclick = () => {
  $("lista_atalhos").append(linhaAtalho("", ""));
  $("lista_atalhos").lastChild.querySelector(".tecla").focus();
};
$("salvar").onclick = salvar;
$("servidor_voz").onchange = mostrarServidor;
$("testar_voz").onclick = testarVoz;
$("som_adicionar").onclick = adicionarSom;
$("presente_adicionar").onclick = adicionarPresente;
$("presente_nome").onkeydown = e => { if (e.key === "Enter") adicionarPresente(); };
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


DONO_TESTE = "voce"  # no modo de teste, quem digita é o dono da live


def modo_teste():
    """Simula o chat sem live: cada linha digitada vira um comentário."""
    from types import SimpleNamespace
    dono = DONO_TESTE
    print("MODO DE TESTE: sem live, o que você digitar aqui entra como mensagem do chat.\n"
          "  oi                -> mensagem sua (você é o dono: pode usar os comandos de moderação)\n"
          "  Fulano: oi        -> mensagem de outra pessoa, chamada Fulano\n"
          "  #presente Rose    -> alguém manda o presente Rose (Fulano: #presente Rose também vale)\n"
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
        if texto.lower().startswith("#presente "):
            receber_presente(SimpleNamespace(unique_id=uid, nick_name=nome), texto[10:].strip(), None, False, 1, dono)
            continue
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
    carregar_creditos()
    salvar_pedidos()  # a fila começa vazia: o pedidos.txt não pode continuar mostrando a da live anterior
    adiantar_voz_local()
    teste = usuario.lower() in ("teste", "--teste")
    iniciar_atalho(DONO_TESTE if teste else usuario)
    if teste:
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
        foram = comecou_live(event.room_id)
        if foram:
            falar(f"{foram} {'pedido' if foram == 1 else 'pedidos'} de presente que ninguém usou "
                  f"{'foi' if foram == 1 else 'foram'} para o geral. Qualquer um pode usar com exclamação pedir.")

    @client.on(DisconnectEvent)
    async def ao_desconectar(event: DisconnectEvent):
        print("Caiu a conexão com a live (ou a live acabou). Tentando voltar...")
        falar("Caiu a conexão com a live. Tentando voltar.")

    @client.on(CommentEvent)
    async def ao_comentar(event: CommentEvent):
        if comentario_repetido_ou_antigo(event):
            return
        processar_comentario(event.user, event.comment or "", usuario)

    @client.on(GiftEvent)
    async def ao_ganhar_presente(event: GiftEvent):
        if event.gift is None or event.user is None or comentario_repetido_ou_antigo(event):
            return
        receber_presente(event.user, event.gift.name or f"presente {event.gift.id}", event.gift.id,
                         event.streaking, event.repeat_count or 1, usuario)

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
