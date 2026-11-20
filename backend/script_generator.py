"""
Gerador de roteiros de alta retencao em portugues do Brasil.

Entrada: tema, publico, duracao alvo, formato e tom.
Saida: um dicionario com duas representacoes do mesmo roteiro:

  * roteiro_texto -> uma fala por linha, pronta para o campo `script` do
    projeto e para o generate_srt() do compiler.py;
  * roteiro_json  -> blocos estruturados (hook, promessa, giro, prova,
    cliffhanger, cta) com sugestao visual e duracao por bloco.

Provedores: passa a usar o router em `llm_router.py`. Padrao `auto`, que
escolhe o primeiro provedor configurado nesta ordem:

  gemini -> groq -> openrouter -> cloudflare -> openai -> anthropic -> ollama

As chaves vem de variaveis de ambiente (Secrets da Cloudflare quando
hospedado). Voce pode fixar um provedor com SCRIPT_PROVIDER ou com o
argumento `provider` da funcao abaixo.
"""

import json
import os
import re
from typing import Any, Dict

from llm_router import PROVIDERS, chamar_modelo, listar_provedores

DEFAULT_PROVIDER = os.environ.get("SCRIPT_PROVIDER", "auto").strip().lower()

GEMINI_DEFAULT_MODEL = PROVIDERS["gemini"]["modelo"]
GEMINI_LITE_MODEL = PROVIDERS["gemini"]["modelo_leve"]
ANTHROPIC_DEFAULT_MODEL = PROVIDERS["anthropic"]["modelo"]

DEFAULT_PUBLICO = "brasileiros que consomem conteudo dark/dramatico no YouTube"
DEFAULT_TOM = "dark, dramatico e direto"

TIPOS_BLOCO = ("hook", "promessa", "giro", "prova", "cliffhanger", "cta")

SYSTEM_PROMPT = """Voce e um roteirista senior de YouTube para o mercado brasileiro,
especialista em retencao nos primeiros 60 segundos. Voce escreve somente em
portugues do Brasil, oral e natural. NUNCA use portugues de Portugal.

REGRAS DE RETENCAO (obedeca todas):
1. HOOK: a primeira fala comeca no segundo 0. Sem saudacao, sem "oi gente", sem
   "bem-vindos", sem apresentar o canal. Comece com pergunta incomoda,
   contradicao ou afirmacao ousada.
2. FRASES FALADAS: no maximo 12 a 15 palavras por bloco. Escreva como se
   estivesse falando, nao como texto de artigo.
3. CURIOSIDADE: abra uma pergunta no comeco e va respondendo aos poucos.
   Nunca responda tudo no primeiro bloco.
4. PATTERN INTERRUPT: a cada 5 a 8 segundos mude de ritmo, cena ou estilo de
   fala. Descreva isso no campo sugestao_visual.
5. CLIFFHANGER: antes de cada virada, use uma frase que segure o espectador
   ("mas o que aconteceu depois nao e o que voce espera...").
6. LOOP: a ultima fala deve retomar a primeira, fechando o ciclo e estimulando
   o rewATCH.
7. CTA: somente no ultimo bloco. Nunca no comeco.
8. DURACAO: some as duracoes dos blocos ate chegar perto da duracao alvo
   informada, com tolerancia de 10 por cento.
9. Zero enrollacao, zero cliche de "nao pule", zero metafora confusa.

FORMATO DE SAIDA — responda SOMENTE com JSON valido, sem markdown e sem
explicacao:

{
  "titulo": "titulo magnetico, ate 60 caracteres",
  "thumbnail_text": "no maximo 4 palavras de impacto",
  "blocos": [
    {
      "tipo": "hook|promessa|giro|prova|cliffhanger|cta",
      "fala": "frase curta falada em pt-BR",
      "sugestao_visual": "o que mostrar na tela nesse bloco",
      "duracao_segundos": 3.0
    }
  ]
}

O primeiro bloco DEVE ser do tipo "hook" e o ultimo do tipo "cta"."""


def _montar_prompt_usuario(
    tema: str,
    publico: str,
    duracao_segundos: float,
    formato: str,
    tom: str,
) -> str:
    return (
        f"Tema: {tema}\n"
        f"Publico: {publico}\n"
        f"Formato: {formato} (shorts = vertical 1080x1920, "
        f"square = 1080x1080, standard = horizontal 1920x1080)\n"
        f"Duracao alvo: {duracao_segundos:.0f} segundos\n"
        f"Tom: {tom}\n"
        "Escreva o roteiro agora."
    )


def _extrair_json(texto_bruto: str) -> Dict[str, Any]:
    """Remove cercas de markdown e devolve o primeiro objeto JSON do texto."""
    texto = texto_bruto.strip()
    texto = re.sub(r"^```(?:json)?\s*", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\s*```$", "", texto)

    inicio = texto.find("{")
    fim = texto.rfind("}")
    if inicio < 0 or fim <= inicio:
        raise ValueError("O modelo nao retornou um JSON valido.")

    try:
        return json.loads(texto[inicio : fim + 1])
    except json.JSONDecodeError as err:
        raise ValueError(f"Nao foi possivel interpretar o JSON do modelo: {err}")


def _normalizar(
    dados: Dict[str, Any],
    duracao_alvo: float,
    formato: str,
    modelo: str,
    provedor: str,
) -> Dict[str, Any]:
    """Valida a resposta e monta as duas representacoes do roteiro."""
    brutos = dados.get("blocos") or []
    if not isinstance(brutos, list) or not brutos:
        raise ValueError("O modelo retornou um roteiro sem blocos.")

    blocos = []
    duracao_padrao = max(2.0, duracao_alvo / max(len(brutos), 1))

    for item in brutos:
        if not isinstance(item, dict):
            continue
        fala = str(item.get("fala", "")).strip()
        if not fala:
            continue

        tipo = str(item.get("tipo", "giro")).strip().lower()
        if tipo not in TIPOS_BLOCO:
            tipo = "giro"

        try:
            duracao = float(item.get("duracao_segundos") or 0)
        except (TypeError, ValueError):
            duracao = 0.0
        if duracao <= 0:
            duracao = duracao_padrao

        blocos.append(
            {
                "tipo": tipo,
                "fala": fala,
                "sugestao_visual": str(item.get("sugestao_visual", "")).strip(),
                "duracao_segundos": round(duracao, 2),
            }
        )

    if not blocos:
        raise ValueError("O modelo retornou blocos sem falas.")

    # Garante a estrutura de retencao mesmo se o modelo desobedecer o prompt.
    blocos[0]["tipo"] = "hook"
    blocos[-1]["tipo"] = "cta"

    duracao_total = round(sum(b["duracao_segundos"] for b in blocos), 2)
    sec_por_bloco = round(duracao_total / len(blocos), 2)
    titulo = str(dados.get("titulo", "")).strip() or "Roteiro NatoDark"
    thumbnail = str(dados.get("thumbnail_text", "")).strip()

    roteiro_json = {
        "titulo": titulo,
        "thumbnail_text": thumbnail,
        "formato": formato,
        "duracao_estimada_segundos": duracao_total,
        "sec_per_block": sec_por_bloco,
        "blocos": blocos,
    }

    return {
        "titulo": titulo,
        "thumbnail_text": thumbnail,
        "formato": formato,
        "duracao_estimada_segundos": duracao_total,
        "sec_per_block": sec_por_bloco,
        "blocos": blocos,
        "roteiro_texto": "\n".join(b["fala"] for b in blocos),
        "roteiro_json": roteiro_json,
        "modo": provedor,
        "modelo": modelo,
    }


def generate_script(
    tema: str,
    *,
    publico: str = DEFAULT_PUBLICO,
    duracao_segundos: float = 60.0,
    formato: str = "shorts",
    tom: str = DEFAULT_TOM,
    api_key: str = None,
    provider: str = None,
    model: str = None,
    fallback: bool = True,
) -> Dict[str, Any]:
    """
    Gera o roteiro e devolve texto + JSON estruturado.

    Padrao: provider='auto', escolhendo o primeiro provedor configurado.
    Para fixar: provider='gemini' | 'groq' | 'openrouter' | 'cloudflare' |
    'openai' | 'anthropic' | 'ollama'. Use `model` para sobrescrever o modelo.

    Levanta ValueError/RuntimeError com mensagem em pt-BR quando nenhum
    provedor responder ou quando a resposta nao puder ser usada.
    """
    tema = (tema or "").strip()
    if not tema:
        raise ValueError("Informe o tema do roteiro.")

    try:
        duracao = float(duracao_segundos)
    except (TypeError, ValueError):
        raise ValueError("Duracao alvo invalida.")
    duracao = max(5.0, min(duracao, 600.0))

    prompt = _montar_prompt_usuario(
        tema, publico or DEFAULT_PUBLICO, duracao, formato, tom or DEFAULT_TOM
    )
    resposta = chamar_modelo(
        prompt,
        system=SYSTEM_PROMPT,
        provider=provider or DEFAULT_PROVIDER,
        model=model,
        api_key=api_key,
        temperatura=0.85,
        max_tokens=4096,
        fallback=fallback,
    )

    resultado = _normalizar(
        _extrair_json(resposta["texto"]), duracao, formato,
        resposta["modelo"], resposta["provedor"],
    )
    resultado["tentativas"] = resposta["tentativas"]
    resultado["fallback_usado"] = bool(resposta["tentativas"])
    return resultado


__all__ = [
    "generate_script",
    "listar_provedores",
    "PROVIDERS",
    "SYSTEM_PROMPT",
]
