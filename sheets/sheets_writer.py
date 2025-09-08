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
        # Standardized headers - All English
        # 
        # 【添加新字段完整流程说明】
        # 如果要添加新的数据字段到Google Sheets，必须按以下步骤操作：
        #
        # 1. 【数据源确认】在monitor/drive_monitor.py中确保API请求包含所需字段
        #    - 修改get_new_files()方法的fields参数
        #    - 修改get_file_metadata()方法的fields参数
        #    - 确保文件信息字典包含新字段
        #
        # 2. 【Sheets表头】在此文件(sheets/sheets_writer.py)中添加新列标题到headers数组
        #    - 在适当位置添加列名（英文）
        #    - 更新field_mapping字典，添加字段名到列索引的映射
        #    - 更新所有相关格式化方法中的列索引（如果新字段会影响其他列位置）
        #
        # 3. 【数据映射】在sheets/data_mapper.py中添加字段提取逻辑
        #    - 在SHEETS_FIELDS中定义新字段及其类型
        #    - 创建或修改相应的_extract_xxx_info()方法
        #    - 确保在map_validation_result()方法中调用提取逻辑
        #    - 在_fill_default_values()方法中添加默认值
        #
        # 4. 【主程序数据传递】在main.py中确保新字段被包含在sheets_record中
        #    - 修改process_file()方法中的sheets_record构建
        #    - 修改_record_failed_processing()方法中的sheets_record构建
        #    - 确保从file_info正确提取数据传递给sheets_record
        #
        # 5. 【范围更新】更新Google Sheets范围引用
        #    - 修改所有涉及列范围的字符串（如A1:Y1 -> A1:AA1）
        #
        # 【本次Owner/Uploader字段添加遇到的问题分析】
        # 问题根本原因：数据流程中断 - 虽然步骤1、2、3都做了，但步骤4遗漏了
        # 具体表现：
        # - drive_monitor正确获取了owners数据 ✓
        # - sheets_writer正确定义了表头和映射 ✓  
        # - data_mapper有提取逻辑但没被调用 ✓
        # - main.py没有将owners字段传递给sheets_record ✗ <- 关键问题
        # - _fill_default_values分支没有调用owner提取 ✗ <- 次要问题
        #
        # 教训：添加字段时必须检查完整的数据流程，确保每个环节都包含新字段
        #
        self.headers = [
            'Entry ID', 'Validation Status', 'Validation Score', 'File ID', 'File Name', 'Upload Time', 'Device ID', 'Owner Name', 'Uploader Email', 'File Size', 'File Type',
            'Extract Status', 'File Count', 'Train/Val Split', 'File Collection Status', 'Process Time', 'Start Time', 'Duration', 'Location', 'Scene Type', 'Size Status', 
            'PCD Scale', 'Transient Detection', 'Weighted Detection Density', 'Weighted Person Occupancy', 'Scene Activity Index', 'Error Message', 'Warning Message', 'HF Upload Status', 'Notes'
        ]
        
        # Field mapping to headers - reorganized for better readability
        # 注意：添加新字段时，所有后续字段的索引都需要相应调整
        self.field_mapping = {
            'entry_id': 0, 'validation_status': 1, 'validation_score': 2, 'file_id': 3, 'file_name': 4, 
            'upload_time': 5, 'device_id': 6, 'owner_name': 7, 'uploader_email': 8, 'file_size': 9, 'file_type': 10, 'extract_status': 11, 'file_count': 12, 
            'train_val_split': 13, 'file_collection_status': 14, 'process_time': 15, 'start_time': 16, 'duration': 17, 'location': 18, 'scene_type': 19, 
            'size_status': 20, 'pcd_scale': 21, 'transient_decision': 22, 'wdd': 23, 'wpo': 24, 
            'sai': 25, 'error_message': 26, 'warning_message': 27, 'hf_upload_status': 28, 'notes': 29
        }
        self._initialize_service()
    
    def prepare_record_row(self, record: Dict[str, Any]) -> List[Any]:
        """
        Convert record to sheets row data - unified data preparation method
        
        This method simplifies data preparation, reduces duplicate code and errors
        """
        from .data_mapper import SheetsDataMapper
        
        # Use unified data mapper
        normalized_record = SheetsDataMapper.map_validation_result(
            record.get('validation_result'), 
            record
        )
        
        # Generate entry ID (sequential number)
        entry_id = self._get_next_entry_id()
        
        # Generate validation status based on score and errors
        validation_status = self._determine_validation_status(normalized_record)
        
        # Format time fields
        process_time = self._format_datetime(normalized_record.get('process_time'))
        
        # Build row data according to field mapping order
        row_data = [''] * len(self.headers)  # Initialize empty row
        
        # Add entry ID and validation status first
        normalized_record['entry_id'] = entry_id
        normalized_record['validation_status'] = validation_status
        
        for field, index in self.field_mapping.items():
            value = normalized_record.get(field, '')
            if field == 'process_time':
                value = process_time
            elif field == 'file_size' and value:
                value = f"{int(value) / (1024*1024):.2f} MB"
            elif field == 'duration' and value:
                # Duration should already be formatted by data_mapper, but ensure it's not a raw number
                if isinstance(value, (int, float)):
                    from .data_mapper import SheetsDataMapper
                    value = SheetsDataMapper._format_duration(value)
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
            
            range_name = f"'{self.sheet_name}'!A1:AC1"
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
                range_name = f"'{self.sheet_name}'!A1:AC1"
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
            range_name = f"'{self.sheet_name}'!A1:AC1"
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
            # Duration is column R (index 17, 0-based) - shifted due to Entry ID, Validation Status, Device ID, Owner Name, Owner Email, Train/Val Split, File Collection Status
            duration_column = 17
            
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
            # Size Status is column U (index 20, 0-based) - shifted due to Entry ID, Validation Status, Device ID, Owner Name, Owner Email, Train/Val Split, File Collection Status
            size_status_column = 20
            
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
            # PCD Scale is column V (index 21, 0-based) - shifted due to Entry ID, Validation Status, Device ID, Owner Name, Owner Email, Train/Val Split, File Collection Status
            pcd_scale_column = 21
            
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
            # Transient Detection is column W (index 22, 0-based) - shifted due to Entry ID, Validation Status, Device ID, Owner Name, Owner Email, Train/Val Split, File Collection Status
            transient_column = 22
            
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
    
    def _format_validation_status_cell(self, row_number: int, validation_status: str):
        """Apply color formatting to Validation Status cell based on status"""
        if not validation_status:
            return
            
        try:
            # Validation Status is column B (index 1, 0-based)
            validation_status_column = 1
            
            # Define colors based on validation status
            colors = {
                'PASSED': {'red': 0.85, 'green': 0.95, 'blue': 0.85},      # Light green
                'WARNING': {'red': 1.0, 'green': 0.95, 'blue': 0.8},      # Light yellow
                'NEEDS_REVIEW': {'red': 1.0, 'green': 0.9, 'blue': 0.8},  # Light orange
                'FAILED': {'red': 1.0, 'green': 0.85, 'blue': 0.85},      # Light red
                'PENDING': {'red': 0.95, 'green': 0.95, 'blue': 1.0},     # Light blue
                'UNKNOWN': {'red': 0.9, 'green': 0.9, 'blue': 0.9}        # Light gray
            }
            
            background_color = colors.get(validation_status, colors['UNKNOWN'])
            
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
                            'startColumnIndex': validation_status_column,
                            'endColumnIndex': validation_status_column + 1
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'backgroundColor': background_color,
                                'textFormat': {'bold': True}
                            }
                        },
                        'fields': 'userEnteredFormat(backgroundColor,textFormat)'
                    }
                }
            ]
            
            body = {'requests': requests}
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=body
            ).execute()
            
            logger.debug(f"Applied {validation_status} formatting to row {row_number}, column {validation_status_column}")
            
        except Exception as e:
            logger.warning(f"Failed to format validation status cell for row {row_number}: {e}")
    
    def _format_train_val_split_cell(self, row_number: int, split_status: str):
        """Apply color formatting to Train/Val Split cell based on split quality"""
        if not split_status:
            return
            
        try:
            # Train/Val Split is column N (index 13, 0-based) - positioned between File Count and File Collection Status
            split_column = 13
            
            # Define colors based on split quality
            colors = {
                'GOOD': {'red': 0.85, 'green': 0.95, 'blue': 0.85},      # Light green
                'SUCCESS': {'red': 0.85, 'green': 0.95, 'blue': 0.85},  # Light green
                'WARNING': {'red': 1.0, 'green': 0.95, 'blue': 0.8},    # Light yellow
                'FAILED': {'red': 1.0, 'green': 0.85, 'blue': 0.85},    # Light red
                'ERROR': {'red': 1.0, 'green': 0.85, 'blue': 0.85},     # Light red
                'NOT_PROCESSED': {'red': 0.9, 'green': 0.9, 'blue': 0.9}, # Light gray
                'N/A': {'red': 0.9, 'green': 0.9, 'blue': 0.9},         # Light gray
                'DISABLED': {'red': 0.9, 'green': 0.9, 'blue': 0.9}     # Light gray
            }
            
            # Extract quality from format like "977|128 (GOOD)" or "FAILED"
            if '(' in split_status and ')' in split_status:
                quality = split_status.split('(')[1].split(')')[0].strip()
            else:
                quality = split_status.strip()
            
            color = colors.get(quality, colors['NOT_PROCESSED'])
            
            # Apply formatting
            requests = [{
                'repeatCell': {
                    'range': {
                        'sheetId': 0,
                        'startRowIndex': row_number - 1,
                        'endRowIndex': row_number,
                        'startColumnIndex': split_column,
                        'endColumnIndex': split_column + 1
                    },
                    'cell': {
                        'userEnteredFormat': {
                            'backgroundColor': color
                        }
                    },
                    'fields': 'userEnteredFormat.backgroundColor'
                }
            }]
            
            body = {'requests': requests}
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=Config.SPREADSHEET_ID,
                body=body
            ).execute()
            
        except Exception as e:
            logger.error(f"Failed to format train/val split cell: {e}")

    def _format_file_collection_status_cell(self, row_number: int, collection_status: str):
        """Apply color formatting to File Collection Status cell based on status"""
        if not collection_status:
            return
            
        try:
            # File Collection Status is now column O (index 14, 0-based) after Train/Val Split insertion
            collection_status_column = 14
            
            # Define colors based on collection status
            colors = {
                'PASS': {'red': 0.85, 'green': 0.95, 'blue': 0.85},          # Light green
                'FAILED': {'red': 1.0, 'green': 0.85, 'blue': 0.85},        # Light red
                'MISSING_FILES': {'red': 1.0, 'green': 0.85, 'blue': 0.85}, # Light red
                'PARTIAL': {'red': 1.0, 'green': 0.95, 'blue': 0.8},        # Light yellow
                'NOT_CHECKED': {'red': 0.9, 'green': 0.9, 'blue': 0.9}      # Light gray
            }
            
            background_color = colors.get(collection_status, colors['NOT_CHECKED'])
            
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
                            'startColumnIndex': collection_status_column,
                            'endColumnIndex': collection_status_column + 1
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
            
            logger.debug(f"Applied {collection_status} formatting to row {row_number}, column {collection_status_column}")
            
        except Exception as e:
            logger.warning(f"Failed to format file collection status cell for row {row_number}: {e}")
    
    def _format_hf_upload_status_cell(self, row_number: int, upload_status: str):
        """Apply color formatting to Hugging Face Upload Status cell"""
        if not upload_status:
            return
            
        try:
            # HF Upload Status is column AC (index 28, 0-based) - positioned before Notes
            hf_upload_column = 28
            
            # Define colors based on upload status
            colors = {
                'SUCCESS': {'red': 0.85, 'green': 0.95, 'blue': 0.85},      # Light green
                'UPLOADED': {'red': 0.85, 'green': 0.95, 'blue': 0.85},     # Light green  
                'SKIPPED': {'red': 1.0, 'green': 0.95, 'blue': 0.8},        # Light yellow
                'DISABLED': {'red': 0.9, 'green': 0.9, 'blue': 0.9},        # Light gray
                'FAILED': {'red': 1.0, 'green': 0.85, 'blue': 0.85},        # Light red
                'ERROR': {'red': 1.0, 'green': 0.85, 'blue': 0.85},         # Light red
                'NOT_PROCESSED': {'red': 0.9, 'green': 0.9, 'blue': 0.9},   # Light gray
            }
            
            # Extract status from upload status text
            status_key = upload_status.upper()
            if 'SUCCESS' in status_key or 'UPLOADED' in status_key:
                background_color = colors.get('SUCCESS', colors['NOT_PROCESSED'])
            elif 'SKIPPED' in status_key:
                background_color = colors.get('SKIPPED', colors['NOT_PROCESSED'])
            elif 'DISABLED' in status_key:
                background_color = colors.get('DISABLED', colors['NOT_PROCESSED'])
            elif 'FAILED' in status_key or 'ERROR' in status_key:
                background_color = colors.get('FAILED', colors['NOT_PROCESSED'])
            else:
                background_color = colors.get('NOT_PROCESSED', colors['NOT_PROCESSED'])
            
            # Get sheet ID
            sheet_metadata = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
            sheet_id = None
            for sheet in sheet_metadata.get('sheets', []):
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
                            'startColumnIndex': hf_upload_column,
                            'endColumnIndex': hf_upload_column + 1
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
            
            logger.debug(f"Applied {upload_status} formatting to row {row_number}, column {hf_upload_column}")
            
        except Exception as e:
            logger.warning(f"Failed to format HF upload status cell for row {row_number}: {e}")
            
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
    
    def _get_next_entry_id(self) -> str:
        """Generate sequential entry ID for data records"""
        try:
            next_row = self._get_next_empty_row()
            # Entry ID starts from 1, header is row 1, so data starts from row 2
            entry_id = next_row - 1  # Row 2 = Entry ID 1
            return f"E{entry_id:04d}"  # Format: E0001, E0002, etc.
        except Exception as e:
            logger.warning(f"Failed to generate entry ID: {e}")
            return f"E{int(time.time()) % 10000:04d}"  # Fallback to timestamp-based ID
    
    def _determine_validation_status(self, record: Dict[str, Any]) -> str:
        """Determine overall validation status based on score and errors"""
        try:
            # Extract validation score
            validation_score_str = record.get('validation_score', '0')
            if isinstance(validation_score_str, str) and '/' in validation_score_str:
                score = float(validation_score_str.split('/')[0])
            else:
                score = float(validation_score_str) if validation_score_str else 0
            
            # Check for errors
            error_message = record.get('error_message', '')
            has_errors = bool(error_message and error_message != 'N/A')
            
            # Check extract status
            extract_status = record.get('extract_status', '')
            extract_failed = 'Failed' in extract_status or 'failed' in extract_status
            
            # Determine status based on criteria
            if extract_failed or has_errors:
                return 'FAILED'
            elif score >= 80:
                return 'PASSED'
            elif score >= 60:
                return 'WARNING'
            elif score > 0:
                return 'NEEDS_REVIEW'
            else:
                return 'PENDING'
                
        except Exception as e:
            logger.warning(f"Failed to determine validation status: {e}")
            return 'UNKNOWN'
            
    def _format_file_size(self, size_bytes: int) -> str:
        if size_bytes is None:
            return "Unknown"
        
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
        Enhanced append_record - uses unified data mapper with English output
        Recommended method to avoid data transfer errors
        """
        max_retries = Config.MAX_RETRY_ATTEMPTS
        
        for attempt in range(max_retries):
            try:
                if not self._get_or_create_headers():
                    return False
                    
                next_row = self._get_next_empty_row()
                range_name = f"'{self.sheet_name}'!A{next_row}:AB{next_row}"
                
                # Use unified data preparation method
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
                
                # Apply validation status formatting
                if len(formatted_record) > 1:  # Ensure we have validation status
                    validation_status = formatted_record[1]  # Column B (index 1)
                    self._format_validation_status_cell(next_row, validation_status)
                
                # Apply other status formatting
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
                    self._format_duration_cell(next_row, duration_status)
                
                # Size status formatting
                size_status_level = record.get('size_status_level')
                if size_status_level:
                    self._format_size_status_cell(next_row, size_status_level)
                
                # PCD scale formatting
                pcd_scale_status = record.get('pcd_scale_status')
                if pcd_scale_status:
                    self._format_pcd_scale_cell(next_row, pcd_scale_status)
                
                # Transient detection formatting
                transient_decision = record.get('transient_decision', '')
                if not transient_decision and validation_result:
                    # Extract from validation result if not directly provided
                    transient_validation = metadata.get('transient_validation', {})
                    transient_data = transient_validation.get('transient_detection', {})
                    if transient_data:
                        transient_decision = transient_data.get('decision', '')
                
                if transient_decision:
                    self._format_transient_detection_cell(next_row, transient_decision)
                
                # Train/Val Split formatting
                train_val_split = record.get('train_val_split', '')
                if train_val_split:
                    self._format_train_val_split_cell(next_row, train_val_split)
                else:
                    # Check if it's in the formatted record directly
                    if len(formatted_record) > 13:  # Ensure we have the train_val_split column (now at index 13)
                        split_status_from_record = formatted_record[13]
                        if split_status_from_record and split_status_from_record not in ['', 'N/A']:
                            self._format_train_val_split_cell(next_row, split_status_from_record)
                
                # File collection status formatting
                file_collection_status = record.get('file_collection_status', '')
                if file_collection_status:
                    self._format_file_collection_status_cell(next_row, file_collection_status)
                else:
                    # Check if it's in the formatted record directly
                    if len(formatted_record) > 13:  # Ensure we have the collection status column
                        collection_status_from_record = formatted_record[14]
                        if collection_status_from_record and collection_status_from_record not in ['', 'NOT_CHECKED']:
                            self._format_file_collection_status_cell(next_row, collection_status_from_record)
                
                # Hugging Face upload status formatting
                hf_upload_status = record.get('hf_upload_status', '')
                if hf_upload_status:
                    self._format_hf_upload_status_cell(next_row, hf_upload_status)
                else:
                    # Check if it's in the formatted record directly
                    if len(formatted_record) > 28:  # Ensure we have the HF upload status column (index 28)
                        hf_status_from_record = formatted_record[28]
                        if hf_status_from_record and hf_status_from_record not in ['', 'NOT_PROCESSED']:
                            self._format_hf_upload_status_cell(next_row, hf_status_from_record)
                
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
        """
        Legacy append_record method - redirects to append_record_v2
        for backward compatibility
        """
        logger.warning("Using legacy append_record method. Consider switching to append_record_v2 for better formatting.")
        return self.append_record_v2(record)
        
    def batch_append_records(self, records: List[Dict[str, Any]]) -> bool:
        """
        Enhanced batch append - uses unified data mapper with English output
        """
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
                        # Use unified data preparation method
                        formatted_record = self.prepare_record_row(record)
                        formatted_records.append(formatted_record)
                    
                    range_name = f"'{self.sheet_name}'!A{next_row}:AB{next_row + len(batch) - 1}"
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
                    for j, (record, formatted_record) in enumerate(zip(batch, formatted_records)):
                        # Apply validation status formatting (Column B, index 1)
                        if len(formatted_record) > 1:
                            validation_status = formatted_record[1]
                            self._format_validation_status_cell(next_row + j, validation_status)
                        
                        # Apply other status formatting
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
                        
                        # File collection status formatting
                        file_collection_status = record.get('file_collection_status', '')
                        if file_collection_status:
                            self._format_file_collection_status_cell(next_row + j, file_collection_status)
                        else:
                            # Check if it's in the formatted record directly
                            if len(formatted_record) > 13:  # Ensure we have the collection status column
                                collection_status_from_record = formatted_record[14]
                                if collection_status_from_record and collection_status_from_record not in ['', 'NOT_CHECKED']:
                                    self._format_file_collection_status_cell(next_row + j, collection_status_from_record)
                        
                        # Hugging Face upload status formatting
                        hf_upload_status = record.get('hf_upload_status', '')
                        if hf_upload_status:
                            self._format_hf_upload_status_cell(next_row + j, hf_upload_status)
                        else:
                            # Check if it's in the formatted record directly
                            if len(formatted_record) > 28:  # Ensure we have the HF upload status column (index 28)
                                hf_status_from_record = formatted_record[28]
                                if hf_status_from_record and hf_status_from_record not in ['', 'NOT_PROCESSED']:
                                    self._format_hf_upload_status_cell(next_row + j, hf_status_from_record)
                    
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