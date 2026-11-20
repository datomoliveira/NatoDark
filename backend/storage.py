import os
import shutil
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

# Read B2 credentials from environment variables
B2_ENDPOINT = os.environ.get("B2_ENDPOINT")
B2_KEY_ID = os.environ.get("B2_KEY_ID")
B2_APPLICATION_KEY = os.environ.get("B2_APPLICATION_KEY")
B2_BUCKET_NAME = os.environ.get("B2_BUCKET_NAME")

# Local storage path for fallback
LOCAL_STORAGE_DIR = os.path.join(os.path.dirname(__file__), "storage")
os.makedirs(LOCAL_STORAGE_DIR, exist_ok=True)

# Determine if we should use B2 or Local Storage
IS_B2_CONFIGURED = all([B2_ENDPOINT, B2_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET_NAME])

# S3 Client initialization if B2 is configured
s3_client = None
if IS_B2_CONFIGURED:
    try:
        s3_client = boto3.client(
            "s3",
            endpoint_url=B2_ENDPOINT,
            aws_access_key_id=B2_KEY_ID,
            aws_secret_access_key=B2_APPLICATION_KEY,
            config=Config(signature_version="s3v4")
        )
        print("Storage: Backblaze B2 S3-compatible storage client initialized successfully.")
    except Exception as e:
        print(f"Storage Error initializing B2 client: {e}. Falling back to Local Storage.")
        IS_B2_CONFIGURED = False
else:
    print("Storage: Backblaze B2 credentials not fully configured. Using Local Storage Fallback.")


def upload_file(local_path: str, target_key: str) -> str:
    """
    Uploads a file to the configured storage (B2 or Local).
    Returns the URL/key identifier for the uploaded file.
    """
    # Clean target_key to use forward slashes
    target_key = target_key.replace("\\", "/")
    
    if IS_B2_CONFIGURED and s3_client:
        try:
            s3_client.upload_file(local_path, B2_BUCKET_NAME, target_key)
            # URL will be generated or presigned later.
            return target_key
        except ClientError as e:
            print(f"B2 upload error: {e}")
            raise e
    else:
        # Local fallback
        dest_path = os.path.join(LOCAL_STORAGE_DIR, target_key.replace("/", os.sep))
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy2(local_path, dest_path)
        return target_key


def download_file(target_key: str, local_dest_path: str):
    """
    Downloads a file from storage to a local path.
    """
    target_key = target_key.replace("\\", "/")
    os.makedirs(os.path.dirname(local_dest_path), exist_ok=True)
    
    if IS_B2_CONFIGURED and s3_client:
        try:
            s3_client.download_file(B2_BUCKET_NAME, target_key, local_dest_path)
        except ClientError as e:
            print(f"B2 download error: {e}")
            raise e
    else:
        # Local fallback
        src_path = os.path.join(LOCAL_STORAGE_DIR, target_key.replace("/", os.sep))
        if not os.path.exists(src_path):
            raise FileNotFoundError(f"Local storage file not found: {src_path}")
        shutil.copy2(src_path, local_dest_path)


def delete_file(target_key: str):
    """
    Deletes a specific file from storage.
    """
    target_key = target_key.replace("\\", "/")
    
    if IS_B2_CONFIGURED and s3_client:
        try:
            s3_client.delete_object(Bucket=B2_BUCKET_NAME, Key=target_key)
        except ClientError as e:
            print(f"B2 delete error: {e}")
    else:
        # Local fallback
        src_path = os.path.join(LOCAL_STORAGE_DIR, target_key.replace("/", os.sep))
        if os.path.exists(src_path):
            os.remove(src_path)


def delete_project_files(project_id: str):
    """
    Deletes all files (uploads/output) belonging to a specific project.
    Path structure: projects/{project_id}/...
    """
    prefix = f"projects/{project_id}/"
    
    if IS_B2_CONFIGURED and s3_client:
        try:
            # List all objects with prefix
            paginator = s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=B2_BUCKET_NAME, Prefix=prefix)
            
            delete_keys = []
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        delete_keys.append({'Key': obj['Key']})
            
            # Delete in batches of 1000
            if delete_keys:
                for i in range(0, len(delete_keys), 1000):
                    s3_client.delete_objects(
                        Bucket=B2_BUCKET_NAME,
                        Delete={'Objects': delete_keys[i:i+1000]}
                    )
                print(f"Storage: Deleted {len(delete_keys)} objects for project {project_id} from B2.")
        except ClientError as e:
            print(f"B2 project cleanup error: {e}")
    else:
        # Local fallback
        project_dir = os.path.join(LOCAL_STORAGE_DIR, "projects", project_id)
        if os.path.exists(project_dir):
            shutil.rmtree(project_dir)
            print(f"Storage: Deleted local storage files for project {project_id}.")


def generate_download_url(target_key: str, expires_in: int = 3600) -> str:
    """
    Generates a presigned URL (if B2) or a local static file serving endpoint URL.
    """
    target_key = target_key.replace("\\", "/")
    
    if IS_B2_CONFIGURED and s3_client:
        try:
            url = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": B2_BUCKET_NAME, "Key": target_key},
                ExpiresIn=expires_in
            )
            return url
        except Exception as e:
            print(f"Error generating presigned URL: {e}")
            # Fallback to simple unpresigned path if error
            return f"{B2_ENDPOINT}/{B2_BUCKET_NAME}/{target_key}"
    else:
        # Local fallback. The endpoint will be served via FastAPI under /api/storage/
        # Return a relative URL. The frontend will query it from the backend server.
        return f"/api/storage/{target_key}"
