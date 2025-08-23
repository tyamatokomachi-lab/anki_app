# preview_image_generator.py
from reportlab.lib.pagesizes import A4
import base64
import os
import io
from PIL import Image, ImageDraw, ImageFont

# 日本語フォントを読み込み
try:
    # 既存のシステムフォントを使用
    # Windows: "C:/Windows/Fonts/meiryo.ttc"
    # Linux/WSL: "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"
    # 環境に合わせて適切なパスを指定してください。
    font_path = "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"
    if not os.path.exists(font_path):
        font_path = "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf" # 別のパスを試す
    if not os.path.exists(font_path):
        # フォントが見つからない場合は警告を表示
        print("Warning: Japanese font not found. Using default font.")
        font_path = None
        
    japanese_font = ImageFont.truetype(font_path, 20) if font_path else ImageFont.load_default()
except Exception as e:
    print(f"Error loading Japanese font: {e}")
    japanese_font = ImageFont.load_default()

def generate_pdf_preview_images(records, cols, rows, images_dir):
    """
    Generates front and back preview images directly using Pillow.
    
    Args:
        records (list): A list of dictionaries representing the spreadsheet data.
        cols (int): The number of columns per page.
        rows (int): The number of rows per page.
        images_dir (str): The directory where downloaded images are stored.
        
    Returns:
        tuple: A tuple containing two lists of base64 encoded PNG strings,
               one for front pages and one for back pages.
    """
    front_images_base64 = []
    back_images_base64 = []
    
    num_cards_per_page = cols * rows
    width, height = A4
    
    for i in range(0, len(records), num_cards_per_page):
        page_records = records[i:i + num_cards_per_page]

        # Create new images for the front and back pages
        front_img = Image.new('RGB', (int(width), int(height)), 'white')
        draw_front = ImageDraw.Draw(front_img)
        
        back_img = Image.new('RGB', (int(width), int(height)), 'white')
        draw_back = ImageDraw.Draw(back_img)
        
        cell_width = width / cols
        cell_height = height / rows

        # Draw front side
        for j, record in enumerate(page_records):
            row = j // cols
            col = j % cols
            x = col * cell_width
            y = height - (row + 1) * cell_height
            
            # Draw cell border
            draw_front.rectangle([x, y, x + cell_width, y + cell_height], outline='black')
            
            # Draw question text
            if 'question' in record and record['question']:
                draw_front.text((x + 10, y + 10), record['question'], font=japanese_font, fill='black')
            
            # Draw image
            if 'image_filename' in record and record['image_filename']:
                try:
                    image_path = os.path.join(images_dir, record['image_filename'])
                    if os.path.exists(image_path):
                        img_pil = Image.open(image_path)
                        
                        # Calculate thumbnail size to fit within cell
                        max_img_width = cell_width - 20
                        max_img_height = cell_height - 40
                        img_pil.thumbnail((max_img_width, max_img_height))
                        
                        # Calculate position to center the image
                        img_x = x + (cell_width - img_pil.width) / 2
                        img_y = y + (cell_height - img_pil.height) / 2
                        
                        # Use front_img.paste() instead of draw_front.paste()
                        front_img.paste(img_pil, (int(img_x), int(img_y)))
                except Exception as e:
                    print(f"Error drawing image for preview: {e}")

        # Draw back side
        page_records_reversed = page_records[::-1]
        for j, record in enumerate(page_records_reversed):
            row = j // cols
            col = j % cols
            x = col * cell_width
            y = height - (row + 1) * cell_height
            
            draw_back.rectangle([x, y, x + cell_width, y + cell_height], outline='black')
            
            # Draw answer text
            if 'answer' in record and record['answer']:
                draw_back.text((x + 10, y + 10), record['answer'], font=japanese_font, fill='black')

        # Convert images to base64 strings
        front_buffer = io.BytesIO()
        front_img.save(front_buffer, format='PNG')
        front_images_base64.append(base64.b64encode(front_buffer.getvalue()).decode('utf-8'))
        
        back_buffer = io.BytesIO()
        back_img.save(back_buffer, format='PNG')
        back_images_base64.append(base64.b64encode(back_buffer.getvalue()).decode('utf-8'))
        
    return front_images_base64, back_images_base64
