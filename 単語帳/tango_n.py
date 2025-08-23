import csv
import os
import tempfile
import sys
import math
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

def draw_wrapped_text(canvas_obj, text, x_center, y_center_area, font_name, initial_font_size, max_width, max_height, line_height_multiplier=1.2):
    """
    指定された幅と高さに合わせてテキストを自動改行し、フォントサイズを調整してcanvas_objに描画します。
    テキストはY座標で指定されたエリアの中心に配置され、その中で折り返されます。
    """
    
    # 最小フォントサイズを設定
    min_font_size = 8
    
    # フォントサイズを下げながら、テキストが収まるまで試行
    font_size = initial_font_size
    lines = []
    
    while font_size >= min_font_size:
        canvas_obj.setFont(font_name, font_size)
        lines = []
        current_line = ""
        
        # テキストの自動改行
        for char in text:
            test_line = current_line + char
            text_width = pdfmetrics.stringWidth(test_line, font_name, font_size)
            
            if text_width <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = char
        
        if current_line:
            lines.append(current_line)
        
        # テキストの総高さを計算
        line_height = font_size * line_height_multiplier
        total_text_height = len(lines) * line_height
        
        # テキストが指定された最大高さを超えるかチェック
        if total_text_height <= max_height:
            # 収まったのでループを終了
            break
        else:
            # 収まらなかったのでフォントサイズを小さくして再試行
            font_size -= 0.5
    
    # y_center_areaはテキストエリアの中心Y座標
    start_y = y_center_area + (total_text_height / 2) - line_height

    current_y = start_y

    for line in lines:
        line_width = pdfmetrics.stringWidth(line, font_name, font_size)
        line_x = x_center - (line_width / 2)

        canvas_obj.drawString(line_x, current_y, line)
        current_y -= line_height

def append_to_csv(csv_file_path):
    """
    ユーザーの入力をCSVファイルに追記します。
    ファイルが存在しない場合はヘッダーを作成します。
    """
    # 新しいフィールド名に 'image_directory' を追加
    fieldnames = ['question', 'answer', 'image_directory', 'image_filename', 'image_description']
    
    file_exists = os.path.exists(csv_file_path)
    
    print("\n--- 単語カードの追加 ---")
    print("入力を終了するには、問題文の入力時に 'n' と入力してください。")

    with open(csv_file_path, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader() # ファイルが新規作成された場合のみヘッダーを書き込む

        while True:
            question = input("問題文を入力してください (終了する場合は 'n'): ").strip()
            if question.lower() == 'n':
                break
            
            answer = input("解答を入力してください: ").strip()
            # 新しい入力項目: イラストディレクトリ名
            image_directory = input("イラストディレクトリ名を入力してください (例: images/chapter1, CSVと同じディレクトリなら空欄): ").strip()
            image_filename = input("イラストファイル名を入力してください (任意): ").strip()
            image_description = input("イラスト内容説明を入力してください (任意): ").strip()

            writer.writerow({
                'question': question,
                'answer': answer,
                'image_directory': image_directory, # 新しい列の値を書き込む
                'image_filename': image_filename,
                'image_description': image_description
            })
            print("カードを追加しました。\n")

def create_flashcards_pdf(csv_file_path, cards_per_row, cards_per_col):
    """
    一問一答の暗記カード（表面と裏面）をPDFで作成します。
    CSVで指定された画像ファイルをPDF表面に埋め込みます。
    画像ファイル名が空欄の場合は画像を埋め込みません。
    指定された枚数（cards_per_row × cards_per_col）で配置します。
    透過画像がある場合、背景は白で描画されます。
    カードの周囲に薄い切り取り線が描画されます。
    出力ファイルがすでに存在する場合は、自動的に連番を付与して保存します。
    問題文はカード内に自動で改行されます。
    A4縦両面印刷時に表裏が正確に対応するように裏面を配置します。

    Args:
        csv_file_path (str): 問題、解答、画像ファイル名が記載されたCSVファイルのパス。
        cards_per_row (int): 1ページあたりのカードの列数（横の枚数）。
        cards_per_col (int): 1ページあたりのカードの行数（縦の枚数）。
    """
    
    # CSVファイルが置かれているディレクトリをベースディレクトリとする
    base_directory = os.path.dirname(os.path.abspath(csv_file_path))
    
    # フォントの登録
    try:
        pdfmetrics.registerFont(TTFont('IPAexGothic', 'IPAexGothic.ttf'))
    except Exception as e:
        print(f"フォントの読み込みに失敗しました。パスを確認してください: {e}")
        print("代わりにデフォルトフォントを使用します。日本語が正しく表示されない可能性があります。")
        pdfmetrics.registerFont(TTFont('Gothic', 'Helvetica'))

    # カード設定
    cards_per_page = cards_per_row * cards_per_col

    # カードのサイズをA4用紙にぴったり収まるように調整
    card_width = A4[0] / cards_per_row
    card_height = A4[1] / cards_per_col
    
    # PDF出力ファイル名のベースをCSVファイル名から取得
    csv_filename_without_ext = os.path.splitext(os.path.basename(csv_file_path))[0]
    
    output_pdf_front_base = os.path.join(base_directory, f'{csv_filename_without_ext}_front.pdf')
    output_pdf_back_base = os.path.join(base_directory, f'{csv_filename_without_ext}_back.pdf')

    # 出力ファイル名を決定
    output_pdf_front = get_available_filename(output_pdf_front_base)
    output_pdf_back = get_available_filename(output_pdf_back_base)

    # PDFキャンバスの初期化
    c_front = canvas.Canvas(output_pdf_front, pagesize=portrait(A4))
    c_back = canvas.Canvas(output_pdf_back, pagesize=portrait(A4))

    # データ読み込み
    qa_pairs = []
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader) # ヘッダーをスキップ
            for row in reader:
                # 修正点: 列数が5以上であれば、最初の5列だけを使用する
                if row and len(row) >= 5 and row[0].strip() != '':
                    qa_pairs.append(row[:5])
                else:
                    print(f"警告: 不正な形式の行をスキップしました (先頭の列が空か、列数が5未満です) - {row}")
    except FileNotFoundError:
        print(f"エラー: 指定されたCSVファイル '{csv_file_path}' が見つかりません。")
        return
    except Exception as e:
        print(f"CSVファイルの読み込み中にエラーが発生しました: {e}")
        return
        
    num_cards = len(qa_pairs)
    if num_cards == 0:
        print("CSVファイルにカードデータがありません。PDFは作成されません。")
        return

    num_pages = math.ceil(num_cards / cards_per_page)

    # --- カード表面の描画 ---
    for i, (question, answer, image_directory, image_filename, image_description) in enumerate(qa_pairs):
        card_on_page_idx = i % cards_per_page

        if card_on_page_idx == 0 and i != 0:
            c_front.showPage()

        row_idx = card_on_page_idx // cards_per_row
        col_idx = card_on_page_idx % cards_per_row

        x_pos_front = col_idx * card_width
        y_pos_front = A4[1] - (row_idx + 1) * card_height

        c_front.setStrokeColorRGB(0.8, 0.8, 0.8)
        c_front.setLineWidth(0.3)
        c_front.rect(x_pos_front, y_pos_front, card_width, card_height)
        
        if question.strip() == "":
            question_text_height = 0
            image_area_height = card_height - (2 * mm)
        else:
            question_text_height = card_height * 0.3
            image_area_height = card_height - question_text_height

        question_text_area_y_center = y_pos_front + question_text_height / 2
        question_text_x_center = x_pos_front + card_width / 2

        if image_filename.strip() != "":
            # 画像パスを結合する際に image_directory を考慮
            if image_directory.strip():
                image_filepath = os.path.join(base_directory, image_directory.strip(), image_filename.strip())
            else:
                image_filepath = os.path.join(base_directory, image_filename.strip())
            
            temp_image_path = None
            try:
                img = Image.open(image_filepath)
                if img.mode == 'RGBA':
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, (0, 0), img)
                    img = background
                
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                img.save(temp_file.name, format='PNG')
                temp_file.close()
                temp_image_path = temp_file.name
                
                img_original_width, img_original_height = img.size

                image_max_width = card_width - (2 * mm)
                image_max_height = image_area_height - (2 * mm)

                aspect_ratio = img_original_width / img_original_height
                
                if image_max_width / image_max_height > aspect_ratio:
                    img_height = image_max_height
                    img_width = img_height * aspect_ratio
                else:
                    img_width = image_max_width
                    img_height = img_width / aspect_ratio
                
                img_x_pos = x_pos_front + (card_width - img_width) / 2
                img_y_pos = y_pos_front + question_text_height + (image_area_height - img_height) / 2

                c_front.drawImage(temp_image_path, img_x_pos, img_y_pos, width=img_width, height=img_height)
            except FileNotFoundError:
                c_front.setFont('IPAexGothic', 10)
                c_front.drawCentredString(x_pos_front + card_width / 2, y_pos_front + question_text_height + image_area_height / 2, f"画像なし: {image_filename.strip()}")
                c_front.drawCentredString(x_pos_front + card_width / 2, y_pos_front + question_text_height + image_area_height / 2 - 5*mm, f"({image_directory.strip() if image_directory.strip() else 'ルート'})")
            except Exception as e:
                print(f"画像 '{image_filename.strip()}' の処理中にエラーが発生しました: {e}")
                c_front.setFont('IPAexGothic', 10)
                c_front.drawCentredString(x_pos_front + card_width / 2, y_pos_front + question_text_height + image_area_height / 2, f"画像エラー: {image_filename.strip()}")
                c_front.drawCentredString(x_pos_front + card_width / 2, y_pos_front + question_text_height + image_area_height / 2 - 5*mm, f"({image_directory.strip() if image_directory.strip() else 'ルート'})")
            finally:
                if temp_image_path and os.path.exists(temp_image_path):
                    os.remove(temp_image_path)
        
        if question.strip() != "":
            question_text_margin_x = 5 * mm
            question_text_max_width = card_width - (question_text_margin_x * 2) 
            question_text_max_height = question_text_height - (5 * mm)
            
            draw_wrapped_text(c_front, question, question_text_x_center, question_text_area_y_center, 
                                 'IPAexGothic', 12, question_text_max_width, question_text_max_height)

    # --- カード裏面の描画（ページ順とカード左右を反転） ---
    # 裏面を最後のページから逆順に描画するため、まず全ページ分のデータを準備し、逆順で処理
    # back_pages_data[0]は表面の1ページ目に対応する裏面のカードデータ、back_pages_data[num_pages-1]は表面の最終ページに対応する裏面のカードデータ
    back_pages_data = [[] for _ in range(num_pages)]

    for i, (question, answer, image_directory, image_filename, image_description) in enumerate(qa_pairs):
        page_idx = i // cards_per_page
        card_on_page_idx = i % cards_per_page

        row_idx = card_on_page_idx // cards_per_row
        col_idx = card_on_page_idx % cards_per_row

        # 裏面のX座標を鏡合わせになるように計算
        x_pos_back = (cards_per_row - 1 - col_idx) * card_width
        y_pos_back = A4[1] - (row_idx + 1) * card_height # Y座標は表面と同じ

        back_pages_data[page_idx].append({
            'answer': answer,
            'x_pos_back': x_pos_back,
            'y_pos_back': y_pos_back,
            'card_width': card_width,
            'card_height': card_height
        })

    # 裏面PDFのページを、表面の最終ページから逆順に描画
    # reversed(back_pages_data) は、[最終ページのデータ, ... , 最初のページのデータ] の順で処理される
    for page_content_index, page_content in enumerate(reversed(back_pages_data)):
        # 最初の物理ページ以外は新しいページを追加
        # reversedループの初回 (back_pages_dataの最終ページ) では showPage() を呼ばない
        if page_content_index > 0:
            c_back.showPage()

        for card_data in page_content:
            # 切り取り線の描画
            c_back.setStrokeColorRGB(0.8, 0.8, 0.8)
            c_back.setLineWidth(0.3)
            c_back.rect(card_data['x_pos_back'], card_data['y_pos_back'], card_data['card_width'], card_data['card_height'])
            
            # 解答文の描画
            answer_text_area_y_center = card_data['y_pos_back'] + card_data['card_height'] / 2
            answer_text_x_center = card_data['x_pos_back'] + card_data['card_width'] / 2
            answer_text_max_width = card_data['card_width'] - (5 * mm * 2)
            answer_text_max_height = card_data['card_height'] - (5 * mm)

            draw_wrapped_text(c_back, card_data['answer'], answer_text_x_center, answer_text_area_y_center, 
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
    csv_file_path = ""
    cards_per_row_input = 0
    cards_per_col_input = 0

    # コマンドライン引数の解析
    # python script.py [csv_file_path] [cards_per_row] [cards_per_col]
    if len(sys.argv) > 1:
        csv_file_path = sys.argv[1]
        if len(sys.argv) > 3:
            try:
                cards_per_row_input = int(sys.argv[2])
                cards_per_col_input = int(sys.argv[3])
            except ValueError:
                print("エラー: 横の枚数と縦の枚数は整数で指定してください。")
                sys.exit(1)
        # コマンドライン引数からCSVファイルパスが与えられた場合でも、空でないことを確認
        if not csv_file_path.strip():
            print("エラー: コマンドライン引数で指定されたCSVファイル名が空です。")
            sys.exit(1)
        print(f"コマンドライン引数からCSVファイルパス '{csv_file_path}' を取得しました。")
    
    # コマンドライン引数がない、またはCSVファイル名が指定されていない場合
    # ここでcsv_file_pathがまだ設定されていない場合にユーザーに尋ねる
    while not csv_file_path.strip(): # 空白文字のみも許容しない
        csv_file_path = input("使用するCSVファイル名を入力してください (例: my_flashcards.csv): ").strip()
        if not csv_file_path.strip():
            print("CSVファイル名が入力されていません。再度入力してください。")
        
    # CSVファイルの存在確認と新規作成の確認
    if not os.path.exists(csv_file_path):
        create_new = input(f"'{csv_file_path}' が見つかりません。新しく作成しますか？ (y/n): ").lower()
        if create_new != 'y':
            print("CSVファイルの作成をキャンセルしました。プログラムを終了します。")
            sys.exit(0)
        # 新規作成の場合は、append_to_csvがヘッダーを書き込む

    # カード枚数の入力（コマンドライン引数で指定されていない場合）
    if cards_per_row_input == 0 or cards_per_col_input == 0:
        while True: # 有効な整数が入力されるまでループ
            try:
                cards_per_row_input = int(input("1ページあたりのカードの横の枚数を入力してください (例: 2): "))
                cards_per_col_input = int(input("1ページあたりのカードの縦の枚数を入力してください (例: 3): "))
            except ValueError:
                print("エラー: 無効な入力です。横と縦の枚数は整数で入力してください。")
            break # 有効な入力が得られたらループを抜ける

    # CSVへのカード追加
    add_cards = input("単語カードを追加しますか？ (y/n): ").lower()
    if add_cards == 'y':
        append_to_csv(csv_file_path)

    # PDF生成
    create_flashcards_pdf(csv_file_path, cards_per_row_input, cards_per_col_input)
