# NatoDark Studio na Cloudflare

Gere roteiros pt-BR de alta retenção **de qualquer lugar**, com os modelos de
IA configurados como **Secrets** da Cloudflare — sem deixar chave no computador
e sem expor chave na API.

## O que roda na Cloudflare e o que fica local

| Tarefa | Onde | Por quê |
|---|---|---|
| Gerar roteiro (router multi-provider) | **Pages Function** `/api/*` ✅ | Roda no mesmo projeto Pages e enxerga os Secrets já cadastrados |
| Escolher queries de mídia por bloco | Pages Function / backend ✅ | Também é só texto |
| Worker separado `natodark-studio` | **deployado** ✅ | API fora do Pages; enxerga os próprios Secrets (diferentes dos do Pages) |
| Clipes do YouTube (yt-dlp + recorte) | backend local ✅ | Workers não têm yt-dlp nem ffmpeg |
| Buscar stock (Pexels/Pixabay/Openverse/Wikimedia) | backend local ✅ | Precisa das chaves de stock e storage |
| Cortar/compilar com ffmpeg | **local / VPS** ❌ no Worker | Workers têm 10 ms de CPU no plano free, 128 MB de memória e nenhum binário ffmpeg |
| Detecção de cenas, crop com rosto, HyperFrames e ML (YuNet/WhisperX/BEN2/etc.) | backend local ✅ | São binários/pesos e uso de CPU/disco; não cabem no Worker |

Ou seja: você adiantar o **roteiro remoto**; a renderização pesada continua no
seu computador (ou numa VPS/Containers, se quiser evoluir depois). Catálogo e
licenças em `docs/FERRAMENTAS.md`.

## 1. Instalar e logar

```bash
cd cloudflare
npm install
npx wrangler login
```

## 2. Colocar os modelos nos Secrets

Use o script abaixo (da raiz do repo) para cadastrar várias chaves de uma vez,
sem imprimir valores. Ele aceita variáveis de ambiente ou `backend/.env`
(gitignored) e atualiza Worker e Pages:

```bash
export CLOUDFLARE_API_TOKEN='...'
export CLOUDFLARE_ACCOUNT_ID='9fd8bdbeea597f736671266d49bb6574'
export GEMINI_API_KEY='...'   # etc.
./scripts/set-secrets.sh all  # ou: worker | pages
```

Ou, se preferir um por um, o nome é o **mesmo** do `.env.example` do backend:

```bash
# Recomendado começar por um gratuito:
npx wrangler secret put GEMINI_API_KEY        # https://aistudio.google.com/apikey

# Outros gratuitos (opcionais, entram no fallback):
npx wrangler secret put NVIDIA_API_KEY        # https://build.nvidia.com/
npx wrangler secret put GROQ_API_KEY          # https://console.groq.com/keys
npx wrangler secret put OPENROUTER_API_KEY    # https://openrouter.ai/keys
# Se você cadastrou como OPEN_ROUTER_API_KEY, use esse nome — o router aceita os dois.
npx wrangler secret put OLLAMA_API_KEY        # opcional: Ollama Cloud (https://ollama.com)
npx wrangler secret put CF_ACCOUNT_ID
npx wrangler secret put CF_API_TOKEN          # permissão "Workers AI - Edit"

# Mídia automática (opcionais, gratuitas):
npx wrangler secret put PEXELS_API_KEY        # https://www.pexels.com/api/
npx wrangler secret put PIXABAY_API_KEY       # https://pixabay.com/api/docs/
npx wrangler secret put UNSPLASH_ACCESS_KEY   # https://unsplash.com/developers

# Pagos, só se quiser:
npx wrangler secret put OPENAI_API_KEY
npx wrangler secret put ANTHROPIC_API_KEY

# Protege a API ( recomendado ) — gere um token forte:
npx wrangler secret put API_TOKEN
```

O Worker usa `SCRIPT_PROVIDER=auto` (definido em `wrangler.toml`) e tenta,
nesta ordem, o primeiro que responder:

```
gemini -> nvidia -> groq -> openrouter
-> kilocode -> llm7 -> aionlabs -> axforge -> zai -> gonka
-> modelscope -> siliconflow -> cloudflare -> ovh
-> openai -> anthropic -> cohere -> ollama
```

Do repositório [awesome-free-llm-apis](https://github.com/mnfst/awesome-free-llm-apis),
três provedores foram **testados ao vivo e aprovados sem chave**:
Kilo Code (`kilo-auto/free`), LLM7.io (`gpt-oss:20b`) e OVHcloud
(`Meta-Llama-3_3-70B-Instruct`, reserva por causa do limite de 2 RPM/IP).
Os demais entram no router assim que a chave correspondente existir.
`Cohere` está marcado como **não-comercial** — evitar em vídeo monetizado.

### Pages x Worker (importante)

O site (`natodark.pages.dev`) é **Cloudflare Pages** e o build roda na raiz do
repo (`npm run build` → `frontend/out` copiado para `dist/`; veja `wrangler.toml`
da raiz). A API principal é a **Pages Function** em `functions/api/[[path]].ts`
— mesma origem, mesma conta, mesmos Secrets. O `cloudflare/` aqui é o Worker
separado `natodark-studio`, deployado em
`https://natodark-studio.datomoliveira.workers.dev` (Pages não aceita `main`
de Worker). As chaves dele são independentes das do Pages.

As chaves que você já cadastrou como **Pages Secrets** são usadas direto pela
Pages Function em `functions/api/[[path]].ts`. Não é preciso copiá-las para o
Worker. A Cloudflare **nunca devolve o valor de um Secret** pela API — só lista
o nome (confirmado: `GEMINI_API_KEY`, `NVIDIA_API_KEY`, `OLLAMA_API_KEY` e
`OPEN_ROUTER_API_KEY` estão no Pages).

`dist/_routes.json` garante que a Function só seja invocada em `/api/*`; o site
estático continua grátis. Os comandos `wrangler secret put` acima valem apenas
se você optar por usar também o Worker separado.

Depois de configurar, teste antes de aprovar:

```bash
curl -s https://natodark.pages.dev/api/models/health \
  -H 'Content-Type: application/json' \
  -d '{"testar_todos": true}'
```

Ollama é testado 3 vezes antes de ser reprovado; os demais, 2 vezes.

Para fixar um provedor/modelo sem mexer no código:

```bash
npx wrangler secret put SCRIPT_PROVIDER   # ex.: groq
npx wrangler secret put SCRIPT_MODEL      # ex.: gemini-3.5-flash-lite
```

## 3. Deploy

```bash
npx wrangler deploy
```

URL final: `https://natodark-studio.<seu-subdominio>.workers.dev`

## 4. Usar

```bash
# Descobre quais provedores estão configurados (nunca devolve as chaves)
curl https://natodark.pages.dev/api/providers \
  -H 'Authorization: Bearer SEU_API_TOKEN'

# Gera o roteiro
curl -X POST https://natodark.pages.dev/api/scripts/generate \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer SEU_API_TOKEN' \
  -d '{
    "tema": "Um caminhoneiro parou para jantar e descobriu algo aterrorizante",
    "duracao_segundos": 60,
    "formato": "shorts",
    "provider": "auto"
  }'
```

Resposta (mesmo formato do backend Python):

```json
{
  "titulo": "...",
  "thumbnail_text": "...",
  "blocos": [{ "tipo": "hook", "fala": "...", "sugestao_visual": "...", "duracao_segundos": 3 }],
  "roteiro_texto": "uma fala por linha",
  "roteiro_json": { "...": "..." },
  "modo": "gemini",
  "modelo": "gemini-3.8-flash",
  "tentativas": [],
  "fallback_usado": false
}
```

Cole `roteiro_texto` no campo de roteiro do projeto local — o botão
**"Buscar e aplicar mídia"** lê os blocos e monta a timeline.

### Guardar roteiros no R2 (opcional)

```bash
npx wrangler r2 bucket create natodark-roteiros
```

Descomente o bloco `[[r2_buckets]]` em `wrangler.toml` e faça deploy de novo.
A resposta passa a incluir `id`; depois:

- `GET /api/scripts` — lista os roteiros salvos
- `GET /api/scripts/:id` — baixa um roteiro
- `DELETE /api/scripts/:id` — remove um roteiro

## 5. Segurança

- Chaves ficam em Secrets; **nunca** aparecem em logs, erros ou em
  `/api/providers`.
- `API_TOKEN` protege todas as rotas `/api`. Sem ele, o Worker fica aberto —
  não faça isso em produção.
- `ALLOWED_ORIGIN` (opcional) restringe CORS ao seu domínio.

## 6. Desenvolvimento local

Crie `cloudflare/.dev.vars` (já ignorado pelo git):

```env
GEMINI_API_KEY=sua_chave
API_TOKEN=um_token_local
```

```bash
npx wrangler dev
npm run typecheck
```
