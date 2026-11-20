// Secrets = variaveis de ambiente do Worker.
// Configure com: wrangler secret put NOME_DA_CHAVE
export interface Env {
  GEMINI_API_KEY?: string;
  GOOGLE_API_KEY?: string;
  GEMINI_MODEL?: string;

  GROQ_API_KEY?: string;
  GROQ_MODEL?: string;

  OPENROUTER_API_KEY?: string;
  OPENROUTER_MODEL?: string;

  CF_ACCOUNT_ID?: string;
  CLOUDFLARE_ACCOUNT_ID?: string;
  CF_API_TOKEN?: string;
  CLOUDFLARE_API_TOKEN?: string;
  CF_AI_MODEL?: string;

  OPENAI_API_KEY?: string;
  OPENAI_MODEL?: string;

  ANTHROPIC_API_KEY?: string;
  ANTHROPIC_MODEL?: string;

  OLLAMA_URL?: string;
  OLLAMA_MODEL?: string;

  SCRIPT_PROVIDER?: string;
  SCRIPT_MODEL?: string;
  ALLOWED_ORIGIN?: string;
  // Recomendado: exige Authorization: Bearer <token> em todas as rotas /api.
  API_TOKEN?: string;

  // Opcional: bucket R2 para guardar os roteiros gerados.
  SCRIPTS?: R2Bucket;
}
