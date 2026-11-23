#!/usr/bin/env bash
# Cadastra Secrets do NatoDark na Cloudflare SEM imprimir nem gravar valores.
#
# Uso (no seu computador, com as chaves na sua mão):
#   export CLOUDFLARE_API_TOKEN='seu_token'
#   export CLOUDFLARE_ACCOUNT_ID='seu_account_id'
#   # opcional: exporte as chaves abaixo, ou deixe em backend/.env (gitignored)
#   ./scripts/set-secrets.sh worker     # natodark-studio
#   ./scripts/set-secrets.sh pages      # natodark (Pages Function /api/*)
#   ./scripts/set-secrets.sh all
#
# O script aceita apenas variáveis de ambiente. Nada é escrito em disco.

set -euo pipefail

ALVO="${1:-all}"
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Carrega backend/.env se existir (arquivo já ignorado pelo git).
if [[ -f "$RAIZ/backend/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$RAIZ/backend/.env"
  set +a
fi

SECRETS=(
  GEMINI_API_KEY
  GOOGLE_API_KEY
  NVIDIA_API_KEY
  GROQ_API_KEY
  OPENROUTER_API_KEY
  OPEN_ROUTER_API_KEY
  CF_API_TOKEN
  CF_ACCOUNT_ID
  CLOUDFLARE_ACCOUNT_ID
  OPENAI_API_KEY
  ANTHROPIC_API_KEY
  OLLAMA_API_KEY
  API_TOKEN
  LLM7_API_KEY
  AION_API_KEY
  AXFORGE_API_KEY
  ZAI_API_KEY
  GONKA_API_KEY
  MODELSCOPE_API_KEY
  SILICONFLOW_API_KEY
  COHERE_API_KEY
  PEXELS_API_KEY
  PIXABAY_API_KEY
  YOUTUBE_API_KEY
)

gravar_worker() {
  echo "=== Worker natodark-studio ==="
  cd "$RAIZ/cloudflare"
  for nome in "${SECRETS[@]}"; do
    valor="${!nome:-}"
    if [[ -n "$valor" ]]; then
      printf '%s' "$valor" | npx wrangler secret put "$nome" --name natodark-studio >/dev/null
      echo "  OK    $nome"
    else
      echo "  PULA  $nome (vazio)"
    fi
  done
}

gravar_pages() {
  echo "=== Pages natodark ==="
  cd "$RAIZ"
  for nome in "${SECRETS[@]}"; do
    valor="${!nome:-}"
    if [[ -n "$valor" ]]; then
      printf '%s' "$valor" | npx wrangler pages secret put "$nome" --project-name natodark >/dev/null
      echo "  OK    $nome"
    else
      echo "  PULA  $nome (vazio)"
    fi
  done
}

case "$ALVO" in
  worker) gravar_worker ;;
  pages)  gravar_pages ;;
  all)    gravar_worker; gravar_pages ;;
  *) echo "Uso: $0 [worker|pages|all]" >&2; exit 2 ;;
esac

echo "Pronto. Nenhum valor foi exibido ou salvo no repositório."
