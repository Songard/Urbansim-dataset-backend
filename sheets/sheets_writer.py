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
        # 使用标准化的headers定义
        self.headers = [
            'File ID', 'File Name', 'Upload Time', 'File Size', 'File Type',
            'Extract Status', 'File Count', 'Process Time', 'Validation Score', 
            'Start Time', 'Duration', 'Location', 'Scene Type', 'Size Status', 
            'PCD Scale', 'Transient Detection', 'Weighted Detection Density', 'Weighted Person Occupancy', 'Scene Activity Index', 'Error Message', 'Notes'
        ]
        
        # 定义字段到headers的映射 - 这样添加新字段时更清晰
        self.field_mapping = {
            'file_id': 0, 'file_name': 1, 'upload_time': 2, 'file_size': 3, 'file_type': 4,
            'extract_status': 5, 'file_count': 6, 'process_time': 7, 'validation_score': 8,
            'start_time': 9, 'duration': 10, 'location': 11, 'scene_type': 12, 'size_status': 13,
            'pcd_scale': 14, 'transient_decision': 15, 'wdd': 16, 'wpo': 17, 'sai': 18,
            'error_message': 19, 'notes': 20
        }
        self._initialize_service()
    
    def prepare_record_row(self, record: Dict[str, Any]) -> List[Any]:
        """
        将record转换为sheets行数据 - 统一的数据准备方法
        
        这个方法简化了数据准备流程，减少重复代码和出错机会
        """
        from .data_mapper import SheetsDataMapper
        
        # 使用统一的数据映射器
        normalized_record = SheetsDataMapper.map_validation_result(
            record.get('validation_result'), 
            record
        )
        
        # 格式化时间字段
        process_time = self._format_datetime(normalized_record.get('process_time'))
        
        # 按照字段映射的顺序构建行数据
        row_data = [''] * len(self.headers)  # 初始化空行
        
        for field, index in self.field_mapping.items():
            value = normalized_record.get(field, '')
            if field == 'process_time':
                value = process_time
            elif field == 'file_size' and value:
                value = f"{int(value) / (1024*1024):.2f} MB"
            row_data[index] = str(value) if value is not None else ''
        
        return row_data
        
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
            
            range_name = f"'{self.sheet_name}'!A1:U1"
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
                range_name = f"'{self.sheet_name}'!A1:U1"
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
            range_name = f"'{self.sheet_name}'!A1:U1"
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
    
    def _format_transient_detection_cell(self, row_number: int, transient_decision: str):
        """Apply color formatting to Transient Detection cell based on decision"""
        if not transient_decision:
            return
            
        try:
            # Transient Detection is column P (index 15, 0-based)
            transient_column = 15
            
            # Define colors based on detection decision
            colors = {
                'PASS': {'red': 0.85, 'green': 0.95, 'blue': 0.85},          # Light green
                'NEED_REVIEW': {'red': 1.0, 'green': 0.95, 'blue': 0.8},    # Light yellow
                'REJECT': {'red': 1.0, 'green': 0.85, 'blue': 0.85},        # Light red
                'ERROR': {'red': 0.9, 'green': 0.9, 'blue': 0.9}           # Light gray
            }
            
            background_color = colors.get(transient_decision, colors['ERROR'])
            
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
                            'startColumnIndex': transient_column,
                            'endColumnIndex': transient_column + 1
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
            
            logger.debug(f"Applied {transient_decision} formatting to row {row_number}, column {transient_column}")
            
        except Exception as e:
            logger.warning(f"Failed to format transient detection cell for row {row_number}: {e}")
            
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
            
    def append_record_v2(self, record: Dict[str, Any]) -> bool:
        """
        新版本的append_record - 使用统一的数据映射器
        推荐使用这个方法来避免数据传递错误
        """
        max_retries = Config.MAX_RETRY_ATTEMPTS
        
        for attempt in range(max_retries):
            try:
                if not self._get_or_create_headers():
                    return False
                    
                next_row = self._get_next_empty_row()
                range_name = f"'{self.sheet_name}'!A{next_row}:U{next_row}"
                
                # 使用统一的数据准备方法
                formatted_record = self.prepare_record_row(record)
                
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
                if e.resp.status in [429, 503]:  # Rate limit or service unavailable
                    wait_time = Config.RETRY_DELAY * (attempt + 1)
                    logger.warning(f"Rate limit/service error, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries}): {e}")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Failed to append record after {max_retries} attempts: {e}")
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

    def append_record(self, record: Dict[str, Any]) -> bool:
        max_retries = Config.MAX_RETRY_ATTEMPTS
        
        for attempt in range(max_retries):
            try:
                if not self._get_or_create_headers():
                    return False
                    
                next_row = self._get_next_empty_row()
                range_name = f"'{self.sheet_name}'!A{next_row}:U{next_row}"
                
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
                
                # ===== TRANSIENT检测数据提取契约 =====
                # 数据来源优先级：
                # 1. main.py准备的直接字段（推荐）
                # 2. validation_result.metadata中的原始数据（fallback）
                #
                # 数据路径契约：metadata.transient_validation.transient_detection
                # 必须包含：decision, metrics.WDD, metrics.WPO, metrics.SAI
                
                transient_detection = record.get('transient_decision', '')
                wdd_value = record.get('wdd', '')
                wpo_value = record.get('wpo', '')
                sai_value = record.get('sai', '')
                
                # Fallback：如果main.py中没有提供这些字段，从validation_result中提取
                if not transient_detection and not wdd_value and validation_result:
                    # 获取metadata（支持字典和对象两种格式）
                    if hasattr(validation_result, 'metadata'):
                        metadata = validation_result.metadata or {}
                    elif isinstance(validation_result, dict):
                        metadata = validation_result.get('metadata', {})
                    else:
                        metadata = {}
                    
                    # 遵循标准数据路径：metadata.transient_validation.transient_detection
                    transient_validation = metadata.get('transient_validation', {})
                    transient_data = transient_validation.get('transient_detection', {})
                    if transient_data:
                        # 提取决策（必须来自ValidationDecisionContract）
                        transient_detection = transient_data.get('decision', '')
                        
                        # 提取指标（遵循标准格式化）
                        transient_metrics = transient_data.get('metrics', {})
                        wdd_value = f"{transient_metrics.get('WDD', 0):.3f}" if 'WDD' in transient_metrics else ""
                        wpo_value = f"{transient_metrics.get('WPO', 0):.1f}%" if 'WPO' in transient_metrics else ""
                        sai_value = f"{transient_metrics.get('SAI', 0):.1f}%" if 'SAI' in transient_metrics else ""
                
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
                    transient_detection,  # Transient Detection column
                    wdd_value,  # WDD column
                    wpo_value,  # WPO column
                    sai_value,  # SAI column
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
                
                # Apply transient detection formatting if available
                if transient_detection:
                    self._format_transient_detection_cell(next_row, transient_detection)
                
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
                        
                        # 提取移动障碍物检测结果
                        transient_detection = record.get('transient_decision', '')
                        wdd_value = record.get('wdd', '')
                        wpo_value = record.get('wpo', '')
                        sai_value = record.get('sai', '')
                        
                        # 如果main.py中没有提供这些字段，尝试从validation_result中提取
                        if not transient_detection and not wdd_value:
                            # 修正数据路径：transient_validation -> transient_detection
                            transient_validation = metadata.get('transient_validation', {})
                            transient_data = transient_validation.get('transient_detection', {})
                            if transient_data:
                                transient_detection = transient_data.get('decision', '')
                                transient_metrics = transient_data.get('metrics', {})
                                wdd_value = f"{transient_metrics.get('WDD', 0):.3f}" if 'WDD' in transient_metrics else ""
                                wpo_value = f"{transient_metrics.get('WPO', 0):.1f}%" if 'WPO' in transient_metrics else ""
                                sai_value = f"{transient_metrics.get('SAI', 0):.1f}%" if 'SAI' in transient_metrics else ""
                        
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
                            transient_detection,  # Transient Detection column
                            wdd_value,  # WDD column
                            wpo_value,  # WPO column
                            sai_value,  # SAI column
                            record.get('error_message', ''),
                            record.get('notes', '')
                        ]
                        formatted_records.append(formatted_record)
                    
                    range_name = f"'{self.sheet_name}'!A{next_row}:U{next_row + len(batch) - 1}"
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
                        
                        # Transient detection formatting
                        batch_transient_data = metadata.get('transient_detection', {})
                        batch_transient_decision = batch_transient_data.get('decision', '') if batch_transient_data else ""
                        if batch_transient_decision:
                            self._format_transient_detection_cell(next_row + j, batch_transient_decision)
                    
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