"""
Router de modelos de linguagem — NatoDark Studio.

Um unico ponto de entrada para gerar texto com diversas APIs. As chaves sao
lidas de variaveis de ambiente; quando hospedado na Cloudflare, essas mesmas
variaveis sao os Secrets do Worker (mesmo nome, sem precisar mudar codigo).

Provedores suportados (todos com saida forcada em JSON):

  gemini       Google Gemini  — tier gratuito  — GEMINI_API_KEY / GOOGLE_API_KEY
  nvidia       NVIDIA NIM     — tier gratuito  — NVIDIA_API_KEY
  groq         Groq           — tier gratuito  — GROQ_API_KEY
  openrouter   OpenRouter     — modelos :free  — OPENROUTER_API_KEY / OPEN_ROUTER_API_KEY
  cloudflare   Workers AI     — tier gratuito  — CF_ACCOUNT_ID + CF_API_TOKEN
  openai       OpenAI         — pago barato    — OPENAI_API_KEY
  anthropic    Anthropic      — pago opcional  — ANTHROPIC_API_KEY
  ollama       Ollama local   — gratuito/local — sem chave (OLLAMA_URL / OLLAMA_API_KEY)

Aliases aceitos: OPEN_ROUTER_API_KEY = OPENROUTER_API_KEY,
OLLAMA_API_KEY = chave opcional para Ollama Cloud (https://ollama.com).

Uso:

    from llm_router import chamar_modelo, listar_provedores
    r = chamar_modelo(prompt, system="...", provider="auto")
    print(r["texto"], r["provedor"], r["modelo"])

`provider="auto"` (padrao) tenta os provedores configurados em ordem e usa o
primeiro que responder. Se um provedor explicito falhar, ha fallback automatico
para os demais (desative com fallback=False).
"""

import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

TIMEOUT = (10, 60)
ORDEM_FALLBACK = (
    "gemini", "nvidia", "groq", "openrouter",
    "kilocode", "llm7", "aionlabs", "axforge", "zai", "gonka",
    "modelscope", "siliconflow", "cloudflare", "ovh",
    "openai", "anthropic", "cohere", "ollama",
)


PROVIDERS: Dict[str, Dict[str, Any]] = {
    "gemini": {
        "nome": "Google Gemini",
        "custo": "gratuito",
        "env_chave": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        # 3.8-flash deu 503/524 por capacidade; 3.5-flash-lite foi aprovado em teste real.
        "modelo": os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        "modelo_leve": os.environ.get("GEMINI_LITE_MODEL", "gemini-3.1-flash-lite"),
        "env_modelo": "GEMINI_MODEL",
    },
    "nvidia": {
        "nome": "NVIDIA NIM",
        "custo": "gratuito (endpoints free)",
        "env_chave": ("NVIDIA_API_KEY",),
        # Modelo antigo retornou 410 Gone; este foi aprovado em teste real.
        "modelo": os.environ.get("NVIDIA_MODEL", "nvidia/nemotron-3-ultra-550b-a55b"),
        "env_modelo": "NVIDIA_MODEL",
    },
    "groq": {
        "nome": "Groq",
        "custo": "gratuito",
        "env_chave": ("GROQ_API_KEY",),
        "modelo": os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "env_modelo": "GROQ_MODEL",
    },
    "openrouter": {
        "nome": "OpenRouter",
        "custo": "gratuito (modelos :free)",
        "env_chave": ("OPENROUTER_API_KEY", "OPEN_ROUTER_API_KEY"),
        # O llama-3.3 :free virou pago (404). Este :free foi aprovado em teste real.
        "modelo": os.environ.get("OPENROUTER_MODEL", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"),
        "env_modelo": "OPENROUTER_MODEL",
    },
    # --- Provedores do repositorio awesome-free-llm-apis (testados/sem chave) ---
    "kilocode": {
        "nome": "Kilo Code Gateway",
        "custo": "gratuito (sem chave)",
        "env_chave": (),
        "base_url": "https://api.kilo.ai/api/gateway",
        "modelo": os.environ.get("KILOCODE_MODEL", "kilo-auto/free"),
        "env_modelo": "KILOCODE_MODEL",
        "nota": "APROVADO em teste real: 200, JSON valido, ~1.5s.",
    },
    "llm7": {
        "nome": "LLM7.io",
        "custo": "gratuito (anonimo; token opcional)",
        "env_chave": (),
        "env_opcional": ("LLM7_API_KEY",),
        "base_url": "https://api.llm7.io/v1",
        "modelo": os.environ.get("LLM7_MODEL", "gpt-oss:20b"),
        "env_modelo": "LLM7_MODEL",
        "nota": "APROVADO em teste real: 200, JSON valido, ~3s.",
    },
    "aionlabs": {
        "nome": "Aion Labs",
        "custo": "gratuito (20K tokens/dia)",
        "env_chave": ("AION_API_KEY",),
        "base_url": "https://api.aionlabs.ai/v1",
        "modelo": os.environ.get("AION_MODEL", "aion-labs/aion-3.0-mini"),
        "env_modelo": "AION_MODEL",
        "nota": "Especializado em roleplay/storytelling — otimo para roteiro dark.",
    },
    "axforge": {
        "nome": "AxForge",
        "custo": "gratuito (3M tokens/30 dias)",
        "env_chave": ("AXFORGE_API_KEY",),
        "base_url": "https://api.axforge.ai/v1",
        "modelo": os.environ.get("AXFORGE_MODEL", "glm-5.3-flash"),
        "env_modelo": "AXFORGE_MODEL",
    },
    "zai": {
        "nome": "Z AI / Zhipu",
        "custo": "gratuito (modelos flash)",
        "env_chave": ("ZAI_API_KEY",),
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "modelo": os.environ.get("ZAI_MODEL", "glm-4.7-flash"),
        "env_modelo": "ZAI_MODEL",
    },
    "gonka": {
        "nome": "Gonka Broker",
        "custo": "gratuito (phone verification)",
        "env_chave": ("GONKA_API_KEY",),
        "base_url": "https://proxy.gonkabroker.com/v1",
        "modelo": os.environ.get("GONKA_MODEL", "deepseek-ai/DeepSeek-V4-Flash-0731"),
        "env_modelo": "GONKA_MODEL",
    },
    "modelscope": {
        "nome": "ModelScope",
        "custo": "gratuito (verificacao real-name)",
        "env_chave": ("MODELSCOPE_API_KEY",),
        "base_url": "https://api-inference.modelscope.cn/v1",
        "modelo": os.environ.get("MODELSCOPE_MODEL", "Qwen/Qwen3.5-35B-A3B"),
        "env_modelo": "MODELSCOPE_MODEL",
    },
    "siliconflow": {
        "nome": "SiliconFlow",
        "custo": "gratuito (verificacao de identidade)",
        "env_chave": ("SILICONFLOW_API_KEY",),
        "base_url": "https://api.siliconflow.cn/v1",
        "modelo": os.environ.get("SILICONFLOW_MODEL", "tencent/Hunyuan-MT-7B"),
        "env_modelo": "SILICONFLOW_MODEL",
    },
    "ovh": {
        "nome": "OVHcloud AI Endpoints",
        "custo": "gratuito (anonimo, 2 RPM/IP)",
        "env_chave": (),
        "base_url": "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1",
        "modelo": os.environ.get("OVH_MODEL", "Meta-Llama-3_3-70B-Instruct"),
        "env_modelo": "OVH_MODEL",
        "nota": "APROVADO em teste real; limite baixo, usar como reserva.",
    },
    "cohere": {
        "nome": "Cohere",
        "custo": "trial (USO NAO COMERCIAL)",
        "env_chave": ("COHERE_API_KEY",),
        "base_url": "https://api.cohere.ai/compatibility/v1",
        "modelo": os.environ.get("COHERE_MODEL", "command-r-08-2024"),
        "env_modelo": "COHERE_MODEL",
        "nota": "EVAR em video monetizado: licenca trial e nao-comercial.",
    },
    "cloudflare": {
        "nome": "Cloudflare Workers AI",
        "custo": "gratuito",
        "env_chave": ("CF_ACCOUNT_ID", "CF_API_TOKEN"),
        "modelo": os.environ.get("CF_AI_MODEL", "@cf/meta/llama-3.3-70b-instruct-fp8-fast"),
        "env_modelo": "CF_AI_MODEL",
    },
    "openai": {
        "nome": "OpenAI",
        "custo": "pago (barato)",
        "env_chave": ("OPENAI_API_KEY",),
        "modelo": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        "env_modelo": "OPENAI_MODEL",
    },
    "anthropic": {
        "nome": "Anthropic Claude",
        "custo": "pago (opcional)",
        "env_chave": ("ANTHROPIC_API_KEY",),
        "modelo": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
        "env_modelo": "ANTHROPIC_MODEL",
    },
    "ollama": {
        "nome": "Ollama (local ou cloud)",
        "custo": "gratuito / local",
        "env_chave": (),
        # Chave opcional: so e usada se OLLAMA_URL apontar para Ollama Cloud.
        "env_opcional": ("OLLAMA_API_KEY",),
        "modelo": os.environ.get("OLLAMA_MODEL", "llama3.1"),
        "env_modelo": "OLLAMA_MODEL",
    },
}


def _env(*nomes: str) -> str:
    for nome in nomes:
        valor = os.environ.get(nome)
        if valor and valor.strip():
            return valor.strip()
    return ""


def _seguro(mensagem: str) -> str:
    """Corta a mensagem e remove qualquer chave que apareca nela."""
    texto = str(mensagem)[:300]
    for info in PROVIDERS.values():
        for nome in (*info["env_chave"], *info.get("env_opcional", ())):
            valor = os.environ.get(nome)
            if valor and len(valor) > 6:
                texto = texto.replace(valor, "***")
    return texto


def listar_provedores() -> List[Dict[str, Any]]:
    """Lista provedores e seus modelos, sem nunca expor as chaves."""
    saida = []
    for chave in ORDEM_FALLBACK:
        info = PROVIDERS[chave]
        if info["env_chave"]:
            configurado = all(_env(n) for n in info["env_chave"])
        elif chave == "ollama":
            configurado = bool(_env("OLLAMA_URL", "OLLAMA_HOST", "OLLAMA_API_KEY"))
        else:
            # kilocode/llm7/ovh funcionam sem chave.
            configurado = True
        saida.append(
            {
                "id": chave,
                "nome": info["nome"],
                "custo": info["custo"],
                "modelo": info["modelo"],
                "env_modelo": info["env_modelo"],
                "env_chave": list(info["env_chave"]),
                "env_opcional": list(info.get("env_opcional", ())),
                "configurado": configurado,
            }
        )
    return saida


def _modelo_padrao(provider: str, model: Optional[str] = None) -> str:
    return (model or "").strip() or PROVIDERS[provider]["modelo"]


def _call_gemini(prompt: str, system: str, model: str, chave: str, temperatura: float, max_tokens: int) -> str:
    from google import genai
    from google.genai import types

    cliente = genai.Client(api_key=chave)
    resposta = cliente.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            temperature=temperatura,
            max_output_tokens=max_tokens,
        ),
    )
    return resposta.text or ""


def _call_openai_compat(
    prompt: str, system: str, model: str, chave: str, temperatura: float, max_tokens: int,
    *, url: str, headers_extra: Optional[Dict[str, str]] = None, json_mode: bool = True,
) -> str:
    headers = {"Content-Type": "application/json"}
    if chave:
        headers["Authorization"] = f"Bearer {chave}"
    headers.update(headers_extra or {})
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "temperature": temperatura,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    r = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
    if r.status_code >= 400:
        # Alguns modelos abertos nao aceitam response_format; tenta sem ele.
        if json_mode and r.status_code in (400, 422):
            payload.pop("response_format", None)
            r = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
    dados = r.json()
    escolhas = dados.get("choices") or []
    if not escolhas:
        raise RuntimeError("Resposta sem choices.")
    msg = escolhas[0].get("message") or {}
    # Modelos reasoning as vezes devolvem o texto em reasoning/reasoning_content.
    return msg.get("content") or msg.get("reasoning") or msg.get("reasoning_content") or ""


def _call_anthropic(prompt: str, system: str, model: str, chave: str, temperatura: float, max_tokens: int) -> str:
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": chave,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperatura,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=TIMEOUT,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
    blocos = r.json().get("content") or []
    return "".join(b.get("text", "") for b in blocos if b.get("type") == "text")


def _call_cloudflare(
    prompt: str, system: str, model: str, temperatura: float, max_tokens: int,
    *, account_id: str, token: str,
) -> str:
    r = requests.post(
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "temperature": temperatura,
            "max_tokens": max_tokens,
        },
        timeout=TIMEOUT,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
    dados = r.json()
    if not dados.get("success", True):
        raise RuntimeError(str((dados.get("errors") or [{}])[0].get("message", "falha na Workers AI"))[:200])
    resultado = dados.get("result") or {}
    texto = resultado.get("response") or resultado.get("text") or ""
    if not texto:
        texto = json.dumps(resultado, ensure_ascii=False)
    return texto


def _call_ollama(prompt: str, system: str, model: str, temperatura: float, max_tokens: int) -> str:
    chave = _env("OLLAMA_API_KEY")
    # Sem URL definida, a presenca de chave indica Ollama Cloud.
    url = _env("OLLAMA_URL", "OLLAMA_HOST") or (
        "https://ollama.com" if chave else "http://127.0.0.1:11434"
    )
    headers = {"Content-Type": "application/json"}
    if chave:
        headers["Authorization"] = f"Bearer {chave}"
    r = requests.post(
        f"{url.rstrip('/')}/api/chat",
        headers=headers,
        json={
            "model": model,
            "stream": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "options": {"temperature": temperatura, "num_predict": max_tokens},
            "format": "json",
        },
        timeout=TIMEOUT,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
    return ((r.json().get("message") or {}).get("content") or "")


def _chamar_um(
    provider: str, prompt: str, system: str, model: Optional[str], api_key: Optional[str],
    temperatura: float, max_tokens: int,
) -> Tuple[str, str]:
    """Chama um unico provedor. Devolve (texto, modelo_usado)."""
    info = PROVIDERS[provider]
    modelo = _modelo_padrao(provider, model)

    # Provedores OpenAI-compatible do awesome-free-llm-apis.
    if info.get("base_url"):
        chave = api_key or _env(*info["env_chave"], *info.get("env_opcional", ()))
        if info["env_chave"] and not chave:
            raise RuntimeError(
                f"{' / '.join(info['env_chave'])} nao configurada. "
                f"Pegue em {info.get('url', 'site do provedor')}."
            )
        return _call_openai_compat(
            prompt, system, modelo, chave, temperatura, max_tokens,
            url=f"{info['base_url'].rstrip('/')}/chat/completions",
        ), modelo

    if provider == "gemini":
        chave = api_key or _env(*info["env_chave"])
        if not chave:
            raise RuntimeError("GEMINI_API_KEY nao configurada (tire uma chave gratuita em https://aistudio.google.com/apikey).")
        return _call_gemini(prompt, system, modelo, chave, temperatura, max_tokens), modelo

    if provider == "nvidia":
        chave = api_key or _env(*info["env_chave"])
        if not chave:
            raise RuntimeError("NVIDIA_API_KEY nao configurada (https://build.nvidia.com).")
        return _call_openai_compat(
            prompt, system, modelo, chave, temperatura, max_tokens,
            url="https://integrate.api.nvidia.com/v1/chat/completions",
        ), modelo

    if provider == "groq":
        chave = api_key or _env(*info["env_chave"])
        if not chave:
            raise RuntimeError("GROQ_API_KEY nao configurada (https://console.groq.com/keys).")
        return _call_openai_compat(
            prompt, system, modelo, chave, temperatura, max_tokens,
            url="https://api.groq.com/openai/v1/chat/completions",
        ), modelo

    if provider == "openrouter":
        chave = api_key or _env(*info["env_chave"])
        if not chave:
            raise RuntimeError("OPENROUTER_API_KEY nao configurada (https://openrouter.ai/keys).")
        return _call_openai_compat(
            prompt, system, modelo, chave, temperatura, max_tokens,
            url="https://openrouter.ai/api/v1/chat/completions",
            headers_extra={
                "HTTP-Referer": _env("APP_URL") or "https://natodark.local",
                "X-Title": "NatoDark Studio",
            },
        ), modelo

    if provider == "cloudflare":
        account = _env("CF_ACCOUNT_ID", "CLOUDFLARE_ACCOUNT_ID")
        token = api_key or _env("CF_API_TOKEN", "CLOUDFLARE_API_TOKEN")
        if not account or not token:
            raise RuntimeError("CF_ACCOUNT_ID e CF_API_TOKEN nao configurados (Secrets do Worker).")
        return _call_cloudflare(
            prompt, system, modelo, temperatura, max_tokens, account_id=account, token=token,
        ), modelo

    if provider == "openai":
        chave = api_key or _env(*info["env_chave"])
        if not chave:
            raise RuntimeError("OPENAI_API_KEY nao configurada.")
        return _call_openai_compat(
            prompt, system, modelo, chave, temperatura, max_tokens,
            url="https://api.openai.com/v1/chat/completions",
        ), modelo

    if provider == "anthropic":
        chave = api_key or _env(*info["env_chave"])
        if not chave:
            raise RuntimeError("ANTHROPIC_API_KEY nao configurada (provedor pago opcional).")
        return _call_anthropic(prompt, system, modelo, chave, temperatura, max_tokens), modelo

    if provider == "ollama":
        return _call_ollama(prompt, system, modelo, temperatura, max_tokens), modelo

    raise ValueError(f"Provedor desconhecido: {provider}")


def chamar_modelo(
    prompt: str,
    *,
    system: str = "",
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    temperatura: float = 0.85,
    max_tokens: int = 4096,
    fallback: bool = True,
) -> Dict[str, Any]:
    """
    Gera texto com fallback automatico entre provedores configurados.

    Devolve:
      {
        "texto": str,
        "provedor": str,
        "modelo": str,
        "tentativas": [{"provedor":..., "erro":...}, ...],
      }
    """
    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("Prompt vazio.")

    escolhido = (provider or _env("SCRIPT_PROVIDER") or "auto").strip().lower()
    if escolhido == "auto":
        ordem = list(ORDEM_FALLBACK)
    elif escolhido in PROVIDERS:
        ordem = [escolhido] + ([p for p in ORDEM_FALLBACK if p != escolhido] if fallback else [])
    else:
        raise ValueError(
            "Provedor invalido. Use: auto, " + ", ".join(PROVIDERS.keys())
        )

    tentativas: List[Dict[str, str]] = []
    ultimo_erro = ""

    for candidato in ordem:
        chave_desta = api_key if candidato == escolhido else None
        try:
            texto, modelo_usado = _chamar_um(
                candidato, prompt, system, model if candidato == escolhido else None,
                chave_desta, temperatura, max_tokens,
            )
            if not (texto or "").strip():
                raise RuntimeError("resposta vazia")
            return {
                "texto": texto,
                "provedor": candidato,
                "modelo": modelo_usado,
                "tentativas": tentativas,
            }
        except Exception as err:
            ultimo_erro = _seguro(err)
            tentativas.append({"provedor": candidato, "erro": ultimo_erro})

    detalhe = "; ".join(f"{t['provedor']}: {t['erro']}" for t in tentativas[-3:])
    raise RuntimeError(f"Nenhum provedor conseguiu gerar o texto. {detalhe}")


# ---------------------------------------------------------------------------
# Saude dos modelos / agentes
# ---------------------------------------------------------------------------

PROMPT_TESTE = (
    "Responda SOMENTE com JSON valido no formato "
    '{"ok": true, "servico": "teste"}. Nao escreva nada fora do JSON.'
)
SYSTEM_TESTE = "Voce e um agente de teste. Responda sempre JSON valido."


def _json_valido(texto: str) -> bool:
    """Aceita JSON puro ou JSON cercado por ```/texto."""
    if not texto or not texto.strip():
        return False
    limpo = texto.strip()
    if limpo.startswith("```"):
        limpo = limpo.strip("`")
        limpo = limpo.replace("json", "", 1).strip()
    inicio, fim = limpo.find("{"), limpo.rfind("}")
    if inicio < 0 or fim <= inicio:
        return False
    try:
        dados = json.loads(limpo[inicio : fim + 1])
    except Exception:
        return False
    return isinstance(dados, dict) and bool(dados)


def testar_modelo(
    provider: str,
    modelo: str,
    *,
    tentativas: Optional[int] = None,
    servico: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Testa um modelo de verdade antes de aprovar.

    - Ollama: 3 tentativas antes de reprovar (exigencia do usuario).
    - Demais: 2 tentativas (evita reprovar por falha transitoria).
    - Usa fallback=False: se o modelo falhar, NAO disfarca com outro.
    """
    from model_agents import nome_agente

    provider = (provider or "").strip().lower()
    if provider not in PROVIDERS:
        raise ValueError(f"Provedor invalido: {provider}")

    if tentativas is None:
        tentativas = 3 if provider == "ollama" else 2
    tentativas = max(1, min(int(tentativas), 5))

    servico = servico or "roteiro"
    agente = nome_agente(provider, servico)
    erros: List[str] = []
    amostra = ""
    inicio = time.monotonic()

    for numero in range(1, tentativas + 1):
        try:
            resposta = chamar_modelo(
                PROMPT_TESTE,
                system=SYSTEM_TESTE,
                provider=provider,
                model=modelo,
                temperatura=0,
                # 128 tokens podem ser gastos so no "pensamento" de modelos reasoning.
                max_tokens=512,
                fallback=False,
            )
            texto = (resposta.get("texto") or "").strip()
            if not texto:
                raise RuntimeError("resposta vazia")
            if not _json_valido(texto):
                raise RuntimeError("resposta nao e JSON valido")
            return {
                "provider": provider,
                "modelo": resposta.get("modelo") or modelo,
                "agente": agente,
                "servico": servico,
                "status": "aprovado",
                "tentativas_realizadas": numero,
                "tentativas_permitidas": tentativas,
                "latencia_ms": int((time.monotonic() - inicio) * 1000),
                "erro": "",
                "amostra": texto[:160],
            }
        except Exception as err:
            erros.append(_seguro(err))

    transient = any(
        sinal in erro
        for erro in erros
        for sinal in ("429", "503", "524", "timeout", "capacity", "Too many")
    )
    return {
        "provider": provider,
        "modelo": modelo,
        "agente": agente,
        "servico": servico,
        "status": "instavel" if transient else "reprovado",
        "tentativas_realizadas": tentativas,
        "tentativas_permitidas": tentativas,
        "latencia_ms": int((time.monotonic() - inicio) * 1000),
        "erro": " | ".join(erros)[:400],
        "amostra": amostra,
    }


def testar_candidatos(
    *,
    provider: Optional[str] = None,
    so_configurados: bool = True,
    servico: Optional[str] = None,
) -> Dict[str, Any]:
    """Testa todos os candidatos conhecidos e separa aprovados/reprovados."""
    from model_agents import candidatos_provider

    configurados = {p["id"] for p in listar_provedores() if p["configurado"]}
    resultados: List[Dict[str, Any]] = []
    for item in candidatos_provider(provider):
        if so_configurados and item["provider"] not in configurados:
            resultados.append({
                "provider": item["provider"],
                "modelo": item["modelo"],
                "agente": item["agente"],
                "servico": servico or item["servicos"][0],
                "status": "nao_testado",
                "motivo": "sem chave/configuracao",
            })
            continue
        resultados.append(testar_modelo(
            item["provider"], item["modelo"], servico=servico or item["servicos"][0],
        ))

    aprovados = [r for r in resultados if r.get("status") == "aprovado"]
    instaveis = [r for r in resultados if r.get("status") == "instavel"]
    reprovados = [r for r in resultados if r.get("status") == "reprovado"]
    return {
        "total_testados": len(aprovados) + len(instaveis) + len(reprovados),
        "aprovados": aprovados,
        "instaveis": instaveis,
        "reprovados": reprovados,
        "nao_testados": [r for r in resultados if r.get("status") == "nao_testado"],
    }
