from pypdf import PdfReader, PdfWriter

def interleave_pdfs(math1_path, math2_path, output_path):
    """
    算数1.pdfのページを前から、算数2.pdfのページを後ろから一枚ずつ順に結合します。

    Args:
        math1_path (str): 算数1.pdfのパス。
        math2_path (str): 算数2.pdfのパス。
        output_path (str): 最終的な出力PDFファイルのパス。
    """
    try:
        reader_math1 = PdfReader(math1_path)
        reader_math2 = PdfReader(math2_path)
        writer = PdfWriter()

        # 算数1のページリスト (前から順)
        math1_pages = reader_math1.pages
        
        # 算数2のページリスト (後ろから順にするため、先にリスト化して逆順にする)
        math2_pages = list(reader_math2.pages) # reader.pagesは直接reverseできない場合があるためリスト化
        math2_pages.reverse() # 後ろから順にする

        print(f"'{math1_path}' から {len(math1_pages)} ページを読み込みました。")
        print(f"'{math2_path}' から {len(math2_pages)} ページを読み込みました。")

        # ページを交互に追加していく
        # どちらかのリストがなくなるまで続ける
        max_len = max(len(math1_pages), len(math2_pages))

        for i in range(max_len):
            # 算数1のページを追加
            if i < len(math1_pages):
                writer.add_page(math1_pages[i])
            
            # 算数2のページを追加 (逆順になっているため、ここに追加されるのは元々の最後のページから)
            if i < len(math2_pages):
                writer.add_page(math2_pages[i])

        # 新しいPDFを保存
        with open(output_path, "wb") as output_file:
            writer.write(output_file)
        
        print(f"PDFファイルの結合が完了しました。'{output_path}' に保存されました。")

    except FileNotFoundError as e:
        print(f"エラー: ファイルが見つかりません。{e}")
    except Exception as e:
        print(f"処理中に予期せぬエラーが発生しました: {e}")

# メイン処理
if __name__ == "__main__":
    # ここにPDFファイル名を指定してください
    # 例として「算数1.pdf」と「算数2.pdf」と仮定します
    math1_pdf = "算数1.pdf" 
    math2_pdf = "算数2.pdf"
    output_combined_pdf = "combined_math_book.pdf"

    interleave_pdfs(math1_pdf, math2_pdf, output_combined_pdf)