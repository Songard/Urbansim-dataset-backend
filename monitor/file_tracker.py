import os
import json
import threading
import platform
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from config import Config
from utils.logger import get_logger

# Cross-platform file locking
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False
    
try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

logger = get_logger(__name__)

class FileTracker:
    """
    文件追踪管理器
    
    功能:
    - 使用JSON文件持久化已处理文件列表
    - 支持并发访问（文件锁）
    - 定期清理过期记录（可配置保留天数）
    - 提供查询接口
    """
    
    def __init__(self, json_file_path: str = None):
        """
        初始化文件追踪器
        
        Args:
            json_file_path (str): JSON文件路径，默认使用配置中的路径
        """
        self.json_file_path = json_file_path or Config.PROCESSED_FILES_JSON
        self.lock = threading.RLock()
        self._ensure_data_file_exists()
        logger.info(f"FileTracker initialized with file: {self.json_file_path}")
    
    def _lock_file(self, file_handle, exclusive=False):
        """跨平台文件锁定"""
        if HAS_FCNTL:
            # Unix/Linux系统
            lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            try:
                fcntl.flock(file_handle.fileno(), lock_type | fcntl.LOCK_NB)
            except IOError:
                # 如果非阻塞锁失败，使用阻塞锁
                fcntl.flock(file_handle.fileno(), lock_type)
        elif HAS_MSVCRT:
            # Windows系统
            try:
                # Windows的文件锁定（简化版）
                msvcrt.locking(file_handle.fileno(), msvcrt.LK_LOCK, 1)
            except IOError:
                # 锁定失败，继续执行
                pass
    
    def _unlock_file(self, file_handle):
        """跨平台文件解锁"""
        if HAS_FCNTL:
            try:
                fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
            except (AttributeError, OSError):
                pass
        elif HAS_MSVCRT:
            try:
                msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)
            except IOError:
                pass
    
    def _ensure_data_file_exists(self):
        """确保数据文件存在，不存在则创建"""
        try:
            os.makedirs(os.path.dirname(self.json_file_path), exist_ok=True)
            
            if not os.path.exists(self.json_file_path):
                initial_data = {
                    "processed_files": [],
                    "last_check_time": None,
                    "total_processed": 0,
                    "created_time": datetime.now().isoformat(),
                    "version": "1.0"
                }
                self._write_data(initial_data)
                logger.info(f"Created new tracking file: {self.json_file_path}")
                
        except Exception as e:
            logger.error(f"Error ensuring data file exists: {e}")
            raise
    
    def _read_data(self) -> Dict:
        """读取数据文件，使用文件锁"""
        try:
            with self.lock:
                with open(self.json_file_path, 'r', encoding='utf-8') as f:
                    try:
                        self._lock_file(f, exclusive=False)
                        data = json.load(f)
                        return data
                    finally:
                        self._unlock_file(f)
        except FileNotFoundError:
            logger.warning(f"Data file not found: {self.json_file_path}")
            self._ensure_data_file_exists()
            return self._read_data()
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in data file: {e}")
            # 备份损坏的文件
            backup_path = f"{self.json_file_path}.backup.{int(datetime.now().timestamp())}"
            try:
                os.rename(self.json_file_path, backup_path)
                logger.info(f"Backed up corrupted file to: {backup_path}")
            except:
                pass
            self._ensure_data_file_exists()
            return self._read_data()
        except Exception as e:
            logger.error(f"Error reading data file: {e}")
            return {
                "processed_files": [],
                "last_check_time": None,
                "total_processed": 0
            }
    
    def _write_data(self, data: Dict):
        """写入数据文件，使用文件锁"""
        try:
            with self.lock:
                with open(self.json_file_path, 'w', encoding='utf-8') as f:
                    try:
                        self._lock_file(f, exclusive=True)
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    finally:
                        self._unlock_file(f)
        except Exception as e:
            logger.error(f"Error writing data file: {e}")
            raise
    
    def add_processed_file(self, file_id: str, file_name: str, status: str = "success", 
                          sheets_row: int = None, metadata: Dict = None) -> bool:
        """
        添加已处理文件记录
        
        Args:
            file_id (str): 文件ID
            file_name (str): 文件名
            status (str): 处理状态
            sheets_row (int): Google Sheets行号
            metadata (Dict): 额外的元数据
            
        Returns:
            bool: 添加是否成功
        """
        try:
            data = self._read_data()
            
            # 检查是否已存在
            if self.is_file_processed(file_id):
                logger.warning(f"File {file_id} already processed")
                return False
            
            # 构建记录
            record = {
                "file_id": file_id,
                "file_name": file_name,
                "processed_time": datetime.now().isoformat(),
                "status": status,
                "sheets_row": sheets_row,
                "metadata": metadata or {}
            }
            
            # 添加记录
            data["processed_files"].append(record)
            data["total_processed"] = len(data["processed_files"])
            data["last_update_time"] = datetime.now().isoformat()
            
            self._write_data(data)
            logger.info(f"Added processed file record: {file_name} ({file_id})")
            return True
            
        except Exception as e:
            logger.error(f"Error adding processed file record: {e}")
            return False
    
    def is_file_processed(self, file_id: str) -> bool:
        """
        检查文件是否已处理
        
        Args:
            file_id (str): 文件ID
            
        Returns:
            bool: 文件是否已处理
        """
        try:
            data = self._read_data()
            processed_ids = {record["file_id"] for record in data.get("processed_files", [])}
            return file_id in processed_ids
        except Exception as e:
            logger.error(f"Error checking if file processed: {e}")
            return False
    
    def get_processed_files(self, limit: int = None, status: str = None) -> List[Dict]:
        """
        获取已处理文件列表
        
        Args:
            limit (int): 限制返回数量
            status (str): 过滤状态
            
        Returns:
            List[Dict]: 已处理文件列表
        """
        try:
            data = self._read_data()
            files = data.get("processed_files", [])
            
            # 状态过滤
            if status:
                files = [f for f in files if f.get("status") == status]
            
            # 按时间排序（最新的在前）
            files.sort(key=lambda x: x.get("processed_time", ""), reverse=True)
            
            # 限制数量
            if limit:
                files = files[:limit]
            
            return files
            
        except Exception as e:
            logger.error(f"Error getting processed files: {e}")
            return []
    
    def get_file_record(self, file_id: str) -> Optional[Dict]:
        """
        获取特定文件的处理记录
        
        Args:
            file_id (str): 文件ID
            
        Returns:
            Optional[Dict]: 文件记录，未找到时返回None
        """
        try:
            data = self._read_data()
            for record in data.get("processed_files", []):
                if record.get("file_id") == file_id:
                    return record
            return None
            
        except Exception as e:
            logger.error(f"Error getting file record: {e}")
            return None
    
    def update_file_record(self, file_id: str, updates: Dict) -> bool:
        """
        更新文件记录
        
        Args:
            file_id (str): 文件ID
            updates (Dict): 要更新的字段
            
        Returns:
            bool: 更新是否成功
        """
        try:
            data = self._read_data()
            
            for i, record in enumerate(data.get("processed_files", [])):
                if record.get("file_id") == file_id:
                    # 更新记录
                    record.update(updates)
                    record["last_updated"] = datetime.now().isoformat()
                    data["processed_files"][i] = record
                    data["last_update_time"] = datetime.now().isoformat()
                    
                    self._write_data(data)
                    logger.info(f"Updated file record: {file_id}")
                    return True
            
            logger.warning(f"File record not found for update: {file_id}")
            return False
            
        except Exception as e:
            logger.error(f"Error updating file record: {e}")
            return False
    
    def remove_file_record(self, file_id: str) -> bool:
        """
        移除文件记录
        
        Args:
            file_id (str): 文件ID
            
        Returns:
            bool: 移除是否成功
        """
        try:
            data = self._read_data()
            original_count = len(data.get("processed_files", []))
            
            # 过滤掉指定文件
            data["processed_files"] = [
                record for record in data.get("processed_files", [])
                if record.get("file_id") != file_id
            ]
            
            if len(data["processed_files"]) < original_count:
                data["total_processed"] = len(data["processed_files"])
                data["last_update_time"] = datetime.now().isoformat()
                self._write_data(data)
                logger.info(f"Removed file record: {file_id}")
                return True
            else:
                logger.warning(f"File record not found for removal: {file_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error removing file record: {e}")
            return False
    
    def cleanup_old_records(self, keep_days: int = None) -> int:
        """
        清理过期记录
        
        Args:
            keep_days (int): 保留天数，默认使用配置中的值
            
        Returns:
            int: 清理的记录数量
        """
        try:
            keep_days = keep_days or Config.KEEP_PROCESSED_DAYS
            cutoff_date = datetime.now() - timedelta(days=keep_days)
            
            data = self._read_data()
            original_count = len(data.get("processed_files", []))
            
            # 过滤掉过期记录
            valid_records = []
            for record in data.get("processed_files", []):
                try:
                    processed_time_str = record.get("processed_time", "")
                    if processed_time_str:
                        processed_time = datetime.fromisoformat(processed_time_str)
                        if processed_time > cutoff_date:
                            valid_records.append(record)
                    else:
                        # 保留没有时间戳的记录
                        valid_records.append(record)
                except ValueError:
                    # 保留无效时间戳的记录
                    valid_records.append(record)
            
            # 更新数据
            cleaned_count = original_count - len(valid_records)
            if cleaned_count > 0:
                data["processed_files"] = valid_records
                data["total_processed"] = len(valid_records)
                data["last_cleanup_time"] = datetime.now().isoformat()
                data["last_update_time"] = datetime.now().isoformat()
                
                self._write_data(data)
                logger.info(f"Cleaned up {cleaned_count} old records (kept {len(valid_records)})")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old records: {e}")
            return 0
    
    def get_statistics(self) -> Dict:
        """
        获取统计信息
        
        Returns:
            Dict: 统计信息
        """
        try:
            data = self._read_data()
            files = data.get("processed_files", [])
            
            stats = {
                "total_processed": len(files),
                "success_count": len([f for f in files if f.get("status") == "success"]),
                "failed_count": len([f for f in files if f.get("status") == "failed"]),
                "last_processed": None,
                "oldest_record": None,
                "data_file_size": 0
            }
            
            # 获取最新和最旧的记录时间
            if files:
                times = [f.get("processed_time") for f in files if f.get("processed_time")]
                if times:
                    times.sort()
                    stats["oldest_record"] = times[0]
                    stats["last_processed"] = times[-1]
            
            # 获取数据文件大小
            if os.path.exists(self.json_file_path):
                stats["data_file_size"] = os.path.getsize(self.json_file_path)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}
    
    def export_records(self, output_path: str, format_type: str = "json") -> bool:
        """
        导出记录到文件
        
        Args:
            output_path (str): 输出文件路径
            format_type (str): 导出格式 ('json' 或 'csv')
            
        Returns:
            bool: 导出是否成功
        """
        try:
            data = self._read_data()
            
            if format_type.lower() == "json":
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            elif format_type.lower() == "csv":
                import csv
                with open(output_path, 'w', newline='', encoding='utf-8') as f:
                    if data.get("processed_files"):
                        fieldnames = ["file_id", "file_name", "processed_time", "status", "sheets_row"]
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        
                        for record in data["processed_files"]:
                            csv_record = {k: record.get(k, "") for k in fieldnames}
                            writer.writerow(csv_record)
            else:
                logger.error(f"Unsupported export format: {format_type}")
                return False
            
            logger.info(f"Records exported to: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting records: {e}")
            return False
    
    def import_records(self, input_path: str, merge: bool = True) -> bool:
        """
        从文件导入记录
        
        Args:
            input_path (str): 输入文件路径
            merge (bool): 是否合并到现有记录（False会覆盖）
            
        Returns:
            bool: 导入是否成功
        """
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            if merge:
                current_data = self._read_data()
                existing_ids = {r["file_id"] for r in current_data.get("processed_files", [])}
                
                # 只导入新记录
                new_records = []
                for record in import_data.get("processed_files", []):
                    if record.get("file_id") not in existing_ids:
                        new_records.append(record)
                
                current_data["processed_files"].extend(new_records)
                current_data["total_processed"] = len(current_data["processed_files"])
                current_data["last_update_time"] = datetime.now().isoformat()
                
                self._write_data(current_data)
                logger.info(f"Imported {len(new_records)} new records")
            else:
                # 直接覆盖
                self._write_data(import_data)
                logger.info("Records imported (overwrite mode)")
            
            return True
            
        except Exception as e:
            logger.error(f"Error importing records: {e}")
            return False
    
    def update_last_check_time(self, check_time: datetime = None):
        """
        更新最后检查时间
        
        Args:
            check_time (datetime): 检查时间，默认为当前时间
        """
        try:
            data = self._read_data()
            data["last_check_time"] = (check_time or datetime.now()).isoformat()
            data["last_update_time"] = datetime.now().isoformat()
            self._write_data(data)
            logger.debug("Updated last check time")
        except Exception as e:
            logger.error(f"Error updating last check time: {e}")
    
    def get_last_check_time(self) -> Optional[datetime]:
        """
        获取最后检查时间
        
        Returns:
            Optional[datetime]: 最后检查时间，未设置时返回None
        """
        try:
            data = self._read_data()
            last_check = data.get("last_check_time")
            if last_check:
                return datetime.fromisoformat(last_check)
            return None
        except Exception as e:
            logger.error(f"Error getting last check time: {e}")
            return None