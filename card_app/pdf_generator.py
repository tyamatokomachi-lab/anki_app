# pdf_generator.py
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
import re
import tempfile
import spreadsheet_manager
import gcs_manager
import sys
import shutil

# 日本語フォントを登録
try:
    font_path = "C:/Windows/Fonts/meiryo.ttc"
    if not os.path.exists(font_path):
        font_path = os.path.join(os.path.dirname(__file__), 'IPAexGothic.ttf')
    if not os.path.exists(font_path):
        raise FileNotFoundError("Japanese font file not found.")
    pdfmetrics.registerFont(TTFont('JapaneseFont', font_path))
except Exception as e:
    print(f"Warning: Failed to register Japanese font. Defaulting to Courier. Error: {e}", file=sys.stderr)
    pass


def generate_front_and_back_pdfs(records, front_output_path, back_output_path, cols, rows, images_dir):
    """
    元のPDFダウンロード用関数。
    """
    if not records:
        print("Warning: No records found to generate PDFs.", file=sys.stderr)
        return

    width, height = A4
    cell_width = width / cols
    cell_height = height / rows
    num_cards_per_page = cols * rows

    # --- Generate Front PDF ---
    c_front = canvas.Canvas(front_output_path, pagesize=A4)
    for i in range(0, len(records), num_cards_per_page):
        page_records = records[i:i + num_cards_per_page]
        for j, record in enumerate(page_records):
            row = j // cols
            col = j % cols
            x = col * cell_width
            y = height - (row + 1) * cell_height
            c_front.rect(x, y, cell_width, cell_height)
            try:
                c_front.setFont('JapaneseFont', 12)
            except:
                c_front.setFont('Helvetica', 12)
            
            if 'question' in record and record['question']:
                text = c_front.beginText()
                text.setTextOrigin(x + 5, y + cell_height - 15)
                text.textLines(record['question'])
                c_front.drawText(text)
            
            if 'image_filename' in record and record['image_filename']:
                image_path = os.path.join(images_dir, record['image_filename'])
                if os.path.exists(image_path):
                    img_width = 100
                    img_height = 100
                    img_x = x + (cell_width - img_width) / 2
                    img_y = y + 20
                    c_front.drawImage(image_path, img_x, img_y, width=img_width, height=img_height, preserveAspectRatio=True, mask='auto')
        c_front.showPage()
    c_front.save()

    # --- Generate Back PDF ---
    c_back = canvas.Canvas(back_output_path, pagesize=A4)
    back_records = records[::-1]
    for i in range(0, len(back_records), num_cards_per_page):
        page_records = back_records[i:i + num_cards_per_page]
        for j, record in enumerate(page_records):
            row = j // cols
            col = j % cols
            x = col * cell_width
            y = height - (row + 1) * cell_height
            c_back.rect(x, y, cell_width, cell_height)
            try:
                c_back.setFont('JapaneseFont', 12)
            except:
                c_back.setFont('Helvetica', 12)
            
            if 'answer' in record and record['answer']:
                text = c_back.beginText()
                text.setTextOrigin(x + 5, y + cell_height - 15)
                text.textLines(record['answer'])
                c_back.drawText(text)
        c_back.showPage()
    c_back.save()