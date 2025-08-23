from flask import render_template, request, send_file, redirect, url_for, Response, stream_with_context, jsonify
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
import io
import zipfile
import math
from spreadsheet_manager import get_spreadsheet_data, get_gspread_client
from pdf_generator import create_flashcards_pdf_in_memory, get_all_card_images
from gcs_manager import list_files_in_bucket, upload_file_to_gcs, delete_file_from_gcs
import gspread
import threading
import queue
import time
import tempfile
import os
import uuid
import fitz # PyMuPDF
import base64

# PDFデータを一時的にキャッシュするための辞書
pdf_cache = {}

# スプレッドシートのデータをキャッシュするための辞書
spreadsheet_data_cache = {}

def get_common_data(app):
    """Helper to get common data for all routes."""
    spreadsheet_id = app.config['SPREADSHEET_ID']
    credentials_path = app.config['CREDENTIALS_PATH']
    
    gc = get_gspread_client(credentials_path)
    
    sheet_names = [sheet.title for sheet in gc.open_by_key(spreadsheet_id).worksheets()]
    return sheet_names, spreadsheet_id, credentials_path

def register_routes(app):
    """Registers all Flask routes with the given app instance."""
    
    # --- Web page routes ---
    @app.route("/", methods=["GET"])
    def index():
        print("GET / -- ページをロード中...")
        sheet_names, _, _ = get_common_data(app)
        print("GET / -- ロード完了")
        return render_template("index.html", sheet_names=sheet_names, cols=3, rows=4)

    @app.route("/files")
    def file_manager():
        print("GET /files -- ファイルマネージャーをロード中...")
        bucket_name = app.config['GCS_BUCKET_NAME']
        credentials_path = app.config['CREDENTIALS_PATH']
        files = list_files_in_bucket(bucket_name, credentials_path)
        if files is None:
            return "GCSファイルの取得に失敗しました。", 500
        print("GET /files -- ロード完了")
        return render_template("file_manager.html", files=files, GCS_BUCKET_NAME=bucket_name)

    # --- API routes ---
    @app.route("/preview_pdf_images")
    def preview_pdf_images():
        """
        PDFを生成し、各ページを画像に変換してJSONで返す新しいエンドポイント。
        """
        sheet_name = request.args.get('sheet_name', type=str)
        cols = request.args.get('cols', default=3, type=int)
        rows = request.args.get('rows', default=4, type=int)
        
        if not sheet_name:
            return jsonify({"status": "error", "message": "シート名が指定されていません。"}), 400

        spreadsheet_id = app.config['SPREADSHEET_ID']
        credentials_path = app.config['CREDENTIALS_PATH']
        bucket_name = app.config['GCS_BUCKET_NAME']
        
        try:
            print(f"[{time.time()}] /preview_pdf_images: スプレッドシート '{sheet_name}' のデータを取得中...")
            if sheet_name not in spreadsheet_data_cache:
                card_data_raw = get_spreadsheet_data(spreadsheet_id, sheet_name, credentials_path)
                if card_data_raw is None:
                    print(f"[{time.time()}] /preview_pdf_images: スプレッドシートデータ取得失敗")
                    return jsonify({"status": "error", "message": "スプレッドシートデータ取得失敗"}), 500
                spreadsheet_data_cache[sheet_name] = card_data_raw
            else:
                card_data_raw = spreadsheet_data_cache[sheet_name]
            print(f"[{time.time()}] /preview_pdf_images: スプレッドシートデータ取得完了。カード数: {len(card_data_raw)}")
            
            # 画像URLを取得
            card_images = get_all_card_images(card_data_raw, bucket_name, credentials_path, lambda msg: None)

            # PDFをメモリ上で生成
            front_pdf_buffer, back_pdf_buffer = create_flashcards_pdf_in_memory(card_data_raw, cols, rows, card_images, lambda msg: None)

            # PDFを画像に変換
            def convert_pdf_to_images(pdf_buffer):
                doc = fitz.open(stream=pdf_buffer.getvalue(), filetype="pdf")
                image_data = []
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    # 高解像度でレンダリング
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    img_bytes = pix.tobytes("png")
                    image_data.append(base64.b64encode(img_bytes).decode('utf-8'))
                return image_data

            front_images = convert_pdf_to_images(front_pdf_buffer)
            back_images = convert_pdf_to_images(back_pdf_buffer)

            return jsonify({"status": "success", "front_images": front_images, "back_images": back_images})
        
        except Exception as e:
            print(f"[{time.time()}] Error in preview_pdf_images: {e}")
            return jsonify({"status": "error", "message": f"内部サーバーエラー: {e}"}), 500

    @app.route("/download_pdf")
    def download_pdf():
        sheet_name = request.args.get('sheet_name', type=str)
        cols = request.args.get('cols', default=3, type=int)
        rows = request.args.get('rows', default=4, type=int)
        
        if not sheet_name:
            return "シート名が指定されていません。", 400

        spreadsheet_id = app.config['SPREADSHEET_ID']
        credentials_path = app.config['CREDENTIALS_PATH']
        bucket_name = app.config['GCS_BUCKET_NAME']
        
        def generate_pdf_and_stream():
            try:
                yield f"data: スプレッドシートデータを取得中...\n\n"
                print(f"[{time.time()}] /download_pdf: スプレッドシート '{sheet_name}' のデータを取得中...")
                if sheet_name not in spreadsheet_data_cache:
                    card_data = get_spreadsheet_data(spreadsheet_id, sheet_name, credentials_path)
                    if card_data is None:
                        yield f"data: スプレッドシートデータ取得失敗\n\n"
                        return
                    spreadsheet_data_cache[sheet_name] = card_data
                else:
                    card_data = spreadsheet_data_cache[sheet_name]
                yield f"data: スプレッドシートデータ取得完了\n\n"
                print(f"[{time.time()}] /download_pdf: スプレッドシートデータ取得完了。")
                
                def sse_callback(msg):
                    yield f"data: {msg}\n\n"
                
                yield f"data: 関連画像をダウンロード中...\n\n"
                print(f"[{time.time()}] /download_pdf: 関連画像をダウンロード中...")
                card_images = get_all_card_images(card_data, bucket_name, credentials_path, sse_callback)
                yield f"data: 画像ダウンロード完了\n\n"
                print(f"[{time.time()}] /download_pdf: 画像ダウンロード完了。")
                
                yield f"data: PDF生成中...\n\n"
                print(f"[{time.time()}] /download_pdf: PDF生成中...")
                front_pdf_buffer, back_pdf_buffer = create_flashcards_pdf_in_memory(card_data, cols, rows, card_images, sse_callback)
                yield f"data: PDF生成完了\n\n"
                print(f"[{time.time()}] /download_pdf: PDF生成完了。")
                
                yield f"data: PDFを結合してZIPを作成中...\n\n"
                print(f"[{time.time()}] /download_pdf: PDFを結合してZIPを作成中...")
                
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                    zf.writestr('front.pdf', front_pdf_buffer.getvalue())
                    zf.writestr('back.pdf', back_pdf_buffer.getvalue())
                
                zip_buffer.seek(0)

                # ユニークなIDを生成し、キャッシュに保存
                unique_id = str(uuid.uuid4())
                pdf_cache[unique_id] = zip_buffer.getvalue()
                
                yield f"data: ダウンロード準備完了|{unique_id}\n\n"

            except Exception as e:
                print(f"[{time.time()}] Error in download_pdf stream: {e}")
                yield f"data: エラーが発生しました: {e}\n\n"
                yield "data: 失敗\n\n"

        return Response(stream_with_context(generate_pdf_and_stream()), mimetype='text/event-stream')

    @app.route("/get_download_zip/<unique_id>")
    def get_download_zip(unique_id):
        """
        キャッシュされたZIPファイルをクライアントに送信するエンドポイント。
        """
        print(f"[{time.time()}] /get_download_zip: ID '{unique_id}' のZIPファイルを送信します。")
        zip_data = pdf_cache.pop(unique_id, None)
        if zip_data is None:
            return "ファイルが見つからないか、有効期限が切れています。", 404
        
        return send_file(
            io.BytesIO(zip_data),
            mimetype='application/zip',
            as_attachment=True,
            download_name=f"flashcards.zip"
        )


    @app.route("/upload_file", methods=["POST"])
    def upload_file():
        print("POST /upload_file -- アップロードを開始します...")
        if 'file' not in request.files:
            return "ファイルが選択されていません。", 400
        
        file = request.files['file']
        if file.filename == '':
            return "ファイル名がありません。", 400
        
        bucket_name = app.config['GCS_BUCKET_NAME']
        credentials_path = app.config['CREDENTIALS_PATH']

        success, error_msg = upload_file_to_gcs(file, bucket_name, credentials_path)
        if not success:
            return f"ファイルのアップロードに失敗しました: {error_msg}", 500
        
        print("POST /upload_file -- アップロード完了")
        return redirect(url_for('file_manager'))

    @app.route("/delete_file", methods=["POST"])
    def delete_file():
        print("POST /delete_file -- 削除を開始します...")
        file_name = request.form.get('file_name')
        if not file_name:
            return "ファイル名が指定されていません。", 400

        bucket_name = app.config['GCS_BUCKET_NAME']
        credentials_path = app.config['CREDENTIALS_PATH']

        success, error_msg = delete_file_from_gcs(file_name, bucket_name, credentials_path)
        if not success:
            return f"ファイルの削除に失敗しました: {error_msg}", 500
        
        print("POST /delete_file -- 削除完了")
        return redirect(url_for('file_manager'))
