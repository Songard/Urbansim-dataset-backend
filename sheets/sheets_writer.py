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
            'Extract Status', 'File Count', 'Process Time', 'Validation Score', 
            'Start Time', 'Duration', 'Location', 'Scene Type', 'Size Status', 
            'PCD Scale', 'Error Message', 'Notes'
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
            
            range_name = f"'{self.sheet_name}'!A1:Q1"
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
                range_name = f"'{self.sheet_name}'!A1:Q1"
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
            range_name = f"'{self.sheet_name}'!A1:Q1"
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
    
    def _format_duration_cell(self, row_number: int, duration_status: str):
        """Apply color formatting to Duration cell based on status"""
        if not duration_status:
            return
            
        try:
            # Duration is column K (index 10, 0-based)
            duration_column = 10
            
            # Define colors based on status
            colors = {
                'optimal': {'red': 0.85, 'green': 0.95, 'blue': 0.85},        # Light green
                'warning_short': {'red': 1.0, 'green': 0.95, 'blue': 0.8},   # Light yellow
                'warning_long': {'red': 1.0, 'green': 0.95, 'blue': 0.8},    # Light yellow  
                'error_too_short': {'red': 1.0, 'green': 0.85, 'blue': 0.85}, # Light red
                'error_too_long': {'red': 1.0, 'green': 0.85, 'blue': 0.85},  # Light red
                'parse_error': {'red': 0.9, 'green': 0.9, 'blue': 0.9}        # Light gray
            }
            
            background_color = colors.get(duration_status, colors['parse_error'])
            
            # Get sheet ID for formatting
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            sheet_id = None
            for sheet in spreadsheet.get('sheets', []):
                if sheet['properties']['title'] == self.sheet_name:
                    sheet_id = sheet['properties']['sheetId']
                    break
            
            if sheet_id is None:
                logger.warning(f"Could not find sheet ID for '{self.sheet_name}'")
                return
            
            requests = [
                {
                    'repeatCell': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': row_number - 1,  # 0-based
                            'endRowIndex': row_number,
                            'startColumnIndex': duration_column,
                            'endColumnIndex': duration_column + 1
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'backgroundColor': background_color
                            }
                        },
                        'fields': 'userEnteredFormat.backgroundColor'
                    }
                }
            ]
            
            body = {'requests': requests}
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=body
            ).execute()
            
            logger.debug(f"Applied {duration_status} formatting to row {row_number}, column {duration_column}")
            
        except Exception as e:
            logger.warning(f"Failed to format duration cell for row {row_number}: {e}")
    
    def _format_size_status_cell(self, row_number: int, size_status: str):
        """Apply color formatting to Size Status cell based on status"""
        if not size_status:
            return
            
        try:
            # Size Status is column N (index 13, 0-based)
            size_status_column = 13
            
            # Define colors based on size status
            colors = {
                'optimal': {'red': 0.85, 'green': 0.95, 'blue': 0.85},        # Light green
                'warning_small': {'red': 1.0, 'green': 0.95, 'blue': 0.8},   # Light yellow
                'warning_large': {'red': 1.0, 'green': 0.95, 'blue': 0.8},   # Light yellow  
                'error_too_small': {'red': 1.0, 'green': 0.85, 'blue': 0.85}, # Light red
                'error_too_large': {'red': 1.0, 'green': 0.85, 'blue': 0.85}, # Light red
                'unknown': {'red': 0.9, 'green': 0.9, 'blue': 0.9}           # Light gray
            }
            
            background_color = colors.get(size_status, colors['unknown'])
            
            # Get sheet ID for formatting
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            sheet_id = None
            for sheet in spreadsheet.get('sheets', []):
                if sheet['properties']['title'] == self.sheet_name:
                    sheet_id = sheet['properties']['sheetId']
                    break
            
            if sheet_id is None:
                logger.warning(f"Could not find sheet ID for '{self.sheet_name}'")
                return
            
            requests = [
                {
                    'repeatCell': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': row_number - 1,  # 0-based
                            'endRowIndex': row_number,
                            'startColumnIndex': size_status_column,
                            'endColumnIndex': size_status_column + 1
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'backgroundColor': background_color
                            }
                        },
                        'fields': 'userEnteredFormat.backgroundColor'
                    }
                }
            ]
            
            body = {'requests': requests}
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=body
            ).execute()
            
            logger.debug(f"Applied {size_status} formatting to row {row_number}, column {size_status_column}")
            
        except Exception as e:
            logger.warning(f"Failed to format size status cell for row {row_number}: {e}")
    
    def _format_pcd_scale_cell(self, row_number: int, pcd_status: str):
        """Apply color formatting to PCD Scale cell based on status"""
        if not pcd_status:
            return
            
        try:
            # PCD Scale is column O (index 14, 0-based)
            pcd_scale_column = 14
            
            # Define colors based on PCD scale status
            colors = {
                'optimal': {'red': 0.85, 'green': 0.95, 'blue': 0.85},        # Light green
                'warning_small': {'red': 1.0, 'green': 0.95, 'blue': 0.8},   # Light yellow
                'warning_large': {'red': 1.0, 'green': 0.95, 'blue': 0.8},   # Light yellow
                'warning_narrow': {'red': 1.0, 'green': 0.95, 'blue': 0.8},  # Light yellow
                'error_too_small': {'red': 1.0, 'green': 0.85, 'blue': 0.85}, # Light red
                'error_too_large': {'red': 1.0, 'green': 0.85, 'blue': 0.85}, # Light red
                'not_found': {'red': 0.9, 'green': 0.9, 'blue': 0.9},        # Light gray
                'error': {'red': 0.9, 'green': 0.9, 'blue': 0.9},            # Light gray
                'unknown': {'red': 0.9, 'green': 0.9, 'blue': 0.9}           # Light gray
            }
            
            background_color = colors.get(pcd_status, colors['unknown'])
            
            # Get sheet ID for formatting
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            sheet_id = None
            for sheet in spreadsheet.get('sheets', []):
                if sheet['properties']['title'] == self.sheet_name:
                    sheet_id = sheet['properties']['sheetId']
                    break
            
            if sheet_id is None:
                logger.warning(f"Could not find sheet ID for '{self.sheet_name}'")
                return
            
            requests = [
                {
                    'repeatCell': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': row_number - 1,  # 0-based
                            'endRowIndex': row_number,
                            'startColumnIndex': pcd_scale_column,
                            'endColumnIndex': pcd_scale_column + 1
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'backgroundColor': background_color
                            }
                        },
                        'fields': 'userEnteredFormat.backgroundColor'
                    }
                }
            ]
            
            body = {'requests': requests}
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=body
            ).execute()
            
            logger.debug(f"Applied {pcd_status} formatting to row {row_number}, column {pcd_scale_column}")
            
        except Exception as e:
            logger.warning(f"Failed to format PCD scale cell for row {row_number}: {e}")
            
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
                range_name = f"'{self.sheet_name}'!A{next_row}:Q{next_row}"
                
                # Extract metadata information if available
                validation_result = record.get('validation_result') or {}
                
                # Handle ValidationResult object
                if hasattr(validation_result, 'metadata'):
                    # ValidationResult object
                    metadata = validation_result.metadata or {}
                elif isinstance(validation_result, dict):
                    # Dictionary format
                    metadata = validation_result.get('metadata', {})
                else:
                    # Invalid type, default to empty
                    metadata = {}
                    
                extracted_metadata = metadata.get('extracted_metadata', {})
                
                # Format location as coordinate pair
                location_str = ""
                if extracted_metadata.get('location'):
                    lat = extracted_metadata['location'].get('latitude', '')
                    lon = extracted_metadata['location'].get('longitude', '')
                    if lat and lon:
                        location_str = f"{lat}, {lon}"
                
                # Format duration to prevent auto-conversion to time format
                duration_raw = extracted_metadata.get('duration', '')
                duration_formatted = f"'{duration_raw}" if duration_raw else ''  # Prefix with ' to force text format
                
                # 获取场景类型、大小状态和PCD尺度信息
                scene_type = record.get('scene_type', '')
                size_status = record.get('size_status', '')
                pcd_scale = record.get('pcd_scale', '')
                
                formatted_record = [
                    record.get('file_id', ''),
                    record.get('file_name', ''),
                    self._format_datetime(record.get('upload_time')),
                    self._format_file_size(record.get('file_size')),
                    record.get('file_type', ''),
                    record.get('extract_status', '不适用'),
                    record.get('file_count', ''),
                    self._format_datetime(record.get('process_time', datetime.now())),
                    record.get('validation_score', ''),
                    extracted_metadata.get('start_time', ''),
                    duration_formatted,  # Use formatted duration
                    location_str,
                    scene_type,  # Scene Type column
                    size_status,  # Size Status column
                    pcd_scale,   # PCD Scale column
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
                
                # Apply duration status formatting if available
                duration_status = extracted_metadata.get('duration_status')
                if duration_status:
                    self._format_duration_cell(next_row, duration_status)
                
                # Apply size status formatting if available
                size_status_level = record.get('size_status_level')
                if size_status_level:
                    self._format_size_status_cell(next_row, size_status_level)
                
                # Apply PCD scale formatting if available  
                pcd_scale_status = record.get('pcd_scale_status')
                if pcd_scale_status:
                    self._format_pcd_scale_cell(next_row, pcd_scale_status)
                
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
                        # Extract metadata information if available
                        validation_result = record.get('validation_result') or {}
                        
                        # Handle ValidationResult object
                        if hasattr(validation_result, 'metadata'):
                            # ValidationResult object
                            metadata = validation_result.metadata or {}
                        elif isinstance(validation_result, dict):
                            # Dictionary format
                            metadata = validation_result.get('metadata', {})
                        else:
                            # Invalid type, default to empty
                            metadata = {}
                            
                        extracted_metadata = metadata.get('extracted_metadata', {})
                        
                        # Format location as coordinate pair
                        location_str = ""
                        if extracted_metadata.get('location'):
                            lat = extracted_metadata['location'].get('latitude', '')
                            lon = extracted_metadata['location'].get('longitude', '')
                            if lat and lon:
                                location_str = f"{lat}, {lon}"
                        
                        # Format duration to prevent auto-conversion to time format
                        duration_raw = extracted_metadata.get('duration', '')
                        duration_formatted = f"'{duration_raw}" if duration_raw else ''
                        
                        # 获取场景类型、大小状态和PCD尺度信息
                        scene_type = record.get('scene_type', '')
                        size_status = record.get('size_status', '')
                        pcd_scale = record.get('pcd_scale', '')
                        
                        formatted_record = [
                            record.get('file_id', ''),
                            record.get('file_name', ''),
                            self._format_datetime(record.get('upload_time')),
                            self._format_file_size(record.get('file_size')),
                            record.get('file_type', ''),
                            record.get('extract_status', '不适用'),
                            record.get('file_count', ''),
                            self._format_datetime(record.get('process_time', datetime.now())),
                            record.get('validation_score', ''),
                            extracted_metadata.get('start_time', ''),
                            duration_formatted,  # Use formatted duration
                            location_str,
                            scene_type,  # Scene Type column
                            size_status,  # Size Status column
                            pcd_scale,   # PCD Scale column
                            record.get('error_message', ''),
                            record.get('notes', '')
                        ]
                        formatted_records.append(formatted_record)
                    
                    range_name = f"'{self.sheet_name}'!A{next_row}:Q{next_row + len(batch) - 1}"
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
                    
                    # Apply status formatting for batch
                    for j, record in enumerate(batch):
                        validation_result = record.get('validation_result') or {}
                        
                        # Handle ValidationResult object
                        if hasattr(validation_result, 'metadata'):
                            metadata = validation_result.metadata or {}
                        elif isinstance(validation_result, dict):
                            metadata = validation_result.get('metadata', {})
                        else:
                            metadata = {}
                            
                        extracted_metadata = metadata.get('extracted_metadata', {})
                        
                        # Duration formatting
                        duration_status = extracted_metadata.get('duration_status')
                        if duration_status:
                            self._format_duration_cell(next_row + j, duration_status)
                        
                        # Size status formatting
                        size_status_level = record.get('size_status_level')
                        if size_status_level:
                            self._format_size_status_cell(next_row + j, size_status_level)
                        
                        # PCD scale formatting
                        pcd_scale_status = record.get('pcd_scale_status')
                        if pcd_scale_status:
                            self._format_pcd_scale_cell(next_row + j, pcd_scale_status)
                    
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