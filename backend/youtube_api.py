"""
YouTube Data API v3 — alternativa oficial ao scraping, para análise dos
próprios vídeos do canal (metadados, estatísticas e comentários).

A pesquisa de HYPE usa `hype_research.py` (HTML do navegador, sem cota).
Aqui entra apenas quando você quer dados confiáveis e históricos do SEU canal.
A chave é opcional: YOUTUBE_API_KEY (ou YOUTUBE_DATA_API_KEY).

Limitação conhecida: a API NÃO expõe o gráfico de retenção; isso só existe no
YouTube Studio. Para auditoria de retenção, use o print do Studio.
"""

import datetime as dt
import os
import re
from typing import Any, Dict, List, Optional

import requests

BASE = "https://www.googleapis.com/youtube/v3"
TIMEOUT = (10, 20)


def chave() -> str:
    return (
        os.environ.get("YOUTUBE_API_KEY")
        or os.environ.get("YOUTUBE_DATA_API_KEY")
        or ""
    ).strip()


def configurado() -> bool:
    return bool(chave())


def _get(recurso: str, params: Dict[str, Any]) -> Dict[str, Any]:
    if not configurado():
        raise RuntimeError(
            "YOUTUBE_API_KEY não configurada. Defina o Secret/variável de ambiente "
            "ou use a pesquisa de hype (sem chave)."
        )
    consulta = {"key": chave(), **params}
    r = requests.get(f"{BASE}/{recurso}", params=consulta, timeout=TIMEOUT)
    if r.status_code >= 400:
        raise RuntimeError(f"YouTube API HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


def video_info(video_id: str) -> Dict[str, Any]:
    dados = _get(
        "videos",
        {
            "part": "snippet,statistics,contentDetails",
            "id": video_id,
        },
    )
    itens = dados.get("items") or []
    if not itens:
        return {}
    item = itens[0]
    snippet = item.get("snippet") or {}
    stats = item.get("statistics") or {}
    detalhes = item.get("contentDetails") or {}
    publicado = snippet.get("publishedAt", "")

    dias = 1.0
    if publicado:
        try:
            alvo = dt.datetime.fromisoformat(publicado.replace("Z", "+00:00"))
            dias = max(1.0, (dt.datetime.now(dt.timezone.utc) - alvo).total_seconds() / 86400)
        except Exception:
            pass

    views = int(stats.get("viewCount") or 0)
    likes = int(stats.get("likeCount") or 0)
    comentarios = int(stats.get("commentCount") or 0)

    return {
        "id": item.get("id"),
        "titulo": snippet.get("title", ""),
        "descricao": snippet.get("description", ""),
        "canal": snippet.get("channelTitle", ""),
        "canal_id": snippet.get("channelId", ""),
        "publicado_em": publicado,
        "thumbnail": (snippet.get("thumbnails") or {}).get("maxres", {}).get("url")
        or (snippet.get("thumbnails") or {}).get("high", {}).get("url", ""),
        "duracao_iso": detalhes.get("duration", ""),
        "views": views,
        "likes": likes,
        "comentarios": comentarios,
        "views_por_dia": int(views / dias),
        "taxa_like": round(likes / views, 4) if views else 0.0,
        "taxa_comentario": round(comentarios / views, 4) if views else 0.0,
        "tags": snippet.get("tags") or [],
        "url": f"https://www.youtube.com/watch?v={item.get('id', '')}",
    }


def comentarios(video_id: str, limite: int = 20) -> List[Dict[str, Any]]:
    dados = _get(
        "commentThreads",
        {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": min(100, max(1, limite)),
            "order": "relevance",
            "textFormat": "plainText",
        },
    )
    saida = []
    for item in dados.get("items") or []:
        topo = (item.get("snippet") or {}).get("topLevelComment") or {}
        s = topo.get("snippet") or {}
        saida.append(
            {
                "autor": s.get("authorDisplayName", ""),
                "texto": s.get("textDisplay", ""),
                "curtidas": int(s.get("likeCount") or 0),
                "data": s.get("publishedAt", ""),
            }
        )
    return saida


def canal_videos(channel_id: str, limite: int = 10) -> List[Dict[str, Any]]:
    dados = _get(
        "search",
        {
            "part": "snippet",
            "channelId": channel_id,
            "order": "date",
            "maxResults": min(50, max(1, limite)),
            "type": "video",
        },
    )
    return [
        {
            "id": (i.get("id") or {}).get("videoId", ""),
            "titulo": (i.get("snippet") or {}).get("title", ""),
            "publicado_em": (i.get("snippet") or {}).get("publishedAt", ""),
            "descricao": (i.get("snippet") or {}).get("description", "")[:300],
        }
        for i in dados.get("items") or []
    ]


def analisar_video(video_id: str, limite_comentarios: int = 20) -> Dict[str, Any]:
    """Resumo para comparar um vídeo nosso contra o benchmark do nicho."""
    info = video_info(video_id)
    if not info:
        return {"erro": "Vídeo não encontrado."}

    titulo = info["titulo"]
    impacto = sum(
        1 for p in ("mistério", "segredo", "aterrorizante", "verdade", "desapareceu", "descoberta")
        if p in titulo.lower()
    )
    return {
        **info,
        "comentarios_top": comentarios(video_id, limite_comentarios),
        "diagnostico": {
            "titulo_persona_acao_descoberta": bool(re.search(r"\b(um|uma|homem|mulher|caminhoneiro|garota|garoto|policial|médico|crianca)\b", titulo, re.I)) and impacto > 0,
            "impacto_no_titulo": impacto,
            "tem_thumb_maxres": bool(info["thumbnail"]),
            "observacao": (
                "Retenção por segundo só no YouTube Studio.Esta análise usa metadados públicos."
            ),
        },
    }
