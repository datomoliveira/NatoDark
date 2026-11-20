# NatoDark Studio na Cloudflare

Gere roteiros pt-BR de alta retenção **de qualquer lugar**, com os modelos de
IA configurados como **Secrets** da Cloudflare — sem deixar chave no computador
e sem expor chave na API.

## O que roda na Cloudflare e o que fica local

| Tarefa | Onde | Por quê |
|---|---|---|
| Gerar roteiro (router multi-provider) | **Worker** ✅ | É só uma chamada HTTP ao modelo; cabe tranquilo no Workers |
| Escolher queries de mídia por bloco | Worker / backend ✅ | Também é só texto |
| Buscar stock (Pexels/Pixabay/Wikimedia) | backend local ✅ | Precisa das chaves de stock e storage |
| Cortar/compilar com ffmpeg | **local / VPS** ❌ no Worker | Workers têm 10 ms de CPU no plano free, 128 MB de memória e nenhum binário ffmpeg |

Ou seja: você adiantar o **roteiro remoto**; a renderização pesada continua no
seu computador (ou numa VPS/Containers, se quiser evoluir depois).

## 1. Instalar e logar

```bash
cd cloudflare
npm install
npx wrangler login
```

## 2. Colocar os modelos nos Secrets

Rode um comando por chave que você quer usar. O nome é o **mesmo** do
`.env.example` do backend:

```bash
# Recomendado começar por um gratuito:
npx wrangler secret put GEMINI_API_KEY        # https://aistudio.google.com/apikey

# Outros gratuitos (opcionais, entram no fallback):
npx wrangler secret put GROQ_API_KEY          # https://console.groq.com/keys
npx wrangler secret put OPENROUTER_API_KEY    # https://openrouter.ai/keys
npx wrangler secret put CF_ACCOUNT_ID
npx wrangler secret put CF_API_TOKEN          # permissão "Workers AI - Edit"

# Pagos, só se quiser:
npx wrangler secret put OPENAI_API_KEY
npx wrangler secret put ANTHROPIC_API_KEY

# Protege a API ( recomendado ) — gere um token forte:
npx wrangler secret put API_TOKEN
```

O Worker usa `SCRIPT_PROVIDER=auto` (definido em `wrangler.toml`) e tenta,
nesta ordem, o primeiro que responder:

```
gemini -> groq -> openrouter -> cloudflare -> openai -> anthropic -> ollama
```

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
curl https://natodark-studio.SEU.workers.dev/api/providers \
  -H 'Authorization: Bearer SEU_API_TOKEN'

# Gera o roteiro
curl -X POST https://natodark-studio.SEU.workers.dev/api/scripts/generate \
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
