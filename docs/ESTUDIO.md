# NatoDark — Estúdio de vídeos para YouTube

Guia único de configuração e operação. Tudo em pt-BR.

## Arquitetura (o que roda onde)

```
                 ┌─ Cloudflare Worker (remoto) ─┐
   qualquer lugar│  roteiro via router de IA     │  ← só HTTP, sem render
                 └──────────────┬────────────────┘
                                │ roteiro_texto / blocos
   seu computador ┌─────────────▼──────────────────────────────┐
                  │ FastAPI + Next.js (estúdio local)          │
                  │  1. roteiro (router)   2. hype (HTML)      │
                  │  3. sua VOZ → Whisper → SRT sincronizado   │
                  │  4. mídia: YouTube (yt-dlp) → stock → CC
                  │  5. ffmpeg/HyperFrames local → final.mp4               │
                  └────────────────────────────────────────────┘
```

O Worker **não** renderiza vídeo: no plano free são 10 ms de CPU, 128 MB de
memória e nenhum binário ffmpeg. O render pesado fica local/VPS.

## Instalação local

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"  # baixa o modelo uma vez
.venv/bin/python -m uvicorn main:app --reload --port 8000
```

Outro terminal:

```bash
cd frontend && npm install && npm run dev
```

Abra `http://localhost:3000`.

## Checklist de chaves (estado atual: **nenhuma configurada**)

Copie `.env.example` para `.env` no `backend/`. Mesmos nomes valem como
Secrets da Cloudflare (`wrangler secret put NOME`).

| Chave | Prioridade | Função | Onde conseguir |
|---|---|---|---|
| `GEMINI_API_KEY` | **Configure esta primeiro** — gratuita, sem cartão | roteiro e queries de mídia | https://aistudio.google.com/apikey |
| `NVIDIA_API_KEY` | Gratuita (NVIDIA NIM) | roteiro longo, revisão e reserva | https://build.nvidia.com/ |
| `GROQ_API_KEY` | Gratuita — entra no fallback | títulos e roteiro rápido | https://console.groq.com/keys |
| `OPENROUTER_API_KEY` **ou** `OPEN_ROUTER_API_KEY` | Gratuita com modelos `:free` | fallback | https://openrouter.ai/keys |
| `OLLAMA_API_KEY` (opcional) | Gratuito/local | modelos locais ou Ollama Cloud | https://ollama.com/ |
| `CF_ACCOUNT_ID` + `CF_API_TOKEN` | Gratuito | Workers AI (fallback) e deploy | painel Cloudflare; token com `Workers AI - Edit` |
| `PEXELS_API_KEY` | Serviço fora do ar — **não** usar por enquanto | legado | https://www.pexels.com/api/ |
| `PIXABAY_API_KEY` | Serviço fora do ar — **não** usar por enquanto | legado | https://pixabay.com/api/docs/ |
| `UNSPLASH_ACCESS_KEY` | Gratuita (demo: 50 req/h) — **também precisa no backend local** | fotos de stock (2º da fila) | https://unsplash.com/developers |
| `API_TOKEN` | Recomendado | protege `/api` do Worker | gere um token forte você mesmo |
| `YOUTUBE_API_KEY` | **Opcional** | análise dos **seus** vídeos (metadados/comentários); **não** é preciso para baixar clipes | Google Cloud Console |
| `YOUTUBE_COOKIES_FILE` | Opcional | cookies locais se o YouTube exigir login (caminho de arquivo, **não** um Secret) | exportação do navegador |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | Pagos, opcionais | último fallback de roteiro | — |
| `HF_TOKEN` | Opcional | só cota/velocidade no download do Whisper | huggingface.co |

Sem **nenhuma** chave de IA, o router ainda tenta `ollama` local
(`OLLAMA_URL`, `OLLAMA_MODEL`). Para mídia, **YouTube vem primeiro** via
`yt-dlp` (sem chave: URL colada ou busca `ytsearch`); se falhar, segue
**Unsplash → Openverse → Wikimedia Commons** e slides locais, sempre
com `credits.json`. O download/recorte é local — nada disso roda na Cloudflare.
Pexels e Pixabay ficaram fora do ar; continuam no código, mas saíram da fila padrão.
A fila efetiva aparece em `GET http://localhost:8000/api/media/config`.

### Bancos de imagem/vídeo gratuitos — links exatos

| Banco | Link da API / cadastro | Chave? | Uso aqui |
|---|---|---|---|
| YouTube | https://www.youtube.com/ · yt-dlp: https://github.com/yt-dlp/yt-dlp | **Não** | clipes como matéria-prima (1º da fila, download local) |
| Pexels | API: https://www.pexels.com/api/ · cadastro: https://www.pexels.com/api/new/ | Sim, gratuita | **fora do ar** — legado |
| Pixabay | Docs: https://pixabay.com/api/docs/ · conta: https://pixabay.com/accounts/ | Sim, gratuita | **fora do ar** — legado |
| Openverse | API: https://api.openverse.org/v1/images/ · busca: https://openverse.org/ | **Não — confirmado HTTP 200 sem chave** | fotos CC/public domain (3º da fila) |
| Wikimedia Commons | API: https://commons.wikimedia.org/w/api.php | **Não** | fotos e vídeos (4º da fila) |
| Unsplash | API: https://unsplash.com/developers · cadastro: https://unsplash.com/oauth/applications | Sim, gratuita (Access Key) | fotos (2º da fila) |

### Clipes do YouTube (matéria-prima)

No gerador, o campo **Clipes do YouTube (opcional)** aceita uma URL por linha,
na mesma ordem dos blocos do roteiro. Se ficar vazio, o `media_scout` faz busca
por HTML (`ytsearch`) usando a sugestão visual do bloco — sem API key e sem
cota. Também dá para buscar candidatos com:

```bash
curl -s "http://localhost:8000/api/youtube/clips/search?q=aviao%20sobre%20o%20mar&limite=3"
```

O `youtube_clips.py` usa yt-dlp para baixar **só o intervalo** de cada bloco
(`youtube_inicio` + `duracao_segundos`, no máximo 30s) e o ffmpeg do
`imageio-ffmpeg` para recortar sem áudio. O arquivo vai para o storage do
projeto e o compiler faz o resto normalmente.

⚠️ **Use apenas vídeos próprios ou autorizados.** Content ID e direitos autorais
não mudam porque o trecho é curto; canal, título, URL e licença informada são
gravados em `projects/<id>/media/credits.json`. Se o YouTube pedir login,
defina `YOUTUBE_COOKIES_FILE` no seu computador (nunca na Cloudflare).

Openverse não pede chave nem cadastro: a API
`https://api.openverse.org/v1/images/` respondeu `200` sem autenticação. É só
deixar `openverse` na lista de fontes (já vem no default) — fotos CC/public
domain com autor e licença gravados no `credits.json`. Wikimedia Commons também
é sem chave e cobre vídeo. Pexels/Pixabay estão fora do ar, então não perca tempo.

Para pegar a **Access Key do Unsplash**: abra
`https://unsplash.com/oauth/applications` → **New Application** → aceite as
diretrizes da API → preencha nome e descrição.

- **Redirect URI**: o campo é obrigatório no cadastro, mas a busca com Access Key
  não usa OAuth. Coloque `https://natodark.pages.dev/` (ou
  `http://localhost:3000/` se for testar local). Só precisa ser exato se você
  implementar o fluxo de autorização do usuário depois.
- **Permissões/scopes**: deixe só o padrão `public` (leitura de dados públicos).
  Não marque `read_user`, `write_user`, `write_photos`, `read_photos` etc. —
  buscar e baixar fotos não exige escopo extra.
- Copie a **Access Key** (não a Secret Key) para `UNSPLASH_ACCESS_KEY`. A chave
  vai como `Authorization: Client-ID ...` e a API registra o download pelo
  `download_location`; o crédito do fotógrafo vai para `credits.json`.
- O app começa em **demo mode** (50 req/h). Se virar produção, peça o aumento
  para 1000 req/h no próprio painel do app. Respeite a atribuição e mantenha o
  parâmetro `ixid` nas URLs do CDN.
- ⚠️ O `media_scout` roda no **backend Python local**, não na Cloudflare. O
  Secret do Pages é usado só pelas rotas de IA (`/api/providers`,
  `/api/scripts/generate`). Para o Unsplash ser usado de fato, coloque a chave
  **também** em `backend/.env` (gitignored):
  `UNSPLASH_ACCESS_KEY=...` e reinicie o uvicorn. Confira com
  `curl -s http://localhost:8000/api/media/config`.

### Chave de API do YouTube (opcional)

Para **baixar clipes** você **não precisa** de API key — o `yt-dlp` busca por
HTML e faz o download local. A API oficial só serve para metadados/análise dos
**seus** vídeos e para hype com cota. Se quiser:

1. Abra https://console.cloud.google.com/ e crie/selecione um projeto.
2. **APIs & Services → Library** → busque **YouTube Data API v3** → **Enable**.
3. **APIs & Services → Credentials → Create credentials → API key**.
4. Na chave criada, em **Application restrictions**, escolha **IP addresses**
   e coloque o IP da máquina que roda o backend (ou **None** só para teste).
   Em **API restrictions**, marque **Restrict key → YouTube Data API v3**.
5. Copie a chave para `YOUTUBE_API_KEY` (ou `YOUTUBE_DATA_API_KEY`) no
   `backend/.env` local. O alias `YOUTUBE_API_KEY / YOUTUBE_DATA_API_KEY` aparece
   em `GET /api/youtube/config`.
6. Cota padrão: 10.000 unidades/dia; uma busca `search.list` custa 100 unidades.
   O gráfico de retenção **não** existe nessa API — só no YouTube Studio.

### Provedores extras do awesome-free-llm-apis

Repositório auditado: https://github.com/mnfst/awesome-free-llm-apis
(`lastUpdated: 2026-11-15`).

Aprovados em teste real, **sem chave**:

| Provider | Modelo aprovado | Base URL | Uso |
|---|---|---|---|
| Kilo Code | `kilo-auto/free` | `https://api.kilo.ai/api/gateway` | roteiro/títulos (1º sem chave) |
| LLM7.io | `gpt-oss:20b` | `https://api.llm7.io/v1` | roteiro/reserva |
| OVHcloud | `Meta-Llama-3_3-70B-Instruct` | `https://oai.endpoints.kepler.ai.cloud.ovh.net/v1` | reserva (2 RPM/IP) |

Opcionais (entram se a chave existir): Aion Labs (ótimo para storytelling),
AxForge, Z AI, Gonka, ModelScope, SiliconFlow e Cohere. Cohere é trial
**não-comercial**: não usar em vídeo monetizado.

### Teste de modelos e agentes

```bash
curl -s http://localhost:8000/api/models/agents
curl -s -X POST http://localhost:8000/api/models/health \
  -H 'Content-Type: application/json' \
  -d '{"testar_todos": true}'
```

Cada modelo aprovado recebe um agente com nome e sobrenome por função:
Dr. Gancho da Silva Corte Seco (roteiro), Capitão Clickbait Pereira (títulos),
Dona Curiosidade AlmeidaTrend (hype), Zé Legendinha Santos (legendas),
Prof. Pattern Interrupt Gomes (revisão) e Tio fallback Ribeiro (reserva).
Ollama só é reprovado após **3 tentativas**; os demais, após 2. Erros 429/503/524
são classificados como `instavel` (não são aprovação, mas também não queimam o modelo
por pico temporário).

**Resultado do teste real em 2026-11-22** (via `POST /api/models/health`):

| Status | Provider / modelo |
|---|---|
| aprovado | `gemini-3.5-flash-lite` (reserva: `gemini-3.1-flash-lite`) |
| aprovado | `nvidia/nemotron-3-ultra-550b-a55b` |
| aprovado | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` (OpenRouter) |
| aprovado | `kilocode/kilo-auto/free` (sem chave) |
| aprovado | `ovh/Meta-Llama-3_3-70B-Instruct` (sem chave, reserva) |
| instável | `llm7/gpt-oss:20b` (429 a partir do IP da Cloudflare) |
| reprovado | `gemini-3.8-flash` (503/524 por capacidade), `gemini-3.6-flash` (não JSON) |
| reprovado | modelos NVIDIA antigos (410 Gone) e OpenRouter `:free` antigos (virou pago/404) |
| reprovado | Ollama Cloud (`glm-5.3-flash:cloud` exige créditos; `qwen3.5:cloud` aposentado) |

O OpenRouter `:free` aprovado é **reasoning** e oscila: em um teste devolveu
`content` vazio porque os 128 tokens foram gastos no "pensamento". O router agora
aceita `reasoning`/`reasoning_content` como resposta e o health usa 512 tokens;
mesmo assim, se falhar, o fallback segue para Kilo Code / OVH.

Defaults do router já foram trocados para os aprovados. Ollama local continua
disponível se você definir `OLLAMA_URL`; a chave `OLLAMA_API_KEY` aponta para a
nuvem, que hoje não tem créditos nesta conta.

### Por que a API do YouTube é opcional

- A pesquisa de hype usa o **HTML do YouTube** (`ytInitialData`, o mesmo que o
  navegador vê) + DuckDuckGo: **sem chave, sem cota, não trava em pico de demanda**.
- A API oficial tem cota diária e serve para outra coisa: estatísticas confiáveis
  e comentários dos **seus** vídeos (`/api/youtube/*`).
- A API **não expõe gráfico de retenção**. Isso só existe no YouTube Studio.
  Para auditoria real de retenção: print do Studio + baseline de um vídeo
  vencedor do mesmo canal (ver `docs/analise-retencao-6xWASbolOXw.md`).

## Loop de produção no estúdio

1. **Pesquisa Hype** → tema/período → ranking por `hype_score` e
   `views_por_dia` → clique num título/ângulo sugerido (preenche o gerador).
2. **Gerar Roteiro** → `auto` escolhe o provedor disponível; hook, curiosidade
   distribuída, pattern interrupt, cliffhanger, loop e CTA. Regras de âncora e
   título incluídas no prompt.
3. **Buscar e aplicar mídia** → uma cena por bloco. Cole as URLs do YouTube
   (ou deixe a busca automática): YouTube → Unsplash → Openverse → Wikimedia →
   slide local. PySceneDetect ajusta o fim do clipe a uma cena completa e YuNet
   evita cortar o rosto no crop 9:16. Créditos em `credits.json`.
4. **Enviar sua voz** na aba de áudio → **Sincronizar com minha voz**: o
   faster-whisper gera SRT com timestamps reais, alinha os blocos e grava
   `subtitle_style.srt_key`. O compiler prefere esse SRT ao estimado por
   `sec_per_block`. Ativa automaticamente o modo "Queimar no Vídeo" se ele
   estivesse como "Nenhuma".
5. **Salvar Alterações** → **Compilar** → download de `final.mp4`.

Variáveis do Whisper: `WHISPER_MODEL=small`, `WHISPER_COMPUTE=int8`,
`WHISPER_LANGUAGE=pt`. Modelo `small` já baixado e testado em CPU/int8. Áudio
não sai do computador e não há custo por minuto. Para acelerar: `base`/`tiny`
(mais rápidos, menos precisos) ou `medium`/`large-v3` (mais lentos, mais exatos).

## Cloudflare (roteiro remoto)

A API roda como **Pages Function** em `functions/api/[[path]].ts`, na mesma origem
do site (`https://natodark.pages.dev/api/...`). Ela enxerga diretamente os Pages
Secrets que você já cadastrou (`GEMINI_API_KEY`, `NVIDIA_API_KEY`,
`OPEN_ROUTER_API_KEY`, `OLLAMA_API_KEY`) — não precisa copiá-los para o Worker.
`dist/_routes.json` faz a Function só rodar em `/api/*`.

O Worker separado `natodark-studio` está deployado em
`https://natodark-studio.datomoliveira.workers.dev` (commit atual). Ele é útil
para chamar a API de fora do Pages e enxerga **os próprios** Secrets — que não
são os mesmos do Pages. Para cadastrá-los sem expor valores:

```bash
export CLOUDFLARE_API_TOKEN='...'
export CLOUDFLARE_ACCOUNT_ID='9fd8bdbeea597f736671266d49bb6574'
export GEMINI_API_KEY='...'   # etc. (ou deixe em backend/.env, gitignored)
./scripts/set-secrets.sh all  # ou: worker | pages
```

O script só imprime `OK/PULA`, nunca o valor. YouTube/ffmpeg continuam locais:
Workers não têm yt-dlp nem binário ffmpeg.

Detalhes, R2 opcional e exemplos de `curl` em `cloudflare/README.md`.

## Remotion — vale ter?

**Sim, como skill de apoio — não como substituto do ffmpeg.**

- Instalada a oficial `remotion-dev/skills@remotion-best-practices`
  (v4.0.545, ~869K instalações, auditoria Gen "Safe", Socket 0 alertas;
  Snyk marca "High Risk" pelo uso de `subprocess`/`npx` e fontes externas —
  esperado para skill de render, mas exige revisão do código gerado).
- Serve para overlays, motion graphics, animação de títulos e legendas
  estilizadas com React/CSS — coisas que o ffmpeg faz com mais esforço.
- **Não foi integrada** ao pipeline atual: a renderização final continua sendo
  ffmpeg puro (determinística, sem runtime Node/Chrome, funciona em qualquer VPS).
- Não instalei `remotion-dev/remotion@video-report`: a auditoria aponta um
  padrão "write-then-execute" com dados controlados pelo usuário (URL → `.tsx`
  → `bunx remotion`). Risco desnecessário para o que precisamos.

## Ferramentas locais (WhisperX, YuNet, HyperFrames e outras)

A análise completa de viabilidade, licença, custo e hardware está em
`docs/FERRAMENTAS.md`. Resumo operacional:

- `GET /api/tools` mostra o que está realmente instalado e se cada ferramenta
  é efetiva no canal monetizado.
- **Ativas**: FFmpeg, PySceneDetect (cenas) e YuNet (crop com rosto).
- **Engine de render**: seletor **FFmpeg / HyperFrames** na tela do projeto
  (ao lado de **Compilar Vídeo**) define a engine por compilação e lembra a
  escolha no navegador. Sem seleção, vale `RENDER_ENGINE=ffmpeg` (padrão) do
  `.env`. Para usar o HyperFrames: `npm install --prefix renderer`; não é
  preciso reiniciar o backend. Render local gratuito, Apache-2.0, sem watermark;
  se faltar Chrome/ffprobe, o compiler volta para o ffmpeg sozinho.
- **Opcionais pesadas** (`backend/requirements-ml.txt`): WhisperX, MediaPipe,
  BEN2, Depth Anything **Small**, CLAP e SAM 2 (este último exige GPU).
- **Desligadas por licença**: Demucs (pesos sem licença clara) e Depth Anything
  Base/Large (CC-BY-NC). Não usar em vídeo monetizado.

## Validação executada

- `py_compile` + `import main`: OK — **38 rotas** API.
- `gerar_srt` e `alinhar_blocos`: teste com falas reais, confiança 1.0.
- `WhisperModel('small', cpu, int8)`: carregado OK.
- `npm run build --prefix frontend`: OK (Next 16.4.6, TypeScript limpo).
- `npm run typecheck --prefix cloudflare`: OK (`tsc --noEmit`).
- `npm audit`: 0 vulnerabilidades.
- PySceneDetect, YuNet e HyperFrames: testados de ponta a ponta; compile com
  `RENDER_ENGINE=hyperframes` gerou `final.mp4` com legenda e narração (fallback
  automático para ffmpeg se faltar Chrome/ffprobe).
- Seletor de engine: `POST /api/projects/{id}/compile` aceita
  `{"engine":"ffmpeg"|"hyperframes"}` (400 para valor inválido); os dois
  caminhos foram testados, incluindo HyperFrames real com `ffmpeg`/`ffprobe`
  disponíveis via `NATODARK_HYPERFRAMES_BIN`.
