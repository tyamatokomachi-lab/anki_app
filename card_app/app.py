# app.py
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, request, jsonify, render_template, Response, url_for, send_file
from werkzeug.utils import secure_filename
import json
import uuid
import os
import re
from google.cloud import storage
import subprocess
import glob
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from spreadsheet_manager import get_spreadsheet_data
from pdf_generator import generate_front_and_back_pdfs
from preview_image_generator import generate_pdf_preview_images
from zipfile import ZipFile, ZIP_DEFLATED
import io
import requests
import tempfile

# Flaskアプリケーションのインスタンスを生成
app = Flask(__name__)

# GCSバケット名
BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME', 'your-gcs-bucket-name')
# スプレッドシートID
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID', 'your-spreadsheet-id')

# GCSクライアント
storage_client = storage.Client()

# 一時ディレクトリのセットアップ
if not os.path.exists('temp'):
    os.makedirs('temp')

# Check and install required packages
try:
    # pdf2imageの代わりにPillowをインストール
    subprocess.check_call(['pip', 'install', 'Pillow'])
    print("Successfully installed Pillow.")
except subprocess.CalledProcessError as e:
    print(f"Error installing packages: {e}")

@app.route('/')
def index():
    """Renders the main page."""
    try:
        gc = get_gspread_client('credentials.json')
        workbook = gc.open_by_key(SPREADSHEET_ID)
        sheet_names = [sheet.title for sheet in workbook.worksheets()]
    except Exception as e:
        print(f"Error fetching sheet names: {e}")
        sheet_names = []
    
    cols = 2
    rows = 3
    
    return render_template('index.html', sheet_names=sheet_names, cols=cols, rows=rows)

@app.route('/preview_pdf_images')
def preview_pdf_images():
    """Generates and returns base64 encoded PDF preview images."""
    sheet_name = request.args.get('sheet_name')
    cols = int(request.args.get('cols', 2))
    rows = int(request.args.get('rows', 3))
    
    try:
        records = get_spreadsheet_data(SPREADSHEET_ID, sheet_name, 'credentials.json')
        if not records:
            return jsonify({'status': 'error', 'message': 'スプレッドシートからデータを取得できませんでした。'})

        images_dir = os.path.join('temp', str(uuid.uuid4()))
        if not os.path.exists(images_dir):
            os.makedirs(images_dir)
        
        # GCS上の画像URLを取得
        image_filenames = [record['image_filename'] for record in records if 'image_filename' in record and record['image_filename']]
        # GCSから画像をダウンロード
        with ThreadPoolExecutor(max_workers=5) as executor:
            download_futures = {executor.submit(download_image_from_gcs, filename, images_dir): filename for filename in image_filenames}
            for future in as_completed(download_futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"Error downloading image from GCS: {e}")

        # 新しい関数を呼び出す
        front_images, back_images = generate_pdf_preview_images(records, cols, rows, images_dir)
        
        # Clean up temporary directory
        for f in glob.glob(os.path.join(images_dir, '*')):
            os.remove(f)
        os.rmdir(images_dir)
        
        return jsonify({
            'status': 'success',
            'front_images': front_images,
            'back_images': back_images
        })
        
    except Exception as e:
        print(f"Error generating preview images: {e}")
        return jsonify({'status': 'error', 'message': f'プレビュー生成中にエラーが発生しました。: {e}'})

@app.route('/download_pdfs')
def download_pdfs():
    """Streams PDF generation progress and serves the download link."""
    sheet_name = request.args.get('sheet_name')
    cols = int(request.args.get('cols', 2))
    rows = int(request.args.get('rows', 3))

    def event_stream():
        unique_id = str(uuid.uuid4())
        download_dir = os.path.join('temp', unique_id)
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)

        yield f"data:スプレッドシートデータを取得中...\n\n"
        records = get_spreadsheet_data(SPREADSHEET_ID, sheet_name, 'credentials.json')
        if not records:
            yield "data:Error: スプレッドシートからデータを取得できませんでした。\n\n"
            return
        
        image_filenames = [record['image_filename'] for record in records if 'image_filename' in record and record['image_filename']]
        
        yield f"data:画像をGCSからダウンロード中... (0/{len(image_filenames)})\n\n"
        with ThreadPoolExecutor(max_workers=5) as executor:
            download_futures = {executor.submit(download_image_from_gcs, filename, download_dir): filename for filename in image_filenames}
            
            for i, future in enumerate(as_completed(download_futures)):
                filename = download_futures[future]
                try:
                    future.result()
                    yield f"data:画像をダウンロード中... {os.path.basename(filename)} ({i+1}/{len(image_filenames)})\n\n"
                except Exception as e:
                    yield f"data:Error: GCSからの画像のダウンロードに失敗しました: {filename}\n\n"
        
        yield f"data:PDFを生成中...\n\n"
        front_pdf_path = os.path.join(download_dir, 'front.pdf')
        back_pdf_path = os.path.join(download_dir, 'back.pdf')
        
        generate_front_and_back_pdfs(records, front_pdf_path, back_pdf_path, cols, rows, download_dir)
        
        yield "data:PDFをGCSにアップロード中...\n\n"
        gcs_front_path = f"generated_pdfs/{unique_id}_front.pdf"
        gcs_back_path = f"generated_pdfs/{unique_id}_back.pdf"
        upload_to_gcs(front_pdf_path, gcs_front_path)
        upload_to_gcs(back_pdf_path, gcs_back_path)

        yield f"data:ダウンロード準備完了|{unique_id}\n\n"

    return Response(event_stream(), mimetype="text/event-stream")

@app.route('/get_download_zip/<unique_id>')
def get_download_zip(unique_id):
    """Generates and serves a ZIP file containing the PDFs."""
    download_dir = os.path.join('temp', unique_id)
    zip_path = os.path.join(download_dir, 'flashcards.zip')

    try:
        with ZipFile(zip_path, 'w', ZIP_DEFLATED) as zipf:
            front_pdf_path = os.path.join(download_dir, 'front.pdf')
            back_pdf_path = os.path.join(download_dir, 'back.pdf')
            
            if os.path.exists(front_pdf_path):
                zipf.write(front_pdf_path, 'front.pdf')
            if os.path.exists(back_pdf_path):
                zipf.write(back_pdf_path, 'back.pdf')
        
        return_data = io.BytesIO()
        with open(zip_path, 'rb') as f:
            return_data.write(f.read())
        return_data.seek(0)
        
        # Clean up temporary files
        os.remove(zip_path)
        for f in glob.glob(os.path.join(download_dir, '*')):
            os.remove(f)
        os.rmdir(download_dir)
        
        return Response(
            return_data,
            mimetype='application/zip',
            headers={'Content-Disposition': f'attachment;filename=flashcards_{unique_id}.zip'}
        )
        
    except FileNotFoundError:
        return "Error: File not found.", 404

# --- GCSファイル管理機能の復元 ---

@app.route('/list_gcs_files', methods=['GET'])
def list_gcs_files():
    """GCSバケット内のファイル一覧を取得します。"""
    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blobs = bucket.list_blobs()
        files = [{'name': blob.name, 'size': blob.size} for blob in blobs]
        return jsonify({'status': 'success', 'files': files})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/upload_gcs_file', methods=['POST'])
def upload_gcs_file():
    """GCSバケットにファイルをアップロードします。"""
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'ファイルがありません。'})
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'ファイルが選択されていません。'})
    
    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(secure_filename(file.filename))
        blob.upload_from_file(file)
        return jsonify({'status': 'success', 'message': 'ファイルが正常にアップロードされました。'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/delete_gcs_file', methods=['POST'])
def delete_gcs_file():
    """GCSバケットからファイルを削除します。"""
    try:
        data = request.json
        filename = data.get('filename')
        if not filename:
            return jsonify({'status': 'error', 'message': 'ファイル名が指定されていません。'})

        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.delete()
        return jsonify({'status': 'success', 'message': 'ファイルが正常に削除されました。'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# --- 共通関数 ---
def download_image_from_gcs(filename, download_dir):
    """Downloads a file from GCS and saves it to a local directory."""
    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)
        local_path = os.path.join(download_dir, secure_filename(filename))
        blob.download_to_filename(local_path)
        return local_path
    except Exception as e:
        print(f"Error downloading {filename} from GCS: {e}")
        return None

def upload_to_gcs(source_file_path, destination_blob_name):
    """Uploads a file to the GCS bucket."""
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_path)

def get_gspread_client(credentials_path):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_path, scope)
    return gspread.authorize(creds)
    
if __name__ == '__main__':
    app.run(debug=True)
