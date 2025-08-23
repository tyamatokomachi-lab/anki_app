# pdf_generator.py
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
import re

# 日本語フォントを登録
try:
    font_path = "C:/Windows/Fonts/meiryo.ttc"
    pdfmetrics.registerFont(TTFont('JapaneseFont', font_path))
except Exception as e:
    print(f"Warning: Failed to register Japanese font. Defaulting to Courier. Error: {e}")
    pass

def generate_front_and_back_pdfs(records, front_output_path, back_output_path, cols, rows, images_dir):
    """
    Generate separate PDF files for the front and back of flashcards.
    
    Args:
        records (list): A list of dictionaries representing the spreadsheet data.
        front_output_path (str): The path to save the front-side PDF.
        back_output_path (str): The path to save the back-side PDF.
        cols (int): The number of columns per page.
        rows (int): The number of rows per page.
        images_dir (str): The directory where downloaded images are stored.
    """
    
    width, height = A4
    cell_width = width / cols
    cell_height = height / rows
    num_cards_per_page = cols * rows

    # --- Generate Front PDF (Questions & Images) ---
    c_front = canvas.Canvas(front_output_path, pagesize=A4)
    for i in range(0, len(records), num_cards_per_page):
        page_records = records[i:i + num_cards_per_page]
        
        for j, record in enumerate(page_records):
            row = j // cols
            col = j % cols
            
            x = col * cell_width
            y = height - (row + 1) * cell_height
            
            # Draw cell border for visual separation
            c_front.rect(x, y, cell_width, cell_height)
            
            try:
                c_front.setFont('JapaneseFont', 12)
            except:
                c_front.setFont('Helvetica', 12)
            
            # Draw question text
            if 'question' in record and record['question']:
                text = c_front.beginText()
                text.setTextOrigin(x + 5, y + cell_height - 15)
                text.setFont('JapaneseFont', 12)
                text.textLine(record['question'])
                c_front.drawText(text)
            
            # Draw image
            if 'image_filename' in record and record['image_filename']:
                try:
                    image_path = os.path.join(images_dir, record['image_filename'])
                    
                    if os.path.exists(image_path):
                        img_width = cell_width - 10
                        img_height = cell_height - 30
                        # Calculate position to center the image below the question text
                        img_x = x + 5
                        img_y = y + 5
                        c_front.drawImage(image_path, img_x, img_y, width=img_width, height=img_height, preserveAspectRatio=True, mask='auto')
                except Exception as e:
                    print(f"Error drawing image {image_path}: {e}")
        
        c_front.showPage()
    
    c_front.save()

    # --- Generate Back PDF (Answers) ---
    c_back = canvas.Canvas(back_output_path, pagesize=A4)
    back_records = records[::-1] # Reverse the order for the back side
    for i in range(0, len(back_records), num_cards_per_page):
        page_records = back_records[i:i + num_cards_per_page]
        
        for j, record in enumerate(page_records):
            row = j // cols
            col = j % cols
            
            x = col * cell_width
            y = height - (row + 1) * cell_height
            
            # Draw cell border
            c_back.rect(x, y, cell_width, cell_height)
            
            try:
                c_back.setFont('JapaneseFont', 12)
            except:
                c_back.setFont('Helvetica', 12)
            
            # Draw answer text
            if 'answer' in record and record['answer']:
                text = c_back.beginText()
                text.setTextOrigin(x + 5, y + cell_height - 15)
                text.setFont('JapaneseFont', 12)
                text.textLine(record['answer'])
                c_back.drawText(text)
        
        c_back.showPage()
    
    c_back.save()
