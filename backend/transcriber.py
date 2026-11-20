"""
Sincronização real de legendas com a VOZ do usuário (faster-whisper).

O roteiro estima `sec_per_block`; a sua narração tem tempos reais. Este módulo
ouve o áudio enviado, devolve segmentos com start/end, gera um SRT sincronizado
e alinha cada bloco do roteiro ao trecho falado correspondente.

Tudo roda LOCALmente: nenhum áudio vai para API de terceiros, nenhum custo por
minuto e funciona offline depois que o modelo foi baixado uma vez.

Modelos (variáveis de ambiente):
  WHISPER_MODEL=small     # tiny | base | small | medium | large-v3
  WHISPER_COMPUTE=int8    # int8 (CPU) | float16 (GPU)
  WHISPER_LANGUAGE=pt
"""

import json
import os
import re
import threading
from typing import Any, Dict, List, Optional, Tuple

from database import get_project, update_project_script, update_project_script_json
from storage import download_file, upload_file

DEFAULT_MODEL = os.environ.get("WHISPER_MODEL", "small").strip() or "small"
DEFAULT_COMPUTE = os.environ.get("WHISPER_COMPUTE", "int8").strip() or "int8"
DEFAULT_LANGUAGE = os.environ.get("WHISPER_LANGUAGE", "pt").strip() or "pt"

_MODELOS: Dict[Tuple[str, str], Any] = {}
_LOCK = threading.Lock()

STOPWORDS = {
    "de", "do", "da", "dos", "das", "em", "no", "na", "um", "uma", "uns", "umas",
    "o", "a", "os", "as", "que", "com", "para", "por", "se", "ao", "e", "ou",
    "mas", "como", "mais", "muito", "foi", "era", "sao", "isso", "isto", "ele",
    "ela", "voce", "me", "te", "lhe", "ja", "ainda", "sobre", "quando", "onde",
    "porque", "qual", "quem", "num", "numa",
}


def _resolver_dispositivo(compute_type: str) -> Tuple[str, str]:
    """Usa CUDA se disponível; senão CPU com int8 (rápido e leve)."""
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", compute_type
    except Exception:
        pass
    return "cpu", "int8" if compute_type in ("float16", "bfloat16") else compute_type


def carregar_modelo(model_size: Optional[str] = None, compute_type: Optional[str] = None):
    """Carrega uma vez e mantém em cache (o download do modelo é único)."""
    tamanho = (model_size or DEFAULT_MODEL).strip()
    compute = (compute_type or DEFAULT_COMPUTE).strip()
    chave = (tamanho, compute)
    with _LOCK:
        if chave not in _MODELOS:
            from faster_whisper import WhisperModel
            dispositivo, compute_efetivo = _resolver_dispositivo(compute)
            print(f"[Whisper] carregando {tamanho} em {dispositivo}/{compute_efetivo}...")
            _MODELOS[chave] = WhisperModel(
                tamanho, device=dispositivo, compute_type=compute_efetivo
            )
        return _MODELOS[chave]


def _limpar(texto: str) -> str:
    return re.sub(r"\s+", " ", (texto or "").replace("\n", " ")).strip()


def transcrever(
    caminho_audio: str,
    *,
    model_size: Optional[str] = None,
    compute_type: Optional[str] = None,
    language: Optional[str] = None,
    beam_size: int = 5,
    vad_filter: bool = True,
) -> Dict[str, Any]:
    """Transcreve o arquivo e devolve segmentos com timestamps reais."""
    if not os.path.exists(caminho_audio):
        raise FileNotFoundError(f"Áudio não encontrado: {caminho_audio}")

    modelo = carregar_modelo(model_size, compute_type)
    tamanho = (model_size or DEFAULT_MODEL).strip()
    idioma = (language or DEFAULT_LANGUAGE).strip() or None

    segmentos_brutos, info = modelo.transcribe(
        caminho_audio,
        language=idioma,
        beam_size=max(1, min(int(beam_size or 5), 10)),
        vad_filter=bool(vad_filter),
        condition_on_previous_text=False,
    )

    segmentos = []
    for seg in segmentos_brutos:
        texto = _limpar(getattr(seg, "text", ""))
        if not texto:
            continue
        segmentos.append(
            {
                "start": round(float(seg.start), 2),
                "end": round(float(seg.end), 2),
                "text": texto,
            }
        )

    return {
        "modelo": tamanho,
        "dispositivo": _resolver_dispositivo(compute_type or DEFAULT_COMPUTE)[0],
        "idioma": getattr(info, "language", idioma or "pt"),
        "confianca_idioma": round(float(getattr(info, "language_probability", 0.0) or 0.0), 3),
        "duracao_segundos": round(float(getattr(info, "duration", 0.0) or 0.0), 2),
        "segmentos": segmentos,
        "texto": "\n".join(s["text"] for s in segmentos),
    }


def _formatar_tempo(segundos: float) -> str:
    segundos = max(0.0, float(segundos))
    h = int(segundos // 3600)
    m = int((segundos % 3600) // 60)
    s = int(segundos % 60)
    ms = int(round((segundos - int(segundos)) * 1000))
    if ms >= 1000:
        ms = 999
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def gerar_srt(segmentos: List[Dict[str, Any]], destino: str, max_chars: int = 48) -> int:
    """
    Escreve SRT a partir dos segmentos. Segmentos muito longos são divididos
    em linhas menores, com o tempo distribuído proporcionalmente ao texto.
    """
    linhas: List[Tuple[float, float, str]] = []

    for seg in segmentos:
        inicio = float(seg.get("start", 0.0))
        fim = float(seg.get("end", inicio + 1.0))
        if fim <= inicio:
            fim = inicio + 0.8
        texto = _limpar(seg.get("text", ""))
        if not texto:
            continue

        palavras = texto.split()
        partes: List[str] = []
        atual: List[str] = []
        for palavra in palavras:
            candidato = " ".join(atual + [palavra])
            if atual and len(candidato) > max_chars:
                partes.append(" ".join(atual))
                atual = [palavra]
            else:
                atual.append(palavra)
        if atual:
            partes.append(" ".join(atual))

        total_chars = sum(len(p) for p in partes) or 1
        cursor = inicio
        duracao = fim - inicio
        for parte in partes:
            pedaco = max(0.6, duracao * (len(parte) / total_chars))
            fim_parte = min(fim, cursor + pedaco)
            linhas.append((cursor, fim_parte, parte))
            cursor = fim_parte

    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "w", encoding="utf-8") as f:
        for idx, (inicio, fim, texto) in enumerate(linhas, start=1):
            f.write(f"{idx}\n")
            f.write(f"{_formatar_tempo(inicio)} --> {_formatar_tempo(fim)}\n")
            f.write(f"{texto}\n\n")
    return len(linhas)


def _tokens(texto: str) -> set:
    palavras = re.findall(r"[A-Za-zÀ-ÿ0-9]+", (texto or "").lower())
    return {p for p in palavras if len(p) > 2 and p not in STOPWORDS}


def alinhar_blocos(
    segmentos: List[Dict[str, Any]],
    blocos: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Acha, para cada bloco do roteiro, o trecho da narração que melhor casa.

    A busca é monotônica (o bloco N vem depois do N-1), o que evita emparelhar
    repetições. A confiança é o quanto dos termos do bloco apareceram na fala.
    """
    if not segmentos or not blocos:
        return []

    candidatos = [(i, _tokens(s.get("text", "")), s) for i, s in enumerate(segmentos)]
    timings: List[Dict[str, Any]] = []
    ultimo_indice = -1

    for pos, bloco in enumerate(blocos):
        alvo = _tokens(bloco.get("fala", ""))
        alvo_texto = _limpar(bloco.get("fala", ""))
        melhor = None
        melhor_score = -1.0

        inicio_busca = max(0, ultimo_indice)
        for indice, tokens, seg in candidatos[inicio_busca:]:
            if not alvo and not tokens:
                score = 1.0
            elif not alvo or not tokens:
                score = 0.0
            else:
                intersecao = len(alvo & tokens)
                score = intersecao / max(1, min(len(alvo), len(tokens)))
                # Penaliza casar com um trecho muito anterior ao esperado.
                score -= 0.02 * (indice - ultimo_indice - 1)
                if _limpar(seg.get("text", "")) == alvo_texto:
                    score += 0.5
            if score > melhor_score:
                melhor_score = score
                melhor = (indice, seg)

        if melhor is None:
            # Sem segmentos suficientes: distribui o tempo restante.
            frac = (pos + 1) / (len(blocos) + 1)
            inicio = float(segmentos[-1]["end"]) * frac
            fim = inicio + 2.0
            confianca = 0.0
            indice_usado = ultimo_indice
        else:
            indice_usado, seg = melhor
            inicio = float(seg["start"])
            fim = float(seg["end"])
            confianca = round(max(0.0, min(1.0, melhor_score)), 2)

        ultimo_indice = max(ultimo_indice, indice_usado)
        timings.append(
            {
                "bloco": pos + 1,
                "tipo": bloco.get("tipo", "giro"),
                "fala_roteiro": alvo_texto,
                "fala_ouvida": _limpar(segmentos[indice_usado].get("text", "")) if 0 <= indice_usado < len(segmentos) else "",
                "start": round(inicio, 2),
                "end": round(fim, 2),
                "confianca": confianca,
            }
        )

    return timings


def sincronizar_projeto(
    project_id: str,
    *,
    model_size: Optional[str] = None,
    compute_type: Optional[str] = None,
    language: Optional[str] = None,
    alinhar: bool = True,
) -> Dict[str, Any]:
    """
    Transcreve a voz UPLOADEADA do projeto e salva:
      - SRT sincronizado no storage (subtitle_style.srt_key)
      - transcrição e timings em script_json
    O compiler passa a usar esse SRT em vez do SRT estimado por sec_per_block.
    """
    projeto = get_project(project_id)
    if not projeto:
        raise ValueError("Projeto não encontrado.")
    chave_audio = projeto.get("audio_file")
    if not chave_audio:
        raise ValueError(
            "Este projeto ainda não tem narração. Suba o áudio da sua voz primeiro."
        )

    temp_dir = os.path.join(os.path.dirname(__file__), "temp", project_id, "transcribe")
    os.makedirs(temp_dir, exist_ok=True)
    extensao = os.path.splitext(str(chave_audio))[1] or ".wav"
    caminho_audio = os.path.join(temp_dir, f"voice{extensao}")
    download_file(chave_audio, caminho_audio)

    transcricao = transcrever(
        caminho_audio,
        model_size=model_size,
        compute_type=compute_type,
        language=language,
    )

    srt_local = os.path.join(temp_dir, "voice.srt")
    total_linhas = gerar_srt(transcricao["segmentos"], srt_local)
    srt_key = f"projects/{project_id}/subtitles/voice.srt"
    upload_file(srt_local, srt_key)

    roteiro = dict(projeto.get("script_json") or {})
    if alinhar:
        blocos = roteiro.get("blocos") or [
            {"tipo": "giro", "fala": linha}
            for linha in (projeto.get("script") or "").split("\n")
            if linha.strip()
        ]
        timings = alinhar_blocos(transcricao["segmentos"], blocos)
    else:
        timings = []

    roteiro["transcricao"] = {
        "texto": transcricao["texto"],
        "idioma": transcricao["idioma"],
        "modelo": transcricao["modelo"],
        "duracao_segundos": transcricao["duracao_segundos"],
        "segmentos": transcricao["segmentos"],
    }
    roteiro["timings_voz"] = timings
    update_project_script_json(project_id, roteiro)

    estilo = dict(projeto.get("subtitle_style") or {})
    estilo["srt_key"] = srt_key
    estilo["sec_per_block"] = round(
        transcricao["duracao_segundos"] / max(1, len(transcricao["segmentos"])), 2
    )
    update_project_script(
        project_id,
        projeto.get("script") or "",
        projeto.get("subtitle_mode") or "none",
        estilo,
    )

    # Limpa temporários; o SRT já está no storage.
    try:
        for nome in os.listdir(temp_dir):
            caminho = os.path.join(temp_dir, nome)
            if os.path.isfile(caminho):
                os.remove(caminho)
    except OSError:
        pass

    return {
        "status": "sucesso",
        "modelo": transcricao["modelo"],
        "idioma": transcricao["idioma"],
        "duracao_segundos": transcricao["duracao_segundos"],
        "segmentos": len(transcricao["segmentos"]),
        "linhas_srt": total_linhas,
        "blocos_alinhados": len(timings),
        "srt_key": srt_key,
        "srt_url": f"/api/storage/{srt_key}",
        "modo_legenda": projeto.get("subtitle_mode") or "none",
        "dica": (
            "Se o modo de legenda estiver como 'Nenhuma', mude para 'Queimar no Vídeo' "
            "antes de compilar para ver a legenda sincronizada."
        ),
    }
