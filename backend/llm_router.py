"""
Router de modelos de linguagem — NatoDark Studio.

Um unico ponto de entrada para gerar texto com diversas APIs. As chaves sao
lidas de variaveis de ambiente; quando hospedado na Cloudflare, essas mesmas
variaveis sao os Secrets do Worker (mesmo nome, sem precisar mudar codigo).

Provedores suportados (todos com saida forcada em JSON):

  gemini       Google Gemini  — tier gratuito  — GEMINI_API_KEY / GOOGLE_API_KEY
  groq         Groq           — tier gratuito  — GROQ_API_KEY
  openrouter   OpenRouter     — modelos :free  — OPENROUTER_API_KEY
  cloudflare   Workers AI     — tier gratuito  — CF_ACCOUNT_ID + CF_API_TOKEN
  openai       OpenAI         — pago barato    — OPENAI_API_KEY
  anthropic    Anthropic      — pago opcional  — ANTHROPIC_API_KEY
  ollama       Ollama local   — gratuito/local — sem chave (OLLAMA_URL)

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
from typing import Any, Dict, List, Optional, Tuple

import requests

TIMEOUT = (10, 60)
ORDEM_FALLBACK = ("gemini", "groq", "openrouter", "cloudflare", "openai", "anthropic", "ollama")


PROVIDERS: Dict[str, Dict[str, Any]] = {
    "gemini": {
        "nome": "Google Gemini",
        "custo": "gratuito",
        "env_chave": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "modelo": os.environ.get("GEMINI_MODEL", "gemini-3.8-flash"),
        "modelo_leve": os.environ.get("GEMINI_LITE_MODEL", "gemini-3.5-flash-lite"),
        "env_modelo": "GEMINI_MODEL",
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
        "env_chave": ("OPENROUTER_API_KEY",),
        "modelo": os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"),
        "env_modelo": "OPENROUTER_MODEL",
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
        "nome": "Ollama (local)",
        "custo": "gratuito / local",
        "env_chave": (),
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
        for nome in info["env_chave"]:
            valor = os.environ.get(nome)
            if valor and len(valor) > 6:
                texto = texto.replace(valor, "***")
    return texto


def listar_provedores() -> List[Dict[str, Any]]:
    """Lista provedores e seus modelos, sem nunca expor as chaves."""
    saida = []
    for chave in ORDEM_FALLBACK:
        info = PROVIDERS[chave]
        configurado = (
            all(_env(n) for n in info["env_chave"])
            if info["env_chave"]
            else bool(_env("OLLAMA_URL", "OLLAMA_HOST") or chave == "ollama")
        )
        saida.append(
            {
                "id": chave,
                "nome": info["nome"],
                "custo": info["custo"],
                "modelo": info["modelo"],
                "env_modelo": info["env_modelo"],
                "env_chave": list(info["env_chave"]),
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
    headers = {"Authorization": f"Bearer {chave}", "Content-Type": "application/json"}
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
    return ((escolhas[0].get("message") or {}).get("content") or "")


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
    url = _env("OLLAMA_URL", "OLLAMA_HOST") or "http://127.0.0.1:11434"
    r = requests.post(
        f"{url.rstrip('/')}/api/chat",
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

    if provider == "gemini":
        chave = api_key or _env(*info["env_chave"])
        if not chave:
            raise RuntimeError("GEMINI_API_KEY nao configurada (tire uma chave gratuita em https://aistudio.google.com/apikey).")
        return _call_gemini(prompt, system, modelo, chave, temperatura, max_tokens), modelo

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
