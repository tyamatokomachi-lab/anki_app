from preview_image_generator import generate_pdf_preview_images, cleanup_preview_images
from pdf_generator import generate_front_and_back_pdfs
from spreadsheet_manager import get_spreadsheet_data
from flask import Blueprint, render_template, request, jsonify, send_from_directory, Response, stream_with_context
import os
import tempfile
import json
import gcs_manager
import spreadsheet_manager
import shutil
import time
import io
from zipfile import ZipFile, ZIP_DEFLATED
import uuid
import sys

routes_bp = Blueprint('routes_bp', __name__)

@routes_bp.route("/")
def index():
    return render_template("index.html")

# プレビュー用ルート (GET リクエストに対応)
@routes_bp.route("/preview_pdf_images", methods=["GET"])
def preview_pdf_images():
    try:
        sheet_name = request.args.get('sheet_name')
        cols = int(request.args.get('cols'))
        rows = int(request.args.get('rows'))

        records = spreadsheet_manager.get_spreadsheet_data(
            spreadsheet_id=os.environ.get('SPREADSHEET_ID'),
            sheet_name=sheet_name,
            credentials_path=os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        )
        if not records:
            print("Warning: No records found for preview.", file=sys.stderr)
            return jsonify({"status": "error", "message": "スプレッドシートデータの取得に失敗しました。"}), 500

        front_pdf_path = os.path.join(tempfile.gettempdir(), f"preview_front_{uuid.uuid4()}.pdf")
        back_pdf_path = os.path.join(tempfile.gettempdir(), f"preview_back_{uuid.uuid4()}.pdf")
        
        generate_front_and_back_pdfs(records, front_pdf_path, back_pdf_path, cols, rows, tempfile.gettempdir())
        
        # PDFを画像に変換
        image_paths = generate_pdf_preview_images(front_pdf_path)
        
        # 一時PDFを削除
        if os.path.exists(front_pdf_path):
            os.remove(front_pdf_path)
        if os.path.exists(back_pdf_path):
            os.remove(back_pdf_path)
        
        if not image_paths:
            return jsonify({"status": "error", "message": "プレビュー画像の生成に失敗しました。"}), 500
        
        return jsonify({"status": "success", "image_path": image_paths[0]})
    
    except Exception as e:
        print(f"プレビュー画像の生成中にエラーが発生しました: {e}", file=sys.stderr)
        return jsonify({"status": "error", "message": f"プレビューの取得中にエラーが発生しました: {str(e)}"}), 500

# ダウンロード用ルート（変更なし）
@routes_bp.route("/download_pdfs", methods=["GET"])
def download_pdfs():
    try:
        sheet_name = request.args.get('sheet_name')
        cols = int(request.args.get('cols'))
        rows = int(request.args.get('rows'))
        
        records = spreadsheet_manager.get_spreadsheet_data(
            spreadsheet_id=os.environ.get('SPREADSHEET_ID'),
            sheet_name=sheet_name,
            credentials_path=os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        )
        if not records:
            return "スプレッドシートデータの取得に失敗しました。", 500

        zip_buffer = io.BytesIO()
        with ZipFile(zip_buffer, 'a', ZIP_DEFLATED, False) as zip_file:
            front_pdf_path = os.path.join(tempfile.gettempdir(), f"front_cards_{uuid.uuid4()}.pdf")
            back_pdf_path = os.path.join(tempfile.gettempdir(), f"back_cards_{uuid.uuid4()}.pdf")
            
            generate_front_and_back_pdfs(records, front_pdf_path, back_pdf_path, cols, rows, tempfile.gettempdir())
            
            zip_file.write(front_pdf_path, 'front_cards.pdf')
            zip_file.write(back_pdf_path, 'back_cards.pdf')
            
            if os.path.exists(front_pdf_path):
                os.remove(front_pdf_path)
            if os.path.exists(back_pdf_path):
                os.remove(back_pdf_path)

        zip_buffer.seek(0)
        
        return Response(
            zip_buffer.getvalue(),
            mimetype='application/zip',
            headers={'Content-Disposition': 'attachment;filename=flashcards.zip'}
        )

    except Exception as e:
        return f"PDFダウンロード中にエラーが発生しました: {str(e)}", 500

@routes_bp.route('/temp_image/<filename>')
def temp_image(filename):
    temp_dir = tempfile.gettempdir()
    return send_from_directory(temp_dir, filename)