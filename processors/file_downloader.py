import os
import time
import logging
import hashlib
import threading
from pathlib import Path
from typing import Optional, Callable, Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed
import io
import socket

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
import httplib2
import urllib3

from config import Config

# 禁用urllib3的警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class DownloadProgress:
    """下载进度跟踪器"""
    
    def __init__(self, file_name: str, total_size: int):
        self.file_name = file_name
        self.total_size = total_size
        self.downloaded = 0
        self.start_time = time.time()
        self.last_update = time.time()
        
    def update(self, chunk_size: int):
        """更新下载进度"""
        self.downloaded += chunk_size
        current_time = time.time()
        
        # 限制更新频率，避免过度输出
        if current_time - self.last_update >= 1.0 or self.downloaded >= self.total_size:
            self.display_progress()
            self.last_update = current_time
    
    def display_progress(self):
        """显示下载进度"""
        if self.total_size > 0:
            percentage = (self.downloaded / self.total_size) * 100
            elapsed = time.time() - self.start_time
            speed = self.downloaded / elapsed if elapsed > 0 else 0
            
            # 计算预计剩余时间
            if speed > 0:
                remaining_bytes = self.total_size - self.downloaded
                eta_seconds = remaining_bytes / speed
                if eta_seconds > 3600:
                    eta_str = f"{eta_seconds/3600:.1f}h"
                elif eta_seconds > 60:
                    eta_str = f"{eta_seconds/60:.1f}m"
                else:
                    eta_str = f"{eta_seconds:.0f}s"
            else:
                eta_str = "∞"
            
            # 格式化速度显示
            if speed > 1024 * 1024:
                speed_str = f"{speed / (1024 * 1024):.1f} MB/s"
            elif speed > 1024:
                speed_str = f"{speed / 1024:.1f} KB/s"
            else:
                speed_str = f"{speed:.0f} B/s"
            
            # 格式化大小显示
            downloaded_mb = self.downloaded / (1024 * 1024)
            total_mb = self.total_size / (1024 * 1024)
            
            # 创建进度条
            bar_length = 30
            filled_length = int(bar_length * percentage / 100)
            bar = '█' * filled_length + '-' * (bar_length - filled_length)
            
            print(f"\r{self.file_name}: {percentage:.1f}% |{bar}| "
                  f"{downloaded_mb:.1f}/{total_mb:.1f} MB @ {speed_str} ETA:{eta_str}", 
                  end="", flush=True)
        
        if self.downloaded >= self.total_size:
            elapsed = time.time() - self.start_time
            avg_speed = self.total_size / elapsed if elapsed > 0 else 0
            if avg_speed > 1024 * 1024:
                avg_speed_str = f"{avg_speed / (1024 * 1024):.1f} MB/s"
            else:
                avg_speed_str = f"{avg_speed / 1024:.1f} KB/s"
            print(f" ✓ Complete! Avg: {avg_speed_str}")  # 完成后换行

class FileDownloader:
    """
    文件下载器
    
    功能:
    - 支持断点续传
    - 显示下载进度
    - 自动重试机制（最多3次）
    - 下载到指定的临时目录
    - 验证下载完整性（比对文件大小）
    - 支持并发下载（可配置最大并发数）
    """
    
    def __init__(self, service=None, credentials_file: str = None):
        """
        初始化下载器
        
        Args:
            service: Google Drive服务实例（可选）
            credentials_file (str): 服务账号凭证文件路径
        """
        self.credentials_file = credentials_file or Config.SERVICE_ACCOUNT_FILE
        self.service = service or self._build_service()
        self.active_downloads = {}
        self.download_lock = threading.Lock()
        
        # 创建下载目录
        os.makedirs(Config.DOWNLOAD_PATH, exist_ok=True)
        
        logger.info("FileDownloader initialized")
    
    def _build_service(self):
        """构建Google Drive服务，带连接优化"""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_file,
                scopes=Config.SCOPES
            )
            
            # 对于新版本的Google客户端，我们需要不同的方法
            # 先尝试使用简化的方法，保持连接优化
            service = build(
                'drive', 
                'v3', 
                credentials=credentials,
                cache_discovery=False  # 禁用discovery缓存以提升启动速度
            )
            
            # 设置HTTP客户端的超时和其他优化
            if hasattr(service, '_http'):
                service._http.timeout = Config.DOWNLOAD_TIMEOUT
                
                # 设置socket选项
                if hasattr(socket, 'TCP_NODELAY') and hasattr(service._http, 'socket_options'):
                    service._http.socket_options = [(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)]
            
            logger.info(f"Google Drive service built for downloader with {Config.DOWNLOAD_TIMEOUT}s timeout")
            return service
        except Exception as e:
            logger.error(f"Failed to build Google Drive service: {e}")
            raise
    
    def _get_file_info(self, file_id: str) -> Optional[Dict]:
        """获取文件基本信息"""
        try:
            result = self.service.files().get(
                fileId=file_id,
                fields="id, name, size, mimeType, md5Checksum"
            ).execute()
            
            return {
                'id': result.get('id'),
                'name': result.get('name'),
                'size': int(result.get('size', 0)),
                'mimeType': result.get('mimeType'),
                'md5Checksum': result.get('md5Checksum')
            }
        except Exception as e:
            logger.error(f"Error getting file info for {file_id}: {e}")
            return None
    
    def _calculate_md5(self, file_path: str) -> str:
        """计算文件MD5校验和"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating MD5 for {file_path}: {e}")
            return ""
    
    def _verify_download(self, file_path: str, expected_size: int, expected_md5: str = None) -> bool:
        """
        验证下载文件的完整性
        
        Args:
            file_path (str): 下载文件路径
            expected_size (int): 期望文件大小
            expected_md5 (str): 期望MD5校验和（可选）
            
        Returns:
            bool: 验证是否通过
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"Downloaded file not found: {file_path}")
                return False
            
            # 检查文件大小
            actual_size = os.path.getsize(file_path)
            if actual_size != expected_size:
                logger.error(f"File size mismatch: expected {expected_size}, got {actual_size}")
                return False
            
            # 检查MD5（如果提供）
            if expected_md5:
                actual_md5 = self._calculate_md5(file_path)
                if actual_md5.lower() != expected_md5.lower():
                    logger.error(f"MD5 checksum mismatch: expected {expected_md5}, got {actual_md5}")
                    return False
            
            logger.info(f"File verification passed: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error verifying download: {e}")
            return False
    
    def _download_with_resume(self, file_id: str, file_name: str, file_size: int, 
                            progress_callback: Callable = None) -> Optional[str]:
        """
        支持断点续传的下载方法
        
        Args:
            file_id (str): 文件ID
            file_name (str): 文件名
            file_size (int): 文件大小
            progress_callback (Callable): 进度回调函数
            
        Returns:
            Optional[str]: 下载文件路径，失败时返回None
        """
        download_path = Path(Config.DOWNLOAD_PATH) / file_name
        temp_path = Path(f"{download_path}.tmp")
        
        # 检查是否有未完成的下载
        start_byte = 0
        if temp_path.exists():
            start_byte = temp_path.stat().st_size
            logger.info(f"Resuming download from byte {start_byte}")
        
        try:
            # 创建下载请求
            request = self.service.files().get_media(fileId=file_id)
            
            # 打开文件进行追加写入
            mode = 'ab' if start_byte > 0 else 'wb'
            with open(temp_path, mode) as file_handle:
                # 设置下载范围（用于断点续传）
                if start_byte > 0:
                    request.headers['Range'] = f'bytes={start_byte}-'
                
                # 使用更大的chunk size来提高下载速度
                chunk_size = Config.DOWNLOAD_CHUNK_SIZE_MB * 1024 * 1024  # Convert MB to bytes
                downloader = MediaIoBaseDownload(
                    file_handle, 
                    request,
                    chunksize=chunk_size
                )
                
                logger.info(f"Starting download with {Config.DOWNLOAD_CHUNK_SIZE_MB}MB chunks")
                
                done = False
                progress = DownloadProgress(file_name, file_size)
                progress.downloaded = start_byte
                
                retry_count = 0
                max_retries = Config.DOWNLOAD_RETRIES
                
                while not done:
                    try:
                        status, done = downloader.next_chunk()
                        if status:
                            chunk_size = status.resumable_progress - progress.downloaded
                            progress.update(chunk_size)
                            
                            if progress_callback:
                                progress_callback(progress.downloaded, file_size)
                        
                        # 重置重试计数器，表示这个chunk成功了
                        retry_count = 0
                                
                    except (HttpError, ConnectionError, TimeoutError) as e:
                        retry_count += 1
                        if retry_count <= max_retries:
                            wait_time = min(2 ** retry_count, 30)  # 指数退避，最大30秒
                            logger.warning(f"Download chunk error (attempt {retry_count}/{max_retries}): {e}")
                            logger.info(f"Retrying in {wait_time} seconds...")
                            time.sleep(wait_time)
                        else:
                            logger.error(f"Download failed after {max_retries} retries: {e}")
                            raise
                    except Exception as e:
                        logger.error(f"Unexpected download error: {e}")
                        raise
            
            # 下载完成，重命名临时文件
            if temp_path.exists():
                temp_path.rename(download_path)
                logger.info(f"Download completed: {download_path}")
                return str(download_path)
            else:
                logger.error("Temporary file not found after download")
                return None
                
        except Exception as e:
            logger.error(f"Error downloading with resume: {e}")
            return None
    
    def download_file(self, file_id: str, file_name: str = None, 
                     progress_callback: Callable = None) -> Optional[str]:
        """
        下载单个文件
        
        Args:
            file_id (str): Google Drive文件ID
            file_name (str): 文件名（可选，将自动获取）
            progress_callback (Callable): 进度回调函数
            
        Returns:
            Optional[str]: 下载文件路径，失败时返回None
        """
        for attempt in range(Config.MAX_RETRY_ATTEMPTS):
            try:
                logger.info(f"Download attempt {attempt + 1}/{Config.MAX_RETRY_ATTEMPTS} for file {file_id}")
                
                # 获取文件信息
                file_info = self._get_file_info(file_id)
                if not file_info:
                    logger.error(f"Failed to get file info for {file_id}")
                    continue
                
                actual_file_name = file_name or file_info['name']
                file_size = file_info['size']
                expected_md5 = file_info.get('md5Checksum')
                
                logger.info(f"Starting download: {actual_file_name} ({file_size / (1024*1024):.2f} MB)")
                
                # 检查磁盘空间
                available_space = self._get_available_space(Config.DOWNLOAD_PATH)
                if file_size > available_space:
                    logger.error(f"Insufficient disk space: need {file_size}, available {available_space}")
                    return None
                
                # 执行下载
                download_path = self._download_with_resume(
                    file_id, actual_file_name, file_size, progress_callback
                )
                
                if download_path:
                    # 验证下载完整性
                    if self._verify_download(download_path, file_size, expected_md5):
                        logger.info(f"Successfully downloaded: {download_path}")
                        return download_path
                    else:
                        logger.error("Download verification failed")
                        # 删除损坏的文件
                        if os.path.exists(download_path):
                            os.remove(download_path)
                
            except HttpError as e:
                if e.resp.status in [403, 429]:  # Rate limit or quota exceeded
                    sleep_time = min(Config.RETRY_DELAY * (2 ** attempt), 60)
                    logger.warning(f"Rate limit hit, sleeping {sleep_time}s")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"HTTP error downloading file: {e}")
                    
            except Exception as e:
                logger.error(f"Error downloading file: {e}")
                
            # 重试前等待
            if attempt < Config.MAX_RETRY_ATTEMPTS - 1:
                time.sleep(Config.RETRY_DELAY)
        
        logger.error(f"Failed to download file {file_id} after {Config.MAX_RETRY_ATTEMPTS} attempts")
        return None
    
    def download_files_batch(self, file_list: List[Dict], 
                           progress_callback: Callable = None) -> List[Dict]:
        """
        批量并发下载文件
        
        Args:
            file_list (List[Dict]): 文件列表，每个包含id和name
            progress_callback (Callable): 进度回调函数
            
        Returns:
            List[Dict]: 下载结果列表
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=Config.MAX_CONCURRENT_DOWNLOADS) as executor:
            # 提交下载任务
            future_to_file = {}
            for file_info in file_list:
                file_id = file_info['id']
                file_name = file_info.get('name', f"file_{file_id}")
                
                future = executor.submit(
                    self.download_file, 
                    file_id, 
                    file_name, 
                    progress_callback
                )
                future_to_file[future] = file_info
            
            # 收集结果
            for future in as_completed(future_to_file):
                file_info = future_to_file[future]
                try:
                    download_path = future.result()
                    result = {
                        'file_id': file_info['id'],
                        'file_name': file_info.get('name'),
                        'download_path': download_path,
                        'success': download_path is not None,
                        'error': None
                    }
                except Exception as e:
                    result = {
                        'file_id': file_info['id'],
                        'file_name': file_info.get('name'),
                        'download_path': None,
                        'success': False,
                        'error': str(e)
                    }
                
                results.append(result)
                logger.info(f"Download result: {result}")
        
        return results
    
    def _get_available_space(self, path: str) -> int:
        """获取可用磁盘空间（字节）"""
        try:
            statvfs = os.statvfs(path)
            return statvfs.f_frsize * statvfs.f_bavail
        except AttributeError:
            # Windows系统
            import shutil
            return shutil.disk_usage(path).free
        except Exception as e:
            logger.error(f"Error getting available space: {e}")
            return float('inf')  # 假设有足够空间
    
    def cleanup_temp_files(self):
        """清理临时文件"""
        try:
            temp_files = list(Path(Config.DOWNLOAD_PATH).glob("*.tmp"))
            for temp_file in temp_files:
                temp_file.unlink()
                logger.info(f"Removed temp file: {temp_file}")
            
            if temp_files:
                logger.info(f"Cleaned up {len(temp_files)} temporary files")
                
        except Exception as e:
            logger.error(f"Error cleaning up temp files: {e}")
    
    def get_download_status(self) -> Dict:
        """获取下载器状态信息"""
        return {
            'active_downloads': len(self.active_downloads),
            'max_concurrent': Config.MAX_CONCURRENT_DOWNLOADS,
            'download_path': Config.DOWNLOAD_PATH,
            'retry_attempts': Config.MAX_RETRY_ATTEMPTS
        }