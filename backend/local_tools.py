"""
Ferramentas locais do NatoDark — registro, detecção de capacidade e adaptadores.

Regras deste módulo (importantes):

* Nada aqui é obrigatório para o app abrir. Todo import pesado é LAZY.
* Nenhuma chave, token ou peso de modelo fica versionado. Modelos baixados
  vão para ``backend/.cache/models`` (gitignored).
* Licença/custo são explícitos: ferramentas com pesos CC-BY-NC ou licença
  duvidosa ficam DESLIGADAS por default, porque o canal é monetizado.
* Isto roda no BACKEND LOCAL (Python), nunca na Cloudflare.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests

BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = Path(
    os.environ.get("NATODARK_MODEL_CACHE", str(BASE_DIR / ".cache" / "models"))
).expanduser()

# O raw.githubusercontent devolve ponteiro Git-LFS; o Hugging Face serve o ONNX real.
YUNET_URL = (
    "https://huggingface.co/opencv/face_detection_yunet/resolve/main/"
    "face_detection_yunet_2023mar.onnx"
)
YUNET_FILE = "face_detection_yunet_2023mar.onnx"


# Catálogo único: usado por /api/tools e pela documentação.
# estado: "ativo" (já serve), "opcional" (instalar quando quiser),
# "bloqueado" (licença/custo/hardware não cabem no canal monetizado).
CATALOGO: List[Dict[str, Any]] = [
    {
        "id": "ffmpeg",
        "nome": "FFmpeg (imageio-ffmpeg)",
        "licenca": "LGPL/GPL (binário embarcado)",
        "custo": "grátis",
        "estado": "ativo",
        "para_que": "cortar clipes, normalizar, mixar áudio e compor o MP4 final",
        "como": "já vem em requirements.txt; get_ffmpeg_exe()",
        "monetizavel": True,
    },
    {
        "id": "pyscenedetect",
        "nome": "PySceneDetect",
        "licenca": "BSD-3-Clause",
        "custo": "grátis",
        "estado": "opcional",
        "para_que": "achar cortes/cenas em clipes do YouTube e escolher trechos limpos",
        "como": "pip install scenedetect-headless",
        "monetizavel": True,
    },
    {
        "id": "yunet",
        "nome": "YuNet (OpenCV Zoo)",
        "licenca": "Apache-2.0 / MIT (OpenCV Zoo)",
        "custo": "grátis",
        "estado": "opcional",
        "para_que": "detectar rosto para crop inteligente (não cortar a cabeça do apresentador)",
        "como": "pip install opencv-python-headless + modelo ONNX (~232 KB) baixado sob demanda",
        "monetizavel": True,
    },
    {
        "id": "whisperx",
        "nome": "WhisperX",
        "licenca": "BSD-2-Clause",
        "custo": "grátis",
        "estado": "opcional",
        "para_que": "alinhamento forçado de palavras/diarização; hoje já usamos faster-whisper",
        "como": "pip install -r requirements-ml.txt e NATODARK_USE_WHISPERX=1",
        "monetizavel": True,
    },
    {
        "id": "mediapipe",
        "nome": "MediaPipe",
        "licenca": "Apache-2.0",
        "custo": "grátis",
        "estado": "opcional",
        "para_que": "face mesh / pose / selfie segmentation para enquadramento e overlays",
        "como": "pip install mediapipe (CPU)",
        "monetizavel": True,
    },
    {
        "id": "ben2",
        "nome": "BEN2 (Background Erase Network)",
        "licenca": "MIT (modelo Base)",
        "custo": "grátis",
        "estado": "opcional",
        "para_que": "recortar fundo de imagens/clipes com matte de cabelo",
        "como": "pip install -r requirements-ml.txt (pesos ~363 MB, melhor com GPU)",
        "monetizavel": True,
    },
    {
        "id": "depth_anything",
        "nome": "Depth Anything V2 Small",
        "licenca": "Apache-2.0 (somente o Small)",
        "custo": "grátis",
        "estado": "opcional",
        "para_que": "mapa de profundidade para parallax/efeito 2.5D",
        "como": "usar depth-anything/Depth-Anything-V2-Small-hf (Base/Large são CC-BY-NC — evitar)",
        "monetizavel": True,
    },
    {
        "id": "hyperframes",
        "nome": "HyperFrames",
        "licenca": "Apache-2.0",
        "custo": "grátis (render local sem watermark; Pro pago é opcional)",
        "estado": "opcional",
        "para_que": "renderizador HTML -> MP4 determinístico, alternativa ao ffmpeg puro",
        "como": "npm install --prefix renderer && RENDER_ENGINE=hyperframes",
        "monetizavel": True,
    },
    {
        "id": "clap",
        "nome": "CLAP (LAION)",
        "licenca": "CC0-1.0",
        "custo": "grátis",
        "estado": "opcional",
        "para_que": "casar trecho de áudio com a intenção do texto (score semântico)",
        "como": "pip install laion-clap (torch + librosa, pesado)",
        "monetizavel": True,
    },
    {
        "id": "sam2",
        "nome": "SAM 2",
        "licenca": "Apache-2.0 (com LICENSE_cctorch BSD-3)",
        "custo": "grátis",
        "estado": "opcional",
        "para_que": "segmentação de objeto em vídeo com memória entre frames",
        "como": "GPU/CUDA necessário; pip install -r requirements-ml.txt",
        "monetizavel": True,
    },
    {
        "id": "demucs",
        "nome": "Demucs",
        "licenca": "MIT no código; PESOS com licença não esclarecida pelo autor",
        "custo": "grátis",
        "estado": "bloqueado",
        "para_que": "separar voz/música de clipes",
        "como": "NATODARK_ENABLE_DEMUCS=1 (use só se aceitar o risco dos pesos)",
        "monetizavel": False,
    },
]


def _tem_modulo(nome: str) -> bool:
    try:
        return importlib.util.find_spec(nome) is not None
    except (ImportError, ValueError):
        return False


def _tem_comando(nome: str) -> bool:
    return shutil.which(nome) is not None


def _hyperframes_disponivel() -> bool:
    """Verifica sem baixar nada: pacote local ou npx já instalado em cache."""
    raiz = BASE_DIR.parent / "renderer" / "node_modules" / ".bin" / "hyperframes"
    if raiz.exists():
        return True
    try:
        proc = subprocess.run(
            ["npx", "--no-install", "hyperframes", "--version"],
            capture_output=True,
            text=True,
            timeout=20,
            cwd=str(BASE_DIR.parent),
        )
        return proc.returncode == 0
    except Exception:
        return False


def status() -> Dict[str, Any]:
    """Retrato do que está realmente instalado nesta máquina."""
    disponivel = {
        "ffmpeg": bool(_tem_modulo("imageio_ffmpeg")),
        "pyscenedetect": _tem_modulo("scenedetect"),
        "yunet": _tem_modulo("cv2") and (CACHE_DIR / YUNET_FILE).is_file(),
        "whisperx": _tem_modulo("whisperx"),
        "mediapipe": _tem_modulo("mediapipe"),
        "ben2": _tem_modulo("ben2"),
        "depth_anything": _tem_modulo("transformers") and _tem_modulo("torch"),
        "hyperframes": _hyperframes_disponivel(),
        "clap": _tem_modulo("laion_clap"),
        "sam2": _tem_modulo("sam2"),
        "demucs": _tem_modulo("demucs"),
    }
    itens: List[Dict[str, Any]] = []
    for item in CATALOGO:
        linha = dict(item)
        ok = disponivel.get(item["id"], False)
        linha["instalado"] = ok
        if item["estado"] == "ativo":
            linha["efetivo"] = ok
        elif item["estado"] == "bloqueado":
            linha["efetivo"] = bool(ok and os.environ.get("NATODARK_ENABLE_DEMUCS") == "1")
        else:
            linha["efetivo"] = ok
        itens.append(linha)

    return {
        "ferramentas": itens,
        "render_engine": os.environ.get("RENDER_ENGINE", "ffmpeg").lower(),
        "cache_modelos": str(CACHE_DIR),
        "env_flags": {
            "RENDER_ENGINE": os.environ.get("RENDER_ENGINE", "ffmpeg"),
            "NATODARK_USE_WHISPERX": os.environ.get("NATODARK_USE_WHISPERX", "0"),
            "NATODARK_ENABLE_DEMUCS": os.environ.get("NATODARK_ENABLE_DEMUCS", "0"),
        },
        "observacao": (
            "Tudo roda no backend local. Nenhuma chave ou peso vai para a Cloudflare. "
            "Ferramentas com pesos CC-BY-NC/licença duvidosa ficam desligadas em canal monetizado."
        ),
    }


# ---------------------------------------------------------------------------
# Adaptadores leves (CPU, sem torch) — usados de verdade no pipeline
# ---------------------------------------------------------------------------

def detectar_cenas(video_path: str, limite: float = 27.0) -> List[Dict[str, float]]:
    """Cortes reais de cena. Devolve [] se PySceneDetect não estiver instalado."""
    if not _tem_modulo("scenedetect"):
        return []
    try:
        from scenedetect import ContentDetector, detect

        cenas = detect(video_path, ContentDetector(threshold=limite))
        resultado: List[Dict[str, float]] = []
        for inicio, fim in cenas:
            resultado.append(
                {
                    "inicio": round(float(inicio.get_seconds()), 3),
                    "fim": round(float(fim.get_seconds()), 3),
                }
            )
        return resultado
    except Exception as err:
        print(f"[LocalTools] PySceneDetect falhou: {err}")
        return []


def _modelo_yunet() -> Optional[Path]:
    destino = CACHE_DIR / YUNET_FILE
    if destino.is_file() and destino.stat().st_size > 10_000:
        return destino
    if not _tem_modulo("cv2"):
        return None
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(YUNET_URL, timeout=(10, 60), stream=True) as resp:
            resp.raise_for_status()
            tmp = destino.with_suffix(".onnx.part")
            with open(tmp, "wb") as fh:
                for parte in resp.iter_content(64 * 1024):
                    fh.write(parte)
            tmp.replace(destino)
        return destino
    except Exception as err:
        print(f"[LocalTools] não foi possível baixar YuNet: {err}")
        return None


def caixa_do_rosto(caminho_imagem: str) -> Optional[Tuple[int, int, int, int]]:
    """(x, y, w, h) do rosto mais provável, ou None."""
    if not _tem_modulo("cv2"):
        return None
    modelo = _modelo_yunet()
    if modelo is None:
        return None
    try:
        import cv2

        imagem = cv2.imread(caminho_imagem)
        if imagem is None:
            return None
        altura, largura = imagem.shape[:2]
        detec = cv2.FaceDetectorYN.create(
            str(modelo), "", (largura, altura), 0.6, 0.3, 5000
        )
        _, rostos = detec.detect(imagem)
        if rostos is None or len(rostos) == 0:
            return None
        x, y, w, h = (float(v) for v in rostos[0][:4])
        return int(max(0, x)), int(max(0, y)), int(w), int(h)
    except Exception as err:
        print(f"[LocalTools] YuNet falhou: {err}")
        return None


def caixa_de_crop(
    caminho_imagem: str, largura: int, altura: int, proporcao: float
) -> Tuple[int, int, int, int]:
    """
    Crop central, deslocado para manter o rosto. Sem OpenCV, faz centro puro.
    """
    if largura <= 0 or altura <= 0:
        return 0, 0, largura, altura
    alvo = proporcao
    if largura / altura > alvo:
        nova_largura = max(1, int(round(altura * alvo)))
        nova_altura = altura
    else:
        nova_largura = largura
        nova_altura = max(1, int(round(largura / alvo)))

    x = (largura - nova_largura) // 2
    y = (altura - nova_altura) // 2

    rosto = caixa_do_rosto(caminho_imagem)
    if rosto:
        rx, ry, rw, rh = rosto
        centro_x = rx + rw / 2
        centro_y = ry + rh / 2
        # Mantém o rosto no terço superior (onde o olho do espectador espera).
        x = int(centro_x - nova_largura * 0.5)
        y = int(centro_y - nova_altura * 0.42)
    x = max(0, min(x, largura - nova_largura))
    y = max(0, min(y, altura - nova_altura))
    return x, y, x + nova_largura, y + nova_altura


# ---------------------------------------------------------------------------
# Adaptadores PESADOS (lazy, desligados por default)
# ---------------------------------------------------------------------------

def transcrever_whisperx(
    audio_path: str, modelo: str = "small", idioma: str = "pt"
) -> List[Dict[str, Any]]:
    """Palavra a palavra com alinhamento. Só se NATODARK_USE_WHISPERX=1."""
    if os.environ.get("NATODARK_USE_WHISPERX", "0") != "1":
        raise RuntimeError("WhisperX desligado (NATODARK_USE_WHISPERX=1 para ativar)")
    import torch
    import whisperx

    dispositivo = "cuda" if torch.cuda.is_available() else "cpu"
    tipo = "float16" if dispositivo == "cuda" else "int8"
    m = whisperx.load_model(modelo, dispositivo, compute_type=tipo, language=idioma)
    audio = whisperx.load_audio(audio_path)
    resultado = m.transcribe(audio, batch_size=4)
    alinhador, meta = whisperx.load_align_model(
        language_code=resultado.get("language", idioma), device=dispositivo
    )
    resultado = whisperx.align(
        resultado["segments"], alinhador, meta, audio, dispositivo
    )
    return [
        {
            "texto": seg.get("text", "").strip(),
            "inicio": float(seg.get("start", 0.0)),
            "fim": float(seg.get("end", 0.0)),
            "palavras": [
                {
                    "texto": p.get("word", ""),
                    "inicio": float(p.get("start", 0.0)),
                    "fim": float(p.get("end", 0.0)),
                }
                for p in seg.get("words", [])
            ],
        }
        for seg in resultado.get("segments", [])
    ]


def remover_fundo_ben2(imagem_path: str, saida_path: str) -> bool:
    """Matte com BEN2 Base (MIT). Retorna False se não estiver instalado."""
    if not _tem_modulo("ben2"):
        return False
    try:
        import torch
        from ben2 import AutoModel
        from PIL import Image

        dispositivo = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        modelo = AutoModel.from_pretrained("PramaLLC/BEN2")
        modelo.to(dispositivo).eval()
        primeiro = Image.open(imagem_path)
        resultado = modelo.inference(primeiro)
        resultado.save(saida_path)
        return True
    except Exception as err:
        print(f"[LocalTools] BEN2 falhou: {err}")
        return False


def mapa_de_profundidade(imagem_path: str, saida_path: Optional[str] = None) -> bool:
    """Apenas o checkpoint Small (Apache-2.0). Base/Large são CC-BY-NC."""
    if not (_tem_modulo("transformers") and _tem_modulo("torch")):
        return False
    try:
        from PIL import Image
        from transformers import pipeline

        extrator = pipeline(
            "depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf"
        )
        with Image.open(imagem_path) as imagem:
            profundo = extrator(imagem.convert("RGB"))["depth"]
        if saida_path:
            profundo.save(saida_path)
        return True
    except Exception as err:
        print(f"[LocalTools] Depth Anything falhou: {err}")
        return False


def pontos_mediapipe(imagem_path: str, tipo: str = "face") -> Optional[Any]:
    if not _tem_modulo("mediapipe"):
        return None
    try:
        import cv2
        import mediapipe as mp

        imagem = cv2.imread(imagem_path)
        if imagem is None:
            return None
        rgb = cv2.cvtColor(imagem, cv2.COLOR_BGR2RGB)
        if tipo == "pose":
            with mp.solutions.pose.Pose(static_image_mode=True) as sol:
                return sol.process(rgb).pose_landmarks
        with mp.solutions.face_mesh.FaceMesh(static_image_mode=True) as sol:
            return sol.process(rgb).multi_face_landmarks
    except Exception as err:
        print(f"[LocalTools] MediaPipe falhou: {err}")
        return None


def score_clap(audio_path: str, descricoes: Sequence[str]) -> Optional[List[float]]:
    if not _tem_modulo("laion_clap"):
        return None
    try:
        import laion_clap

        modelo = laion_clap.CLAP_Module(enable_fusion=False)
        modelo.load_ckpt()
        audio = modelo.get_audio_embedding_from_filelist(
            x=[audio_path], use_tensor=False
        )
        texto = modelo.get_text_embedding(list(descricoes), use_tensor=False)
        return (audio @ texto.T)[0].tolist()
    except Exception as err:
        print(f"[LocalTools] CLAP falhou: {err}")
        return None


def separar_voz_demucs(audio_path: str, diretorio_saida: str) -> Optional[str]:
    """Desligado por default: licença dos pesos não é clara para uso comercial."""
    if os.environ.get("NATODARK_ENABLE_DEMUCS", "0") != "1":
        return None
    if not _tem_modulo("demucs"):
        return None
    try:
        import demucs.separate

        demucs.separate.main(
            [
                "--mp3",
                "--two-stems",
                "vocals",
                "-n",
                "mdx_extra_q",
                "-d",
                "cpu",
                "-o",
                diretorio_saida,
                audio_path,
            ]
        )
        return diretorio_saida
    except Exception as err:
        print(f"[LocalTools] Demucs falhou: {err}")
        return None
