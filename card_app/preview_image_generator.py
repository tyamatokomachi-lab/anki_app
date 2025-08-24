import os
import fitz  # PyMuPDF
from PIL import Image
import tempfile
import sys
import shutil

# 他のモジュールからのインポート
import pdf_generator

def generate_pdf_preview_images(pdf_path):
    """
    指定されたPDFファイルのプレビュー画像を生成する。
    """
    image_paths = []

    try:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found at {pdf_path}")
        
        doc = fitz.open(pdf_path)
        temp_dir = tempfile.mkdtemp()

        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=150)
            
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            image_path = os.path.join(temp_dir, f"preview_page_{i}.jpeg")
            img.save(image_path, "JPEG")
            
            image_paths.append(image_path)
        
        doc.close()
        
        return image_paths

    except Exception as e:
        print(f"プレビュー画像の生成中にエラーが発生しました: {e}", file=sys.stderr)
        return []

def cleanup_preview_images(image_paths):
    """
    生成されたプレビュー画像を保存している一時ディレクトリを削除する。
    """
    if image_paths:
        temp_dir = os.path.dirname(image_paths[0])
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)