from google.cloud import storage
from werkzeug.utils import secure_filename
import io
import tempfile
import os
from PIL import Image

def get_storage_client(credentials_path):
    """Initializes and returns a Google Cloud Storage client."""
    return storage.Client.from_service_account_json(credentials_path)

def list_files_in_bucket(bucket_name, credentials_path):
    """Lists all files in a GCS bucket."""
    try:
        storage_client = get_storage_client(credentials_path)
        bucket = storage_client.bucket(bucket_name)
        # Exclude folders
        blobs = [blob for blob in bucket.list_blobs() if not blob.name.endswith('/')]
        return blobs
    except Exception as e:
        print(f"Error listing files from GCS: {e}")
        return None

def upload_file_to_gcs(file_obj, bucket_name, credentials_path):
    """Uploads a file object to GCS."""
    try:
        storage_client = get_storage_client(credentials_path)
        bucket = storage_client.bucket(bucket_name)
        filename = secure_filename(file_obj.filename)
        blob = bucket.blob(filename)
        blob.upload_from_file(file_obj)
        return True, None
    except Exception as e:
        print(f"Error uploading file to GCS: {e}")
        return False, str(e)

def delete_file_from_gcs(file_name, bucket_name, credentials_path):
    """Deletes a file from GCS."""
    try:
        storage_client = get_storage_client(credentials_path)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        blob.delete()
        return True, None
    except Exception as e:
        print(f"Error deleting file from GCS: {e}")
        return False, str(e)

def download_image_as_bytes(blob_path, bucket_name, credentials_path):
    """Downloads an image from GCS as bytes and converts it to PIL Image object."""
    storage_client = get_storage_client(credentials_path)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    
    # Check if the blob exists
    if not blob.exists():
        raise FileNotFoundError(f"Image not found at {blob_path}")

    image_bytes = blob.download_as_bytes()
    img = Image.open(io.BytesIO(image_bytes))

    if img.mode == 'RGBA':
        rgb_img = Image.new("RGB", img.size, (255, 255, 255))
        rgb_img.paste(img, mask=img.split()[3])
        return rgb_img
    elif img.mode != 'RGB':
        return img.convert('RGB')
    
    return img
