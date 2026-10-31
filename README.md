# Leitor de Chat — Manual

Programa que lê o chat da sua live do TikTok em voz alta, responde a comandos
e se conecta ao osu! (via tosu) para falar sobre o mapa, o PP e o seu perfil.

---

## Sumário

1. [Como abrir](#1-como-abrir)
2. [Como ligar e desligar as coisas](#2-como-ligar-e-desligar-as-coisas)
3. [Leitura do chat em voz alta](#3-leitura-do-chat-em-voz-alta)
4. [Comandos para todo mundo](#4-comandos-para-todo-mundo)
5. [Comandos de moderação](#5-comandos-de-moderação)
6. [Pedidos de mapas do osu!](#6-pedidos-de-mapas-do-osu)
7. [osu! ao vivo (tosu)](#7-osu-ao-vivo-tosu)
8. [Arquivos que o programa cria](#8-arquivos-que-o-programa-cria)
9. [Tabela-resumo: liga/desliga](#9-tabela-resumo-ligadesliga)
10. [Problemas comuns](#10-problemas-comuns)

---

## 1. Como abrir

Ordem certa para a live:

1. Abra o **osu!**
2. Abra o **tosu** (`tosu\tosu.exe`, dentro da pasta do programa) — só necessário para os recursos de osu!
3. **Comece a live** no TikTok
4. Abra o **LeitorChat.exe** (ou o `iniciar.bat`) e digite seu usuário do TikTok, sem o @

> A live precisa já estar **ao vivo** quando você abrir o programa.
> Para fechar: **Ctrl+C** na janela, depois **Enter**.

| Arquivo | Para que serve |
|---|---|
| `LeitorChat.exe` | O programa pronto. Não precisa de Python. |
| `iniciar.bat` | Abre o programa direto pelo `leitor_chat.py`. Na primeira vez, instala sozinho o Python, as bibliotecas e o tosu que faltarem. |
| `config.json` | **Todas as configurações** (veja a [seção 2](#2-como-ligar-e-desligar-as-coisas)). |
| `leitor_chat.py` | O código do programa. |
| `tosu\tosu.exe` | O tosu, que lê os dados do osu! (do GitHub oficial `tosuapp/tosu`). Se não estiver na pasta, o `instalar.bat` baixa a versão mais recente; depois ele mesmo se atualiza. |
| `README.md` | Este manual. |
| `Guia de uso - Leitor de Chat.pdf` | Guia de uso passo a passo, em PDF. |

Arquivos para quem for mexer no código:

| Arquivo | Para que serve |
|---|---|
| `gerar_exe.bat` | Gera o `LeitorChat.exe` de novo a partir do `leitor_chat.py`. |
| `gerar_manual.bat` | Gera o guia em PDF de novo (usa o `gerar_manual.py`). |
| `instalar.bat` | Instala o que falta: o Python 3.13 (pelo winget), as bibliotecas do `requirements.txt` e o tosu (uns 50 MB). Os outros `.bat` já chamam ele sozinhos. Se o download do tosu falhar, o chat funciona do mesmo jeito, só os recursos de osu! ficam sem resposta. |
| `requirements.txt` | Lista das bibliotecas Python e versões usadas. |

Na primeira vez, os `.bat` podem demorar alguns minutos para instalar tudo. Nas
próximas, eles só conferem (menos de 1 segundo) e já rodam. Se o Windows não
tiver o winget, o `instalar.bat` abre o site do Python para instalar à mão —
marque a opção **"Add python.exe to PATH"** na instalação.

> Extraia o zip inteiro para uma pasta antes de usar — não rode o programa de
> dentro do zip, senão ele não consegue salvar planilhas, apelidos e pedidos.

---

## 2. Como ligar e desligar as coisas

Existem **quatro jeitos**, dependendo do que você quer mudar:

### A) Durante a live, pelo chat (vale só até fechar o programa)

Você (ou um moderador) digita no chat do TikTok, por exemplo `!mudo`, `!nomes`,
`!fecharpedidos`. Veja a [seção 5](#5-comandos-de-moderação).

### B) Pela página de configurações (vale na hora e para sempre)

Com o programa aberto, abra **http://localhost:8765** no navegador. Lá estão
todas as opções do `config.json`; ao clicar em **Salvar**, elas já valem na
live (sem reabrir o programa) e ficam gravadas no `config.json`.

- Para mexer pelo **celular**, ligue `web_rede_local` (na própria página ou no
  `config.json`) e abra o programa de novo. Ele mostra na janela o endereço
  para digitar no celular, que precisa estar no mesmo Wi-Fi. Na primeira vez o
  Windows pergunta se libera o acesso: clique em **Permitir**. Atenção:
  qualquer pessoa nesse Wi-Fi também consegue abrir a página.
- Para trocar a porta, mude `web_porta`. Com `0` a página fica desligada.

### C) Configurações fixas, no `config.json` (vale para sempre)

Abra o `config.json` com o Bloco de Notas, mude o que quiser, **salve e abra o
programa de novo**. Não precisa fazer mais nada — vale tanto para o `.exe`
quanto para o `iniciar.bat`.

```json
{
  "voz": "pt-BR-FranciscaNeural",
  "velocidade": 1,
  "volume": 100,
  "ler_nome": true,
  ...
  "comandos_desativados": [],
  "avisar_mapa": true,
  "avisar_recorde": true
}
```

Regras do formato JSON:
- `true` = ligado, `false` = desligado (**tudo minúsculo**).
- Textos ficam entre aspas duplas: `"assim"`.
- Listas ficam entre colchetes: `["copiar", "top"]`.
- Uma **vírgula entre cada linha**, mas **nenhuma depois da última**.

Se o arquivo tiver um erro, o programa avisa a **linha do problema** e abre com
as configurações padrão (não fecha no meio da live). Opções com nome escrito
errado ou com valor do tipo errado também são avisadas.

Se você apagar o `config.json`, o programa cria um novo com os valores padrão.
Pode também deixar só as opções que quer mudar — as que faltarem usam o padrão.

### D) Desligar comandos específicos

Coloque o nome do comando (sem o `!`) em `comandos_desativados`:

```json
"comandos_desativados": ["copiar", "top", "pedir"]
```

O comando desligado passa a ser **ignorado em silêncio** (nem responde, nem é
lido em voz alta) e some da lista falada pelo `!comandos`.

---

## 3. Leitura do chat em voz alta

Toda mensagem do chat é falada: **"Fulano disse: mensagem"**.

Tratamentos automáticos:
- Links viram a palavra **"link"**
- Letras repetidas são encurtadas: "kkkkkkkk" → "kkk"
- Mensagens longas são cortadas
- Se o chat estiver rápido demais, as mensagens mais antigas são puladas para a voz não ficar atrasada
- Mensagens com palavras bloqueadas não são lidas

| Configuração | O que faz | Padrão |
|---|---|---|
| `voz` | Qual voz usar: `"pt-BR-FranciscaNeural"` (feminina), `"pt-BR-ThalitaMultilingualNeural"` (feminina), `"pt-BR-AntonioNeural"` (masculina), `"pt-PT-RaquelNeural"` (Portugal, feminina), `"pt-PT-DuarteNeural"` (Portugal, masculina) ou `"windows"` (voz do Windows, funciona sem internet). | `"pt-BR-FranciscaNeural"` |
| `velocidade` | De `-10` (lento) a `10` (rápido) | `1` |
| `volume` | De `0` a `100` | `100` |
| `ler_nome` | `true` fala "Fulano disse:", `false` fala só a mensagem | `true` |
| `tamanho_maximo` | Quantos caracteres no máximo de cada mensagem | `200` |
| `fila_maxima` | Quantas mensagens podem ficar esperando para serem lidas | `15` |
| `palavras_bloqueadas` | Mensagens com essas palavras não são lidas. Ex.: `["spam", "feio"]` | `[]` |

**Durante a live:** `!mudo` / `!voltar`, `!velocidade`, `!volume`, `!nomes`,
`!bloquear` (veja a [seção 5](#5-comandos-de-moderação)).

### Apelidos

A voz pode chamar alguém por um apelido em vez do nome do TikTok. Os apelidos
ficam no arquivo `apelidos.txt`, um por linha:

```
usuario_do_tiktok = Apelido
```

Pode editar esse arquivo **durante a live** — vale na hora. As pessoas também
podem escolher o próprio apelido com `!apelido`.

---

## 4. Comandos para todo mundo

Todo comando começa com **`!`** no início da mensagem. Maiúsculas não importam
(`!NP` = `!np`). As respostas são **faladas pela voz** (o programa não escreve
no chat do TikTok).

| Comando | O que a voz responde | Para desligar |
|---|---|---|
| `!comandos` (ou `!ajuda`) | Lista os comandos ligados | `"comandos"` em `comandos_desativados` |
| `!apelido João` | "Beleza, agora vou te chamar de João." | `"apelido"` |
| `!mensagens` | "Fulano, você mandou 12 mensagens nesta live." | `"mensagens"` |
| `!top` | As 3 pessoas que mais mandaram mensagem | `"top"` |
| `!copiar texto` | Copia o texto para o seu **Ctrl+C**. "Copiei a mensagem de Fulano." | `"copiar"` |
| `!np` (ou `!mapa`) | Mapa atual — veja a [seção 7](#7-osu-ao-vivo-tosu) | `"np"` |
| `!pp` | PP do SS com os mods atuais — [seção 7](#7-osu-ao-vivo-tosu) | `"pp"` |
| `!rank` | Seu rank global — [seção 7](#7-osu-ao-vivo-tosu) | `"rank"` |
| `!recorde` | Recorde de PP da live — [seção 7](#7-osu-ao-vivo-tosu) | `"recorde"` |
| `!pedir` | Pede um mapa — [seção 6](#6-pedidos-de-mapas-do-osu) | `"pedir"` |
| `!pedidos` | Tamanho da fila de pedidos — [seção 6](#6-pedidos-de-mapas-do-osu) | `"pedidos"` |

### Anti-spam

Cada pessoa só pode usar um comando a cada **15 segundos**. Comandos a mais
são ignorados em silêncio. Você e os moderadores não têm esse limite.

| Configuração | O que faz | Padrão |
|---|---|---|
| `espera_comando` | Segundos entre um comando e outro, por pessoa | `15` |
| `prefixo` | O símbolo que marca um comando | `"!"` |

### Sobre o `!copiar`

Qualquer pessoa da live pode usar, então alguém pode trocar o seu Ctrl+C enquanto
você está copiando outra coisa. Se atrapalhar, desligue com
`"comandos_desativados": ["copiar"]`.

---

## 5. Comandos de moderação

Só funcionam para **você** (o dono da live) e para quem estiver na lista
`moderadores` do `config.json` (usuários do TikTok, sem @). Se outra pessoa
tentar, é ignorado em silêncio.

```json
"moderadores": ["usuario1", "usuario2"]
```

Tudo o que esses comandos mudam vale **só até fechar o programa**. Para mudar
de vez, altere a configuração correspondente no `config.json`.

| Comando | O que faz | Configuração fixa equivalente |
|---|---|---|
| `!mudo` | Para de ler o chat (e apaga o que estava esperando). Os avisos automáticos também param. | — |
| `!voltar` | Volta a ler o chat | — |
| `!limpar` | Apaga as mensagens que estavam esperando para serem lidas | — |
| `!velocidade 5` | Muda a velocidade da voz (-10 a 10) | `velocidade` |
| `!volume 70` | Muda o volume (0 a 100) | `volume` |
| `!nomes` | Liga/desliga o "Fulano disse:" | `ler_nome` |
| `!bloquear palavra` | Bloqueia uma palavra | `palavras_bloqueadas` |
| `!proximo` | Abre o próximo pedido de mapa — [seção 6](#6-pedidos-de-mapas-do-osu) | — |
| `!fecharpedidos` / `!abrirpedidos` | Para / volta a aceitar pedidos | — |
| `!zerarpedidos` | Apaga a fila de pedidos | — |

Esses comandos também podem ser desligados em `comandos_desativados`.

---

## 6. Pedidos de mapas do osu!

O chat pede mapas, eles entram numa fila e você abre um de cada vez.

| Comando | Quem | O que faz |
|---|---|---|
| `!pedir https://osu.ppy.sh/beatmapsets/...` | Todos | Pede pelo link |
| `!pedir Freedom Dive` | Todos | Pede pelo nome (útil porque o TikTok costuma bloquear links) |
| `!pedidos` | Todos | "Tem 5 pedidos na fila. O seu é o número 3." |
| `!proximo` | Você/mods | Abre o próximo no navegador e fala de quem é |
| `!fecharpedidos` / `!abrirpedidos` | Você/mods | Para / volta a aceitar pedidos (também aceita `!fechar pedidos`) |
| `!zerarpedidos` | Você/mods | Apaga a fila inteira |

- Pedido com **link** abre a página do mapa; pedido com **nome** abre a busca do site do osu!.
- No **lazer**: baixe o mapa no site (logado) e dê dois cliques no `.osz`.
- Cada pessoa pode ter **um pedido por vez** na fila.
- A fila fica visível no arquivo **`pedidos.txt`**, atualizado na hora.
- A fila **zera** quando o programa é fechado.

| Configuração | O que faz | Padrão |
|---|---|---|
| `pedidos_maximos` | Tamanho máximo da fila | `30` |
| Desligar tudo | `"comandos_desativados": ["pedir", "pedidos", "proximo", "fecharpedidos", "abrirpedidos", "zerarpedidos"]` | — |

---

## 7. osu! ao vivo (tosu)

Precisa do **tosu** aberto junto com o osu! (stable ou lazer). Se o tosu estiver
fechado, o chat funciona normal e esses comandos respondem
"Não consegui ver o osu agora."

> Para conferir se o tosu está funcionando: abra **http://127.0.0.1:24050** no navegador.

### Comandos

| Comando | Exemplo do que a voz fala |
|---|---|
| `!np` / `!mapa` | "Agora: Rhapsody - Emerald Sword, dificuldade Paladin, 6,5 estrelas, com HD DT." |
| `!pp` | "SS com HD DT HR vale 1.773 PP. Com 98 por cento, 1.630, e com 95, 1.471." |
| `!rank` | "capucci está em número 124.519 no mundo, com 4.796 PP e 97,36 por cento de precisão." |
| `!recorde` | "O recorde da live é 513 PP em Chronostasis, com HD DT." |

O `!pp` usa os **mods selecionados no momento** — trocou os mods na lista de
músicas, o próximo `!pp` já usa os novos.

### Avisos automáticos

| Aviso | Quando acontece | O que a voz fala | Configuração |
|---|---|---|---|
| Mapa novo | Quando você **começa a jogar** um mapa diferente do anterior (não fala enquanto você só navega pela lista) | "Agora: Artista - Música, dificuldade X, 5,6 estrelas." | `avisar_mapa` |
| Recorde da live | Quando você **passa** um mapa com mais PP que qualquer jogada anterior da live (fail não conta) | "Novo recorde da live! 513 PP em Chronostasis, com HD DT." | `avisar_recorde` |

- Para desligar: `"avisar_mapa": false` e/ou `"avisar_recorde": false`.
- Durante a live, o `!mudo` também silencia os avisos.
- O recorde **começa do zero** cada vez que o programa é aberto.

| Configuração | O que faz | Padrão |
|---|---|---|
| `tosu_url` | Endereço do tosu (só mude se mudou a porta no tosu) | `"http://127.0.0.1:24050/json/v2"` |

---

## 8. Arquivos que o programa cria

Todos ficam na mesma pasta do programa.

| Arquivo | O que tem |
|---|---|
| `registros\live_DATA_HORA.csv` | Planilha (abre no Excel) com quem entrou na live, horário e quantas mensagens mandou. Salva sozinha a cada 5 segundos. |
| `apelidos.txt` | Apelidos usados pela voz. Pode editar à vontade. |
| `pedidos.txt` | Fila de pedidos de mapas, atualizada na hora. |

> Se a planilha estiver aberta no Excel, o programa não consegue salvar —
> feche o Excel antes de encerrar o programa para salvar a versão final.

---

## 9. Tabela-resumo: liga/desliga

| Funcionalidade | Durante a live (chat) | Fixo (`config.json`) |
|---|---|---|
| Ler o chat | `!mudo` / `!voltar` | — |
| Falar "Fulano disse:" | `!nomes` | `"ler_nome": true/false` |
| Velocidade da voz | `!velocidade N` | `"velocidade": N` |
| Volume | `!volume N` | `"volume": N` |
| Palavras bloqueadas | `!bloquear palavra` | `"palavras_bloqueadas": [...]` |
| Qualquer comando | — | `"comandos_desativados": ["nome"]` |
| Aceitar pedidos | `!fecharpedidos` / `!abrirpedidos` | — |
| Aviso de mapa novo | `!mudo` (silencia tudo) | `"avisar_mapa": true/false` |
| Aviso de recorde | `!mudo` (silencia tudo) | `"avisar_recorde": true/false` |
| Quem é moderador | — | `"moderadores": ["usuario"]` |
| Tempo anti-spam | — | `"espera_comando": N` |
| Tamanho da fila de pedidos | — | `"pedidos_maximos": N` |
| Voz | — | `"voz": "..."` |

---

## 10. Problemas comuns

| Problema | Solução |
|---|---|
| "Erro: ... UserOfflineError" | A live não está ao vivo, ou o usuário foi digitado errado. Comece a live antes de abrir o programa. |
| O Windows diz "O Windows protegeu o computador" | Clique em **Mais informações → Executar assim mesmo** (acontece porque o programa não tem assinatura digital). |
| A voz não fala nada | A voz neural precisa de internet. Sem internet, use `"voz": "windows"`. Veja também se alguém usou `!mudo`. |
| `!np`/`!pp`/`!rank` respondem "Não consegui ver o osu agora" | Abra o tosu e confira em http://127.0.0.1:24050 |
| Mudei o `config.json` e nada mudou | Feche e abra o programa de novo. Veja também se apareceu um aviso de erro no `config.json` ao abrir. |
| A planilha não salvou | Feche o Excel e encerre o programa de novo. |
