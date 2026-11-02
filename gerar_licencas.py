"""
Gera a pasta "licencas" dentro de "dist" com as licenças de tudo o que vai no zip de distribuição:
as bibliotecas empacotadas no LeitorChat.exe, o próprio Python e o tosu.

Uso:
    python gerar_licencas.py
    (rode no mesmo Python que gera o .exe, para pegar as mesmas versões das bibliotecas)
"""
import os
import shutil
import sys
import urllib.request
from importlib.metadata import PackageNotFoundError, distribution

from packaging.requirements import Requirement

PASTA = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(PASTA, "dist", "licencas")
RAIZES = ["TikTokLive", "edge-tts", "comtypes"]  # o que o leitor_chat.py importa (veja requirements.txt)
REPOSITORIO = "https://github.com/gscapucci/TOB-Tiktok-Osu-Bot"

# pacotes cuja licença precisa de explicação
OBSERVACOES = {
    "tiktoklive": "AGPL-3.0 com exceção (seções 18 a 21 do texto): permite usar em bots de live sem que o "
                  "programa precise adotar a AGPL, desde que não seja um serviço hospedado para terceiros.",
    "tiktokliveproto": "Mesma licença e mesma exceção do TikTokLive.",
    "edge-tts": "LGPL-3.0. O código do Leitor de Chat é aberto e o gerar_exe.bat gera o .exe de novo, "
                "então dá para trocar o edge-tts por outra versão.",
    "eulerapisdk": "Não declara licença (nem no pacote, nem no PyPI). É o cliente da API da Euler Stream, "
                   "dependência obrigatória do TikTokLive.",
}

# pacotes que não trazem o texto da licença instalado: baixa do repositório oficial
LICENCAS_NO_GITHUB = {
    "betterproto2": "https://raw.githubusercontent.com/betterproto/python-betterproto2/main/LICENSE.md",
    "ffmpy": "https://raw.githubusercontent.com/Ch00k/ffmpy/master/LICENSE",
    "protobuf3-to-dict": "https://raw.githubusercontent.com/kaporzhu/protobuf-to-dict/master/LICENSE",
}


def baixar(url: str, arquivo: str):
    os.makedirs(os.path.dirname(arquivo), exist_ok=True)
    with urllib.request.urlopen(url, timeout=30) as r, open(arquivo, "wb") as f:
        f.write(r.read())


def dependencias() -> list:
    """As bibliotecas de RAIZES e tudo de que elas dependem (o que o PyInstaller empacota)."""
    vistos = {}

    def visitar(nome):
        try:
            d = distribution(nome)
        except PackageNotFoundError:
            return
        chave = d.metadata["Name"].lower().replace("_", "-")
        if chave in vistos:
            return
        vistos[chave] = d
        for r in d.requires or []:
            req = Requirement(r)
            if req.marker is None or req.marker.evaluate({"extra": ""}):
                visitar(req.name)

    for nome in RAIZES:
        visitar(nome)
    return sorted(vistos.values(), key=lambda d: d.metadata["Name"].lower())


def nome_da_licenca(d) -> str:
    m = d.metadata
    if m.get("License-Expression"):
        return m["License-Expression"]
    if m.get("License") and len(m["License"]) < 60:  # às vezes o campo tem o texto inteiro da licença
        return m["License"]
    classificadores = [c.split("::")[-1].strip() for c in m.get_all("Classifier") or [] if c.startswith("License ::")]
    return ", ".join(classificadores) or "não declarada"


def copiar_licencas(d, destino: str) -> int:
    """Copia os arquivos de licença que vêm instalados com o pacote. Devolve quantos copiou."""
    n = 0
    for f in d.files or []:
        caminho = str(f).replace("\\", "/")
        base = caminho.rsplit("/", 1)[-1].upper()
        if not any(x in base for x in ("LICEN", "COPYING", "NOTICE")):
            continue
        # licenses/vendor/llhttp/LICENSE -> vendor_llhttp_LICENSE, para não sobrescrever o LICENSE principal
        relativo = caminho.split("/licenses/", 1)[-1] if "/licenses/" in caminho else caminho.rsplit("/", 1)[-1]
        os.makedirs(destino, exist_ok=True)
        shutil.copyfile(d.locate_file(f), os.path.join(destino, relativo.replace("/", "_")))
        n += 1
    return n


def main():
    shutil.rmtree(SAIDA, ignore_errors=True)
    os.makedirs(SAIDA)
    linhas = []  # (nome, versão, licença, código-fonte, pasta, observação)

    for d in dependencias():
        nome, versao = d.metadata["Name"], d.metadata["Version"]
        pasta = f"{nome}-{versao}"
        fonte = f"https://pypi.org/project/{nome}/{versao}/"
        if not copiar_licencas(d, os.path.join(SAIDA, pasta)):
            url = LICENCAS_NO_GITHUB.get(nome.lower())
            if url:
                baixar(url, os.path.join(SAIDA, pasta, url.rsplit("/", 1)[-1]))
            else:
                pasta = "(o pacote não traz o texto da licença)"
        linhas.append((nome, versao, nome_da_licenca(d), fonte, pasta,
                       OBSERVACOES.get(nome.lower().replace("_", "-"), "")))

    # o .exe leva o Python junto
    versao_py = ".".join(map(str, sys.version_info[:3]))
    pasta = f"Python-{versao_py}"
    os.makedirs(os.path.join(SAIDA, pasta))
    shutil.copyfile(os.path.join(sys.base_prefix, "LICENSE.txt"), os.path.join(SAIDA, pasta, "LICENSE.txt"))
    linhas.append(("Python", versao_py, "PSF-2.0", "https://www.python.org/downloads/source/", pasta, ""))

    # e o Tcl/Tk (janela da fila de pedidos); o Tcl e o Tk usam o mesmo texto de licença
    termos = os.path.join(sys.base_prefix, "tcl", "tk8.6", "license.terms")
    if os.path.exists(termos):
        import tkinter
        versao_tk = tkinter.Tcl().eval("info patchlevel")
        pasta = f"Tcl-Tk-{versao_tk}"
        os.makedirs(os.path.join(SAIDA, pasta))
        shutil.copyfile(termos, os.path.join(SAIDA, pasta, "license.terms"))
        linhas.append(("Tcl/Tk", versao_tk, "TCL (estilo BSD)", "https://www.tcl-lang.org/software/tcltk/",
                       pasta, "Vai junto com o Python, para a janela da fila de pedidos."))

    # tosu: a versão fica anotada pelo instalar.bat quando ele baixa
    try:
        with open(os.path.join(PASTA, "tosu", "VERSAO.txt"), encoding="utf-8-sig") as f:
            versao_tosu = f.read().strip()
    except FileNotFoundError:
        versao_tosu = ""
    ref = versao_tosu or "master"
    pasta = f"tosu-{versao_tosu or 'atual'}"
    baixar(f"https://raw.githubusercontent.com/tosuapp/tosu/{ref}/LICENSE", os.path.join(SAIDA, pasta, "LICENSE"))
    fonte = f"https://github.com/tosuapp/tosu/tree/{ref}"
    linhas.append(("tosu", versao_tosu or "?", "LGPL-3.0", fonte, pasta,
                   "Incluído sem modificações, na pasta tosu." +
                   ("" if versao_tosu else " Versão desconhecida: confira em github.com/tosuapp/tosu/releases.")))

    # a LGPL-3.0 (tosu, edge-tts) é escrita como acréscimo à GPL-3.0 e pede o texto das duas
    baixar("https://www.gnu.org/licenses/gpl-3.0.txt", os.path.join(SAIDA, "GPL-3.0.txt"))

    with open(os.path.join(SAIDA, "LEIA-ME.txt"), "w", encoding="utf-8") as f:
        f.write("LICENÇAS DE TERCEIROS\n\n"
                "O Leitor de Chat é distribuído sob a licença MIT (arquivo LICENSE, ao lado do programa).\n"
                f"Código-fonte: {REPOSITORIO}\n\n"
                "Junto com ele vão programas e bibliotecas de outros autores, cada um com a sua licença.\n"
                "Os textos das licenças estão nas subpastas desta pasta. A LGPL-3.0 complementa a\n"
                "GPL-3.0, cujo texto está em GPL-3.0.txt.\n\n")
        for nome, versao, licenca, fonte, pasta, obs in linhas:
            f.write(f"{nome} {versao}\n  Licença: {licenca}\n  Código-fonte: {fonte}\n  Texto da licença: {pasta}\n")
            if obs:
                f.write(f"  Observação: {obs}\n")
            f.write("\n")
    print(f"Licenças de {len(linhas)} componentes em: {SAIDA}")


if __name__ == "__main__":
    main()
