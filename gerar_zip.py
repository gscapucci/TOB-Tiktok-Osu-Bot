"""
Gera o zip de distribuição em dist, por exemplo dist/LeitorChat-v0.1.1.zip.

Uso:
    python gerar_zip.py v0.1.1
    (antes: gerar_exe.bat, gerar_manual.bat e gerar_licencas.py)

O config.json, apelidos.txt, pedidos.txt, pedidos_por_presente.json e registros não vão no zip: são de quem usa,
e assim extrair uma versão nova por cima não apaga nada disso. Da pasta sons, só vão os
arquivos dos sons padrão (SONS no leitor_chat.py); os que a pessoa acrescentou continuam lá.
"""
import ast
import os
import sys
import zipfile

PASTA = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(PASTA, "dist")

# caminho no zip (dentro de LeitorChat/) -> arquivo aqui
ARQUIVOS = {
    "LeitorChat.exe": os.path.join(DIST, "LeitorChat.exe"),
    "LEIA-ME.txt": os.path.join(PASTA, "LEIA-ME.txt"),
    "LICENSE": os.path.join(PASTA, "LICENSE"),
    "Guia de uso - Leitor de Chat.pdf": os.path.join(PASTA, "Guia de uso - Leitor de Chat.pdf"),
    "tosu/tosu.exe": os.path.join(PASTA, "tosu", "tosu.exe"),  # só o exe: o resto da pasta é do seu tosu
}
LICENCAS = os.path.join(DIST, "licencas")


def sons_padrao() -> list:
    """Os arquivos do SONS padrão, lidos do leitor_chat.py."""
    arvore = ast.parse(open(os.path.join(PASTA, "leitor_chat.py"), encoding="utf-8").read())
    for no in arvore.body:
        if isinstance(no, ast.Assign) and getattr(no.targets[0], "id", "") == "SONS":
            return sorted({som["arquivo"] for som in ast.literal_eval(no.value).values()})
    return []


for _arquivo in sons_padrao():
    ARQUIVOS["sons/" + _arquivo] = os.path.join(PASTA, "sons", _arquivo)


def main():
    if len(sys.argv) != 2:
        sys.exit("Uso: python gerar_zip.py v0.1.1")
    faltando = [a for a in list(ARQUIVOS.values()) + [LICENCAS] if not os.path.exists(a)]
    if faltando:
        sys.exit("Faltam arquivos (rode antes os outros scripts de gerar):\n  " + "\n  ".join(faltando))

    saida = os.path.join(DIST, f"LeitorChat-{sys.argv[1]}.zip")
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as z:
        for nome, arquivo in ARQUIVOS.items():
            z.write(arquivo, f"LeitorChat/{nome}")
        for raiz, _, nomes in os.walk(LICENCAS):
            for nome in nomes:
                arquivo = os.path.join(raiz, nome)
                z.write(arquivo, "LeitorChat/licencas/" + os.path.relpath(arquivo, LICENCAS).replace(os.sep, "/"))
    print(f"Zip gerado: {saida}")


if __name__ == "__main__":
    main()
