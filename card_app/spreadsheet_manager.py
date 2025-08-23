# spreadsheet_manager.py
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import re

def get_spreadsheet_data(spreadsheet_id, sheet_name, credentials_path):
    """
    指定されたスプレッドシートからデータを取得します。
    
    Args:
        spreadsheet_id (str): GoogleスプレッドシートのID。
        sheet_name (str): データを取得するシート名。
        credentials_path (str): サービスアカウントキーファイルのパス。
        
    Returns:
        list: スプレッドシートの各行を辞書としたリスト。
              各辞書には 'question', 'answer', 'image_filename' のキーが含まれます。
    """
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_path, scope)
        gc = gspread.authorize(creds)
        
        workbook = gc.open_by_key(spreadsheet_id)
        worksheet = workbook.worksheet(sheet_name)
        
        # ヘッダーを取得
        headers = [header.lower().replace(' ', '_') for header in worksheet.row_values(1)]
        
        records = worksheet.get_all_records()
        
        # 必要なデータのみを抽出し、キー名を統一
        processed_records = []
        for record in records:
            new_record = {}
            if 'question' in headers and record.get('question'):
                new_record['question'] = record['question']
            if 'answer' in headers and record.get('answer'):
                new_record['answer'] = record['answer']
            if 'image_filename' in headers and record.get('image_filename'):
                new_record['image_filename'] = record['image_filename']
            processed_records.append(new_record)
            
        return processed_records
        
    except Exception as e:
        print(f"Error getting spreadsheet data: {e}")
        return []
