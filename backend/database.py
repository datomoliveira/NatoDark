import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "natodark.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create projects table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        format TEXT NOT NULL,
        status TEXT NOT NULL,
        timeline TEXT,
        script TEXT,
        subtitle_mode TEXT,
        subtitle_style TEXT,
        audio_file TEXT,
        audio_volume REAL DEFAULT 1.0,
        audio_fade_in REAL DEFAULT 0.0,
        audio_fade_out REAL DEFAULT 0.0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)
    
    # Create reusable clips table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clips (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        file_url TEXT NOT NULL,
        storage_key TEXT NOT NULL,
        duration REAL NOT NULL,
        created_at TEXT NOT NULL
    )
    """)
    
    # Create batches table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS batches (
        id TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        projects TEXT,
        progress REAL DEFAULT 0.0,
        created_at TEXT NOT NULL
    )
    """)
    
    # Create cutter_jobs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cutter_jobs (
        id TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        error_message TEXT,
        source_url TEXT,
        duration REAL DEFAULT 0.0,
        file_url TEXT,
        created_at TEXT NOT NULL
    )
    """)
    
    conn.commit()
    conn.close()

# Helper functions for Project CRUD
def create_project(project_id: str, name: str, format: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    # Default values
    timeline = json.dumps([])
    subtitle_style = json.dumps({
        "FontName": "Arial",
        "FontSize": 48,
        "PrimaryColour": "&H00FFFFFF",  # white
        "OutlineColour": "&H00000000",  # black
        "Outline": 3,
        "Alignment": 2  # bottom center
    })
    
    cursor.execute("""
    INSERT INTO projects (
        id, name, format, status, timeline, script, subtitle_mode, subtitle_style, 
        audio_file, audio_volume, audio_fade_in, audio_fade_out, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        project_id, name, format, "rascunho", timeline, "", "none", subtitle_style,
        None, 1.0, 0.0, 0.0, now, now
    ))
    conn.commit()
    conn.close()

def get_project(project_id: str):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()
    if row:
        res = dict(row)
        res["timeline"] = json.loads(res["timeline"]) if res["timeline"] else []
        res["subtitle_style"] = json.loads(res["subtitle_style"]) if res["subtitle_style"] else {}
        return res
    return None

def list_projects():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
    conn.close()
    projects = []
    for row in rows:
        res = dict(row)
        res["timeline"] = json.loads(res["timeline"]) if res["timeline"] else []
        res["subtitle_style"] = json.loads(res["subtitle_style"]) if res["subtitle_style"] else {}
        projects.append(res)
    return projects

def update_project_status(project_id: str, status: str):
    conn = get_db_connection()
    now = datetime.utcnow().isoformat()
    conn.execute("UPDATE projects SET status = ?, updated_at = ? WHERE id = ?", (status, now, project_id))
    conn.commit()
    conn.close()

def update_project_timeline(project_id: str, timeline_data: list):
    conn = get_db_connection()
    now = datetime.utcnow().isoformat()
    conn.execute(
        "UPDATE projects SET timeline = ?, updated_at = ? WHERE id = ?",
        (json.dumps(timeline_data), now, project_id)
    )
    conn.commit()
    conn.close()

def update_project_script(project_id: str, script: str, subtitle_mode: str, subtitle_style: dict = None):
    conn = get_db_connection()
    now = datetime.utcnow().isoformat()
    if subtitle_style:
        conn.execute(
            "UPDATE projects SET script = ?, subtitle_mode = ?, subtitle_style = ?, updated_at = ? WHERE id = ?",
            (script, subtitle_mode, json.dumps(subtitle_style), now, project_id)
        )
    else:
        conn.execute(
            "UPDATE projects SET script = ?, subtitle_mode = ?, updated_at = ? WHERE id = ?",
            (script, subtitle_mode, now, project_id)
        )
    conn.commit()
    conn.close()

def update_project_audio(project_id: str, audio_file: str, volume: float = 1.0, fade_in: float = 0.0, fade_out: float = 0.0):
    conn = get_db_connection()
    now = datetime.utcnow().isoformat()
    conn.execute(
        """
        UPDATE projects 
        SET audio_file = ?, audio_volume = ?, audio_fade_in = ?, audio_fade_out = ?, updated_at = ? 
        WHERE id = ?
        """,
        (audio_file, volume, fade_in, fade_out, now, project_id)
    )
    conn.commit()
    conn.close()

def delete_project_row(project_id: str):
    conn = get_db_connection()
    conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    conn.close()

# Helper functions for Clip bank
def add_clip(clip_id: str, name: str, file_url: str, storage_key: str, duration: float):
    conn = get_db_connection()
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO clips (id, name, file_url, storage_key, duration, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (clip_id, name, file_url, storage_key, duration, now)
    )
    conn.commit()
    conn.close()

def get_clips():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM clips ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]

# Helper functions for Batches
def create_batch(batch_id: str, projects_list: list):
    conn = get_db_connection()
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO batches (id, status, projects, progress, created_at) VALUES (?, ?, ?, ?, ?)",
        (batch_id, "pending", json.dumps(projects_list), 0.0, now)
    )
    conn.commit()
    conn.close()

def get_batch(batch_id: str):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()
    conn.close()
    if row:
        res = dict(row)
        res["projects"] = json.loads(res["projects"]) if res["projects"] else []
        return res
    return None

def update_batch_progress(batch_id: str, status: str, progress: float):
    conn = get_db_connection()
    conn.execute("UPDATE batches SET status = ?, progress = ? WHERE id = ?", (status, progress, batch_id))
    conn.commit()
    conn.close()

# Helper functions for Cutter Jobs
def create_cutter_job(job_id: str, status: str, source_url: str = None):
    conn = get_db_connection()
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO cutter_jobs (id, status, source_url, created_at) VALUES (?, ?, ?, ?)",
        (job_id, status, source_url, now)
    )
    conn.commit()
    conn.close()

def get_cutter_job(job_id: str):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM cutter_jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def update_cutter_job(job_id: str, status: str, file_url: str = None, duration: float = 0.0, error_message: str = None):
    conn = get_db_connection()
    conn.execute(
        "UPDATE cutter_jobs SET status = ?, file_url = ?, duration = ?, error_message = ? WHERE id = ?",
        (status, file_url, duration, error_message, job_id)
    )
    conn.commit()
    conn.close()
