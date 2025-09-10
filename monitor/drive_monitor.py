import os
import json
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Callable, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import Config

logger = logging.getLogger(__name__)

class DriveMonitor:
    """
    Google Drive监控器
    
    功能:
    - 使用Google Drive API v3连接到指定文件夹
    - 每30秒轮询检查新文件（可配置）
    - 识别新上传的文件（通过比对processed_files.json）
    - 获取文件元数据：名称、大小、创建时间、修改时间、MIME类型
    - 支持文件过滤：按文件类型、大小限制
    - 实现增量检查，避免重复处理
    """
    
    def __init__(self, folder_id: str, credentials_file: str = None):
        """
        初始化监控器
        
        Args:
            folder_id (str): Google Drive文件夹ID
            credentials_file (str): 服务账号凭证文件路径
        """
        self.folder_id = folder_id or Config.DRIVE_FOLDER_ID
        self.credentials_file = credentials_file or Config.SERVICE_ACCOUNT_FILE
        self.service = None
        self.processed_files = set()
        self.last_check_time = None
        
        # 初始化Google Drive服务
        self._initialize_service()
        
        # 加载已处理文件记录
        self._load_processed_files()
        
        logger.info(f"DriveMonitor initialized for folder: {self.folder_id}")
    
    def _initialize_service(self):
        """初始化Google Drive服务"""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_file,
                scopes=Config.SCOPES
            )
            self.service = build('drive', 'v3', credentials=credentials)
            logger.info("Google Drive service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Google Drive service: {e}")
            raise
    
    def _load_processed_files(self):
        """从processed_files.json加载已处理文件记录"""
        try:
            if os.path.exists(Config.PROCESSED_FILES_JSON):
                with open(Config.PROCESSED_FILES_JSON, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # 加载已处理文件ID集合
                processed_list = data.get('processed_files', [])
                self.processed_files = {item['file_id'] for item in processed_list}
                
                # 加载最后检查时间
                last_check = data.get('last_check_time')
                if last_check:
                    self.last_check_time = datetime.fromisoformat(last_check)
                
                logger.info(f"Loaded {len(self.processed_files)} processed files from cache")
            else:
                logger.info("No processed files cache found, starting fresh")
                self.processed_files = set()
                self.last_check_time = None
                
        except Exception as e:
            logger.error(f"Error loading processed files: {e}")
            self.processed_files = set()
            self.last_check_time = None
    
    def _save_processed_files(self):
        """保存已处理文件记录到processed_files.json"""
        try:
            # 构建数据结构
            data = {
                "processed_files": [
                    {
                        "file_id": file_id,
                        "processed_time": datetime.now().isoformat(),
                        "status": "processed"
                    }
                    for file_id in self.processed_files
                ],
                "last_check_time": self.last_check_time.isoformat() if self.last_check_time else None,
                "total_processed": len(self.processed_files)
            }
            
            # 保存到文件
            with open(Config.PROCESSED_FILES_JSON, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            logger.debug("Processed files saved to cache")
            
        except Exception as e:
            logger.error(f"Error saving processed files: {e}")
    
    def _is_file_allowed(self, file_info: Dict) -> bool:
        """
        检查文件是否符合过滤条件
        
        Args:
            file_info (Dict): 文件信息字典
            
        Returns:
            bool: 是否允许处理此文件
        """
        try:
            # 检查文件大小
            file_size_mb = int(file_info.get('size', 0)) / (1024 * 1024)
            if file_size_mb > Config.MAX_FILE_SIZE_MB:
                logger.info(f"File {file_info['name']} too large: {file_size_mb:.2f}MB")
                return False
            
            # 检查文件扩展名
            file_name = file_info.get('name', '')
            file_ext = Path(file_name).suffix.lower()
            
            if Config.ALLOWED_EXTENSIONS and file_ext not in Config.ALLOWED_EXTENSIONS:
                logger.debug(f"File {file_name} extension {file_ext} not in allowed list")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking file filter: {e}")
            return False
    
    def get_new_files(self) -> List[Dict]:
        """
        获取新文件列表
        
        Returns:
            List[Dict]: 新文件信息列表，每个文件包含元数据
        """
        try:
            logger.info("Checking for new files...")
            
            # 构建查询条件
            query = f"'{self.folder_id}' in parents and trashed=false"
            
            # 如果有最后检查时间，只获取之后的文件
            if self.last_check_time:
                time_filter = self.last_check_time.isoformat()
                query += f" and modifiedTime > '{time_filter}'"
            
            # 调用Drive API
            results = self.service.files().list(
                q=query,
                fields="nextPageToken, files(id, name, size, mimeType, createdTime, modifiedTime, parents, owners)",
                orderBy="createdTime desc",
                pageSize=1000  # 最大页面大小
            ).execute()
            
            all_files = results.get('files', [])
            
            # 过滤出新文件
            new_files = []
            for file in all_files:
                file_id = file['id']
                
                # 跳过已处理的文件
                if file_id in self.processed_files:
                    continue
                
                # 应用文件过滤规则
                if not self._is_file_allowed(file):
                    # 将不符合条件的文件也标记为已处理，避免重复检查
                    self.processed_files.add(file_id)
                    continue
                
                # 添加到新文件列表
                file_info = {
                    'id': file_id,
                    'name': file.get('name', 'Unknown'),
                    'size': int(file.get('size', 0)),
                    'mimeType': file.get('mimeType', ''),
                    'createdTime': file.get('createdTime', ''),
                    'modifiedTime': file.get('modifiedTime', ''),
                    'parents': file.get('parents', []),
                    'owners': file.get('owners', [])
                }
                new_files.append(file_info)
            
            # 更新最后检查时间
            self.last_check_time = datetime.now()
            
            logger.info(f"Found {len(new_files)} new files out of {len(all_files)} total files")
            return new_files
            
        except HttpError as e:
            logger.error(f"HTTP error occurred while listing files: {e}")
            return []
        except Exception as e:
            logger.error(f"Error getting new files: {e}")
            return []
    
    def mark_as_processed(self, file_id: str):
        """
        标记文件为已处理
        
        Args:
            file_id (str): 文件ID
        """
        try:
            self.processed_files.add(file_id)
            self._save_processed_files()
            logger.debug(f"Marked file as processed: {file_id}")
        except Exception as e:
            logger.error(f"Error marking file as processed: {e}")
    
    def get_file_metadata(self, file_id: str) -> Optional[Dict]:
        """
        获取文件详细元数据
        
        Args:
            file_id (str): 文件ID
            
        Returns:
            Optional[Dict]: 文件元数据，失败时返回None
        """
        try:
            result = self.service.files().get(
                fileId=file_id,
                fields="id, name, size, mimeType, createdTime, modifiedTime, owners, parents, webViewLink, md5Checksum"
            ).execute()
            
            metadata = {
                'id': result.get('id'),
                'name': result.get('name'),
                'size': int(result.get('size', 0)),
                'mimeType': result.get('mimeType'),
                'createdTime': result.get('createdTime'),
                'modifiedTime': result.get('modifiedTime'),
                'owners': result.get('owners', []),
                'parents': result.get('parents', []),
                'webViewLink': result.get('webViewLink'),
                'md5Checksum': result.get('md5Checksum')
            }
            
            logger.debug(f"Retrieved metadata for file: {metadata['name']}")
            return metadata
            
        except HttpError as e:
            logger.error(f"HTTP error occurred while getting metadata for {file_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting file metadata for {file_id}: {e}")
            return None
    
    def start_monitoring(self, callback: Callable[[List[Dict]], None]):
        """
        开始监控循环
        
        Args:
            callback (Callable): 处理新文件的回调函数，接收文件列表作为参数
        """
        logger.info(f"Starting monitoring loop with {Config.CHECK_INTERVAL}s interval")
        
        try:
            while Config.ENABLE_MONITORING:
                try:
                    # 获取新文件
                    new_files = self.get_new_files()
                    
                    # 如果有新文件，调用回调函数处理
                    if new_files:
                        logger.info(f"Processing {len(new_files)} new files")
                        callback(new_files)
                    
                    # 定期清理过期记录
                    self._cleanup_old_records()
                    
                    # 等待下次检查
                    time.sleep(Config.CHECK_INTERVAL)
                    
                except KeyboardInterrupt:
                    logger.info("Monitoring stopped by user")
                    break
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
                    time.sleep(Config.RETRY_DELAY)
                    
        except Exception as e:
            logger.error(f"Fatal error in monitoring: {e}")
            raise
        finally:
            logger.info("Monitoring stopped")
    
    def _cleanup_old_records(self):
        """清理过期的已处理文件记录"""
        try:
            if not os.path.exists(Config.PROCESSED_FILES_JSON):
                return
            
            with open(Config.PROCESSED_FILES_JSON, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            processed_list = data.get('processed_files', [])
            cutoff_date = datetime.now() - timedelta(days=Config.KEEP_PROCESSED_DAYS)
            
            # 过滤掉过期记录
            valid_records = []
            for record in processed_list:
                try:
                    processed_time = datetime.fromisoformat(record.get('processed_time', ''))
                    if processed_time > cutoff_date:
                        valid_records.append(record)
                except ValueError:
                    # 保留无效时间戳的记录
                    valid_records.append(record)
            
            # 如果记录数量发生变化，保存更新后的数据
            if len(valid_records) != len(processed_list):
                data['processed_files'] = valid_records
                data['total_processed'] = len(valid_records)
                
                with open(Config.PROCESSED_FILES_JSON, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                # 更新内存中的集合
                self.processed_files = {record['file_id'] for record in valid_records}
                
                logger.info(f"Cleaned up {len(processed_list) - len(valid_records)} old records")
                
        except Exception as e:
            logger.error(f"Error cleaning up old records: {e}")
    
    def delete_file(self, file_id: str) -> bool:
        """
        删除Google Drive上的文件
        
        Args:
            file_id (str): 要删除的文件ID
            
        Returns:
            bool: 删除是否成功
        """
        try:
            # 检查是否启用了自动删除功能
            if not Config.AUTO_DELETE_SOURCE_FILES:
                logger.info(f"Auto-delete disabled, skipping deletion of file {file_id}")
                return False
            
            # 先获取文件信息用于日志记录
            file_metadata = self.get_file_metadata(file_id)
            file_name = file_metadata.get('name', 'Unknown') if file_metadata else 'Unknown'
            
            logger.info(f"Attempting to delete file: {file_name} (ID: {file_id})")
            
            # 执行删除操作
            self.service.files().delete(fileId=file_id).execute()
            
            logger.success(f"Successfully deleted file from Google Drive: {file_name}")
            return True
            
        except HttpError as e:
            if e.resp.status == 404:
                logger.warning(f"File {file_id} not found, may have been already deleted")
                return True  # 文件不存在也算成功
            else:
                logger.error(f"HTTP error deleting file {file_id}: {e}")
                return False
        except Exception as e:
            logger.error(f"Error deleting file {file_id}: {e}")
            return False
    
    def stop_monitoring(self):
        """停止监控"""
        Config.ENABLE_MONITORING = False
        logger.info("Monitoring will stop after current cycle")
    
    def get_status(self) -> Dict:
        """
        获取监控状态信息
        
        Returns:
            Dict: 状态信息
        """
        return {
            'folder_id': self.folder_id,
            'processed_count': len(self.processed_files),
            'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
            'monitoring_enabled': Config.ENABLE_MONITORING,
            'check_interval': Config.CHECK_INTERVAL
        }