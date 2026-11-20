"""
Pesquisa de HYPE via NAVEGADOR/página HTML — sem API do YouTube.

A YouTube Data API tem cota diária e trava em picos de demanda. Aqui a gente
lê o HTML público de resultados (o mesmo que o navegador vê), extrai o
`ytInitialData` e monta o ranking. A API oficial fica como alternativa em
`youtube_api.py`, para análise dos vídeos do próprio canal.

Fontes:
  1. YouTube search HTML (títulos, canal, views, idade, duração) — sem chave
  2. DuckDuckGo HTML (pauta/tendências fora do YouTube) — sem chave
  3. Router de LLMs para transformar o que está bombando em ângulos de roteiro
"""

import html
import json
import math
import os
import re
import urllib.parse
from typing import Any, Dict, List, Optional

import requests

TIMEOUT = (10, 20)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}

PERIODOS = {
    "day": "EgQIARAB",
    "week": "EgQIAxAB",
    "month": "EgQIBBAB",
    "year": "EgQICBAB",
    "all": "",
}

PALAVRAS_IMPACTO = (
    "aterrorizante", "misterio", "segredo", "desapareceu", "descoberta", "verdade",
    "proibido", "oculto", "inesperado", "chocante", "real", "nunca", "primeira vez",
    "assustador", "inexplicavel", "surpreendente", "ocorreu", "sumiu", "acontecia",
)


def _texto(obj: Any) -> str:
    if not isinstance(obj, dict):
        return ""
    if obj.get("simpleText"):
        return str(obj["simpleText"]).strip()
    runs = obj.get("runs") or []
    return "".join(str(r.get("text", "")) for r in runs if isinstance(r, dict)).strip()


def _percorrer(obj: Any):
    """Percorre o ytInitialData procurando renderizadores de vídeo."""
    if isinstance(obj, dict):
        for chave in ("videoRenderer", "videoWithContextRenderer", "gridVideoRenderer"):
            if isinstance(obj.get(chave), dict):
                yield obj[chave]
        for valor in obj.values():
            yield from _percorrer(valor)
    elif isinstance(obj, list):
        for valor in obj:
            yield from _percorrer(valor)


def _parse_views(texto: str) -> float:
    s = (texto or "").lower().replace(".", "").replace(",", ".")
    m = re.search(r"([\d]+(?:\.\d+)?)\s*(mil|mi|bi|m\b)", s)
    if m:
        fator = {"mil": 1_000, "mi": 1_000_000, "m": 1_000_000, "bi": 1_000_000_000}[m.group(2)]
        return float(m.group(1)) * fator
    m = re.search(r"([\d]+(?:\.\d+)?)", s)
    return float(m.group(1)) if m else 0.0


def _parse_dias(texto: str) -> float:
    s = (texto or "").lower()
    m = re.search(r"(\d+)\s*(minuto|hora|dia|semana|m[eê]s|ano)", s)
    if not m:
        if "hoje" in s or "agora" in s or "streamed" in s:
            return 0.0
        if "ontem" in s or "1 dia" in s:
            return 1.0
        return 30.0
    numero = int(m.group(1))
    unidade = m.group(2)
    fator = {
        "minuto": 1 / 1440, "hora": 1 / 24, "dia": 1,
        "semana": 7, "mês": 30, "mes": 30, "ano": 365,
    }.get(unidade, 30)
    return numero * fator


def _hype_score(titulo: str, views: float, dias: float) -> int:
    impacto = sum(1 for p in PALAVRAS_IMPACTO if p in titulo.lower())
    frescor = max(0.0, 1.0 - dias / 30.0)
    velocidade = min(1.0, math.log10(max(10.0, views / max(1.0, dias))) / 6.0)
    return int(round(max(0, min(100, 45 * velocidade + 30 * frescor + 25 * min(1.0, impacto / 2)))))


def buscar_youtube(termo: str, periodo: str = "week", limite: int = 10) -> List[Dict[str, Any]]:
    """Lê a página de busca do YouTube e devolve os vídeos encontrados."""
    sp = PERIODOS.get((periodo or "week").lower(), PERIODOS["week"])
    params = {"search_query": termo, "hl": "pt", "gl": "BR"}
    if sp:
        params["sp"] = sp

    r = requests.get(
        "https://www.youtube.com/results",
        headers=HEADERS,
        params=params,
        timeout=TIMEOUT,
    )
    if r.status_code != 200:
        raise RuntimeError(f"YouTube respondeu HTTP {r.status_code}.")

    marca = r.text.find("ytInitialData")
    if marca < 0:
        raise RuntimeError("Não foi possível ler os resultados do YouTube (ytInitialData ausente).")
    inicio = r.text.find("{", marca)
    if inicio < 0:
        raise RuntimeError("ytInitialData inválido.")
    dados, _ = json.JSONDecoder().raw_decode(r.text[inicio:])

    resultados: List[Dict[str, Any]] = []
    vistos = set()
    for item in _percorrer(dados):
        video_id = item.get("videoId")
        if not video_id or video_id in vistos:
            continue
        titulo = _texto(item.get("title"))
        if not titulo:
            continue
        vistos.add(video_id)
        canal = _texto(item.get("ownerText") or item.get("longBylineText"))
        views_txt = _texto(item.get("viewCountText"))
        idade_txt = _texto(item.get("publishedTimeText"))
        views = _parse_views(views_txt)
        dias = _parse_dias(idade_txt)
        resultados.append(
            {
                "fonte": "youtube",
                "id": video_id,
                "titulo": titulo,
                "canal": canal,
                "views_texto": views_txt,
                "views": int(views),
                "idade": idade_txt,
                "dias": round(dias, 2),
                "views_por_dia": int(views / max(1.0, dias)),
                "duracao": _texto(item.get("lengthText")),
                "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "hype_score": _hype_score(titulo, views, dias),
            }
        )
        if len(resultados) >= max(1, limite):
            break

    resultados.sort(key=lambda x: (x["hype_score"], x["views_por_dia"]), reverse=True)
    return resultados


def buscar_duckduckgo(termo: str, limite: int = 5) -> List[Dict[str, Any]]:
    """Busca pauta/tendências no HTML do DuckDuckGo (sem chave de API)."""
    try:
        r = requests.get(
            "https://html.duckduckgo.com/html/",
            headers=HEADERS,
            params={"q": termo, "kl": "br-pt"},
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            return []
    except Exception as err:
        print(f"[Hype] DuckDuckGo falhou: {err}")
        return []

    padrao = re.compile(
        r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        re.S,
    )
    saida = []
    for url, titulo_html in padrao.findall(r.text):
        titulo = html.unescape(re.sub(r"<[^>]+>", "", titulo_html)).strip()
        url = html.unescape(url)
        m = re.search(r"uddg=([^&]+)", url)
        if m:
            url = urllib.parse.unquote(m.group(1))
        if not titulo or not url.startswith("http"):
            continue
        saida.append(
            {
                "fonte": "web",
                "titulo": titulo,
                "url": url,
                "hype_score": 0,
            }
        )
        if len(saida) >= max(1, limite):
            break
    return saida


def sugerir_angulos(tema: str, tendencias: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Transforma o que está bombando em títulos e ângulos para o nosso estúdio."""
    from llm_router import chamar_modelo

    resumo = [
        {
            "titulo": t.get("titulo", ""),
            "canal": t.get("canal", ""),
            "views_por_dia": t.get("views_por_dia", 0),
        }
        for t in tendencias[:8]
    ]
    prompt = (
        "Voce e um estrategista de YouTube no Brasil. Com base nas tendencias abaixo "
        "e no tema do usuario, crie novos angulos ORIGINAIS — nao copie titulos alheios. "
        "Use o modelo: persona comum + acao cotidiana + descoberta impactante. "
        "Responda SOMENTE JSON: {\"titulos\":[\"...\"],\"angulos\":[\"...\"],\"insight\":\"...\"}\n\n"
        f"Tema: {tema}\nTendencias: {json.dumps(resumo, ensure_ascii=False)}"
    )
    try:
        resposta = chamar_modelo(
            prompt,
            system="Estrategista de retencao para YouTube pt-BR. Responda apenas JSON valido.",
            provider="auto",
            temperatura=0.8,
            max_tokens=1200,
        )
        texto = resposta["texto"].strip()
        texto = re.sub(r"^```(?:json)?\s*", "", texto).rstrip("`")
        inicio, fim = texto.find("{"), texto.rfind("}")
        if inicio < 0 or fim <= inicio:
            return None
        dados = json.loads(texto[inicio : fim + 1])
        return {
            "titulos": [str(x) for x in (dados.get("titulos") or [])[:5]],
            "angulos": [str(x) for x in (dados.get("angulos") or [])[:5]],
            "insight": str(dados.get("insight", ""))[:300],
            "provedor": resposta["provedor"],
        }
    except Exception as err:
        print(f"[Hype] LLM falhou: {err}")
        return None


def pesquisar_hype(
    tema: str,
    *,
    periodo: str = "week",
    limite: int = 10,
    usar_llm: bool = True,
) -> Dict[str, Any]:
    """Pesquisa completa: YouTube + web + sugestões de ângulo."""
    tema = (tema or "").strip()
    if not tema:
        raise ValueError("Informe o tema da pesquisa.")

    erros: List[str] = []
    try:
        videos = buscar_youtube(tema, periodo, limite)
    except Exception as err:
        erros.append(f"YouTube: {err}")
        videos = []

    web = buscar_duckduckgo(f"{tema} tendências mistério história", 5)

    sugestoes = None
    if usar_llm and (videos or web):
        sugestoes = sugerir_angulos(tema, videos or web)

    return {
        "status": "sucesso" if (videos or web) else "sem_resultados",
        "tema": tema,
        "periodo": periodo,
        "videos": videos,
        "web": web,
        "sugestoes": sugestoes,
        "erros": erros,
        "fonte": "HTML do YouTube + DuckDuckGo (sem API key)",
        "dica": (
            "Use 'hype_score' e 'views_por_dia' para escolher o angulo. "
            "Clique em 'Usar angulo' para jogar o titulo no gerador de roteiro."
        ),
    }
