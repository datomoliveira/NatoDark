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
                  │  4. mídia licenciada (Pexels/Pixabay/Commons)
                  │  5. ffmpeg local → final.mp4               │
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
| `PEXELS_API_KEY` | Gratuita — melhora muito a mídia | busca de stock | https://www.pexels.com/api/ |
| `PIXABAY_API_KEY` | Gratuita | segundo fallback de stock | https://pixabay.com/api/docs/ |
| `API_TOKEN` | Recomendado | protege `/api` do Worker | gere um token forte você mesmo |
| `YOUTUBE_API_KEY` | **Opcional** | análise dos **seus** vídeos (metadados/comentários) | Google Cloud Console |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | Pagos, opcionais | último fallback de roteiro | — |
| `HF_TOKEN` | Opcional | só cota/velocidade no download do Whisper | huggingface.co |

Sem **nenhuma** chave de IA, o router ainda tenta `ollama` local
(`OLLAMA_URL`, `OLLAMA_MODEL`). Sem chaves de stock, o sistema usa
**Openverse → Wikimedia Commons** e slides locais com `credits.json`.

### Bancos de imagem/vídeo gratuitos — links exatos

| Banco | Link da API / cadastro | Chave? | Uso aqui |
|---|---|---|---|
| Pexels | API: https://www.pexels.com/api/ · cadastro: https://www.pexels.com/api/new/ | Sim, gratuita | vídeos e fotos (1º da fila) |
| Pixabay | Docs: https://pixabay.com/api/docs/ · conta: https://pixabay.com/accounts/ | Sim, gratuita | vídeos e fotos (2º da fila) |
| Openverse | API: https://api.openverse.org/v1/images/ · busca: https://openverse.org/ | **Não** | fotos CC/public domain (3º da fila) |
| Wikimedia Commons | API: https://commons.wikimedia.org/w/api.php | **Não** | fotos e vídeos (4º da fila) |
| Unsplash | https://unsplash.com/developers | Sim, gratuita | referência/fotos (não integrada ao auto-scout) |

Para pegar a chave da Pixabay: crie conta em `pixabay.com/accounts/`, entre em
**Account settings → API**, copie a chave e cole em `PIXABAY_API_KEY`.
A da Pexels: `pexels.com/api/new/` → preencha o formulário → copie em
`PEXELS_API_KEY`. Se o site estiver fora, use Openverse/Wikimedia — não travam.

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
Ollama só é reprovado após **3 tentativas**; os demais, após 2.

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
3. **Buscar e aplicar mídia** → uma cena por bloco, Pexels → Pixabay →
   Openverse → Wikimedia, com créditos em `credits.json`. **Nunca** usa clipes
   do YouTube.
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

O Worker separado `natodark-studio` (`cd cloudflare && npx wrangler deploy`)
continua disponível se você quiser a API fora do Pages; nesse caso ele precisa
dos próprios Secrets via `wrangler secret put`.

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

## Validação executada

- `py_compile` + `import main`: OK — **33 rotas** API.
- `gerar_srt` e `alinhar_blocos`: teste com falas reais, confiança 1.0.
- `WhisperModel('small', cpu, int8)`: carregado OK.
- `npm run build --prefix frontend`: OK (Next 16.4.6, TypeScript limpo).
- `npm run typecheck --prefix cloudflare`: OK (`tsc --noEmit`).
- `npm audit`: 0 vulnerabilidades.
