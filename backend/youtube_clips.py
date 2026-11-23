"""
Clipes do YouTube como materia-prima — download e recorte LOCAL via yt-dlp.

Roda no computador, nunca na Cloudflare (Workers nao tem ffmpeg nem yt-dlp).
Nao usa chave de API: busca pelo HTML do YouTube (ytsearch) e, se o usuario
colar uma URL, baixa apenas o trecho pedido.

IMPORTANTE: use apenas videos proprios, autorizados ou com licenca compativel.
O modulo grava sempre o canal/a pagina/credito em credits.json para atribuicao.
O mito dos "10 segundos" nao protege ninguem; a responsabilidade e do usuario.
"""

import os
import tempfile
from typing import Any, Dict, List, Optional

import imageio_ffmpeg

try:
    import yt_dlp
except ImportError:  # pragma: no cover - dependencia deckarada em requirements.txt
    yt_dlp = None  # type: ignore[assignment]

LICENCA_PADRAO = "YouTube — uso autorizado pelo titular dos direitos"
MAX_SOURCE_BYTES = 120 * 1024 * 1024


def configurado() -> bool:
    return yt_dlp is not None


def _ffmpeg_bin() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def _ffmpeg_location() -> str:
    """
    yt-dlp procura um executável chamado `ffmpeg`. O imageio-ffmpeg instala
    `ffmpeg-linux-x86_64-vX`, então criamos um symlink com o nome esperado.
    """
    destino = os.path.join(tempfile.gettempdir(), "natodark_ffmpeg_bin")
    os.makedirs(destino, exist_ok=True)
    link = os.path.join(destino, "ffmpeg")
    if not os.path.exists(link):
        try:
            os.symlink(_ffmpeg_bin(), link)
        except OSError:
            # Em sistemas sem symlink, o fallback é o diretório original.
            return os.path.dirname(_ffmpeg_bin())
    # O yt-dlp checa `ffmpeg` na PATH (ignora ffmpeg_location nessa checagem).
    caminho = os.environ.get("PATH", "")
    if destino not in caminho.split(os.pathsep):
        os.environ["PATH"] = destino + os.pathsep + caminho
    return destino


def _opcoes_base(skip_download: bool = True) -> Dict[str, Any]:
    opcoes: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": skip_download,
        "retries": 2,
        "ffmpeg_location": _ffmpeg_location(),
    }
    cookie = os.environ.get("YOUTUBE_COOKIES_FILE", "").strip()
    if cookie and os.path.isfile(cookie):
        opcoes["cookiefile"] = cookie
    return opcoes


def _resumo(info: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "url": info.get("webpage_url") or info.get("url") or "",
        "titulo": info.get("title") or "Sem titulo",
        "autor": info.get("uploader") or info.get("channel") or "Canal nao informado",
        "duracao": float(info.get("duration") or 0),
        "licenca": info.get("license") or LICENCA_PADRAO,
        "pagina": info.get("webpage_url") or info.get("url") or "",
    }


def info(url: str) -> Dict[str, Any]:
    """Metadados de um video, sem baixar nada."""
    if not yt_dlp:
        raise RuntimeError("yt-dlp nao esta instalado (pip install -r requirements.txt).")
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise RuntimeError("URL invalida. Use um link https://...")
    with yt_dlp.YoutubeDL(_opcoes_base(True)) as ydl:
        dado = ydl.extract_info(url, download=False)
    if not dado:
        raise RuntimeError("Nao foi possivel ler os metadados do video.")
    return _resumo(dado)


def buscar(query: str, limite: int = 3) -> List[Dict[str, Any]]:
    """Busca por HTML (ytsearch), sem API key. Devolve candidatos para escolha."""
    if not yt_dlp:
        return []
    query = (query or "").strip()
    if not query:
        return []
    opcoes = _opcoes_base(True)
    opcoes["playlistend"] = max(1, min(limite, 10))
    try:
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            dado = ydl.extract_info(f"ytsearch{limite}:{query}", download=False)
        entradas = (dado or {}).get("entries") or []
        return [_resumo(e) for e in entradas if isinstance(e, dict) and e.get("id")]
    except Exception as err:
        print(f"[YouTube] Busca falhou: {err}")
        return []


def baixar_clipe(
    url: str,
    destino: str,
    *,
    inicio: float = 0.0,
    duracao: float = 5.0,
    altura_max: int = 720,
) -> Dict[str, Any]:
    """
    Baixa só o intervalo [inicio, inicio+duracao] e salva um mp4 sem audio em
    `destino` (o compiler já remove o audio original dos clipes).

    Devolve os metadados para gravar creditos. Erros sobem como RuntimeError
    para o media_scout tentar a proxima fonte.
    """
    if not yt_dlp:
        raise RuntimeError("yt-dlp nao esta instalado.")
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise RuntimeError("URL invalida.")

    os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
    inicio = max(0.0, float(inicio or 0.0))
    duracao = max(0.5, min(float(duracao or 5.0), 30.0))
    fim = inicio + duracao

    with tempfile.TemporaryDirectory(prefix="natodark_yt_") as tmp:
        opcoes = _opcoes_base(False)
        opcoes.update(
            {
                "format": (
                    f"bestvideo[height<={altura_max}][ext=mp4]+bestaudio[ext=m4a]/"
                    f"best[height<={altura_max}]/best"
                ),
                "merge_output_format": "mp4",
                "outtmpl": os.path.join(tmp, "source.%(ext)s"),
            }
        )
        if inicio > 0 or duracao > 0:
            # Formato exigido pelo yt-dlp 2026: lista de dicts start_time/end_time.
            opcoes["download_ranges"] = lambda info_dict, ydl: [
                {"start_time": inicio, "end_time": fim}
            ]
            opcoes["force_keyframes_at_cuts"] = True

        with yt_dlp.YoutubeDL(opcoes) as ydl:
            dado = ydl.extract_info(url, download=True)
            if not dado:
                raise RuntimeError("Download do YouTube nao retornou metadados.")

        candidatos = [
            os.path.join(tmp, nome)
            for nome in os.listdir(tmp)
            if nome.startswith("source.") and not nome.endswith((".part", ".ytdl"))
        ]
        if not candidatos:
            raise RuntimeError("yt-dlp nao gerou arquivo de video.")
        origem = max(candidatos, key=os.path.getsize)
        if os.path.getsize(origem) > MAX_SOURCE_BYTES:
            raise RuntimeError("Video origem muito grande; use um clipe menor.")

        # Normaliza o trecho: garante a duracao pedida e remove audio (o compiler
        # coloca a narração do usuario depois).
        import subprocess

        cmd = [
            _ffmpeg_bin(), "-y", "-loglevel", "error",
            "-i", origem, "-t", f"{duracao:.3f}",
            "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", destino,
        ]
        resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if resultado.returncode != 0 or not os.path.isfile(destino):
            raise RuntimeError(f"ffmpeg falhou ao recortar: {resultado.stderr[:180]}")

    return _resumo(dado)
