import csv
import os
import tempfile
from reportlab.lib.pagesizes import A4, portrait
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image
from reportlab.lib.enums import TA_CENTER # テキストアラインメント用

def get_available_filename(base_filepath):
    """
    指定されたファイルパスが既に存在するか、アクセス可能かを確認し、
    必要に応じて連番を付与した新しいファイルパスを返します。
    例: my_file.pdf -> my_file_01.pdf -> my_file_02.pdf
    """
    if not os.path.exists(base_filepath):
        return base_filepath

    directory, filename = os.path.split(base_filepath)
    name, ext = os.path.splitext(filename)

    counter = 1
    while True:
        new_filename = f"{name}_{counter:02d}{ext}"
        new_filepath = os.path.join(directory, new_filename)
        
        if not os.path.exists(new_filepath):
            return new_filepath
        
        counter += 1
        if counter > 999:
            raise Exception("利用可能なファイル名が見つかりませんでした (999個以上の連番を試行)。")

def draw_wrapped_text(canvas_obj, text, x_center, y_center_area, font_name, font_size, max_width, max_height, line_height_multiplier=1.2):
    """
    指定された幅と高さに合わせてテキストを自動改行し、canvas_objに描画します。
    テキストはY座標で指定されたエリアの中心に配置され、その中で折り返されます。
    """
    canvas_obj.setFont(font_name, font_size)
    
    lines = []
    current_line = ""
    
    for char in text:
        # 1文字追加した場合の現在の行の幅を計算
        test_line = current_line + char
        text_width = pdfmetrics.stringWidth(test_line, font_name, font_size)
        
        if text_width <= max_width:
            current_line = test_line
        else:
            # 幅を超えたら現在の行を確定し、新しい行を開始
            lines.append(current_line)
            current_line = char # 新しい行の最初の文字
    
    if current_line: # 最後の行を追加
        lines.append(current_line)

    # テキストの総高さと、テキストブロック全体の中心Y座標を計算
    line_height = font_size * line_height_multiplier
    total_text_height = len(lines) * line_height

    # テキストが指定された最大高さを超えるかチェック
    if total_text_height > max_height:
        displayable_lines_count = int(max_height / line_height)
        if displayable_lines_count < len(lines):
            lines = lines[:displayable_lines_count]
            # 必要であれば、最後の行に"..."を追加するなどの処理も検討
            # 例: if lines: lines[-1] = lines[-1][:int(len(lines[-1])*0.8)] + "..."

    # y_center_areaはテキストエリアの中心Y座標なので、
    # そこからテキストブロック全体の高さの半分を引くと、テキストブロックの最上部の行のベースラインのY座標となる
    start_y = y_center_area + (total_text_height / 2) - line_height # 最初の行のベースラインの開始Y座標

    current_y = start_y # 最初の行のベースライン

    for line in lines:
        line_width = pdfmetrics.stringWidth(line, font_name, font_size)
        line_x = x_center - (line_width / 2) # 中央寄せ

        canvas_obj.drawString(line_x, current_y, line)
        current_y -= line_height # 次の行のY座標


def create_flashcards_pdf(data_file, output_pdf_front_base, output_pdf_back_base):
    """
    一問一答の暗記カード（表面と裏面）をPDFで作成します。
    CSVで指定された画像ファイルをPDF表面に埋め込みます。
    画像ファイル名が空欄の場合は画像を埋め込みません。
    1ページに10枚（フチなし、余白ゼロ）で配置します。
    透過画像がある場合、背景は白で描画されます。
    カードの周囲に薄い切り取り線が描画されます。
    出力ファイルがすでに存在する場合は、自動的に連番を付与して保存します。
    問題文はカード内に自動で改行されます。
    A4縦両面印刷時に表裏が正確に対応するように裏面を配置します。

    Args:
        data_file (str): 問題、解答、画像ファイル名が記載されたCSVファイルのパス。
                         1列目: 問題、2列目: 解答、3列目: イラストファイル名、4列目: イラスト内容説明
        output_pdf_front_base (str): カード表面のPDF出力ファイル名のベース（連番付与前）。
        output_pdf_back_base (str): カード裏面のPDF出力ファイル名のベース（連番付与前）。
    """

    # フォントの登録
    try:
        pdfmetrics.registerFont(TTFont('IPAexGothic', 'IPAexGothic.ttf'))
    except Exception as e:
        print(f"フォントの読み込みに失敗しました。パスを確認してください: {e}")
        print("代わりにデフォルトフォントを使用します。日本語が正しく表示されない可能性があります。")
        pdfmetrics.registerFont(TTFont('Gothic', 'Helvetica'))

    # カード設定
    cards_per_row = 2
    cards_per_col = 5

    # カードのサイズをA4用紙にぴったり収まるように調整
    card_width = A4[0] / cards_per_row
    card_height = A4[1] / cards_per_col

    # 画像の最大サイズ設定
    image_area_height = card_height * 0.6
    question_text_margin_x = 5 * mm
    question_text_max_width = card_width - (question_text_margin_x * 2) 
    question_text_max_height = card_height - image_area_height - (5 * mm)

    image_max_width = card_width - 10 * mm
    image_max_height = image_area_height - 5 * mm

    # 出力ファイル名を決定
    output_pdf_front = get_available_filename(output_pdf_front_base)
    output_pdf_back = get_available_filename(output_pdf_back_base)

    # PDFキャンバスの初期化
    c_front = canvas.Canvas(output_pdf_front, pagesize=portrait(A4))
    c_back = canvas.Canvas(output_pdf_back, pagesize=portrait(A4))

    # データ読み込み
    qa_pairs = []
    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            for row in reader:
                if row and row[0].strip() != '':
                    if len(row) == 4:
                        qa_pairs.append(row)
                    else:
                        print(f"警告: 列数が4でない不正な行をスキップしました - {row}")
    except FileNotFoundError:
        print(f"エラー: 指定されたCSVファイル '{data_file}' が見つかりません。")
        return
    except Exception as e:
        print(f"CSVファイルの読み込み中にエラーが発生しました: {e}")
        return

    # カードの描画
    for i, (question, answer, image_filename, image_description) in enumerate(qa_pairs):
        card_on_page_idx = i % (cards_per_row * cards_per_col)

        if card_on_page_idx == 0 and i != 0:
            c_front.showPage()
            c_back.showPage()

        # カードの配置座標を計算 (左下を基準)
        row_idx = card_on_page_idx // cards_per_row
        col_idx = card_on_page_idx % cards_per_row

        x_pos_front = col_idx * card_width
        y_pos_front = A4[1] - (row_idx + 1) * card_height

        # 裏面のX座標は、表面のX座標を横方向に反転させる
        # 例: 表面の左列(col_idx=0)の裏は右列(col_idx=1)に、表面の右列(col_idx=1)の裏は左列(col_idx=0)に
        x_pos_back = (cards_per_row - 1 - col_idx) * card_width
        y_pos_back = y_pos_front # Y座標は表面と同じ

        # --- 切り取り線の描画 (表面) ---
        c_front.setStrokeColorRGB(0.8, 0.8, 0.8)
        c_front.setLineWidth(0.3)
        c_front.rect(x_pos_front, y_pos_front, card_width, card_height)

        # --- 切り取り線の描画 (裏面) ---
        c_back.setStrokeColorRGB(0.8, 0.8, 0.8)
        c_back.setLineWidth(0.3)
        c_back.rect(x_pos_back, y_pos_back, card_width, card_height)


        # --- カード表面（問題と画像） ---
        
        # 問題文の描画エリアの中心Y座標
        question_text_area_y_center = y_pos_front + (card_height - image_area_height) / 2
        # 問題文の描画基準X座標（中央寄せのためカードの中心）
        question_text_x_center = x_pos_front + card_width / 2

        if image_filename.strip() != "":
            temp_image_path = None
            try:
                img = Image.open(image_filename.strip())
                
                if img.mode == 'RGBA':
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, (0, 0), img)
                    img = background
                
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                img.save(temp_file.name, format='PNG')
                temp_file.close()
                temp_image_path = temp_file.name

                img_original_width, img_original_height = img.size

                img_width = img_original_width
                img_height = img_original_height

                aspect_ratio = img_original_width / img_original_height

                if img_width > image_max_width:
                    img_width = image_max_width
                    img_height = img_width / aspect_ratio
                
                if img_height > image_max_height:
                    img_height = image_max_height
                    img_width = img_height * aspect_ratio

                img_x_pos = x_pos_front + (card_width - img_width) / 2
                img_y_pos = y_pos_front + (card_height - image_area_height) + (image_area_height - img_height) / 2

                c_front.drawImage(temp_image_path, img_x_pos, img_y_pos, width=img_width, height=img_height)

            except FileNotFoundError:
                c_front.setFont('IPAexGothic', 10)
                # エラーメッセージを画像エリア中央に表示
                c_front.drawCentredString(x_pos_front + card_width / 2, y_pos_front + card_height - image_area_height / 2 + 5 * mm, f"画像なし: {image_filename.strip()}")
                c_front.drawCentredString(x_pos_front + card_width / 2, y_pos_front + card_height - image_area_height / 2 - 5 * mm, f"({image_description})")
            except Exception as e:
                print(f"画像 '{image_filename.strip()}' の処理中にエラーが発生しました: {e}")
                c_front.setFont('IPAexGothic', 10)
                c_front.drawCentredString(x_pos_front + card_width / 2, y_pos_front + card_height - image_area_height / 2 + 5 * mm, f"画像エラー: {image_filename.strip()}")
                c_front.drawCentredString(x_pos_front + card_width / 2, y_pos_front + card_height - image_area_height / 2 - 5 * mm, f"({image_description})")
            finally:
                if temp_image_path and os.path.exists(temp_image_path):
                    os.remove(temp_image_path)
        
        # 問題文の描画（自動改行）
        draw_wrapped_text(c_front, question, question_text_x_center, question_text_area_y_center, 
                          'IPAexGothic', 12, question_text_max_width, question_text_max_height)


        # --- カード裏面（解答） ---
        answer_text_area_y_center = y_pos_back + card_height / 2 # 解答はカード中央
        answer_text_x_center = x_pos_back + card_width / 2 # 解答はカード中央
        answer_text_max_width = card_width - (question_text_margin_x * 2) # 問題文と同じ幅
        answer_text_max_height = card_height - (5 * mm) # カードほぼ全体を使う

        # 解答文も改行して描画
        draw_wrapped_text(c_back, answer, answer_text_x_center, answer_text_area_y_center, 
                          'IPAexGothic', 14, answer_text_max_width, answer_text_max_height)


    # PDF保存
    try:
        c_front.save()
        print(f"暗記カード表面のPDF '{output_pdf_front}' を作成しました。")
    except Exception as e:
        print(f"エラー: 表面PDF '{output_pdf_front}' の保存に失敗しました。ファイルが使用中か確認してください。エラー: {e}")

    try:
        c_back.save()
        print(f"暗記カード裏面のPDF '{output_pdf_back}' を作成しました。")
    except Exception as e:
        print(f"エラー: 裏面PDF '{output_pdf_back}' の保存に失敗しました。ファイルが使用中か確認してください。エラー: {e}")

if __name__ == "__main__":
    # CSVファイルのパス
    input_csv_file = 'qa_data.csv'
    # 出力PDFファイル名のベース
    output_pdf_front_base_file = 'flashcards_front_10_per_page.pdf'
    output_pdf_back_base_file = 'flashcards_back_10_per_page.pdf'

    create_flashcards_pdf(input_csv_file, output_pdf_front_base_file, output_pdf_back_base_file)