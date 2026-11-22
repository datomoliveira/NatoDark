// Pages Function da API do NatoDark.
//
// Roda no MESMO projeto Pages, por isso enxerga os Secrets que você cadastrou
// (GEMINI_API_KEY, NVIDIA_API_KEY, OPEN_ROUTER_API_KEY, OLLAMA_API_KEY...).
// O Worker separado (cloudflare/) continua disponível, mas aqui não é necessário.
import type { Env } from "../../cloudflare/src/types";
import worker from "../../cloudflare/src/index";

type ContextoPages = { request: Request; env: Env };

export const onRequest = async (context: ContextoPages): Promise<Response> => {
  return worker.fetch(context.request, context.env);
};
