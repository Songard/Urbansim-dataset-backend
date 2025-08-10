#!/usr/bin/env python3
"""
检查Google Sheets中的Location列数据
"""

from sheets.sheets_writer import SheetsWriter

def check_location_in_sheets():
    """检查Google Sheets中的Location数据"""
    try:
        writer = SheetsWriter()
        service = writer.service
        
        # 获取sheet信息
        spreadsheet = service.spreadsheets().get(
            spreadsheetId=writer.spreadsheet_id
        ).execute()
        
        sheets = spreadsheet.get('sheets', [])
        if not sheets:
            print("No sheets found")
            return
        
        sheet_id = sheets[0]['properties']['sheetId']
        
        # 使用A1:N格式读取所有数据（避免中文sheet名称问题）
        range_name = "A1:N"
        result = service.spreadsheets().values().get(
            spreadsheetId=writer.spreadsheet_id,
            range=range_name
        ).execute()
        
        values = result.get('values', [])
        print(f"Total rows: {len(values)}")
        
        if not values:
            print("No data found")
            return
        
        # 获取headers
        headers = values[0]
        print("Headers:")
        for i, header in enumerate(headers):
            print(f"  {i}: {repr(header)}")
        
        # Location应该在第12列（索引11）
        location_col_index = 11
        if len(headers) <= location_col_index:
            print(f"ERROR: Location column (index {location_col_index}) not found!")
            return
        
        print(f"\nLocation column header: {repr(headers[location_col_index])}")
        print("\nRecent Location data:")
        
        # 检查最近的数据行
        for i in range(max(1, len(values)-10), len(values)):
            if i < len(values):
                row = values[i]
                file_name = row[1] if len(row) > 1 else "N/A"
                location = row[location_col_index] if len(row) > location_col_index else ""
                print(f"  Row {i+1}: {file_name} -> Location: '{location}'")
        
        # 统计空位置的数量
        empty_locations = 0
        total_data_rows = len(values) - 1  # 减去header行
        
        for i in range(1, len(values)):
            row = values[i]
            location = row[location_col_index] if len(row) > location_col_index else ""
            if not location or location.strip() == "":
                empty_locations += 1
        
        print(f"\nSummary:")
        print(f"  Total data rows: {total_data_rows}")
        print(f"  Empty locations: {empty_locations}")
        print(f"  Non-empty locations: {total_data_rows - empty_locations}")
        
        if empty_locations == total_data_rows:
            print("  ALL LOCATIONS ARE EMPTY!")
        elif empty_locations > 0:
            print(f"  {empty_locations}/{total_data_rows} locations are empty")
        else:
            print("  All locations have data")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_location_in_sheets()