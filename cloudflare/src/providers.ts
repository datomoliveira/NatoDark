// Chamadas HTTP para todos os provedores. Nenhuma chave e escrita em log.
// No Worker, as chaves vem de env (Secrets configurados via wrangler secret put).
import type { Env } from "./types";

export type ProviderId =
  | "gemini"
  | "nvidia"
  | "groq"
  | "openrouter"
  | "cloudflare"
  | "openai"
  | "anthropic"
  | "ollama"
  | "kilocode"
  | "llm7"
  | "aionlabs"
  | "axforge"
  | "zai"
  | "gonka"
  | "modelscope"
  | "siliconflow"
  | "ovh"
  | "cohere";

export const ORDEM_FALLBACK: ProviderId[] = [
  "gemini",
  "nvidia",
  "groq",
  "openrouter",
  "kilocode",
  "llm7",
  "aionlabs",
  "axforge",
  "zai",
  "gonka",
  "modelscope",
  "siliconflow",
  "cloudflare",
  "ovh",
  "openai",
  "anthropic",
  "cohere",
  "ollama",
];

type Meta = {
  nome: string;
  custo: string;
  envChave: string[];
  envModelo: string;
  modeloPadrao: string;
  baseUrl?: string;
  configurado: (env: Env) => boolean;
};

function primeiroEnv(env: Env, nomes: string[]): string {
  for (const nome of nomes) {
    const valor = (env as Record<string, any>)[nome];
    if (typeof valor === "string" && valor.trim()) return valor.trim();
  }
  return "";
}

export const PROVIDERS: Record<ProviderId, Meta> = {
  gemini: {
    nome: "Google Gemini",
    custo: "gratuito",
    envChave: ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
    envModelo: "GEMINI_MODEL",
    modeloPadrao: "gemini-3.5-flash-lite", // 3.8-flash deu 503/524; aprovado em teste real
    configurado: (e) => !!primeiroEnv(e, ["GEMINI_API_KEY", "GOOGLE_API_KEY"]),
  },
  nvidia: {
    nome: "NVIDIA NIM",
    custo: "gratuito (endpoints free)",
    envChave: ["NVIDIA_API_KEY"],
    envModelo: "NVIDIA_MODEL",
    modeloPadrao: "nvidia/nemotron-3-ultra-550b-a55b", // aprovado; o antigo deu 410 Gone
    configurado: (e) => !!primeiroEnv(e, ["NVIDIA_API_KEY"]),
  },
  groq: {
    nome: "Groq",
    custo: "gratuito",
    envChave: ["GROQ_API_KEY"],
    envModelo: "GROQ_MODEL",
    modeloPadrao: "llama-3.3-70b-versatile",
    configurado: (e) => !!primeiroEnv(e, ["GROQ_API_KEY"]),
  },
  openrouter: {
    nome: "OpenRouter",
    custo: "gratuito (modelos :free)",
    envChave: ["OPENROUTER_API_KEY", "OPEN_ROUTER_API_KEY"],
    envModelo: "OPENROUTER_MODEL",
    modeloPadrao: "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", // :free aprovado
    configurado: (e) => !!primeiroEnv(e, ["OPENROUTER_API_KEY", "OPEN_ROUTER_API_KEY"]),
  },
  // awesome-free-llm-apis — 3 aprovados em teste real, sem chave.
  kilocode: {
    nome: "Kilo Code Gateway",
    custo: "gratuito (sem chave)",
    envChave: [],
    envModelo: "KILOCODE_MODEL",
    modeloPadrao: "kilo-auto/free",
    baseUrl: "https://api.kilo.ai/api/gateway",
    configurado: () => true,
  },
  llm7: {
    nome: "LLM7.io",
    custo: "gratuito (anonimo)",
    envChave: [],
    envModelo: "LLM7_MODEL",
    modeloPadrao: "gpt-oss:20b",
    baseUrl: "https://api.llm7.io/v1",
    configurado: () => true,
  },
  ovh: {
    nome: "OVHcloud AI Endpoints",
    custo: "gratuito (anonimo, 2 RPM/IP)",
    envChave: [],
    envModelo: "OVH_MODEL",
    modeloPadrao: "Meta-Llama-3_3-70B-Instruct",
    baseUrl: "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1",
    configurado: () => true,
  },
  aionlabs: {
    nome: "Aion Labs",
    custo: "gratuito (20K tokens/dia)",
    envChave: ["AION_API_KEY"],
    envModelo: "AION_MODEL",
    modeloPadrao: "aion-labs/aion-3.0-mini",
    baseUrl: "https://api.aionlabs.ai/v1",
    configurado: (e) => !!primeiroEnv(e, ["AION_API_KEY"]),
  },
  axforge: {
    nome: "AxForge",
    custo: "gratuito (3M tokens/30 dias)",
    envChave: ["AXFORGE_API_KEY"],
    envModelo: "AXFORGE_MODEL",
    modeloPadrao: "glm-5.3-flash",
    baseUrl: "https://api.axforge.ai/v1",
    configurado: (e) => !!primeiroEnv(e, ["AXFORGE_API_KEY"]),
  },
  zai: {
    nome: "Z AI / Zhipu",
    custo: "gratuito (flash)",
    envChave: ["ZAI_API_KEY"],
    envModelo: "ZAI_MODEL",
    modeloPadrao: "glm-4.7-flash",
    baseUrl: "https://open.bigmodel.cn/api/paas/v4",
    configurado: (e) => !!primeiroEnv(e, ["ZAI_API_KEY"]),
  },
  gonka: {
    nome: "Gonka Broker",
    custo: "gratuito (phone verification)",
    envChave: ["GONKA_API_KEY"],
    envModelo: "GONKA_MODEL",
    modeloPadrao: "deepseek-ai/DeepSeek-V4-Flash-0731",
    baseUrl: "https://proxy.gonkabroker.com/v1",
    configurado: (e) => !!primeiroEnv(e, ["GONKA_API_KEY"]),
  },
  modelscope: {
    nome: "ModelScope",
    custo: "gratuito (real-name)",
    envChave: ["MODELSCOPE_API_KEY"],
    envModelo: "MODELSCOPE_MODEL",
    modeloPadrao: "Qwen/Qwen3.5-35B-A3B",
    baseUrl: "https://api-inference.modelscope.cn/v1",
    configurado: (e) => !!primeiroEnv(e, ["MODELSCOPE_API_KEY"]),
  },
  siliconflow: {
    nome: "SiliconFlow",
    custo: "gratuito (verificacao)",
    envChave: ["SILICONFLOW_API_KEY"],
    envModelo: "SILICONFLOW_MODEL",
    modeloPadrao: "tencent/Hunyuan-MT-7B",
    baseUrl: "https://api.siliconflow.cn/v1",
    configurado: (e) => !!primeiroEnv(e, ["SILICONFLOW_API_KEY"]),
  },
  cohere: {
    nome: "Cohere (trial nao-comercial)",
    custo: "trial — EVAR em video monetizado",
    envChave: ["COHERE_API_KEY"],
    envModelo: "COHERE_MODEL",
    modeloPadrao: "command-r-08-2024",
    baseUrl: "https://api.cohere.ai/compatibility/v1",
    configurado: (e) => !!primeiroEnv(e, ["COHERE_API_KEY"]),
  },
  cloudflare: {
    nome: "Cloudflare Workers AI",
    custo: "gratuito",
    envChave: ["CF_ACCOUNT_ID", "CF_API_TOKEN"],
    envModelo: "CF_AI_MODEL",
    modeloPadrao: "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
    configurado: (e) =>
      !!primeiroEnv(e, ["CF_ACCOUNT_ID", "CLOUDFLARE_ACCOUNT_ID"]) &&
      !!primeiroEnv(e, ["CF_API_TOKEN", "CLOUDFLARE_API_TOKEN"]),
  },
  openai: {
    nome: "OpenAI",
    custo: "pago (barato)",
    envChave: ["OPENAI_API_KEY"],
    envModelo: "OPENAI_MODEL",
    modeloPadrao: "gpt-4o-mini",
    configurado: (e) => !!primeiroEnv(e, ["OPENAI_API_KEY"]),
  },
  anthropic: {
    nome: "Anthropic Claude",
    custo: "pago (opcional)",
    envChave: ["ANTHROPIC_API_KEY"],
    envModelo: "ANTHROPIC_MODEL",
    modeloPadrao: "claude-sonnet-4-5",
    configurado: (e) => !!primeiroEnv(e, ["ANTHROPIC_API_KEY"]),
  },
  ollama: {
    nome: "Ollama (local)",
    custo: "gratuito / local",
    envChave: [], // OLLAMA_API_KEY e opcional (Ollama Cloud)
    envModelo: "OLLAMA_MODEL",
    modeloPadrao: "llama3.1",
    // No Worker nao ha Ollama local; so faz sentido com URL/chave de Ollama Cloud.
    configurado: (e) => !!primeiroEnv(e, ["OLLAMA_URL", "OLLAMA_HOST", "OLLAMA_API_KEY"]),
  },
};

export function listarProviders(env: Env) {
  return ORDEM_FALLBACK.map((id) => ({
    id,
    nome: PROVIDERS[id].nome,
    custo: PROVIDERS[id].custo,
    modelo: primeiroEnv(env, [PROVIDERS[id].envModelo]) || PROVIDERS[id].modeloPadrao,
    env_modelo: PROVIDERS[id].envModelo,
    env_chave: PROVIDERS[id].envChave,
    configurado: PROVIDERS[id].configurado(env),
  }));
}

export function segredo(env: Env, mensagem: string): string {
  let texto = mensagem.slice(0, 300);
  for (const meta of Object.values(PROVIDERS)) {
    for (const nome of meta.envChave) {
      const valor = primeiroEnv(env, [nome]);
      if (valor.length > 6) texto = texto.split(valor).join("***");
    }
  }
  for (const nome of ["OLLAMA_API_KEY", "LLM7_API_KEY"]) {
    const valor = primeiroEnv(env, [nome]);
    if (valor.length > 6) texto = texto.split(valor).join("***");
  }
  return texto;
}

async function jsonDaResposta(r: Response, contexto: string): Promise<any> {
  const texto = await r.text();
  if (r.status >= 400) {
    throw new Error(`HTTP ${r.status}: ${texto.slice(0, 200)}`);
  }
  try {
    return JSON.parse(texto);
  } catch {
    throw new Error(`${contexto}: resposta nao e JSON (${texto.slice(0, 120)})`);
  }
}

type Chamada = {
  prompt: string;
  system: string;
  modelo: string;
  temperatura: number;
  maxTokens: number;
};

async function chatarCompat(
  url: string,
  chave: string,
  headersExtra: Record<string, string>,
  c: Chamada,
): Promise<string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(chave ? { Authorization: `Bearer ${chave}` } : {}),
    ...headersExtra,
  };
  const payload: Record<string, any> = {
    model: c.modelo,
    messages: [
      { role: "system", content: c.system },
      { role: "user", content: c.prompt },
    ],
    temperature: c.temperatura,
    max_tokens: c.maxTokens,
    response_format: { type: "json_object" },
  };

  let r = await fetch(url, { method: "POST", headers, body: JSON.stringify(payload) });
  if (r.status === 400 || r.status === 422) {
    // Modelos abertos as vezes nao aceitam response_format.
    delete payload.response_format;
    r = await fetch(url, { method: "POST", headers, body: JSON.stringify(payload) });
  }
  const dados = await jsonDaResposta(r, "chat/completions");
  const escolhas = dados.choices as any[] | undefined;
  if (!escolhas?.length) throw new Error("Resposta sem choices.");
  return String(escolhas[0]?.message?.content ?? "");
}

async function chamarGemini(env: Env, chave: string, c: Chamada): Promise<string> {
  const r = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(c.modelo)}:generateContent`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-goog-api-key": chave },
      body: JSON.stringify({
        system_instruction: { parts: [{ text: c.system }] },
        contents: [{ role: "user", parts: [{ text: c.prompt }] }],
        generationConfig: {
          responseMimeType: "application/json",
          temperature: c.temperatura,
          maxOutputTokens: c.maxTokens,
        },
      }),
    },
  );
  const dados = await jsonDaResposta(r, "Gemini");
  const partes: any[] = dados.candidates?.[0]?.content?.parts ?? [];
  const texto = partes.map((p) => String(p.text ?? "")).join("");
  if (!texto.trim()) throw new Error("Gemini devolveu uma resposta vazia.");
  return texto;
}

async function chamarCloudflare(env: Env, c: Chamada): Promise<string> {
  const account =
    primeiroEnv(env, ["CF_ACCOUNT_ID", "CLOUDFLARE_ACCOUNT_ID"]);
  const token = primeiroEnv(env, ["CF_API_TOKEN", "CLOUDFLARE_API_TOKEN"]);
  if (!account || !token) throw new Error("CF_ACCOUNT_ID e CF_API_TOKEN nao configurados.");
  const r = await fetch(
    `https://api.cloudflare.com/client/v4/accounts/${encodeURIComponent(account)}/ai/run/${c.modelo}`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: [
          { role: "system", content: c.system },
          { role: "user", content: c.prompt },
        ],
        temperature: c.temperatura,
        max_tokens: c.maxTokens,
      }),
    },
  );
  const dados = await jsonDaResposta(r, "Workers AI");
  if (dados.success === false) {
    throw new Error(String(dados.errors?.[0]?.message ?? "falha na Workers AI").slice(0, 200));
  }
  const resultado = dados.result ?? {};
  const texto = String(resultado.response ?? resultado.text ?? "");
  return texto || JSON.stringify(resultado);
}

async function chamarAnthropic(chave: string, c: Chamada): Promise<string> {
  const r = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": chave,
      "anthropic-version": "2023-06-01",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: c.modelo,
      max_tokens: c.maxTokens,
      temperature: c.temperatura,
      system: c.system,
      messages: [{ role: "user", content: c.prompt }],
    }),
  });
  const dados = await jsonDaResposta(r, "Anthropic");
  const blocos: any[] = Array.isArray(dados.content) ? dados.content : [];
  return blocos
    .filter((b) => b?.type === "text")
    .map((b) => String(b.text ?? ""))
    .join("");
}

async function chamarOllama(env: Env, c: Chamada): Promise<string> {
  const chave = primeiroEnv(env, ["OLLAMA_API_KEY"]);
  const base =
    primeiroEnv(env, ["OLLAMA_URL", "OLLAMA_HOST"]) ||
    (chave ? "https://ollama.com" : "http://127.0.0.1:11434");
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (chave) headers.Authorization = `Bearer ${chave}`;
  const r = await fetch(`${base.replace(/\/$/, "")}/api/chat`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      model: c.modelo,
      stream: false,
      messages: [
        { role: "system", content: c.system },
        { role: "user", content: c.prompt },
      ],
      options: { temperature: c.temperatura, num_predict: c.maxTokens },
      format: "json",
    }),
  });
  const dados = await jsonDaResposta(r, "Ollama");
  return String(dados.message?.content ?? "");
}

async function chamarCompatBase(env: Env, id: ProviderId, c: Chamada) {
  const meta = PROVIDERS[id];
  if (!meta.baseUrl) throw new Error(`${id}: baseUrl nao configurada.`);
  const modelo = c.modelo || primeiroEnv(env, [meta.envModelo]) || meta.modeloPadrao;
  const chave = primeiroEnv(env, meta.envChave);
  if (meta.envChave.length && !chave) {
    throw new Error(`${meta.envChave[0]} nao configurada.`);
  }
  const texto = await chatarCompat(
    `${meta.baseUrl.replace(/\/$/, "")}/chat/completions`,
    chave,
    {},
    { ...c, modelo },
  );
  return { texto, modelo };
}

export async function chamarProvider(
  env: Env,
  id: ProviderId,
  c: Chamada,
): Promise<{ texto: string; modelo: string }> {
  const meta = PROVIDERS[id];
  const modelo = c.modelo || primeiroEnv(env, [meta.envModelo]) || meta.modeloPadrao;
  const chamada: Chamada = { ...c, modelo };

  switch (id) {
    case "gemini": {
      const chave = primeiroEnv(env, meta.envChave);
      if (!chave) throw new Error("GEMINI_API_KEY nao configurada.");
      return { texto: await chamarGemini(env, chave, chamada), modelo };
    }
    case "nvidia": {
      const chave = primeiroEnv(env, meta.envChave);
      if (!chave) throw new Error("NVIDIA_API_KEY nao configurada.");
      return {
        texto: await chatarCompat(
          "https://integrate.api.nvidia.com/v1/chat/completions",
          chave,
          {},
          chamada,
        ),
        modelo,
      };
    }
    case "groq": {
      const chave = primeiroEnv(env, meta.envChave);
      if (!chave) throw new Error("GROQ_API_KEY nao configurada.");
      return {
        texto: await chatarCompat("https://api.groq.com/openai/v1/chat/completions", chave, {}, chamada),
        modelo,
      };
    }
    case "openrouter": {
      const chave = primeiroEnv(env, meta.envChave);
      if (!chave) throw new Error("OPENROUTER_API_KEY nao configurada.");
      return {
        texto: await chatarCompat(
          "https://openrouter.ai/api/v1/chat/completions",
          chave,
          {
            "HTTP-Referer": "https://natodark.pages.dev",
            "X-Title": "NatoDark Studio",
          },
          chamada,
        ),
        modelo,
      };
    }
    case "cloudflare":
      return { texto: await chamarCloudflare(env, chamada), modelo };
    case "openai": {
      const chave = primeiroEnv(env, meta.envChave);
      if (!chave) throw new Error("OPENAI_API_KEY nao configurada.");
      return {
        texto: await chatarCompat("https://api.openai.com/v1/chat/completions", chave, {}, chamada),
        modelo,
      };
    }
    case "anthropic": {
      const chave = primeiroEnv(env, meta.envChave);
      if (!chave) throw new Error("ANTHROPIC_API_KEY nao configurada.");
      return { texto: await chamarAnthropic(chave, chamada), modelo };
    }
    case "ollama":
      return { texto: await chamarOllama(env, chamada), modelo };
    case "kilocode":
    case "llm7":
    case "ovh":
    case "aionlabs":
    case "axforge":
    case "zai":
    case "gonka":
    case "modelscope":
    case "siliconflow":
    case "cohere":
      return chamarCompatBase(env, id, chamada);
  }
}

export async function gerarComFallback(
  env: Env,
  escolhido: ProviderId | "auto",
  c: Chamada,
  fallback: boolean,
): Promise<{
  texto: string;
  provedor: ProviderId;
  modelo: string;
  tentativas: Array<{ provedor: string; erro: string }>;
}> {
  const ordem: ProviderId[] =
    escolhido === "auto"
      ? [...ORDEM_FALLBACK]
      : [escolhido, ...ORDEM_FALLBACK.filter((p) => p !== escolhido)];
  const tentativas: Array<{ provedor: string; erro: string }> = [];

  for (const id of ordem) {
    try {
      const resposta = await chamarProvider(env, id, c);
      if (!resposta.texto.trim()) throw new Error("resposta vazia");
      return { ...resposta, provedor: id, tentativas };
    } catch (err) {
      tentativas.push({ provedor: id, erro: segredo(env, String(err)) });
    }
    if (!fallback && escolhido !== "auto") break;
  }

  const detalhe = tentativas.slice(-3).map((t) => `${t.provedor}: ${t.erro}`).join("; ");
  throw new Error(`Nenhum provedor conseguiu gerar o texto. ${detalhe}`);
}

// Nomes de zueira por servico — o mesmo padrao usado no backend Python.
const AGENTES: Record<string, string> = {
  roteiro: "Dr. Gancho da Silva Corte Seco",
  titulos: "Capitao Clickbait Pereira",
  hype: "Dona Curiosidade AlmeidaTrend",
  legendas: "Zé Legendinha Santos",
  revisao: "Prof. Pattern Interrupt Gomes",
  reserva: "Tio fallback Ribeiro",
};

export function nomeAgente(servico = "reserva"): string {
  return AGENTES[servico] || AGENTES.reserva;
}

export async function testarModelo(
  env: Env,
  id: ProviderId,
  modelo: string,
  servico = "roteiro",
  tentativas?: number,
): Promise<Record<string, unknown>> {
  const permitidas = Math.max(1, Math.min(tentativas ?? (id === "ollama" ? 3 : 2), 5));
  const erros: string[] = [];
  const inicio = Date.now();
  for (let n = 1; n <= permitidas; n++) {
    try {
      const resposta = await chamarProvider(env, id, {
        prompt: 'Responda SOMENTE com JSON valido: {"ok": true, "servico": "teste"}.',
        system: "Voce e um agente de teste. Responda sempre JSON valido.",
        modelo,
        temperatura: 0,
        maxTokens: 128,
      });
      if (!resposta.texto.trim()) throw new Error("resposta vazia");
      if (!resposta.texto.includes("{") || !resposta.texto.includes("}")) {
        throw new Error("resposta nao e JSON valido");
      }
      return {
        provider: id,
        modelo: resposta.modelo,
        agente: nomeAgente(servico),
        servico,
        status: "aprovado",
        tentativas_realizadas: n,
        tentativas_permitidas: permitidas,
        latencia_ms: Date.now() - inicio,
        erro: "",
      };
    } catch (err) {
      erros.push(segredo(env, String(err)));
    }
  }
  const transient = erros.some((e) =>
    ["429", "503", "524", "timeout", "capacity", "Too many"].some((s) => e.includes(s)),
  );
  return {
    provider: id,
    modelo,
    agente: nomeAgente(servico),
    servico,
    status: transient ? "instavel" : "reprovado",
    tentativas_realizadas: permitidas,
    tentativas_permitidas: permitidas,
    latencia_ms: Date.now() - inicio,
    erro: erros.join(" | ").slice(0, 400),
  };
}
