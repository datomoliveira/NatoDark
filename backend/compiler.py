import os
import re
import subprocess
import json
import shutil
from datetime import datetime
from typing import List
import imageio_ffmpeg
from database import (
    get_project, update_project_status, 
    update_cutter_job, add_clip
)
from storage import upload_file, download_file, generate_download_url

# Helper to write compilation logs
def log_compile(project_id: str, message: str):
    log_dir = os.path.join(os.path.dirname(__file__), "temp", project_id)
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "compile.log")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {message}\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(formatted)
    print(f"[Project {project_id}] {message}")

def get_compile_logs(project_id: str) -> str:
    log_path = os.path.join(os.path.dirname(__file__), "temp", project_id, "compile.log")
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            return f.read()
    return "Nenhum log disponível."

# Get media duration by running FFmpeg and parsing the output
def get_media_duration(file_path: str) -> float:
    try:
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        result = subprocess.run(
            [ffmpeg_exe, "-i", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )
        output = result.stderr
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", output)
        if not match:
            match = re.search(r"Duration:\s*(\d+):(\d+):(\d+)", output)
        
        if match:
            hours = int(match.group(1))
            minutes = int(match.group(2))
            seconds = float(match.group(3))
            return hours * 3600 + minutes * 60 + seconds
    except Exception as e:
        print(f"Error getting media duration for {file_path}: {e}")
    return 0.0

# Helper to convert HEX colors (#RRGGBB) to ASS colors (&H00BBGGRR)
def hex_to_ass_color(hex_color: str) -> str:
    if not hex_color:
        return "&H00FFFFFF"
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r = hex_color[0:2]
        g = hex_color[2:4]
        b = hex_color[4:6]
        return f"&H00{b.upper()}{g.upper()}{r.upper()}"
    return "&H00FFFFFF"

# Generates SRT file from script text
def generate_srt(script_text: str, seconds_per_block: float, dest_path: str) -> bool:
    if not script_text.strip():
        return False
        
    # Split the script into lines
    lines = [line.strip() for line in script_text.split("\n") if line.strip()]
    if not lines:
        return False
        
    def format_srt_time(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int(round((seconds - int(seconds)) * 1000))
        if millis >= 1000:
            millis = 999
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
        
    with open(dest_path, "w", encoding="utf-8") as f:
        for idx, line in enumerate(lines):
            start = idx * seconds_per_block
            end = start + seconds_per_block
            
            f.write(f"{idx + 1}\n")
            f.write(f"{format_srt_time(start)} --> {format_srt_time(end)}\n")
            f.write(f"{line}\n\n")
            
    return True

def _filtro_padrao(width: int, height: int) -> str:
    """Enquadramento atual: reduz e faz letterbox, sem perder nada da imagem."""
    return (
        f"scale=w={width}:h={height}:force_original_aspect_ratio=decrease,"
        f"pad=w={width}:h={height}:x=(ow-iw)/2:y=(oh-ih)/2:color=black,setsar=1"
    )


def _filtro_enquadramento(
    caminho: str,
    width: int,
    height: int,
    *,
    eh_video: bool,
    trim_start: float,
    duracao: float,
    ffmpeg_exe: str,
    workdir: str,
    project_id: str,
) -> str:
    """
    Crop que mantem o rosto no terco superior (YuNet, CPU).
    Se OpenCV/modelo/PIL falharem, volta para o scale+pad original.
    """
    padrao = _filtro_padrao(width, height)
    if os.environ.get("NATODARK_SMART_CROP", "1").strip().lower() in ("0", "false", "no"):
        return padrao
    try:
        from PIL import Image
        from local_tools import caixa_de_crop

        quadro = caminho
        if eh_video:
            quadro = os.path.join(workdir, "crop_frame.png")
            meio = max(0.0, trim_start + max(0.0, duracao) / 2)
            res = subprocess.run(
                [
                    ffmpeg_exe, "-y", "-loglevel", "error",
                    "-ss", f"{meio:.2f}", "-i", caminho,
                    "-frames:v", "1", quadro,
                ],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            if res.returncode != 0 or not os.path.isfile(quadro):
                raise RuntimeError("nao foi possivel extrair quadro para o crop")

        with Image.open(quadro) as imagem:
            largura, altura = imagem.size
        x0, y0, x1, y1 = caixa_de_crop(quadro, largura, altura, width / height)
        crop_w, crop_h = x1 - x0, y1 - y0
        if crop_w < 2 or crop_h < 2:
            raise RuntimeError("crop invalido")
        log_compile(
            project_id,
            f"YuNet: crop inteligente {crop_w}x{crop_h} (origem {largura}x{altura})",
        )
        return f"crop=w={crop_w}:h={crop_h}:x={x0}:y={y0},scale=w={width}:h={height},setsar=1"
    except Exception as err:
        log_compile(project_id, f"Crop inteligente indisponivel; usando scale+pad: {err}")
        return padrao


def _renderizar_hyperframes(
    project_id: str,
    itens: List[dict],
    temp_dir: str,
    destino: str,
    width: int,
    height: int,
) -> bool:
    """
    Render local com HyperFrames (Apache-2.0, sem watermark, sem conta).
    Retorna False para o chamador usar o concat ffmpeg padrao.
    """
    try:
        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        gerador = os.path.join(raiz, "renderer", "generate.mjs")
        cli = os.path.join(raiz, "renderer", "node_modules", ".bin", "hyperframes")
        if not (os.path.isfile(gerador) and os.path.isfile(cli)):
            log_compile(project_id, "HyperFrames nao instalado (npm install --prefix renderer).")
            return False
        if not shutil.which("node"):
            log_compile(project_id, "Node.js ausente; HyperFrames ignorado.")
            return False

        projeto_hf = os.path.join(temp_dir, "hyperframes")
        os.makedirs(projeto_hf, exist_ok=True)
        spec_path = os.path.join(projeto_hf, "spec.json")
        with open(spec_path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "width": width,
                    "height": height,
                    "fps": 30,
                    "items": [
                        {
                            "path": item["path"],
                            "type": item.get("type", "video"),
                            "duration": item.get("duration", 5.0),
                        }
                        for item in itens
                    ],
                },
                fh,
            )

        res = subprocess.run(
            ["node", gerador, spec_path, projeto_hf],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        if res.returncode != 0:
            log_compile(project_id, f"HyperFrames: falha ao gerar composicao: {res.stderr}")
            return False

        env = os.environ.copy()
        env.update({
            "HYPERFRAMES_NO_UPDATE_CHECK": "1",
            "HYPERFRAMES_SKIP_SKILLS": "1",
            "HYPERFRAMES_NO_TELEMETRY": "1",
        })
        if not env.get("HYPERFRAMES_BROWSER_PATH"):
            for navegador in ("google-chrome", "chromium", "chromium-browser"):
                encontrado = shutil.which(navegador)
                if encontrado:
                    env["HYPERFRAMES_BROWSER_PATH"] = encontrado
                    break
        # HyperFrames precisa de ffmpeg e ffprobe no PATH. O imageio-ffmpeg so
        # traz o ffmpeg; NATODARK_HYPERFRAMES_BIN pode apontar para um dir com os dois.
        bin_dir = os.environ.get("NATODARK_HYPERFRAMES_BIN", "").strip()
        if bin_dir:
            env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
        elif not shutil.which("ffprobe"):
            env["PATH"] = os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe()) + os.pathsep + env.get("PATH", "")

        cmd = [
            cli, "render", projeto_hf, "--output", destino,
            "--quality", env.get("HYPERFRAMES_QUALITY", "draft"),
        ]
        log_compile(project_id, "Renderizando com HyperFrames (local, gratuito)...")
        res = subprocess.run(cmd, cwd=projeto_hf, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0 or not os.path.isfile(destino):
            log_compile(project_id, f"HyperFrames falhou; usando ffmpeg: {res.stderr[-1200:]}")
            return False
        if get_media_duration(destino) <= 0:
            log_compile(project_id, "HyperFrames gerou arquivo sem duracao; usando ffmpeg.")
            return False
        log_compile(project_id, "HyperFrames concluiu o render da timeline.")
        return True
    except Exception as err:
        log_compile(project_id, f"HyperFrames indisponivel; usando ffmpeg: {err}")
        return False


# Compile single project process
def compile_project_pipeline(project_id: str) -> str:
    """
    Executes the compile sequence for a project.
    Returns the storage key of the compiled video or raises an exception.
    """
    log_compile(project_id, "Iniciando compilação do projeto.")
    update_project_status(project_id, "compilando")
    
    project = get_project(project_id)
    if not project:
        raise ValueError(f"Project {project_id} not found in database.")
    
    # Create isolated temp folder for compilation
    temp_dir = os.path.join(os.path.dirname(__file__), "temp", project_id)
    os.makedirs(temp_dir, exist_ok=True)
    
    inputs_dir = os.path.join(temp_dir, "inputs")
    normalized_dir = os.path.join(temp_dir, "normalized")
    os.makedirs(inputs_dir, exist_ok=True)
    os.makedirs(normalized_dir, exist_ok=True)
    
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    
    try:
        timeline = project["timeline"]
        if not timeline:
            raise ValueError("A timeline está vazia. Adicione clipes ou imagens para compilar.")
            
        # Get aspect ratio dimensions
        fmt = project["format"].lower()
        if fmt == "shorts":
            width, height = 1080, 1920
        elif fmt == "square":
            width, height = 1080, 1080
        else: # standard / 16:9
            width, height = 1920, 1080
            
        log_compile(project_id, f"Resolução de saída selecionada: {width}x{height} (Formato: {fmt})")
        
        # 1. Download and normalize timeline clips
        normalized_paths = []
        normalized_itens: List[dict] = []
        for idx, item in enumerate(timeline):
            item_id = item.get("id", f"clip_{idx}")
            item_type = item.get("type", "video") # 'video' or 'image'
            storage_key = item.get("key")
            duration = float(item.get("duration", 5.0))
            trim_start = float(item.get("trim_start", 0.0))
            trim_end = float(item.get("trim_end", 0.0))
            
            # Local input path
            local_ext = os.path.splitext(storage_key)[1] if storage_key else ".mp4"
            if item_type == "image" and not local_ext:
                local_ext = ".png"
            local_in_path = os.path.join(inputs_dir, f"{item_id}{local_ext}")
            
            # Download file from storage
            log_compile(project_id, f"Baixando mídia {idx+1}/{len(timeline)}: {storage_key}")
            download_file(storage_key, local_in_path)
            
            # Normalize path
            local_norm_path = os.path.join(normalized_dir, f"norm_{idx}.mp4")
            
            if item_type == "image":
                log_compile(project_id, f"Convertendo imagem estática em vídeo (Duração: {duration}s)")
                vf_filter = _filtro_enquadramento(
                    local_in_path, width, height,
                    eh_video=False, trim_start=0.0, duracao=duration,
                    ffmpeg_exe=ffmpeg_exe, workdir=inputs_dir, project_id=project_id,
                )
                cmd = [
                    ffmpeg_exe, "-y",
                    "-loop", "1",
                    "-framerate", "30",
                    "-i", local_in_path,
                    "-t", str(duration),
                    "-vf", vf_filter,
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    local_norm_path
                ]
            else:
                log_compile(project_id, f"Normalizando clipe de vídeo {idx+1} (Trim Start: {trim_start}s, Trim End: {trim_end}s)")
                # Normalize video clip (trim, remove audio, adjust format)
                vf_filter = _filtro_enquadramento(
                    local_in_path, width, height,
                    eh_video=True, trim_start=trim_start,
                    duracao=(trim_end - trim_start) if trim_end > trim_start else duration,
                    ffmpeg_exe=ffmpeg_exe, workdir=inputs_dir, project_id=project_id,
                )

                cmd = [ffmpeg_exe, "-y"]
                if trim_start > 0:
                    cmd.extend(["-ss", f"{trim_start:.2f}"])
                if trim_end > trim_start:
                    clip_dur = trim_end - trim_start
                    cmd.extend(["-t", f"{clip_dur:.2f}"])
                    
                cmd.extend([
                    "-i", local_in_path,
                    "-vf", vf_filter,
                    "-r", "30",
                    "-an", # Strip audio from source clip
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    local_norm_path
                ])
                
            # Execute normalization
            log_compile(project_id, f"Executando normalização do clipe {idx+1}...")
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode != 0:
                log_compile(project_id, f"Erro na normalização do clipe {idx+1}: {res.stderr}")
                raise RuntimeError(f"Falha ao normalizar clipe {idx+1}")
                
            normalized_paths.append(local_norm_path)
            duracao_normalizada = (
                (trim_end - trim_start)
                if item_type == "video" and trim_end > trim_start
                else duration
            )
            # Todos os normalizados sao MP4 sem audio — o HyperFrames so os sequencia.
            normalized_itens.append({
                "path": local_norm_path,
                "type": "video",
                "duration": max(0.04, duracao_normalizada),
            })

        # 2. Concatenate normalized clips (HyperFrames e o engine preferido;
        #    cai para o concat demuxer do ffmpeg se ele nao estiver disponivel).
        concat_video_path = os.path.join(temp_dir, "concatenated.mp4")
        usou_hyperframes = False
        if os.environ.get("RENDER_ENGINE", "ffmpeg").strip().lower() == "hyperframes":
            usou_hyperframes = _renderizar_hyperframes(
                project_id, normalized_itens, temp_dir, concat_video_path, width, height
            )

        if not usou_hyperframes:
            log_compile(project_id, "Concatenando clipes da timeline com ffmpeg...")
            list_file_path = os.path.join(temp_dir, "list.txt")
            with open(list_file_path, "w", encoding="utf-8") as lf:
                for path in normalized_paths:
                    # Use relative paths for safety with spaces
                    lf.write(f"file 'normalized/{os.path.basename(path)}'\n")

            cmd = [
                ffmpeg_exe, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", "list.txt",
                "-c", "copy",
                "concatenated.mp4"
            ]
            res = subprocess.run(cmd, cwd=temp_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode != 0:
                log_compile(project_id, f"Erro de concatenação: {res.stderr}")
                raise RuntimeError("Falha ao concatenar clipes.")
            
        video_dur = get_media_duration(concat_video_path)
        log_compile(project_id, f"Concatenação finalizada. Duração do vídeo: {video_dur:.2f}s")
        
        # 3. Process voice audio
        final_video_path = concat_video_path
        voice_key = project.get("audio_file")
        
        if voice_key:
            log_compile(project_id, f"Processando áudio de voz: {voice_key}")
            local_audio_ext = os.path.splitext(voice_key)[1] if voice_key else ".mp3"
            local_audio_in = os.path.join(temp_dir, f"voice_input{local_audio_ext}")
            download_file(voice_key, local_audio_in)
            
            audio_dur = get_media_duration(local_audio_in)
            effective_dur = min(video_dur, audio_dur)
            
            # Apply volume and fade-in/fade-out
            volume = float(project.get("audio_volume", 1.0))
            fade_in = float(project.get("audio_fade_in", 0.0))
            fade_out = float(project.get("audio_fade_out", 0.0))
            
            audio_filters = []
            if volume != 1.0:
                audio_filters.append(f"volume={volume}")
            if fade_in > 0:
                audio_filters.append(f"afade=t=in:ss=0:d={fade_in}")
            if fade_out > 0 and (effective_dur - fade_out) > 0:
                audio_filters.append(f"afade=t=out:st={effective_dur - fade_out:.2f}:d={fade_out}")
                
            processed_audio_path = os.path.join(temp_dir, "processed_audio.wav")
            
            cmd = [ffmpeg_exe, "-y", "-i", local_audio_in]
            if audio_filters:
                cmd.extend(["-filter_complex", ",".join(audio_filters)])
            cmd.append(processed_audio_path)
            
            log_compile(project_id, "Aplicando filtros de áudio (volume, fade)...")
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode != 0:
                log_compile(project_id, f"Erro ao processar áudio: {res.stderr}")
                raise RuntimeError("Falha ao processar áudio de voz.")
                
            # Mix Video track and audio track
            log_compile(project_id, "Muxando áudio processado com a trilha de vídeo...")
            combined_video_path = os.path.join(temp_dir, "combined.mp4")
            
            cmd = [
                ffmpeg_exe, "-y",
                "-i", "concatenated.mp4",
                "-i", "processed_audio.wav",
                "-map", "0:v",
                "-map", "1:a",
                "-c:v", "copy",
                "-c:a", "aac",
                "-shortest",
                "combined.mp4"
            ]
            res = subprocess.run(cmd, cwd=temp_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode != 0:
                log_compile(project_id, f"Erro ao muxar vídeo e áudio: {res.stderr}")
                raise RuntimeError("Falha ao combinar trilhas de vídeo e áudio.")
                
            final_video_path = combined_video_path
            
        # 4. Burn subtitles if enabled
        sub_mode = project.get("subtitle_mode", "none")
        script = project.get("script", "")
        
        if sub_mode == "burn" and script.strip():
            log_compile(project_id, "Configurando e gravando legendas no vídeo...")
            
            # Extract styles
            styles = project.get("subtitle_style", {})
            font = styles.get("FontName", "Arial")
            size = styles.get("FontSize", 48)
            primary_color = hex_to_ass_color(styles.get("PrimaryColour", "#FFFFFF"))
            outline_color = hex_to_ass_color(styles.get("OutlineColour", "#000000"))
            outline_thickness = styles.get("Outline", 3)
            alignment = styles.get("Alignment", 2)
            
            # Settings for time per block
            # For subtitles, let's look up project seconds per block or default to 3s
            seconds_per_block = 3.0
            if "sec_per_block" in styles:
                seconds_per_block = float(styles["sec_per_block"])
                
            # SRT: prefere o gerado pela voz do usuario (timestamps reais).
            # Se nao houver, cai para a estimativa por sec_per_block.
            srt_path = os.path.join(temp_dir, "subtitles.srt")
            srt_pronto = False
            srt_key_voz = (styles or {}).get("srt_key")
            if srt_key_voz:
                try:
                    download_file(srt_key_voz, srt_path)
                    srt_pronto = os.path.getsize(srt_path) > 0
                    log_compile(project_id, f"Legenda sincronizada pela voz aplicada: {srt_key_voz}")
                except Exception as exc:
                    log_compile(project_id, f"Falha ao carregar legenda da voz ({exc}); usando estimativa.")
            if not srt_pronto:
                srt_pronto = generate_srt(script, seconds_per_block, srt_path)
            if srt_pronto:
                subtitled_video_path = os.path.join(temp_dir, "subtitled.mp4")
                
                # Command to burn subtitle
                # Note: Run in temp_dir context, so file path is relative "subtitles.srt"
                # This prevents escaping errors on Windows!
                vf_subtitle = f"subtitles=subtitles.srt:force_style='FontName={font},Bold=1,FontSize={size},PrimaryColour={primary_color},OutlineColour={outline_color},Outline={outline_thickness},Alignment={alignment}'"
                
                cmd = [
                    ffmpeg_exe, "-y",
                    "-i", os.path.basename(final_video_path),
                    "-vf", vf_subtitle,
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "copy",
                    "subtitled.mp4"
                ]
                log_compile(project_id, "Executando renderização de legendas (re-encodando vídeo)...")
                res = subprocess.run(cmd, cwd=temp_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if res.returncode != 0:
                    log_compile(project_id, f"Erro ao queimar legendas: {res.stderr}")
                    raise RuntimeError("Falha ao queimar legendas.")
                    
                final_video_path = subtitled_video_path
            else:
                log_compile(project_id, "Script sem conteúdo. Ignorando renderização de legenda.")
                
        # 5. Upload final output to storage
        log_compile(project_id, "Compilação concluída! Enviando vídeo para o Storage...")
        output_key = f"projects/{project_id}/output/final.mp4"
        upload_file(final_video_path, output_key)
        
        # 6. Clean up temporary files
        log_compile(project_id, "Limpando arquivos temporários locais...")
        try:
            # Delete inputs and intermediate paths
            shutil.rmtree(inputs_dir)
            shutil.rmtree(normalized_dir)
            # Keep compile.log for status polling, but delete intermediate mp4s
            for file in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, file)
                if os.path.isfile(file_path) and file != "compile.log":
                    os.remove(file_path)
        except Exception as cleanup_err:
            print(f"Non-fatal error cleaning temp files: {cleanup_err}")
            
        log_compile(project_id, "Processo concluído com sucesso!")
        update_project_status(project_id, "pronto")
        return output_key
        
    except Exception as err:
        log_compile(project_id, f"ERRO NA COMPILAÇÃO: {str(err)}")
        update_project_status(project_id, "rascunho") # Return to draft on error
        raise err

# Cutter logic
def process_cutter_job(job_id: str, input_path: str, start_time: float, duration: float, add_to_bank: bool = False, clip_name: str = None) -> str:
    """
    Cuts video and uploads to storage. Returns the download URL.
    """
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    temp_dir = os.path.join(os.path.dirname(__file__), "temp", "cutter")
    os.makedirs(temp_dir, exist_ok=True)
    
    output_filename = f"cut_{job_id}.mp4"
    output_path = os.path.join(temp_dir, output_filename)
    
    try:
        # Command to cut video
        cmd = [
            ffmpeg_exe, "-y",
            "-ss", f"{start_time:.2f}",
            "-i", input_path,
            "-t", f"{duration:.2f}",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            output_path
        ]
        
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg cutter error: {res.stderr}")
            
        # Upload cut video to storage
        storage_key = f"cutter/{job_id}/output.mp4"
        upload_file(output_path, storage_key)
        
        # Presigned URL
        file_url = generate_download_url(storage_key)
        
        # If adding to clips bank
        if add_to_bank:
            clip_id = f"clip_{job_id}"
            bank_name = clip_name or f"Corte {job_id[:8]}"
            bank_key = f"clips/{clip_id}.mp4"
            # Upload clip to bank key
            upload_file(output_path, bank_key)
            bank_url = generate_download_url(bank_key)
            add_clip(clip_id, bank_name, bank_url, bank_key, duration)
            
        update_cutter_job(job_id, "completed", file_url=file_url, duration=duration)
        
        # Cleanup local file
        if os.path.exists(output_path):
            os.remove(output_path)
            
        return file_url
        
    except Exception as e:
        error_msg = str(e)
        update_cutter_job(job_id, "failed", error_message=error_msg)
        if os.path.exists(output_path):
            os.remove(output_path)
        raise e
