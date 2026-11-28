import os
import sys
import uuid
import json
import shutil
from PIL import Image, ImageDraw

# Add backend directory to path
sys.path.append(os.path.dirname(__file__))

import database
from database import init_db, create_project, update_project_timeline, update_project_script, get_project
from compiler import compile_project_pipeline
from storage import upload_file, LOCAL_STORAGE_DIR

def create_mock_assets(project_id: str):
    print("Test: Creating mock assets...")
    # Create temp directory for generating test assets
    temp_test_dir = os.path.join(os.path.dirname(__file__), "temp_test_assets")
    os.makedirs(temp_test_dir, exist_ok=True)
    
    # 1. Create a mock dark image using Pillow
    img_path = os.path.join(temp_test_dir, "mock_image.png")
    image = Image.new("RGB", (800, 600), color=(10, 10, 10)) # Dark gray background
    draw = ImageDraw.Draw(image)
    draw.rectangle([10, 10, 790, 590], outline=(139, 0, 0), width=10) # Dark Red Border
    image.save(img_path)
    
    # Upload image asset to project storage path
    img_key = f"projects/{project_id}/uploads/mock_image.png"
    upload_file(img_path, img_key)
    print(f"Test: Uploaded mock image: {img_key}")
    
    # 2. Try to generate a mock audio WAV file (silent)
    # A tiny silent wav file can be written manually
    # Or we can just bypass audio if we test compilation without audio
    # Let's generate a tiny silent audio or let's compile without audio for simplicity.
    # To test audio mixing, let's create a tiny valid 1-second WAV file:
    audio_path = os.path.join(temp_test_dir, "mock_silent.wav")
    import wave
    with wave.open(audio_path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2) # 16-bit
        w.setframerate(44100)
        # Write 1 second of silence
        w.writeframes(b'\x00' * 88200)
        
    audio_key = f"projects/{project_id}/uploads/mock_audio.wav"
    upload_file(audio_path, audio_key)
    print(f"Test: Uploaded mock audio: {audio_key}")
    
    # Cleanup local temp assets folder
    try:
        shutil.rmtree(temp_test_dir)
    except Exception:
        pass
        
    return img_key, audio_key

def main():
    print("=== STARTING NATODARK COMPILER INTEGRATION TEST ===")
    
    # Initialize DB
    init_db()
    
    # Create test project
    project_id = f"test_{uuid.uuid4().hex[:8]}"
    print(f"Test: Creating test project with ID: {project_id}")
    create_project(project_id, "Projeto de Teste Dark", "shorts")
    
    # Create assets
    img_key, audio_key = create_mock_assets(project_id)
    
    # Set up timeline: two image clips (each 3 seconds)
    timeline = [
        {
            "id": "clip_1",
            "type": "image",
            "key": img_key,
            "duration": 3.0,
            "trim_start": 0.0,
            "trim_end": 0.0
        },
        {
            "id": "clip_2",
            "type": "image",
            "key": img_key,
            "duration": 4.0,
            "trim_start": 0.0,
            "trim_end": 0.0
        }
    ]
    update_project_timeline(project_id, timeline)
    
    # Save script and enable subtitle burning
    script = "Bem-vindo ao NatoDark.\nEsta e uma legenda de teste.\nO video dark foi gerado com sucesso!"
    subtitle_style = {
        "FontName": "Arial",
        "FontSize": 40,
        "PrimaryColour": "#FFFFFF",
        "OutlineColour": "#000000",
        "Outline": 2,
        "Alignment": 2, # Bottom Center
        "sec_per_block": 2.5 # 2.5 seconds per subtitle block
    }
    update_project_script(project_id, script, "burn", subtitle_style)
    
    # Add voice audio
    # Let's verify volume and fades
    from database import update_project_audio
    update_project_audio(project_id, audio_key, volume=1.2, fade_in=1.0, fade_out=1.0)
    
    # Run compiler pipeline (opcional: "ffmpeg" ou "hyperframes" como argv[1])
    engine_arg = sys.argv[1] if len(sys.argv) > 1 else None
    if engine_arg and engine_arg not in ("ffmpeg", "hyperframes"):
        print(f"Test Error: engine invalida: {engine_arg}")
        sys.exit(1)
    print(f"Test: Triggering compilation pipeline (engine={engine_arg or 'padrao'})...")
    try:
        output_key = compile_project_pipeline(project_id, engine=engine_arg)
        print(f"Test: COMPILATION SUCCESSFUL! Output key: {output_key}")
        
        # Verify output exists in storage
        expected_path = os.path.join(LOCAL_STORAGE_DIR, output_key.replace("/", os.sep))
        if os.path.exists(expected_path):
            print(f"Test: Verified file exists locally at {expected_path}")
            print(f"Test: Final file size: {os.path.getsize(expected_path)} bytes")
            print("=== INTEGRATION TEST PASSED SUCCESSFULLY ===")
            sys.exit(0)
        else:
            print(f"Test Error: Compiled file not found in local storage path: {expected_path}")
            sys.exit(1)
            
    except Exception as e:
        print(f"Test Error: Compilation pipeline failed: {e}")
        # Print compiler logs
        from compiler import get_compile_logs
        print("\n--- COMPILER LOGS ---")
        print(get_compile_logs(project_id))
        sys.exit(1)

if __name__ == "__main__":
    main()
