"""
Gera o "Guia de uso - Leitor de Chat.pdf" a partir deste script.

Uso:
    python gerar_manual.py
    (precisa de: pip install reportlab)
"""
import os
import sys

PASTA = os.path.dirname(os.path.abspath(__file__))
PROGRAMA = os.path.join(PASTA, "leitor_chat.py")
SAIDA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(PASTA, "Guia de uso - Leitor de Chat.pdf")
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

F = "C:/Windows/Fonts/"
pdfmetrics.registerFont(TTFont("Segoe", F + "segoeui.ttf"))
pdfmetrics.registerFont(TTFont("Segoe-B", F + "segoeuib.ttf"))
pdfmetrics.registerFont(TTFont("Segoe-SB", F + "seguisb.ttf"))
pdfmetrics.registerFont(TTFont("Segoe-L", F + "segoeuil.ttf"))
pdfmetrics.registerFont(TTFont("Mono", F + "consola.ttf"))
pdfmetrics.registerFontFamily("Segoe", normal="Segoe", bold="Segoe-B", italic="Segoe", boldItalic="Segoe-B")

ROSA = colors.HexColor("#E0457B")
ROSA_CLARO = colors.HexColor("#FDECF2")
TINTA = colors.HexColor("#1F2330")
CINZA = colors.HexColor("#5B6170")
LINHA = colors.HexColor("#E3E5EA")
FUNDO = colors.HexColor("#F6F7F9")
AZUL_CLARO = colors.HexColor("#EAF2FD")
AZUL = colors.HexColor("#2F6FD0")
AMARELO_CLARO = colors.HexColor("#FFF6E0")
AMARELO = colors.HexColor("#C98A00")

corpo = ParagraphStyle("corpo", fontName="Segoe", fontSize=10.5, leading=15.5, textColor=TINTA, spaceAfter=6)
h1 = ParagraphStyle("h1", fontName="Segoe-B", fontSize=20, leading=25, textColor=TINTA, spaceBefore=4, spaceAfter=4)
h2 = ParagraphStyle("h2", fontName="Segoe-SB", fontSize=13.5, leading=18, textColor=ROSA, spaceBefore=12, spaceAfter=5, keepWithNext=1)
rotulo = ParagraphStyle("rotulo", parent=corpo, keepWithNext=1)
sub = ParagraphStyle("sub", parent=corpo, textColor=CINZA, fontSize=11, leading=16, spaceAfter=10)
cel = ParagraphStyle("cel", parent=corpo, fontSize=9.5, leading=13, spaceAfter=0)
cel_b = ParagraphStyle("cel_b", parent=cel, fontName="Segoe-SB", textColor=colors.white)
item = ParagraphStyle("item", parent=corpo, leftIndent=14, bulletIndent=3, spaceAfter=3)
passo_n = ParagraphStyle("passo_n", fontName="Segoe-B", fontSize=15, leading=18, textColor=colors.white,
                         alignment=TA_CENTER)


def cmd(t):
    return f'<font name="Mono" color="#B0305E">{t}</font>'


def p(t, s=corpo):
    return Paragraph(t, s)


def itens(lista):
    return [Paragraph(t, item, bulletText="•") for t in lista]


def tabela(cab, linhas, larguras):
    dados = [[p(c, cel_b) for c in cab]] + [[p(c, cel) for c in l] for l in linhas]
    t = Table(dados, colWidths=[w * mm for w in larguras], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TINTA),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, FUNDO]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINHA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def caixa(titulo, texto, fundo=AZUL_CLARO, cor=AZUL):
    t = Table([[p(f'<font name="Segoe-SB" color="{cor.hexval().replace("0x", "#")}">{titulo}</font><br/>{texto}',
                  ParagraphStyle("cx", parent=corpo, spaceAfter=0))]], colWidths=[170 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fundo), ("LINEBEFORE", (0, 0), (0, -1), 3, cor),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return KeepTogether([Spacer(1, 4), t, Spacer(1, 8)])


def dica(t):
    return caixa("Dica", t)


def atencao(t):
    return caixa("Atenção", t, AMARELO_CLARO, AMARELO)


def passos(lista):
    linhas = []
    for i, (titulo, texto) in enumerate(lista, 1):
        bolinha = Table([[p(str(i), passo_n)]], colWidths=[9 * mm], rowHeights=[9 * mm])
        bolinha.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), ROSA),
                                     ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                     ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                                     ("ROUNDEDCORNERS", [4.5 * mm] * 4)]))
        linhas.append([bolinha, p(f"<b>{titulo}</b><br/>{texto}", ParagraphStyle("ps", parent=corpo, spaceAfter=0))])
    t = Table(linhas, colWidths=[13 * mm, 157 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                           ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    return t


def fala(t):
    """Balão com o que a voz fala."""
    tb = Table([[p(f'<font color="#5B6170">A voz fala:</font>  <i>“{t}”</i>',
                   ParagraphStyle("f", parent=corpo, spaceAfter=0, fontSize=10))]], colWidths=[170 * mm])
    tb.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), ROSA_CLARO),
                            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                            ("LEFTPADDING", (0, 0), (-1, -1), 10), ("ROUNDEDCORNERS", [3, 3, 3, 3])]))
    return KeepTogether([tb, Spacer(1, 6)])


def capa(c, doc):
    w, h = A4
    c.saveState()
    c.setFillColor(TINTA)
    c.rect(0, 0, w, h, stroke=0, fill=1)
    c.setFillColor(ROSA)
    c.circle(w - 40 * mm, h - 55 * mm, 70 * mm, stroke=0, fill=1)
    c.setFillColor(colors.HexColor("#2A2F3F"))
    c.circle(35 * mm, 40 * mm, 45 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Segoe-L", 15)
    c.drawString(25 * mm, 150 * mm, "GUIA DE USO")
    c.setFont("Segoe-B", 44)
    c.drawString(25 * mm, 132 * mm, "Leitor de Chat")
    c.setFont("Segoe", 15)
    c.setFillColor(colors.HexColor("#C9CDD8"))
    c.drawString(25 * mm, 120 * mm, "Chat da live do TikTok em voz alta,")
    c.drawString(25 * mm, 113 * mm, "comandos e integração com o osu!")
    c.setFillColor(ROSA)
    c.rect(25 * mm, 104 * mm, 30 * mm, 1.5 * mm, stroke=0, fill=1)
    c.setFont("Segoe", 10)
    c.setFillColor(colors.HexColor("#8D93A3"))
    c.drawString(25 * mm, 25 * mm, "Outubro de 2026")
    c.restoreState()


def rodape(c, doc):
    w, h = A4
    c.saveState()
    c.setFont("Segoe", 8.5)
    c.setFillColor(CINZA)
    c.drawString(20 * mm, 12 * mm, "Leitor de Chat — Guia de uso")
    c.drawRightString(w - 20 * mm, 12 * mm, str(doc.page - 1))
    c.setStrokeColor(LINHA)
    c.line(20 * mm, 16 * mm, w - 20 * mm, 16 * mm)
    c.restoreState()


s = [PageBreak()]

# ---------- Sumário ----------
s += [p("Sumário", h1), Spacer(1, 6)]
secoes = ["O que o app faz", "Primeira vez: preparando tudo", "Passo a passo de cada live",
          "Comandos para o chat", "Comandos de moderação", "Pedidos de mapas do osu!",
          "osu! ao vivo", "Ligando e desligando funções", "O arquivo config.json", "Arquivos criados pelo app", "Problemas comuns"]
s.append(tabela(["", "Seção"], [[str(i), t] for i, t in enumerate(secoes, 1)], [12, 158]))
s.append(PageBreak())

# ---------- 1 ----------
s += [p("1. O que o app faz", h1),
      p("O <b>Leitor de Chat</b> acompanha a sua live do TikTok e fala em voz alta tudo o que o "
        "chat escreve. Além disso, o público pode usar comandos, e o app se conecta ao osu! para "
        "falar sobre o mapa que você está jogando.", sub)]
s.append(tabela(["Recurso", "O que faz"], [
    ["<b>Leitura do chat</b>", "Fala cada mensagem: “Fulano disse: ...”, com voz natural em português."],
    ["<b>Comandos</b>", f"O chat pode usar {cmd('!np')}, {cmd('!pp')}, {cmd('!top')}, {cmd('!mensagens')} e outros. As respostas são faladas."],
    ["<b>Moderação</b>", f"Você pode silenciar a voz, mudar volume e velocidade e bloquear palavras pelo próprio chat."],
    ["<b>Pedidos de mapas</b>", "O chat pede mapas do osu!, eles entram numa fila e você abre um por um."],
    ["<b>osu! ao vivo</b>", "Anuncia o mapa que você começou e o recorde de PP da live."],
    ["<b>Registro da live</b>", "Planilha com quem entrou, a que horas e quantas mensagens mandou."],
], [42, 128]))
s.append(dica("O app <b>não escreve</b> no chat do TikTok, ele só lê. Por isso todas as respostas "
              "aos comandos são dadas <b>pela voz</b>."))

# ---------- 2 ----------
s += [p("2. Primeira vez: preparando tudo", h1),
      p("Isso só precisa ser feito uma vez.", sub)]
s.append(passos([
    ("Extraia o zip", "Clique com o botão direito no <b>LeitorChat.zip</b> e escolha <b>Extrair tudo</b>. "
                      "Não abra o programa de dentro do zip, senão ele não consegue salvar arquivos."),
    ("Confira os arquivos", "A pasta <b>LeitorChat</b> deve ter: <b>LeitorChat.exe</b>, "
                            "<b>LEIA-ME.txt</b>, <b>LICENSE</b>, este guia e as pastas <b>tosu</b> e <b>licencas</b> "
                            "(as licenças do tosu e das bibliotecas que o programa usa). "
                            "O <b>config.json</b> aparece sozinho na primeira vez que o programa abre."),
    ("Libere no Windows", "Na primeira vez que abrir o <b>LeitorChat.exe</b>, o Windows "
                          "pode mostrar “O Windows protegeu o computador”. Clique em <b>Mais informações</b> "
                          "e depois em <b>Executar assim mesmo</b>. O firewall também pode pedir permissão para o tosu: permita."),
    ("Tenha internet", "A voz e a conexão com o TikTok precisam de internet."),
]))
s.append(dica("Não precisa instalar Python nem nada mais. Só o osu! precisa estar instalado, "
              "se você for usar os recursos de osu!."))

# ---------- 3 ----------
s += [PageBreak(), p("3. Passo a passo de cada live", h1),
      p("Siga esta ordem sempre que for fazer live.", sub)]
s.append(passos([
    ("Abra o osu!", "Pode ser o stable ou o lazer."),
    ("Comece a live no TikTok", "A live precisa estar <b>ao vivo</b> antes do próximo passo."),
    ("Abra o LeitorChat.exe", "Digite o seu usuário do TikTok <b>sem o @</b> e aperte <b>Enter</b>. "
                              "Ele abre o <b>tosu</b> sozinho, numa janela separada: deixe ela aberta durante a live."),
    ("Pronto!", "A voz fala “Conectado ao chat da live.” e começa a ler as mensagens. "
                "Para mudar as configurações durante a live, abra <b>http://localhost:8765</b> no navegador (seção 8)."),
]))
s.append(p("Para encerrar", h2))
s.append(p(f"Na janela do programa, aperte <b>Ctrl+C</b>. Ele salva a planilha da live e mostra onde "
           f"ela ficou. Depois aperte <b>Enter</b> para fechar a janela."))
s.append(atencao("Se aparecer <b>UserOfflineError</b>, a live ainda não está ao vivo ou o usuário "
                 "foi digitado errado. Comece a live e abra o programa de novo."))

s.append(p("Como a voz lê o chat", h2))
s += itens([
    "Só são lidas as mensagens escritas <b>depois</b> que o programa abriu. As mais antigas do chat "
    "ficam de fora, e nenhuma mensagem é lida duas vezes, mesmo se a conexão cair e voltar.",
    "Cada mensagem é falada como <b>“Fulano disse: mensagem”</b>.",
    "Links viram a palavra <b>“link”</b>.",
    "Letras repetidas são encurtadas: “kkkkkkkk” vira “kkk”.",
    "Mensagens muito longas são cortadas.",
    "Se o chat estiver rápido demais, a voz pula as mensagens mais antigas para não ficar atrasada.",
])

s.append(p("Testando sem live", h2))
s.append(p("Para experimentar a voz, os comandos e as configurações antes da live, abra o LeitorChat.exe "
           f"e, no lugar do usuário do TikTok, digite <b>teste</b>. O programa não conecta no TikTok: "
           "o que você digitar na janela entra como mensagem do chat."))
s.append(tabela(["Você digita", "O que acontece"], [
    ["oi gente", "Mensagem sua. Você é o dono da live, então os comandos de moderação funcionam."],
    [f"Fulano: {cmd('!top')}", "Mensagem de outra pessoa, chamada Fulano. Bom para testar o que o público vê."],
    ["sair", "Fecha o programa."],
], [45, 125]))
s.append(Spacer(1, 6))
s.append(atencao(f"No teste, {cmd('!apelido')} e {cmd('!pedir')} gravam de verdade no apelidos.txt e no "
                 f"pedidos.txt. Depois, use {cmd('!zerarpedidos')} e apague os apelidos de teste. "
                 "A planilha da live não é criada no modo de teste."))

# ---------- 4 ----------
s += [PageBreak(), p("4. Comandos para o chat", h1),
      p(f"Qualquer pessoa da live pode usar. Todo comando começa com {cmd('!')} no início da "
        f"mensagem. Maiúsculas não importam: {cmd('!NP')} funciona igual a {cmd('!np')}. "
        f"Vários comandos têm um atalho mais curto, como {cmd('!msg')} (veja o fim da seção 5).", sub)]
s.append(tabela(["Comando", "O que faz"], [
    [cmd("!comandos"), f"Fala a lista de comandos. {cmd('!ajuda')} faz o mesmo. Para você e os "
                       "moderadores, fala a lista dos comandos de moderação."],
    [cmd("!mensagens"), "Quantas mensagens a pessoa mandou nesta live."],
    [cmd("!top"), "As 3 pessoas que mais mandaram mensagem."],
    [cmd("!copiar texto"), "Copia o texto para o seu Ctrl+C. É só dar Ctrl+V onde quiser."],
    [cmd("!np"), f"O mapa do osu! que você está jogando. {cmd('!mapa')} faz o mesmo."],
    [cmd("!pp"), "Quanto PP o mapa vale com os mods atuais."],
    [cmd("!rank"), "Seu rank global, PP e precisão."],
    [cmd("!recorde"), "O recorde de PP desta live."],
    [cmd("!pedir mapa"), "Pede um mapa do osu! (veja a seção 6)."],
    [cmd("!pedidos"), "Quantos pedidos tem na fila e a posição da pessoa."],
], [38, 132]))
s.append(Spacer(1, 8))
s.append(p("Exemplo", h2))
s.append(p(f"<b>Lucas</b> escreve {cmd('!mensagens')}"))
s.append(fala("Lucas, você mandou 12 mensagens nesta live."))
s.append(atencao("Cada pessoa só pode usar <b>um comando a cada 15 segundos</b>. Os comandos a mais "
                 "são ignorados, para ninguém lotar a voz. Você e os moderadores não têm esse limite."))
s.append(caixa("Sobre o !copiar", "Qualquer pessoa pode usar, então alguém pode trocar o seu Ctrl+C "
               "enquanto você copia outra coisa. Se atrapalhar, dá para desligar (seção 8).",
               AMARELO_CLARO, AMARELO))

# ---------- 5 ----------
s += [PageBreak(), p("5. Comandos de moderação", h1),
      p("Só funcionam para <b>você</b> (o dono da live) e para quem estiver na lista de moderadores. "
        "Se outra pessoa tentar, o comando é ignorado em silêncio.", sub)]
s.append(p("Controlando a live", h2))
s.append(tabela(["Comando", "O que faz"], [
    [cmd("!mudo"), "Para de ler o chat. Os avisos automáticos do osu! e as respostas dos comandos do "
                   f"público (como {cmd('!np')} e {cmd('!top')}) também param."],
    [cmd("!voltar"), "Volta a ler o chat."],
    [cmd("!limpar"), "Apaga as mensagens que estavam esperando para serem lidas."],
    [cmd("!apelido fulano Aninha"), "A voz passa a chamar o usuário fulano de Aninha. O público não pode "
                                    "escolher o próprio apelido, senão a voz falaria qualquer coisa."],
    [cmd("!proximo"), "Abre o próximo pedido de mapa (seção 6)."],
    [cmd("!fecharpedidos"), "Para de aceitar pedidos."],
    [cmd("!abrirpedidos"), "Volta a aceitar pedidos."],
    [cmd("!zerarpedidos"), "Apaga a fila de pedidos inteira."],
], [42, 128]))
s.append(Spacer(1, 4))
s.append(p("Estes valem até fechar o programa, menos o apelido, que fica gravado no <b>apelidos.txt</b> "
           "para as próximas lives (seção 10)."))
s.append(p("Mudando as configurações", h2))
s.append(p("Estes ficam <b>gravados no config.json</b>, como se você tivesse mudado pela página de "
           "configurações. Assim os moderadores conseguem ajustar tudo de qualquer lugar, só pelo chat."))
s.append(tabela(["Comando", "O que faz"], [
    [cmd("!voz antonio"), "Troca a voz: francisca, thalita, antonio, raquel, duarte ou maria (do Windows, "
                          f"funciona sem internet). Só {cmd('!voz')} fala a lista."],
    [cmd("!velocidade 5"), "Muda a velocidade da voz, de -10 (lenta) a 10 (rápida)."],
    [cmd("!volume 70"), "Muda o volume, de 0 a 100."],
    [cmd("!nomes"), "Liga ou desliga o “Fulano disse:” antes das mensagens."],
    [cmd("!bloquear palavra"), "Mensagens com essa palavra deixam de ser lidas. A voz não repete a palavra."],
    [cmd("!desbloquear palavra"), "Volta a ler mensagens com essa palavra."],
    [cmd("!desligar copiar"), f"Desliga um comando (o nome vai sem o !). {cmd('!ligar copiar')} liga de novo."],
    [cmd("!avisos mapa"), f"Liga ou desliga o aviso de mapa novo. {cmd('!avisos recorde')} faz o mesmo com o "
                          f"aviso de recorde. Só {cmd('!avisos')} fala como estão."],
    [cmd("!espera 10"), "Segundos que cada pessoa espera entre um comando e outro."],
    [cmd("!tamanho 150"), "Quantas letras de cada mensagem são lidas."],
    [cmd("!fila 10"), "Quantas mensagens podem ficar esperando a voz."],
    [cmd("!limitepedidos 20"), "Quantos pedidos cabem na fila."],
], [42, 128]))
s.append(dica(f"Valores fora da faixa usam o limite mais próximo: {cmd('!volume 150')} vira volume 100. "
              f"O {cmd('!ligar')} e o {cmd('!desligar')} não podem ser desligados pelo chat, senão não "
              "daria para religar."))
s.append(p("Só para você", h2))
s.append(tabela(["Comando", "O que faz"], [
    [cmd("!mod usuario"), "Torna alguém moderador (usuário do TikTok, sem o @)."],
    [cmd("!desmod usuario"), "Tira alguém dos moderadores."],
], [42, 128]))
s.append(p("Atalhos", h2))
s.append(p("Os comandos mais compridos também funcionam com um nome curto. O atalho faz exatamente o "
           "mesmo que o comando completo, e quem não pode usar o comando também não pode usar o atalho. "
           "Desligar um comando desliga os atalhos dele junto."))
s.append(tabela(["Atalho", "É o mesmo que", "Quem pode"], [
    [f"{cmd('!ajuda')} {cmd('!cmd')}", cmd("!comandos"), "Todo mundo"],
    [cmd("!mapa"), cmd("!np"), "Todo mundo"],
    [cmd("!rec"), cmd("!recorde"), "Todo mundo"],
    [cmd("!msg"), cmd("!mensagens"), "Todo mundo"],
    [cmd("!ap fulano Aninha"), cmd("!apelido fulano Aninha"), "Você e mods"],
    [cmd("!vel 5"), cmd("!velocidade 5"), "Você e mods"],
    [cmd("!vol 70"), cmd("!volume 70"), "Você e mods"],
    [f"{cmd('!bl')} {cmd('!dbl')}", f"{cmd('!bloquear')} {cmd('!desbloquear')}", "Você e mods"],
    [f"{cmd('!prox')} {cmd('!próx')}", cmd("!proximo"), "Você e mods"],
    [f"{cmd('!fechar')} {cmd('!abrir')}", f"{cmd('!fecharpedidos')} {cmd('!abrirpedidos')}", "Você e mods"],
    [cmd("!zerar"), cmd("!zerarpedidos"), "Você e mods"],
    [cmd("!limite 20"), cmd("!limitepedidos 20"), "Você e mods"],
], [50, 80, 40]))
s.append(Spacer(1, 4))
s.append(p("Os moderadores não podem criar outros moderadores: assim, se um deles fizer besteira, não "
           "consegue dar acesso a mais ninguém. O prefixo, o endereço do tosu e as opções da página também "
           "não mudam pelo chat, porque um erro de digitação no meio da live quebraria os comandos."))
s.append(p("Outros jeitos de adicionar moderadores", h2))
s.append(p("Pela página de configurações (seção 8): escreva os usuários do TikTok, sem o @, um por linha, "
           "no campo <b>Moderadores</b> e clique em <b>Salvar</b>. Vale na hora."))
s.append(p("Ou abra o <b>config.json</b> com o Bloco de Notas, procure a linha <b>moderadores</b> e "
           "coloque os usuários, entre aspas:"))
s.append(p('<font name="Mono">"moderadores": ["usuario1", "usuario2"],</font>',
           ParagraphStyle("code", parent=corpo, backColor=FUNDO, borderPadding=6, leftIndent=6)))
s.append(Spacer(1, 4))
s.append(p("Salve o arquivo e abra o programa de novo. A seção 9 explica o arquivo em detalhes."))

# ---------- 6 ----------
s += [PageBreak(), p("6. Pedidos de mapas do osu!", h1),
      p("O chat pede mapas, eles entram numa fila e você abre um de cada vez.", sub)]
s.append(p("Como o chat pede", h2))
s += itens([
    f"Pelo link: {cmd('!pedir https://osu.ppy.sh/beatmapsets/...')}",
    f"Pelo nome: {cmd('!pedir Freedom Dive')}. Útil porque o TikTok costuma bloquear links no chat.",
])
s.append(fala("Pedido de Caio anotado, posição 3."))
s.append(p("Como você abre os pedidos", h2))
s.append(passos([
    (f"Escreva {cmd('!proximo')} no chat", "A voz fala de quem é o pedido. Se você configurou o chat do osu! "
                                           "(veja abaixo), o pedido chega numa mensagem sua para você mesmo, "
                                           "dentro do jogo. Se não, abre no navegador."),
    ("Abra o mapa", "No chat do osu!, clique no pedido: pedido com link abre o mapa <b>direto no jogo</b>. "
                    "Pedido com nome abre a busca do site do osu! no navegador."),
    ("Baixe, se precisar", "Pelo navegador, você precisa estar logado no site. No lazer, dê dois cliques no "
                           "arquivo <b>.osz</b> baixado."),
]))
s.append(p("Mandando os pedidos para o chat do osu!", h2))
s.append(passos([
    ("Pegue a senha de IRC", "No site do osu!, clique no seu avatar, <b>Configurações</b>, e role até "
                             "<b>Legacy API</b>, parte <b>IRC</b>. Ela <b>não é</b> a senha da sua conta."),
    ("Coloque no config.json", "Com o programa fechado, preencha <b>osu_usuario</b> com o seu nome no osu! e "
                               "<b>osu_irc_senha</b> com a senha de IRC (seção 9)."),
    ("Pronto", f"O próximo {cmd('!proximo')} já chega no seu chat do osu!."),
]))
s.append(atencao("Não mostre a senha de IRC na live: com ela, qualquer um escreve no chat do osu! "
                 "no seu nome. Por isso a página de configurações não mostra a senha. Se ela vazar, "
                 "gere outra no site do osu!."))
s.append(dica("Se a senha estiver errada ou o osu! não responder, a janela do programa avisa e o "
              "pedido abre no navegador, como antes."))
s.append(p("Regras da fila", h2))
s += itens([
    "Cada pessoa pode ter <b>um pedido por vez</b> na fila.",
    f"A fila aceita até <b>30 pedidos</b>. Você ou um moderador pode mudar com {cmd('!limitepedidos 20')}.",
    "A fila aparece no arquivo <b>pedidos.txt</b>, atualizado na hora. Dá para deixar aberto durante a live.",
    "A fila <b>zera</b> quando o programa é fechado.",
])

# ---------- 7 ----------
s += [PageBreak(), p("7. osu! ao vivo", h1),
      p("Estes recursos precisam do <b>tosu</b> aberto junto com o osu! (o programa abre ele sozinho). "
        "Se o tosu estiver fechado, "
        "o chat funciona normal e estes comandos respondem “Não consegui ver o osu agora.”", sub)]
s.append(p("Comandos", h2))
s.append(p(f"{cmd('!np')} — mapa atual"))
s.append(fala("Agora: Rhapsody - Emerald Sword, dificuldade Paladin, 6,5 estrelas, com HD DT."))
s.append(p(f"{cmd('!pp')} — PP do SS com os mods selecionados"))
s.append(fala("SS com HD DT HR vale 1.773 PP. Com 98 por cento, 1.630, e com 95, 1.471."))
s.append(p(f"{cmd('!rank')} — seu perfil"))
s.append(fala("capucci está em número 124.519 no mundo, com 4.796 PP e 97,36 por cento de precisão."))
s.append(p(f"{cmd('!recorde')} — melhor jogada da live"))
s.append(fala("O recorde da live é 513 PP em Chronostasis, com HD DT."))
s.append(dica(f"O {cmd('!pp')} acompanha os mods na hora: trocou os mods na lista de músicas, "
              f"o próximo {cmd('!pp')} já usa os novos."))
s.append(p("Avisos automáticos", h2))
s.append(tabela(["Aviso", "Quando acontece"], [
    ["<b>Mapa novo</b><br/><i>“Agora: Artista - Música, dificuldade X, 5,6 estrelas.”</i>",
     "Quando você <b>começa a jogar</b> um mapa diferente do anterior. Não fala enquanto você só navega pela lista de músicas."],
    ["<b>Recorde da live</b><br/><i>“Novo recorde da live! 513 PP em Chronostasis, com HD DT.”</i>",
     "Quando você <b>passa</b> um mapa com mais PP que todas as jogadas anteriores da live. Fail não conta."],
], [85, 85]))
s.append(Spacer(1, 6))
s.append(p("O recorde começa do zero toda vez que o programa é aberto."))
s.append(dica("Para conferir se o tosu está funcionando, abra <b>http://127.0.0.1:24050</b> no navegador "
              "com o osu! aberto."))

# ---------- 8 ----------
s += [PageBreak(), p("8. Ligando e desligando funções", h1),
      p("Existem três jeitos: pelo chat, durante a live (seção 5); pela página de configurações; ou "
        "editando o config.json à mão. Os dois primeiros valem na hora e ficam gravados.", sub)]
s.append(p("Pela página de configurações (o jeito mais fácil)", h2))
s.append(passos([
    ("Abra o LeitorChat", "A página só funciona com o programa aberto, ao vivo ou no modo de teste (seção 3)."),
    ("Abra a página no navegador", "Digite <b>http://localhost:8765</b> na barra de endereço. "
                                   "Dica: salve nos favoritos."),
    ("Mude o que quiser e clique em Salvar", "Vale <b>na hora</b>, sem fechar o programa, e fica gravado "
                                             "no config.json para as próximas lives."),
]))
s.append(p("A página tem todas as opções da seção 9: voz, velocidade e volume, palavras bloqueadas, "
           "moderadores, uma caixinha para ligar e desligar cada comando, pedidos e osu!. Se algum valor não "
           "puder ser usado (um volume acima de 100, por exemplo), a página avisa o que foi ajustado."))
s.append(p("Pelo celular", h2))
s.append(p("Por padrão a página só abre no próprio PC. Para mexer pelo celular:"))
s.append(passos([
    ("Ligue “Abrir na rede local”", "No fim da página, marque a opção e salve."),
    ("Feche e abra o LeitorChat de novo", "A janela do programa mostra o endereço para o celular, "
                                          "algo como <b>http://192.168.0.10:8765</b>."),
    ("Permita no Windows", "Na primeira vez, o firewall pergunta se libera o LeitorChat na rede: clique em <b>Permitir</b>."),
    ("Abra o endereço no celular", "O celular precisa estar no <b>mesmo Wi-Fi</b> que o PC."),
]))
s.append(atencao("Com “Abrir na rede local” ligado, <b>qualquer pessoa no mesmo Wi-Fi</b> consegue abrir a "
                 "página e mudar as configurações. Use só numa rede de confiança, como a da sua casa."))
s.append(p("Pelo config.json", h2))
s.append(p("Abra o <b>config.json</b> (na pasta do programa) com o Bloco de Notas, mude o que quiser, "
           "<b>salve e abra o programa de novo</b>. A seção 9 explica cada opção. Regras para editar:"))
s += itens([
    "<b>true</b> = ligado, <b>false</b> = desligado (tudo minúsculo).",
    "Textos ficam entre aspas duplas: <b>\"assim\"</b>.",
    "Listas ficam entre colchetes: <b>[\"copiar\", \"top\"]</b>.",
    "Uma <b>vírgula</b> no fim de cada linha, menos na última.",
    "Para desligar um comando, coloque o nome dele, sem o !, em <b>comandos_desativados</b>. "
    "Ele passa a ser ignorado em silêncio e some do !comandos.",
])
s.append(Spacer(1, 4))
s.append(atencao("Se o arquivo tiver algum erro de digitação, o programa avisa <b>a linha do problema</b> "
                 "ao abrir e usa as configurações padrão, sem fechar. Se apagar o config.json, ele cria um novo."))
s.append(p("Resumo", h2))
s.append(p("Tudo o que está na coluna “No config.json” também pode ser mudado pela página de configurações. "
           "Os comandos de chat que mudam uma configuração também gravam no config.json."))
s.append(tabela(["Função", "Durante a live", "No config.json"], [
    ["Ler o chat", f"{cmd('!mudo')} / {cmd('!voltar')}", "—"],
    ["“Fulano disse:”", cmd("!nomes"), '"ler_nome": true / false'],
    ["Velocidade da voz", cmd("!velocidade 5"), '"velocidade": 5'],
    ["Volume", cmd("!volume 70"), '"volume": 70'],
    ["Palavras bloqueadas", f"{cmd('!bloquear')} / {cmd('!desbloquear')}", '"palavras_bloqueadas": ["palavra"]'],
    ["Qualquer comando", f"{cmd('!desligar')} / {cmd('!ligar')}", '"comandos_desativados": ["copiar"]'],
    ["Aceitar pedidos", f"{cmd('!fecharpedidos')} / {cmd('!abrirpedidos')}", "—"],
    ["Aviso de mapa novo", cmd("!avisos mapa"), '"avisar_mapa": true / false'],
    ["Aviso de recorde", cmd("!avisos recorde"), '"avisar_recorde": true / false'],
    ["Moderadores", f"{cmd('!mod')} / {cmd('!desmod')} (só você)", '"moderadores": ["usuario"]'],
    ["Tempo entre comandos", cmd("!espera 15"), '"espera_comando": 15'],
    ["Tamanho das mensagens", cmd("!tamanho 200"), '"tamanho_maximo": 200'],
    ["Fila de fala", cmd("!fila 15"), '"fila_maxima": 15'],
    ["Tamanho da fila de pedidos", cmd("!limitepedidos 30"), '"pedidos_maximos": 30'],
    ["Voz", cmd("!voz francisca"), '"voz": "pt-BR-FranciscaNeural"'],
    ["Página no celular", "—", '"web_rede_local": true / false'],
], [45, 50, 75]))

# ---------- 9 (config.json) ----------
import ast as _ast
import json as _json


def padroes() -> dict:
    """Os valores padrão, lidos do leitor_chat.py (o config.json é de quem usa, não serve de padrão)."""
    arvore = _ast.parse(open(PROGRAMA, encoding="utf-8").read())
    valores, ordem = {}, []
    for no in arvore.body:
        if isinstance(no, _ast.Assign) and isinstance(no.targets[0], _ast.Name):
            nome = no.targets[0].id
            if nome == "OPCOES":  # a ordem das opções, igual à do config.json que o programa grava
                ordem = [c.value for c in _ast.walk(no.value) if isinstance(c, _ast.Constant)
                         and isinstance(c.value, str) and c.value.isupper()]
            else:
                try:
                    valores[nome] = _ast.literal_eval(no.value)
                except ValueError:
                    pass
    return {nome.lower(): valores[nome] for nome in ordem}


_cfg = padroes()
codigo = ParagraphStyle("codigo", parent=corpo, fontName="Mono", fontSize=9, leading=12.5,
                        backColor=FUNDO, borderPadding=8, leftIndent=8, rightIndent=8, spaceBefore=4, spaceAfter=12)


def bloco(linhas):
    return p("<br/>".join(l.replace(" ", "&nbsp;") for l in linhas), codigo)


def j(v):
    return _json.dumps(v, ensure_ascii=False)


def opcoes(linhas):
    return tabela(["Opção", "Padrão", "O que faz"],
                  [[f'<font name="Mono" size="8.5">{n}</font>',
                    PADRAO_TEXTO.get(n, f'<font name="Mono" size="8.5">{j(_cfg[n])}</font>'), t]
                   for n, t in linhas], [42, 44, 84])


# valores longos demais para a coluna: descritos em palavras
PADRAO_TEXTO = {"tosu_url": "<i>o endereço padrão do tosu</i>"}


s += [PageBreak(), p("9. O arquivo config.json", h1),
      p("O <b>config.json</b> guarda todas as configurações do app. Ele fica na mesma pasta do "
        "LeitorChat.exe e é lido <b>toda vez que o programa abre</b>. Ele não vem no zip: o programa "
        "cria na primeira vez, e por isso uma versão nova extraída por cima não apaga as suas configurações.", sub)]
s.append(p("Como mudar uma configuração", h2))
s.append(passos([
    ("Feche o LeitorChat", "As mudanças só valem quando o programa abre."),
    ("Abra o config.json", "Clique com o botão direito no arquivo, <b>Abrir com</b> e <b>Bloco de Notas</b>."),
    ("Mude o valor e salve", "Troque só o valor, do lado direito dos dois-pontos. Salve com <b>Ctrl+S</b>."),
    ("Abra o LeitorChat de novo", "Se tiver algum erro no arquivo, ele avisa logo ao abrir."),
]))
s.append(dica("Pela página de configurações (seção 8) não precisa fechar o programa nem se preocupar "
              "com vírgulas e aspas: ela grava o config.json certinho para você."))
s.append(p("O arquivo completo", h2))
s.append(p("É assim que ele vem, com os valores padrão:"))
s.append(bloco(_json.dumps(_cfg, ensure_ascii=False, indent=2).splitlines()))
s.append(p("Cada linha tem o <b>nome da opção</b> entre aspas, dois-pontos e o <b>valor</b>. "
           "Os nomes nunca mudam; você só mexe nos valores."))

s.append(PageBreak())
s.append(p("Regras do formato", h2))
s.append(tabela(["Tipo de valor", "Como escrever", "Exemplo"], [
    ["<b>Texto</b>", "Entre aspas duplas", '<font name="Mono">"windows"</font>'],
    ["<b>Número</b>", "Sem aspas e sem vírgula decimal", '<font name="Mono">80</font>'],
    ["<b>Ligado / desligado</b>", "<b>true</b> ou <b>false</b>, tudo minúsculo e sem aspas", '<font name="Mono">true</font>'],
    ["<b>Lista</b>", "Entre colchetes, itens entre aspas e separados por vírgula", '<font name="Mono">["ana", "caio"]</font>'],
    ["<b>Lista vazia</b>", "Só os colchetes", '<font name="Mono">[]</font>'],
], [40, 75, 55]))
s.append(Spacer(1, 6))
s += itens([
    "Cada linha termina com <b>vírgula</b>, <b>menos a última</b> antes do <b>}</b>.",
    "O arquivo começa com <b>{</b> e termina com <b>}</b>.",
    "Não dá para escrever comentários ou anotações no arquivo.",
    "Não precisa ter todas as opções: as que faltarem usam o valor padrão.",
])

s.append(p("Todas as opções", h2))
s.append(p("<b>Voz e leitura do chat</b>", rotulo))
s.append(opcoes([
    ("voz", "Qual voz fala. Opções: <b>\"pt-BR-FranciscaNeural\"</b> (feminina), "
            "<b>\"pt-BR-ThalitaMultilingualNeural\"</b> (feminina), <b>\"pt-BR-AntonioNeural\"</b> (masculina), "
            "<b>\"pt-PT-RaquelNeural\"</b> (Portugal, feminina), <b>\"pt-PT-DuarteNeural\"</b> (Portugal, masculina) "
            "ou <b>\"windows\"</b> (voz do Windows, funciona sem internet)."),
    ("velocidade", "Velocidade da voz, de <b>-10</b> (bem lenta) a <b>10</b> (bem rápida)."),
    ("volume", "Volume da voz, de <b>0</b> a <b>100</b>."),
    ("ler_nome", "<b>true</b>: fala “Fulano disse: mensagem”. <b>false</b>: fala só a mensagem."),
    ("tamanho_maximo", "Quantos caracteres de cada mensagem são lidos. O resto é cortado."),
    ("fila_maxima", "Quantas mensagens podem ficar esperando a voz. Se o chat passar disso, "
                    "as mais antigas são puladas, para a voz não ficar atrasada."),
    ("palavras_bloqueadas", "Mensagens com qualquer uma dessas palavras não são lidas. "
                            "Ex.: <b>[\"spam\", \"feio\"]</b>."),
]))
s.append(Spacer(1, 8))
s.append(p("<b>Comandos</b>", rotulo))
s.append(opcoes([
    ("prefixo", "O símbolo que marca um comando no começo da mensagem."),
    ("moderadores", "Usuários do TikTok, sem o @, que podem usar os comandos de moderação. "
                    "Você, o dono da live, já pode sempre. Ex.: <b>[\"ana\", \"caio\"]</b>."),
    ("espera_comando", "Segundos que cada pessoa espera entre um comando e outro (anti-spam). "
                       "Não vale para você e os moderadores."),
    ("comandos_desativados", "Comandos desligados, sem o !. Eles passam a ser ignorados em silêncio "
                             "e saem do !comandos. Ex.: <b>[\"copiar\", \"top\"]</b>."),
]))
s.append(Spacer(1, 8))
s.append(p("<b>Pedidos de mapas e osu!</b>", rotulo))
s.append(opcoes([
    ("pedidos_maximos", "Quantos pedidos cabem na fila. Quando enche, o !pedir responde que a fila está cheia."),
    ("avisar_mapa", "<b>true</b>: a voz anuncia quando você começa a jogar um mapa novo."),
    ("avisar_recorde", "<b>true</b>: a voz anuncia quando você bate o recorde de PP da live."),
    ("tosu_url", "Endereço onde o app busca os dados do tosu: <b>http://127.0.0.1:24050/json/v2</b>. "
                 "Só mude se você trocou a porta nas configurações do tosu."),
    ("osu_usuario", "Seu nome no osu!. Com ele e a senha de IRC, o !proximo manda o pedido no seu chat "
                    "do osu! (seção 6)."),
    ("osu_irc_senha", "A senha de IRC do osu! (Configurações, Legacy API, no site). <b>Não é</b> a senha "
                      "da conta. Vazio: o !proximo abre no navegador."),
]))
s.append(Spacer(1, 8))
s.append(p("<b>Página de configurações</b> (estas duas só valem quando o programa abre de novo)", rotulo))
s.append(opcoes([
    ("web_porta", "A porta da página: o número no fim de <b>http://localhost:8765</b>. "
                  "Troque se outro programa já usar essa porta. <b>0</b> desliga a página."),
    ("web_rede_local", "<b>true</b>: a página abre também no celular ou em outro PC do mesmo Wi-Fi "
                       "(qualquer pessoa nessa rede consegue mexer). <b>false</b>: só neste PC."),
]))

s.append(p("Exemplos prontos", h2))
s.append(p("Copie só as linhas que interessam para dentro do seu config.json, trocando os valores "
           "que já estão lá. Lembre da vírgula no fim de cada linha, menos na última."))
s.append(p("<b>Voz masculina, um pouco mais rápida e mais baixa</b>", rotulo))
s.append(bloco(['"voz": "pt-BR-AntonioNeural",', '"velocidade": 3,', '"volume": 70,']))
s.append(p("<b>Ler só a mensagem, sem o nome de quem mandou</b>", rotulo))
s.append(bloco(['"ler_nome": false,']))
s.append(p("<b>Dois moderadores e sem o !copiar</b>", rotulo))
s.append(bloco(['"moderadores": ["ana", "caio"],', '"comandos_desativados": ["copiar"],']))
s.append(p("<b>Live sem osu! (só ler o chat)</b>", rotulo))
s.append(bloco(['"comandos_desativados": ["np", "pp", "rank", "recorde", "pedir", "pedidos",',
                '                         "proximo", "fecharpedidos", "abrirpedidos", "zerarpedidos"],',
                '"avisar_mapa": false,', '"avisar_recorde": false']))

s.append(p("Avisos ao abrir o programa", h2))
s.append(p("Se algo estiver errado no config.json, o programa mostra um aviso com <b>***</b> na janela "
           "e continua funcionando:"))
s.append(tabela(["O aviso diz", "O que aconteceu", "O que fazer"], [
    ["ERRO no config.json, perto da linha X",
     "O arquivo tem um erro de formato. O programa usa <b>todas</b> as configurações padrão.",
     "Veja a linha indicada e a de cima: falta ou sobra vírgula? true/false com maiúscula? Aspas faltando?"],
    ["não conheço a opção \"...\"", "Um nome de opção está escrito errado. Só essa linha é ignorada.",
     "Corrija o nome, comparando com a lista de opções."],
    ["\"...\" deveria ser ...", "O valor é do tipo errado, como um texto onde devia ter número. "
                              "Só essa opção usa o padrão.", "Corrija o valor seguindo as regras do formato."],
    ["\"...\" vai de X a Y", "O número passou do limite, como um volume 150. O programa usa o limite mais próximo.",
     "Coloque um número dentro da faixa."],
    ["\"prefixo\" não pode ficar vazio", "Sem prefixo, qualquer mensagem viraria comando. Fica o anterior.",
     "Coloque um símbolo, como <b>\"!\"</b>."],
    ["Não consegui abrir a página de configurações", "Outro programa já usa a porta da página. "
     "O resto do app funciona normal.", "Troque <b>web_porta</b> para outro número, como 8766."],
], [48, 62, 60]))
s.append(Spacer(1, 6))
s.append(p("Os mesmos avisos aparecem na página de configurações quando você clica em Salvar."))
s.append(dica("Se bagunçar o arquivo e quiser começar de novo, <b>apague o config.json</b>. "
              "Na próxima vez que abrir, o programa cria um novo com os valores padrão."))

# ---------- 10 ----------
s += [PageBreak(), p("10. Arquivos criados pelo app", h1),
      p("Todos ficam na mesma pasta do programa.", sub)]
s.append(tabela(["Arquivo", "O que tem"], [
    ["<b>registros\\live_DATA_HORA.csv</b>", "Planilha (abre no Excel) com quem entrou na live, a que horas e "
                                            "quantas mensagens mandou. Salva sozinha a cada 5 segundos."],
    ["<b>apelidos.txt</b>", "Os apelidos usados pela voz. Pode editar durante a live, vale na hora."],
    ["<b>pedidos.txt</b>", "A fila de pedidos de mapas, atualizada na hora."],
    ["<b>config.json</b>", "As configurações (seção 9). O programa cria na primeira vez que abre; "
                           "se apagar, ele cria de novo com os valores padrão."],
], [55, 115]))
s.append(Spacer(1, 8))
s.append(p("Editando apelidos à mão", h2))
s.append(p("Um apelido por linha, no formato:"))
s.append(p('<font name="Mono">usuario_do_tiktok = Apelido</font>',
           ParagraphStyle("code2", parent=corpo, backColor=FUNDO, borderPadding=6, leftIndent=6)))
s.append(Spacer(1, 4))
s.append(atencao("Se a planilha estiver aberta no Excel, o programa não consegue salvar. Feche o Excel "
                 "antes de encerrar o programa para salvar a versão final."))

# ---------- 10 ----------
s += [p("11. Problemas comuns", h1), Spacer(1, 4)]
s.append(tabela(["Problema", "Solução"], [
    ["Aparece <b>UserOfflineError</b>", "A live não está ao vivo ou o usuário está errado. Comece a live antes "
     "de abrir o programa. Para testar sem live, use o modo de teste (seção 3)."],
    ["“O Windows protegeu o computador”", "Clique em <b>Mais informações</b> e depois em <b>Executar assim mesmo</b>."],
    ["A voz não fala nada", f"Confira a internet e se alguém usou {cmd('!mudo')}. Sem internet, use \"voz\": \"windows\" no config.json."],
    [f"{cmd('!np')}, {cmd('!pp')} ou {cmd('!rank')} respondem “Não consegui ver o osu agora”",
     "Veja se a janela do tosu está aberta (se não, abra o <b>tosu\\tosu.exe</b>) e confira em http://127.0.0.1:24050."],
    ["Aparece “tosu não encontrado na pasta tosu”", "Falta o <b>tosu.exe</b> dentro da pasta <b>tosu</b>, "
     "ao lado do LeitorChat.exe. Extraia o zip de novo. O chat funciona; só os comandos do osu! não respondem."],
    ["Aparece “o relógio do computador está X minutos adiantado” (ou atrasado)",
     "O programa já usa a hora da internet e funciona normal. Para acertar o relógio do Windows: "
     "Configurações → Hora e idioma → Data e hora → <b>Sincronizar agora</b>."],
    ["Mudei o config.json e nada mudou", "Feche e abra o programa de novo. Veja se apareceu algum aviso de erro do config.json ao abrir."],
    ["A página de configurações não abre", "O LeitorChat precisa estar aberto. Confira o endereço "
     "<b>http://localhost:8765</b> e se apareceu algum aviso sobre a página na janela do programa."],
    ["A página não abre no celular", "Ligue “Abrir na rede local”, reabra o programa, use o endereço que aparece "
     "na janela e confira se o celular está no mesmo Wi-Fi. Se o Windows perguntou, você precisa ter clicado em <b>Permitir</b>."],
    ["Quero testar sem estar ao vivo", "Digite <b>teste</b> no lugar do usuário do TikTok (seção 3)."],
    ["A planilha não salvou", "Feche o Excel e encerre o programa de novo."],
    ["Um comando não responde", "Pode ser o limite de 15 segundos por pessoa, ou o comando está em comandos_desativados."],
], [60, 110]))

doc = SimpleDocTemplate(SAIDA, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                        topMargin=18 * mm, bottomMargin=22 * mm, title="Leitor de Chat — Guia de uso",
                        author="Leitor de Chat", subject="Como usar o Leitor de Chat")
doc.build(s, onFirstPage=capa, onLaterPages=rodape)
print(f"PDF gerado: {SAIDA}")
