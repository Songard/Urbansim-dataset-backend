import os
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from config import Config
from utils.logger import get_logger

logger = get_logger(__name__)

class SheetsWriter:
    def __init__(self):
        self.credentials = None
        self.service = None
        self.spreadsheet_id = Config.SPREADSHEET_ID
        self.sheet_name = Config.SHEET_NAME
        self.headers = [
            'File ID', 'File Name', 'Upload Time', 'File Size', 'File Type',
            'Extract Status', 'File Count', 'Process Time', 'Validation Score', 'Error Message', 'Notes'
        ]
        self._initialize_service()
        
    def _initialize_service(self):
        try:
            self.credentials = service_account.Credentials.from_service_account_file(
                Config.SERVICE_ACCOUNT_FILE,
                scopes=Config.SCOPES
            )
            self.service = build('sheets', 'v4', credentials=self.credentials)
            logger.info(f"Google Sheets service initialized for spreadsheet: {self.spreadsheet_id}")
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets service: {e}")
            raise
            
    def _get_or_create_headers(self) -> bool:
        try:
            # First, verify the sheet exists and get the correct name
            if not self._verify_and_get_sheet_name():
                return False
            
            range_name = f"'{self.sheet_name}'!A1:K1"
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            
            if not values or len(values[0]) != len(self.headers):
                self._create_headers()
                return True
            else:
                logger.info("Headers already exist in the sheet")
                return True
                
        except HttpError as e:
            if e.resp.status == 400 and "Unable to parse range" in str(e):
                logger.warning(f"Range parsing error, attempting to use first sheet")
                return self._fallback_to_first_sheet()
            logger.error(f"Error checking/creating headers: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in _get_or_create_headers: {e}")
            return False
    
    def _verify_and_get_sheet_name(self) -> bool:
        """Verify sheet exists and get correct name"""
        try:
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            sheets = spreadsheet.get('sheets', [])
            if not sheets:
                logger.error("No sheets found in spreadsheet")
                return False
            
            # Check if our configured sheet name exists
            sheet_names = [sheet['properties']['title'] for sheet in sheets]
            
            if self.sheet_name in sheet_names:
                logger.debug(f"Sheet '{self.sheet_name}' found")
                return True
            else:
                # Use the first available sheet
                self.sheet_name = sheet_names[0]
                logger.info(f"Sheet name updated to first available sheet: '{self.sheet_name}'")
                return True
                
        except Exception as e:
            logger.error(f"Error verifying sheet: {e}")
            return False
    
    def _fallback_to_first_sheet(self) -> bool:
        """Fallback method when range parsing fails"""
        try:
            # Get spreadsheet metadata
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            sheets = spreadsheet.get('sheets', [])
            if sheets:
                first_sheet_name = sheets[0]['properties']['title']
                self.sheet_name = first_sheet_name
                logger.info(f"Using first sheet: '{self.sheet_name}'")
                
                # Try again with proper sheet name
                range_name = f"'{self.sheet_name}'!A1:K1"
                result = self.service.spreadsheets().values().get(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_name
                ).execute()
                
                values = result.get('values', [])
                if not values or len(values[0]) != len(self.headers):
                    self._create_headers()
                
                return True
            else:
                logger.error("No sheets found in spreadsheet")
                return False
                
        except Exception as e:
            logger.error(f"Fallback method failed: {e}")
            return False
            
    def _create_headers(self):
        try:
            range_name = f"'{self.sheet_name}'!A1:K1"
            body = {
                'values': [self.headers]
            }
            
            result = self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                body=body
            ).execute()
            
            self._format_headers()
            logger.info(f"Created headers in sheet: {self.headers}")
            
        except Exception as e:
            logger.error(f"Failed to create headers: {e}")
            raise
            
    def _format_headers(self):
        try:
            requests = [
                {
                    'repeatCell': {
                        'range': {
                            'sheetId': 0,
                            'startRowIndex': 0,
                            'endRowIndex': 1,
                            'startColumnIndex': 0,
                            'endColumnIndex': len(self.headers)
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'textFormat': {'bold': True},
                                'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
                            }
                        },
                        'fields': 'userEnteredFormat(textFormat,backgroundColor)'
                    }
                }
            ]
            
            body = {'requests': requests}
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=body
            ).execute()
            
        except Exception as e:
            logger.warning(f"Failed to format headers: {e}")
            
    def _get_next_empty_row(self) -> int:
        try:
            range_name = f"'{self.sheet_name}'!A:A"
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            return len(values) + 1
            
        except Exception as e:
            logger.error(f"Failed to get next empty row: {e}")
            return 2
            
    def _format_file_size(self, size_bytes: int) -> str:
        if size_bytes is None:
            return "未知"
        
        size_mb = size_bytes / (1024 * 1024)
        return f"{size_mb:.2f} MB"
        
    def _format_datetime(self, dt: Any) -> str:
        if dt is None:
            return ""
            
        if isinstance(dt, str):
            return dt
        elif isinstance(dt, datetime):
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        else:
            return str(dt)
            
    def append_record(self, record: Dict[str, Any]) -> bool:
        max_retries = Config.MAX_RETRY_ATTEMPTS
        
        for attempt in range(max_retries):
            try:
                if not self._get_or_create_headers():
                    return False
                    
                next_row = self._get_next_empty_row()
                range_name = f"'{self.sheet_name}'!A{next_row}:J{next_row}"
                
                formatted_record = [
                    record.get('file_id', ''),
                    record.get('file_name', ''),
                    self._format_datetime(record.get('upload_time')),
                    self._format_file_size(record.get('file_size')),
                    record.get('file_type', ''),
                    record.get('extract_status', '不适用'),
                    record.get('file_count', ''),
                    self._format_datetime(record.get('process_time', datetime.now())),
                    record.get('error_message', ''),
                    record.get('notes', '')
                ]
                
                body = {
                    'values': [formatted_record]
                }
                
                result = self.service.spreadsheets().values().append(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_name,
                    valueInputOption='USER_ENTERED',
                    insertDataOption='INSERT_ROWS',
                    body=body
                ).execute()
                
                logger.info(f"Successfully wrote record to row {next_row}: {record.get('file_name', 'Unknown')}")
                return True
                
            except HttpError as e:
                if e.resp.status in [429, 500, 502, 503, 504] and attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + (attempt * 0.1)
                    logger.warning(f"HTTP error {e.resp.status}, retrying in {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Failed to append record after {attempt + 1} attempts: {e}")
                    return False
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = Config.RETRY_DELAY * (attempt + 1)
                    logger.warning(f"Error writing to sheet, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries}): {e}")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Failed to append record after {max_retries} attempts: {e}")
                    return False
                    
        return False
        
    def batch_append_records(self, records: List[Dict[str, Any]]) -> bool:
        if not records:
            return True
            
        max_retries = Config.MAX_RETRY_ATTEMPTS
        batch_size = Config.BATCH_WRITE_SIZE
        
        for attempt in range(max_retries):
            try:
                if not self._get_or_create_headers():
                    return False
                
                for i in range(0, len(records), batch_size):
                    batch = records[i:i + batch_size]
                    next_row = self._get_next_empty_row()
                    
                    formatted_records = []
                    for record in batch:
                        formatted_record = [
                            record.get('file_id', ''),
                            record.get('file_name', ''),
                            self._format_datetime(record.get('upload_time')),
                            self._format_file_size(record.get('file_size')),
                            record.get('file_type', ''),
                            record.get('extract_status', '不适用'),
                            record.get('file_count', ''),
                            self._format_datetime(record.get('process_time', datetime.now())),
                            record.get('error_message', ''),
                            record.get('notes', '')
                        ]
                        formatted_records.append(formatted_record)
                    
                    range_name = f"'{self.sheet_name}'!A{next_row}:J{next_row + len(batch) - 1}"
                    body = {
                        'values': formatted_records
                    }
                    
                    result = self.service.spreadsheets().values().append(
                        spreadsheetId=self.spreadsheet_id,
                        range=range_name,
                        valueInputOption='USER_ENTERED',
                        insertDataOption='INSERT_ROWS',
                        body=body
                    ).execute()
                    
                    logger.info(f"Successfully wrote batch of {len(batch)} records starting at row {next_row}")
                    
                    if i + batch_size < len(records):
                        time.sleep(0.1)
                        
                return True
                
            except HttpError as e:
                if e.resp.status in [429, 500, 502, 503, 504] and attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + (attempt * 0.1)
                    logger.warning(f"HTTP error {e.resp.status}, retrying batch write in {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Failed to batch append records after {attempt + 1} attempts: {e}")
                    return False
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = Config.RETRY_DELAY * (attempt + 1)
                    logger.warning(f"Error in batch write, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries}): {e}")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Failed to batch append records after {max_retries} attempts: {e}")
                    return False
                    
        return False
        
    def test_connection(self) -> bool:
        try:
            result = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            sheet_title = result['properties']['title']
            logger.info(f"Successfully connected to spreadsheet: {sheet_title}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to spreadsheet: {e}")
            return False