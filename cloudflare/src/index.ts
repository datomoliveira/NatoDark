// Worker do NatoDark Studio: gera roteiros de qualquer lugar, com as chaves
// dos modelos guardadas em Secrets da Cloudflare.
//
// O render com ffmpeg NAO roda aqui (Workers tem limite de CPU/memoria e nao
// tem binario ffmpeg). O fluxo e: gerar roteiro remoto -> baixar JSON no PC ->
// renderizar localmente. Veja README.md.
import type { Env } from "./types";
import {
  PROVIDERS,
  gerarComFallback,
  listarProviders,
  segredo,
  type ProviderId,
} from "./providers";
import { SYSTEM_PROMPT, montarPrompt, extrairJson, normalizar } from "./prompt";

const DEFAULT_PUBLICO = "brasileiros que consomem conteúdo dark/dramático no YouTube";
const DEFAULT_TOM = "dark, dramático e direto";

function cors(env: Env): Record<string, string> {
  return {
    "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN || "*",
    "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
}

function json(data: unknown, env: Env, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...cors(env) },
  });
}

function idValido(id: string): boolean {
  return /^[A-Za-z0-9_-]{1,40}$/.test(id);
}

function autorizado(request: Request, env: Env): boolean {
  if (!env.API_TOKEN) return true;
  const bearer = request.headers.get("Authorization") || "";
  const chave = request.headers.get("X-API-Key") || "";
  return bearer === `Bearer ${env.API_TOKEN}` || chave === env.API_TOKEN;
}

async function gerarRoteiro(request: Request, env: Env): Promise<Response> {
  let body: Record<string, any>;
  try {
    body = (await request.json()) as Record<string, any>;
  } catch {
    return json({ erro: "Body JSON invalido." }, env, 400);
  }

  const tema = String(body.tema ?? "").trim();
  if (!tema) return json({ erro: "Informe o tema do roteiro." }, env, 400);

  let duracao = Number(body.duracao_segundos ?? 60);
  if (!Number.isFinite(duracao)) duracao = 60;
  duracao = Math.max(5, Math.min(duracao, 600));

  const formato = String(body.formato ?? "shorts").trim() || "shorts";
  const publico = String(body.publico ?? DEFAULT_PUBLICO);
  const tom = String(body.tom ?? DEFAULT_TOM);
  const escolhido = String(
    body.provider ?? env.SCRIPT_PROVIDER ?? "auto",
  ).trim().toLowerCase() as ProviderId | "auto";

  if (escolhido !== "auto" && !(escolhido in PROVIDERS)) {
    return json(
      {
        erro: "Provedor invalido. Use: auto, " + Object.keys(PROVIDERS).join(", "),
      },
      env,
      400,
    );
  }

  const modelo = String(body.model ?? env.SCRIPT_MODEL ?? "").trim();
  const fallback = body.fallback !== false;

  const resposta = await gerarComFallback(
    env,
    escolhido,
    {
      prompt: montarPrompt({ tema, publico, duracaoSegundos: duracao, formato, tom }),
      system: SYSTEM_PROMPT,
      temperatura: 0.85,
      maxTokens: 4096,
      modelo,
    },
    fallback,
  );

  const roteiro = normalizar(
    extrairJson(resposta.texto),
    duracao,
    formato,
    resposta.provedor,
    resposta.modelo,
  );

  let id: string | undefined;
  if (env.SCRIPTS) {
    id = crypto.randomUUID().slice(0, 8);
    await env.SCRIPTS.put(
      `roteiros/${id}.json`,
      JSON.stringify({ ...roteiro, criado_em: new Date().toISOString() }, null, 2),
      { httpMetadata: { contentType: "application/json; charset=utf-8" } },
    );
  }

  return json(
    {
      ...roteiro,
      modo: resposta.provedor,
      modelo: resposta.modelo,
      tentativas: resposta.tentativas,
      fallback_usado: resposta.tentativas.length > 0,
      ...(id ? { id, storage: "r2" } : {}),
    },
    env,
  );
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors(env) });
    }

    const url = new URL(request.url);
    const path = url.pathname.replace(/\/$/, "") || "/";

    if (path !== "/" && !autorizado(request, env)) {
      return json({ erro: "Nao autorizado." }, env, 401);
    }

    try {
      if (path === "/" && request.method === "GET") {
        return json(
          {
            servico: "NatoDark Studio",
            versao: "1.0",
            provedores_configurados: listarProviders(env)
              .filter((p) => p.configurado)
              .map((p) => p.id),
            render: "local (ffmpeg) — o Worker gera roteiro e guarda JSON",
          },
          env,
        );
      }

      if (path === "/api/providers" && request.method === "GET") {
        return json(
          { padrao: env.SCRIPT_PROVIDER || "auto", provedores: listarProviders(env) },
          env,
        );
      }

      if (path === "/api/scripts/generate" && request.method === "POST") {
        return await gerarRoteiro(request, env);
      }

      if (path === "/api/scripts" && request.method === "GET") {
        if (!env.SCRIPTS) {
          return json({ erro: "Bucket R2 'SCRIPTS' nao configurado." }, env, 503);
        }
        const objetos = await env.SCRIPTS.list({ prefix: "roteiros/", limit: 50 });
        return json(
          {
            roteiros: objetos.objects.map((o) => ({
              id: o.key.split("/").pop(),
              key: o.key,
              size: o.size,
              uploaded: o.uploaded,
            })),
          },
          env,
        );
      }

      const match = path.match(/^\/api\/scripts\/([^/]+)$/);
      if (match) {
        const id = decodeURIComponent(match[1]);
        if (!idValido(id)) return json({ erro: "ID invalido." }, env, 400);
        if (!env.SCRIPTS) {
          return json({ erro: "Bucket R2 'SCRIPTS' nao configurado." }, env, 503);
        }
        const key = `roteiros/${id}.json`;
        if (request.method === "GET") {
          const objeto = await env.SCRIPTS.get(key);
          if (!objeto) return json({ erro: "Roteiro nao encontrado." }, env, 404);
          const texto = await objeto.text();
          return new Response(texto, {
            headers: { "Content-Type": "application/json; charset=utf-8", ...cors(env) },
          });
        }
        if (request.method === "DELETE") {
          await env.SCRIPTS.delete(key);
          return json({ status: "removido", id }, env);
        }
      }

      return json({ erro: "Rota nao encontrada." }, env, 404);
    } catch (err) {
      const mensagem = segredo(env, String(err instanceof Error ? err.message : err));
      const status = mensagem.includes("Informe o tema") || mensagem.includes("invalido") ? 400 : 500;
      return json({ erro: mensagem }, env, status);
    }
  },
};
