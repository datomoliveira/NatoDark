"""
Media Scout — busca e aplica mídia licenciada em cima do roteiro.

Fontes (em ordem de preferencia):
  1. YouTube  -> clipes via yt-dlp, SEM chave (URL colada ou busca ytsearch)
  2. Unsplash -> fotos, chave gratuita UNSPLASH_ACCESS_KEY (local)
  3. Openverse / Wikimedia Commons -> CC / dominio publico, SEM chave
  Pexels e Pixabay continuam suportados se as chaves estiverem definidas,
  mas nao vem mais no default (os servicos estao fora do ar).

O download e o recorte do YouTube acontecem LOCALMENTE (youtube_clips.py);
nada disso roda na Cloudflare. Use apenas videos proprios/autorizados e
confira os creditos gravados em credits.json (canal, pagina e licenca).

As queries de busca por bloco vem do router de LLMs (llm_router.py), entao
funcionam com qualquer provedor configurado — nao so Gemini. Se nenhuma fonte
responder, gera slides escuros com Pillow para a timeline nao ficar vazia.
Sempre devolve creditos para atribuicao.
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
import youtube_clips
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


def _buscar_youtube(
    query: str,
    bloco: Dict[str, Any],
    indice: int,
    duracao: float,
    temp_dir: str,
) -> Optional[Dict[str, Any]]:
    """Clipe do YouTube: URL colada no bloco ou busca por HTML (ytsearch)."""
    if not youtube_clips.configurado():
        print("[MediaScout] YouTube indisponivel (yt-dlp nao instalado).")
        return None

    url = str(bloco.get("youtube_url") or "").strip()
    if not url:
        candidatos = youtube_clips.buscar(query, limite=2)
        if not candidatos:
            return None
        url = candidatos[0].get("url") or ""

    inicio = float(bloco.get("youtube_inicio") or 0.0)
    licenca = str(bloco.get("youtube_licenca") or youtube_clips.LICENCA_PADRAO)
    nome = f"yt_{indice:02d}_{uuid.uuid4().hex[:6]}.mp4"
    local = os.path.join(temp_dir, nome)
    try:
        meta = youtube_clips.baixar_clipe(
            url, local, inicio=inicio, duracao=duracao, altura_max=720
        )
    except Exception as err:
        print(f"[MediaScout] YouTube falhou: {err}")
        return None

    return {
        "url": url,
        "pagina": meta.get("pagina") or url,
        "autor": meta.get("autor") or "Canal do YouTube",
        "licenca": licenca,
        "fonte": "YouTube",
        "titulo": meta.get("titulo") or "",
        "local": local,
    }


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


def _buscar_unsplash(query: str, chave: str) -> Optional[Dict[str, str]]:
    """
    Unsplash so tem fotos. Autenticacao publica: `Authorization: Client-ID ...`.
    O download e registrado no endpoint `download_location` (exigido pelas
    diretrizes da API) e o credito do fotografo vai para credits.json.
    """
    headers = {**HEADERS, "Authorization": f"Client-ID {chave}", "Accept-Version": "v1"}
    try:
        r = requests.get(
            "https://api.unsplash.com/search/photos",
            headers=headers,
            params={"query": query, "per_page": 5, "orientation": "landscape"},
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            return None
        resultados = r.json().get("results") or []
        if not resultados:
            return None
        item = resultados[0]
        urls = item.get("urls") or {}
        foto = urls.get("regular") or urls.get("small") or ""
        if not foto:
            return None
        # Registra o download para a estatistica do fotografo (best-effort).
        download_location = (item.get("links") or {}).get("download_location")
        if download_location:
            try:
                requests.post(download_location, headers=headers, timeout=(5, 10))
            except Exception:
                pass
        return {
            "url": foto,
            "pagina": (item.get("links") or {}).get("html", ""),
            "autor": (item.get("user") or {}).get("name", ""),
            "licenca": "Unsplash License (uso gratuito; atribuicao recomendada)",
            "fonte": "Unsplash",
        }
    except Exception as err:
        print(f"[MediaScout] Unsplash falhou: {err}")
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


def _buscar_openverse(query: str, tipo: str) -> Optional[Dict[str, str]]:
    """
    Openverse (WordPress) — imagens CC/public domain, SEM chave e sem cota.
    API: https://api.openverse.org/v1/images/  (nao tem video; so imagem/audio).
    """
    if tipo != "image":
        return None
    # A Openverse e literal: "aviao sobre o mar" devolve 0, mas "aviao" acha
    # centenas. Tenta a frase, depois as palavras-chave, depois so a primeira.
    tentativas = [query]
    palavras = [
        p for p in re.split(r"\s+", query.strip())
        if p and p.lower() not in STOPWORDS
    ]
    if len(palavras) > 2:
        tentativas.append(" ".join(palavras[:2]))
    if len(palavras) > 1:
        tentativas.append(palavras[0])

    for termo in dict.fromkeys(tentativas):
        try:
            r = requests.get(
                "https://api.openverse.org/v1/images/",
                headers=HEADERS,
                params={
                    "q": termo,
                    "page_size": 10,
                    "license": "cc0,pdm,by,by-sa",
                    "mature": "false",
                },
                timeout=TIMEOUT,
            )
            if r.status_code != 200:
                continue
            for item in ((r.json() or {}).get("results") or []):
                url = item.get("url") or item.get("thumbnail")
                if not url:
                    continue
                return {
                    "url": url,
                    "pagina": item.get("foreign_landing_url") or item.get("source") or "",
                    "autor": _limpar_texto(item.get("creator") or "Autor na Openverse"),
                    "licenca": (item.get("license") or "Ver pagina (Openverse)").upper(),
                    "fonte": "Openverse",
                }
        except Exception as err:
            print(f"[MediaScout] Openverse falhou ({termo}): {err}")
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
    fontes = fontes or ["youtube", "unsplash", "openverse", "wikimedia"]
    fontes = [
        f.lower() for f in fontes
        if f.lower() in ("youtube", "unsplash", "openverse", "wikimedia", "pexels", "pixabay")
    ]
    if not fontes:
        fontes = ["youtube", "openverse", "wikimedia"]

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
            if fonte == "youtube":
                # Clipe do YouTube e sempre video; se falhar, cai para as outras fontes.
                tipo = "video"
                encontrado = _buscar_youtube(query, bloco, indice, duracao, temp_dir)
            elif fonte == "pexels":
                chave = os.environ.get("PEXELS_API_KEY")
                if not chave:
                    continue
                encontrado = _buscar_pexels(query, tipo, chave)
            elif fonte == "pixabay":
                chave = os.environ.get("PIXABAY_API_KEY")
                if not chave:
                    continue
                encontrado = _buscar_pixabay(query, tipo, chave)
            elif fonte == "unsplash":
                chave = os.environ.get("UNSPLASH_ACCESS_KEY")
                if not chave:
                    continue
                tipo = "image"  # Unsplash e banco de fotos: entra como still.
                encontrado = _buscar_unsplash(query, chave)
            elif fonte == "openverse":
                tipo = "image"  # Openverse e so imagem: entra como still.
                encontrado = _buscar_openverse(query, tipo)
            else:
                encontrado = _buscar_wikimedia(query, tipo)

            if encontrado and encontrado.get("url") and encontrado["url"] not in cache_de_urls:
                break
            encontrado = None

        if encontrado:
            cache_de_urls.add(encontrado["url"])
            if encontrado.get("local") and os.path.isfile(encontrado["local"]):
                # YouTube: yt-dlp + ffmpeg ja salvaram o recorte localmente.
                local = encontrado["local"]
                nome_arquivo = os.path.basename(local)
            else:
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
            "YouTube vem primeiro (yt-dlp local, sem chave): cole uma URL por bloco "
            "ou deixe a busca ytsearch decidir. Se falhar, cai para Pexels/Pixabay/"
            "Openverse/Wikimedia e, no ultimo caso, slide local. Use apenas clipes "
            "proprios ou autorizados — creditos em media/credits.json."
        ),
    }
