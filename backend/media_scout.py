"""
Media Scout — busca e aplica mídia licenciada em cima do roteiro.

Fontes (em ordem de preferencia):
  1. Pexels   -> video/images gratis, chave gratuita PEXELS_API_KEY
  2. Pixabay  -> video/images gratis, chave gratuita PIXABAY_API_KEY
  3. Wikimedia Commons -> CC / dominio publico, SEM chave

As queries de busca por bloco vem do router de LLMs (llm_router.py), entao
funcionam com qualquer provedor configurado — nao so Gemini. Se nenhuma fonte
responder, gera slides escuros com Pillow para a timeline nao ficar vazia.
Sempre devolve creditos para atribuicao.

Este modulo NAO baixa video do YouTube: usar clipes alheios de la e risco
juridico (Content ID) e o mito dos "10 segundos" nao protege ninguem.
"""

import html
import json
import os
import re
import uuid
from typing import Any, Dict, List, Optional

import requests

from compiler import get_media_duration
from database import update_project_timeline
from storage import LOCAL_STORAGE_DIR, generate_download_url, upload_file

TIMEOUT = (10, 25)
MAX_BYTES = 90 * 1024 * 1024
HEADERS = {"User-Agent": "NatoDarkStudio/1.0 (auto media sourcing)"}

STOPWORDS = {
    "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas", "um", "uma",
    "uns", "umas", "o", "a", "os", "as", "que", "com", "para", "por", "pelo",
    "pela", "se", "ao", "aos", "e", "ou", "mas", "como", "mais", "muito", "tem",
    "ter", "foi", "era", "sao", "isso", "isto", "aquele", "essa", "este", "seu",
    "sua", "ele", "ela", "eles", "elas", "nos", "voce", "voces", "me", "te", "lhe",
    "nem", "so", "ja", "ainda", "sobre", "entre", "antes", "depois", "quando",
    "onde", "porque", "qual", "quem", "cujo", "cuja", "seu", "sua", "os", "as",
    "pelo", "pela", "pelos", "pelas", "num", "numa", "numa", "dum", "duma",
}

TIPOS_POR_BLOCO = {
    "hook": "video",
    "giro": "video",
    "cliffhanger": "video",
    "promessa": "image",
    "prova": "image",
    "cta": "image",
}


def _limpar_texto(texto: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(texto or "")).strip()


def _termos_chave(texto: str, limite: int = 4) -> List[str]:
    palavras = re.findall(r"[A-Za-zÀ-ÿ0-9]{4,}", _limpar_texto(texto).lower())
    vistas = []
    for p in palavras:
        if p not in STOPWORDS and p not in vistas:
            vistas.append(p)
        if len(vistas) >= limite:
            break
    return vistas


def _query_fallback(bloco: Dict[str, Any], tema: str, indice: int) -> Dict[str, str]:
    base = " ".join(_termos_chave(f"{tema} {bloco.get('fala','')} {bloco.get('sugestao_visual','')}"))
    if not base:
        base = "dark atmosphere cinematic"
    return {
        "query_video": f"{base} cinematic dark footage",
        "query_image": f"{base} cinematic dark photo",
        "tipo": TIPOS_POR_BLOCO.get(bloco.get("tipo", ""), "video" if indice % 2 == 0 else "image"),
    }


def _queries_com_llm(
    blocos: List[Dict[str, Any]], tema: str
) -> Optional[List[Dict[str, str]]]:
    """Pede ao router (qualquer provedor) termos de busca em ingles, um por bloco."""
    from llm_router import chamar_modelo
    from script_generator import _extrair_json

    resumo = [
        {
            "i": i,
            "tipo": b.get("tipo", ""),
            "fala": b.get("fala", ""),
            "visual": b.get("sugestao_visual", ""),
        }
        for i, b in enumerate(blocos)
    ]
    prompt = (
        "Voce prepara a busca de metragem para um video de YouTube. "
        "Para CADA bloco abaixo, devolva uma query curta em INGLES para stock video "
        "e outra para stock photo. Use termos visuais concretos (lugares, objetos, "
        "emocoes, acoes), nao traducao literal. Evite marcas e nomes de pessoas.\n\n"
        f"Tema: {tema}\nBlocos: {json.dumps(resumo, ensure_ascii=False)}\n\n"
        "Responda JSON: {\"queries\":[{\"query_video\":\"...\",\"query_image\":\"...\",\"tipo\":\"video|image\"}]}"
    )
    system = (
        "Voce prepara a busca de metragem para um video de YouTube. "
        "Responda SOMENTE com JSON valido, sem markdown."
    )
    try:
        resposta = chamar_modelo(
            prompt, system=system, provider="auto",
            temperatura=0.4, max_tokens=2048,
        )
        dados = _extrair_json(resposta["texto"])
        itens = dados.get("queries") or []
        if len(itens) != len(blocos):
            return None
        saida = []
        for item in itens:
            tipo = str(item.get("tipo", "video")).lower()
            saida.append(
                {
                    "query_video": str(item.get("query_video", "")).strip(),
                    "query_image": str(item.get("query_image", "")).strip(),
                    "tipo": "image" if tipo == "image" else "video",
                }
            )
        return saida
    except Exception as err:
        print(f"[MediaScout] LLM falhou, usando fallback: {err}")
        return None


def _primeiro_valor(dados: dict, *chaves: str) -> str:
    for chave in chaves:
        valor = dados.get(chave)
        if valor:
            return str(valor)
    return ""


def _buscar_pexels(query: str, tipo: str, chave: str) -> Optional[Dict[str, str]]:
    url = (
        "https://api.pexels.com/videos/search"
        if tipo == "video"
        else "https://api.pexels.com/v1/search"
    )
    try:
        r = requests.get(
            url,
            headers={**HEADERS, "Authorization": chave},
            params={"query": query, "per_page": 5},
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            return None
        dados = r.json()
        itens = dados.get("videos") or dados.get("photos") or []
        if not itens:
            return None
        item = itens[0]
        if tipo == "video":
            arquivos = [
                f for f in (item.get("video_files") or [])
                if str(f.get("file_type", "")).startswith("video/")
            ]
            arquivos.sort(key=lambda f: int(f.get("width") or 0))
            arquivo = next(
                (f for f in arquivos if int(f.get("width") or 0) >= 640),
                arquivos[0] if arquivos else None,
            )
            if not arquivo:
                return None
            return {
                "url": arquivo["link"],
                "pagina": item.get("url", ""),
                "autor": _primeiro_valor(item.get("user") or {}, "name"),
                "licenca": "Pexels License (uso gratuito, sem atribuicao obrigatoria)",
                "fonte": "Pexels",
            }
        return {
            "url": (item.get("src") or {}).get("large") or (item.get("src") or {}).get("medium", ""),
            "pagina": item.get("url", ""),
            "autor": item.get("photographer", ""),
            "licenca": "Pexels License (uso gratuito, sem atribuicao obrigatoria)",
            "fonte": "Pexels",
        }
    except Exception as err:
        print(f"[MediaScout] Pexels falhou: {err}")
        return None


def _buscar_pixabay(query: str, tipo: str, chave: str) -> Optional[Dict[str, str]]:
    url = "https://pixabay.com/api/videos/" if tipo == "video" else "https://pixabay.com/api/"
    params = {"key": chave, "q": query, "per_page": 5}
    if tipo == "image":
        params["image_type"] = "photo"
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        hits = r.json().get("hits") or []
        if not hits:
            return None
        item = hits[0]
        if tipo == "video":
            arquivos = item.get("videos") or {}
            arquivo = arquivos.get("large") or arquivos.get("medium")
            if not arquivo:
                return None
            return {
                "url": arquivo.get("url", ""),
                "pagina": item.get("pageURL", ""),
                "autor": item.get("user", ""),
                "licenca": "Pixabay Content License (uso gratuito)",
                "fonte": "Pixabay",
            }
        return {
            "url": item.get("largeImageURL") or item.get("webformatURL", ""),
            "pagina": item.get("pageURL", ""),
            "autor": item.get("user", ""),
            "licenca": "Pixabay Content License (uso gratuito)",
            "fonte": "Pixabay",
        }
    except Exception as err:
        print(f"[MediaScout] Pixabay falhou: {err}")
        return None


def _buscar_wikimedia(query: str, tipo: str) -> Optional[Dict[str, str]]:
    filtro = "filetype:video" if tipo == "video" else "filetype:bitmap"
    try:
        r = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            headers=HEADERS,
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": f"{query} {filtro}",
                "gsrnamespace": 6,
                "gsrlimit": 8,
                "prop": "imageinfo",
                "iiprop": "url|extmetadata",
                "iiurlwidth": 1280,
                "format": "json",
            },
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            return None
        paginas = (r.json().get("query") or {}).get("pages") or {}
        for pagina in paginas.values():
            info = (pagina.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata") or {}
            url = info.get("thumburl") or info.get("url")
            if not url:
                continue
            licenca = _limpar_texto((meta.get("LicenseShortName") or {}).get("value", ""))
            autor = _limpar_texto((meta.get("Artist") or {}).get("value", ""))
            return {
                "url": url,
                "pagina": info.get("descriptionurl", ""),
                "autor": autor,
                "licenca": licenca or "Ver pagina (Wikimedia Commons)",
                "fonte": "Wikimedia Commons",
            }
        return None
    except Exception as err:
        print(f"[MediaScout] Wikimedia falhou: {err}")
        return None


def _extensao(url: str, tipo: str) -> str:
    caminho = url.split("?")[0].split("#")[0].lower()
    for ext in (".mp4", ".webm", ".mov", ".m4v", ".jpg", ".jpeg", ".png", ".webp"):
        if caminho.endswith(ext):
            return ext
    return ".mp4" if tipo == "video" else ".jpg"


def _baixar(url: str, destino: str) -> bool:
    try:
        with requests.get(url, headers=HEADERS, stream=True, timeout=TIMEOUT) as r:
            if r.status_code not in (200, 206):
                return False
            tamanho = 0
            with open(destino, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if not chunk:
                        continue
                    tamanho += len(chunk)
                    if tamanho > MAX_BYTES:
                        return False
                    f.write(chunk)
        return os.path.getsize(destino) > 1024
    except Exception as err:
        print(f"[MediaScout] Download falhou: {err}")
        return False


def _gerar_slide(tema: str, falas: str, indice: int, destino: str) -> None:
    """Fallback visual: slide dark com formas, sem depender de rede."""
    from PIL import Image, ImageDraw

    w, h = 1080, 1920
    img = Image.new("RGB", (w, h), (8, 8, 10))
    draw = ImageDraw.Draw(img)
    tom = (139, 0, 0) if indice % 2 == 0 else (70, 10, 20)
    for i in range(9):
        y = 180 + i * 180
        draw.rectangle([60, y, w - 60, y + 6], fill=tom)
    draw.ellipse([w - 420, 220, w + 160, 800], outline=tom, width=18)
    draw.ellipse([-160, h - 780, 420, h - 200], outline=(60, 60, 70), width=12)
    draw.text((80, 100), _limpar_texto(tema)[:46], fill=(230, 230, 235))
    draw.text((80, h - 130), f"NATODARK  /  {indice + 1:02d}", fill=(120, 120, 130))
    img.save(destino, "JPEG", quality=88)


def _blocos_do_roteiro(roteiro_json: Dict[str, Any], script_texto: str) -> List[Dict[str, Any]]:
    blocos = roteiro_json.get("blocos") if isinstance(roteiro_json, dict) else None
    if blocos:
        return [b for b in blocos if isinstance(b, dict)]
    linhas = [l.strip() for l in (script_texto or "").split("\n") if l.strip()]
    sec = float((roteiro_json or {}).get("sec_per_block", 3.0) or 3.0)
    return [
        {"tipo": "giro", "fala": linha, "sugestao_visual": "", "duracao_segundos": sec}
        for linha in linhas
    ]


def build_auto_timeline(
    project_id: str,
    roteiro_json: Dict[str, Any],
    *,
    script_texto: str = "",
    tema: str = "",
    fontes: Optional[List[str]] = None,
    usar_gemini: bool = True,
    max_blocos: int = 12,
) -> Dict[str, Any]:
    """
    Busca midia para cada bloco e SUBSTITUI a timeline do projeto.
    Devolve relatorio com creditos de atribuicao.
    """
    fontes = fontes or ["pexels", "pixabay", "wikimedia"]
    fontes = [f.lower() for f in fontes if f.lower() in ("pexels", "pixabay", "wikimedia")]
    if not fontes:
        fontes = ["wikimedia"]

    blocos = _blocos_do_roteiro(roteiro_json, script_texto)[: max(1, max_blocos)]
    if not blocos:
        raise ValueError("Sem blocos no roteiro. Gere um roteiro antes de buscar midia.")

    titulo = (roteiro_json.get("titulo") if isinstance(roteiro_json, dict) else "") or tema
    tema_busca = tema or titulo or "misterio historia"

    queries = None
    if usar_gemini:
        queries = _queries_com_llm(blocos, tema_busca)

    cache_de_urls = set()
    temp_dir = os.path.join(os.path.dirname(__file__), "temp", "media_scout", project_id)
    os.makedirs(temp_dir, exist_ok=True)

    timeline = []
    creditos = []
    usadas = set()

    for indice, bloco in enumerate(blocos):
        sugestao = (
            queries[indice]
            if queries
            else _query_fallback(bloco, tema_busca, indice)
        )
        tipo = sugestao.get("tipo") or TIPOS_POR_BLOCO.get(bloco.get("tipo", ""), "video")
        query = (sugestao.get("query_video") if tipo == "video" else sugestao.get("query_image")) or ""
        if not query:
            query = _query_fallback(bloco, tema_busca, indice)[
                "query_video" if tipo == "video" else "query_image"
            ]

        duracao = float(bloco.get("duracao_segundos") or 3.0)
        duracao = max(1.0, min(duracao, 30.0))

        encontrado = None
        for fonte in fontes:
            if fonte == "pexels":
                chave = os.environ.get("PEXELS_API_KEY")
                if not chave:
                    continue
                encontrado = _buscar_pexels(query, tipo, chave)
            elif fonte == "pixabay":
                chave = os.environ.get("PIXABAY_API_KEY")
                if not chave:
                    continue
                encontrado = _buscar_pixabay(query, tipo, chave)
            else:
                encontrado = _buscar_wikimedia(query, tipo)

            if encontrado and encontrado.get("url") and encontrado["url"] not in cache_de_urls:
                break
            encontrado = None

        if encontrado:
            cache_de_urls.add(encontrado["url"])
            ext = _extensao(encontrado["url"], tipo)
            nome_arquivo = f"auto_{indice:02d}_{uuid.uuid4().hex[:6]}{ext}"
            local = os.path.join(temp_dir, nome_arquivo)
            if not _baixar(encontrado["url"], local):
                encontrado = None

        if not encontrado:
            tipo = "image"
            ext = ".jpg"
            nome_arquivo = f"auto_{indice:02d}_{uuid.uuid4().hex[:6]}{ext}"
            local = os.path.join(temp_dir, nome_arquivo)
            _gerar_slide(tema_busca, bloco.get("fala", ""), indice, local)
            encontrado = {
                "url": "",
                "pagina": "",
                "autor": "NatoDark",
                "licenca": "Gerado localmente",
                "fonte": "Slide local",
            }

        trim_start = 0.0
        trim_end = 0.0
        if tipo == "video":
            real = get_media_duration(local)
            trim_end = round(min(duracao, real), 2) if real > 0 else duracao

        storage_key = f"projects/{project_id}/media/{nome_arquivo}"
        upload_file(local, storage_key)
        usadas.add(encontrado["fonte"])

        timeline.append(
            {
                "id": f"auto_{uuid.uuid4().hex[:10]}",
                "type": tipo,
                "key": storage_key,
                "url": generate_download_url(storage_key),
                "name": f"{indice + 1:02d} · {bloco.get('tipo','giro')} · {encontrado['fonte']}",
                "duration": round(duracao, 2),
                "trim_start": trim_start,
                "trim_end": trim_end,
                "auto": True,
                "query": query,
            }
        )
        creditos.append(
            {
                "bloco": indice + 1,
                "tipo": bloco.get("tipo", "giro"),
                "fonte": encontrado["fonte"],
                "autor": encontrado["autor"],
                "licenca": encontrado["licenca"],
                "pagina": encontrado["pagina"],
            }
        )

    update_project_timeline(project_id, timeline)

    creditos_dir = os.path.join(LOCAL_STORAGE_DIR, "projects", project_id, "media")
    os.makedirs(creditos_dir, exist_ok=True)
    with open(os.path.join(creditos_dir, "credits.json"), "w", encoding="utf-8") as f:
        json.dump(creditos, f, ensure_ascii=False, indent=2)

    # Limpa temporarios (o arquivo ja esta no storage)
    try:
        for arquivo in os.listdir(temp_dir):
            caminho = os.path.join(temp_dir, arquivo)
            if os.path.isfile(caminho):
                os.remove(caminho)
    except OSError:
        pass

    return {
        "status": "sucesso",
        "blocos": len(timeline),
        "videos": sum(1 for t in timeline if t["type"] == "video"),
        "imagens": sum(1 for t in timeline if t["type"] == "image"),
        "fontes_usadas": sorted(usadas),
        "creditos": creditos,
        "timeline": timeline,
        "arquivo_creditos": f"projects/{project_id}/media/credits.json",
        "dica": (
            "Configure PEXELS_API_KEY e PIXABAY_API_KEY (gratuitas) para metragem real. "
            "Sem elas, usa Wikimedia Commons e slides locais."
        ),
    }
