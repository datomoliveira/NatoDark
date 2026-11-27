# Ferramentas locais do NatoDark — viabilidade, licença e uso

Regra fixa: **render, download, áudio e ML pesado ficam no backend local**. A Cloudflare
só faz IA textual (roteiro). Nada aqui roda em Worker gratuito e nenhum peso/modelo/
chave é versionado.

Status em tempo real: `GET http://127.0.0.1:8000/api/tools`.

## Resumo executivo

| Ferramenta | Veredito | Licença | Custo | Hardware | Estado aqui |
|---|---|---|---|---|---|
| **FFmpeg** (imageio-ffmpeg) | ✅ essencial | LGPL/GPL no binário | grátis | CPU | **ativo** — corta, normaliza, mixa e gera o MP4 |
| **PySceneDetect** | ✅ viável e leve | BSD-3-Clause | grátis | CPU | **ativo** — ligado ao `/media/auto` (clipes do YouTube) |
| **YuNet** (OpenCV Zoo) | ✅ viável e leve | Apache-2.0/MIT | grátis | CPU | **ativo** — crop com rosto no terço superior |
| **HyperFrames** | ✅ renderizador preferido | Apache-2.0 | grátis (local, sem watermark) | CPU + Chrome + ffmpeg/ffprobe | **implementado**, opcional (`RENDER_ENGINE=hyperframes`) |
| **WhisperX** | ⚙️ opcional | BSD-2-Clause | grátis | CPU lenta / GPU recomendada | adaptador pronto, desligado (`NATODARK_USE_WHISPERX=1`) |
| **MediaPipe** | ⚙️ opcional | Apache-2.0 | grátis | CPU | adaptador de face mesh/pose, lazy |
| **BEN2** | ⚙️ opcional | MIT (modelo Base) | grátis | GPU recomendada (~363 MB) | adaptador de recorte de fundo, lazy |
| **Depth Anything V2 Small** | ⚙️ opcional | Apache-2.0 (**só o Small**) | grátis | CPU/GPU | adaptador de mapa de profundidade, lazy |
| **CLAP** (LAION) | ⚙️ opcional | CC0-1.0 | grátis | CPU/GPU, pesado | adaptador de score áudio↔texto, lazy |
| **SAM 2** | ⚙️ opcional | Apache-2.0 (+ cctorch BSD-3) | grátis | **CUDA/GPU obrigatório** | adaptador preguiçoso; instalar só com GPU |
| **Demucs** | ⛔ desligado | MIT no código, **pesos sem licença clara** | grátis | CPU lenta / GPU | bloqueado por default (`NATODARK_ENABLE_DEMUCS=1`) |
| **Remotion** | 🔸 apoio | MIT/Comercial* | grátis local | Node + Chrome | não é o engine; skills de apoio já instaladas |

\* Remotion é MIT para uso local; funcionalidades premium da empresa são pagas. Fica
como referência/skill porque o HyperFrames atende melhor o critério "HTML simples +
render local gratuito" deste projeto.

## Detalhes por ferramenta

### Já ativas no pipeline

**FFmpeg** — `imageio_ffmpeg.get_ffmpeg_exe()`. Não depende de `ffmpeg` no PATH.
Faz normalização 1080×1920/1080×1080/1920×1080, concat, fades, mix da narração e
queima de legendas. É o fallback garantido de todo render.

**PySceneDetect** — `scenedetect-headless` em `backend/requirements.txt` (BSD-3, CPU).
`backend/local_tools.py::detectar_cenas()` roda quando o auto-scout pega um clipe do
YouTube. O fim do trecho é ajustado para um limite de cena real, evitando cortes no
meio de uma fala. Sem a lib, o fluxo continua com o corte simples. Para desligar:
`{"usar_cenas": false}` no POST `/api/projects/{id}/media/auto`.

**YuNet** — modelo ONNX ~232 KB, baixado sob demanda para `backend/.cache/models`
(gitignored). Atenção: a URL `raw.githubusercontent.com` devolve ponteiro Git-LFS de
131 bytes; o código usa o Hugging Face, que serve o ONNX real.
`caixa_de_crop()` mantém o rosto no terço superior e ajusta 16:9 → 9:16 sem cortar a
cabeça. Se OpenCV/modelo falharem, o compiler volta para `scale+pad`.
Para desligar: `NATODARK_SMART_CROP=0`.

**HyperFrames** — `renderer/` com `hyperframes@0.9.102` fixado (Node >= 22).
`renderer/generate.mjs` transforma a timeline já normalizada em `index.html` com
`class="clip"` + `data-start`/`data-duration`. O render roda local:
`npx hyperframes render --output final.mp4`. Apache-2.0, uso comercial permitido,
sem conta e sem watermark no render local. O plano Pro (US$ 25/mês) e o render em nuvem
são **opcionais e não usados** — não entre com conta HeyGen neste fluxo.

Como ativar:

```bash
npm install --prefix renderer
# RENDER_ENGINE=hyperframes no backend/.env
```

Requisitos do render HyperFrames: Node >= 22, Chrome e `ffmpeg` + `ffprobe` no PATH.
O `imageio-ffmpeg` já traz só o `ffmpeg`; se não houver `ffprobe` no sistema, aponte
`NATODARK_HYPERFRAMES_BIN` para uma pasta com os dois binários. Se algo faltar, o
compiler registra o motivo no log e cai automaticamente para o concat do ffmpeg —
a publicação nunca fica travada por causa disso.

### Opcionais (lazy, não instalados por default)

Instale apenas se necessário e com folga de RAM/SSD:
`uv pip install --python backend/.venv/bin/python -r backend/requirements-ml.txt`.

- **WhisperX**: `faster-whisper` já entrega word timestamps; o WhisperX só vale a pena
  para alinhamento forçado/diarização. Ative com `NATODARK_USE_WHISPERX=1`.
- **MediaPipe**: face mesh/pose/selfie segmentation. Hoje expõe landmarks; útil para
  overlays e enquadramento futuro. CPU, Apache-2.0.
- **BEN2 Base**: matte de cabelo/fundo, MIT. As versões full não são open source —
  usar apenas o modelo Base. GPU recomendada.
- **Depth Anything V2 Small**: parallax/2.5D. **Base e Large são CC-BY-NC-4.0** e
  foram descartados: canal monetizado não pode usá-los. O código fixa o Small.
- **CLAP**: score semântico entre trecho de áudio e intenção do texto (CC0). Pesado
  (torch + librosa); útil para escolher trilha/SFX sem chave de API.
- **SAM 2**: segmentação com memória entre frames. Apache-2.0, mas exige CUDA e
  compilação da extensão — só vale se você tiver GPU.

### Descartado / bloqueado

- **Demucs**: o código é MIT, mas o próprio autor avisa que a licença dos pesos não
  é clara. Para vídeo monetizado isso é risco jurídico. Adaptador existe, porém só
  roda com `NATODARK_ENABLE_DEMUCS=1` e assume o risco por sua conta.
- **Pexels/Pixabay**: fora do ar; continuam no código mas saíram da fila padrão.
- **TTS/voz clonada**: fora. A voz é gravada pelo usuário; `faster-whisper` local
  sincroniza as legendas.
- **Render na Cloudflare**: impossível no plano gratuito (sem binários nativos, sem
  disco persistente, limites de CPU/tempo). Documentado em `docs/ESTUDIO.md`.

## Superfície de API

- `GET /api/tools` — catálogo com `licenca`, `custo`, `estado`, `instalado` e
  `efetivo`, além das flags e do caminho do cache de modelos.
- `POST /api/projects/{id}/media/auto` — aceita `usar_cenas` e devolve
  `cenas_detectadas` e as cenas encontradas em cada item da timeline.
- `POST /api/projects/{id}/compile` — usa `RENDER_ENGINE` e `NATODARK_SMART_CROP`;
  o log mostra quando YuNet/HyperFrames atuam e quando houve fallback.

## Validação feita nesta máquina

- PySceneDetect detectou `[0.0–3.0]` e `[3.0–6.0]` em vídeo sintético de 2 cenas.
- YuNet baixou 232.589 bytes do Hugging Face e detectou rosto em imagem de teste;
  o crop 9:16 manteve o rosto no quadro.
- HyperFrames: `check` passou e `render` gerou MP4 de 2,0s a partir de 2 clipes,
  sem conta e sem watermark (Chrome do sistema + ffmpeg/ffprobe locais). O teste
  de integração `backend/test_compile.py` também passou com
  `RENDER_ENGINE=hyperframes`, incluindo narração e legendas queimadas.
- `python -m py_compile` e import do FastAPI passaram após as integrações.
