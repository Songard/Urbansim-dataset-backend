#!/usr/bin/env python3
"""
集成示例：Google Drive监控 + 文件下载 + 压缩文件处理

此脚本演示如何将DriveMonitor、FileDownloader和ArchiveHandler
结合使用，实现完整的文件监控和处理流程。
"""

import logging
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from config import Config
from monitor.drive_monitor import DriveMonitor
from processors.file_downloader import FileDownloader
from processors.archive_handler import ArchiveHandler

# 设置日志
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

class IntegratedProcessor:
    """集成处理器：结合监控、下载和压缩文件处理"""
    
    def __init__(self):
        """初始化所有组件"""
        self.monitor = None
        self.downloader = None
        self.archive_handler = None
        self.processed_count = 0
        self.failed_count = 0
        
        try:
            # 初始化各个组件
            self.monitor = DriveMonitor(Config.DRIVE_FOLDER_ID)
            self.downloader = FileDownloader()
            self.archive_handler = ArchiveHandler()
            
            logger.info("IntegratedProcessor initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize IntegratedProcessor: {e}")
            raise
    
    def download_progress_callback(self, downloaded: int, total: int):
        """下载进度回调"""
        if total > 0:
            percentage = (downloaded / total) * 100
            if percentage % 10 == 0:  # 每10%记录一次
                logger.info(f"Download progress: {percentage:.0f}%")
    
    def process_single_file(self, file_info: Dict) -> Dict[str, Any]:
        """
        处理单个文件的完整流程
        
        Args:
            file_info (Dict): 从Drive监控器获取的文件信息
            
        Returns:
            Dict[str, Any]: 处理结果记录
        """
        file_id = file_info['id']
        file_name = file_info['name']
        file_size = file_info.get('size', 0)
        created_time = file_info.get('createdTime', '')
        
        # 创建处理记录
        record = {
            'file_id': file_id,
            'file_name': file_name,
            'upload_time': created_time,
            'file_size': file_size,
            'file_type': Path(file_name).suffix.lower(),
            'extract_status': '未处理',
            'file_count': '',
            'process_time': datetime.now(),
            'error_message': '',
            'notes': ''
        }
        
        try:
            logger.info(f"Processing file: {file_name} ({file_size / (1024*1024):.2f} MB)")
            
            # 步骤1：下载文件
            logger.info("Step 1: Downloading file...")
            download_path = self.downloader.download_file(
                file_id, 
                file_name, 
                self.download_progress_callback
            )
            
            if not download_path:
                record['error_message'] = 'Download failed'
                record['extract_status'] = '下载失败'
                return record
            
            logger.info(f"Download completed: {download_path}")
            record['notes'] = f'Downloaded to: {download_path}'
            
            # 步骤2：检测是否为压缩文件
            file_format = self.archive_handler.detect_format(download_path)
            if not file_format:
                logger.info("File is not a supported archive format")
                record['extract_status'] = '不适用'
                record['notes'] += '; Not an archive file'
                
                # 标记为已处理
                self.monitor.mark_as_processed(file_id)
                return record
            
            logger.info(f"Detected archive format: {file_format}")
            record['file_type'] = file_format
            
            # 步骤3：处理压缩文件
            logger.info("Step 2: Processing archive...")
            archive_result = self._process_archive(download_path, record)
            
            if archive_result['success']:
                record['extract_status'] = '成功'
                record['file_count'] = archive_result.get('file_count', '')
                record['notes'] += f"; Extracted {archive_result.get('file_count', 0)} files"
                
                if archive_result.get('password_used'):
                    record['notes'] += '; Password protected'
                    
                logger.info(f"Archive processing completed successfully")
            else:
                record['extract_status'] = '失败'
                record['error_message'] = archive_result.get('error', 'Unknown error')
                logger.error(f"Archive processing failed: {record['error_message']}")
            
            # 标记为已处理
            self.monitor.mark_as_processed(file_id)
            self.processed_count += 1
            
        except Exception as e:
            logger.error(f"Error processing file {file_name}: {e}")
            record['error_message'] = str(e)
            record['extract_status'] = '错误'
            self.failed_count += 1
        
        return record
    
    def _process_archive(self, file_path: str, record: Dict) -> Dict:
        """处理压缩文件"""
        result = {'success': False, 'error': None}
        
        try:
            # 获取压缩文件信息
            archive_info = self.archive_handler.get_archive_info(file_path)
            
            # 检查是否需要密码
            password = None
            if archive_info.get('is_password_protected'):
                logger.info("Archive is password protected, trying default passwords...")
                password = self.archive_handler.try_passwords(file_path)
                if not password:
                    result['error'] = 'No valid password found'
                    return result
                result['password_used'] = password
            
            # 验证压缩文件
            validation_result = self.archive_handler.validate_archive(file_path, password)
            if not validation_result.get('is_valid'):
                result['error'] = validation_result.get('error', 'Archive validation failed')
                return result
            
            result['file_count'] = validation_result.get('file_count', 0)
            result['total_size'] = validation_result.get('total_size', 0)
            
            # 解压到处理目录
            extract_path = Path(Config.PROCESSED_PATH) / Path(file_path).stem
            extract_result = self.archive_handler.extract_archive(
                file_path, str(extract_path), password
            )
            
            if extract_result:
                result['success'] = True
                result['extract_path'] = extract_result
                logger.info(f"Archive extracted to: {extract_result}")
            else:
                result['error'] = 'Archive extraction failed'
                
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    def process_new_files_callback(self, files: List[Dict]):
        """处理新文件的回调函数"""
        logger.info(f"Processing {len(files)} new files")
        
        processed_records = []
        
        for file_info in files:
            try:
                # 处理单个文件
                record = self.process_single_file(file_info)
                processed_records.append(record)
                
                # 显示处理结果
                status = "✓" if record['extract_status'] in ['成功', '不适用'] else "✗"
                logger.info(f"{status} {record['file_name']}: {record['extract_status']}")
                
            except Exception as e:
                logger.error(f"Error processing file {file_info.get('name', 'Unknown')}: {e}")
                self.failed_count += 1
        
        # TODO: 将处理记录写入Google Sheets
        # sheets_writer = SheetsWriter()
        # sheets_writer.batch_append_records(processed_records)
        
        logger.info(f"Batch processing completed: {len(processed_records)} files processed")
    
    def run_single_check(self):
        """执行单次检查"""
        logger.info("Performing single check for new files...")
        
        try:
            new_files = self.monitor.get_new_files()
            if new_files:
                self.process_new_files_callback(new_files)
            else:
                logger.info("No new files found")
                
        except Exception as e:
            logger.error(f"Error in single check: {e}")
    
    def start_continuous_monitoring(self):
        """开始持续监控"""
        logger.info("Starting continuous monitoring...")
        
        try:
            self.monitor.start_monitoring(self.process_new_files_callback)
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        except Exception as e:
            logger.error(f"Error in continuous monitoring: {e}")
    
    def cleanup(self):
        """清理资源"""
        try:
            if self.downloader:
                self.downloader.cleanup_temp_files()
            
            if self.archive_handler:
                self.archive_handler.cleanup_temp_dirs()
                
            logger.info("Cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def get_status(self) -> Dict:
        """获取处理器状态"""
        return {
            'processed_count': self.processed_count,
            'failed_count': self.failed_count,
            'monitor_status': self.monitor.get_status() if self.monitor else None,
            'downloader_status': self.downloader.get_download_status() if self.downloader else None
        }

def main():
    """主函数"""
    processor = None
    
    try:
        # 验证配置
        Config.validate()
        logger.info("Configuration validated successfully")
        
        # 初始化集成处理器
        processor = IntegratedProcessor()
        
        # 显示初始状态
        status = processor.get_status()
        logger.info("Processor Status:")
        for key, value in status.items():
            logger.info(f"  {key}: {value}")
        
        # 根据命令行参数选择运行模式
        if len(sys.argv) > 1 and sys.argv[1] == "--continuous":
            # 持续监控模式
            processor.start_continuous_monitoring()
        else:
            # 单次检查模式
            processor.run_single_check()
        
        # 显示最终统计
        final_status = processor.get_status()
        logger.info("Final Statistics:")
        logger.info(f"  Processed: {final_status['processed_count']}")
        logger.info(f"  Failed: {final_status['failed_count']}")
        
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Error in main: {e}")
        return 1
    finally:
        if processor:
            processor.cleanup()
    
    return 0

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Usage:")
        print("  python example_integrated.py           # Single check mode")
        print("  python example_integrated.py --continuous  # Continuous monitoring")
        sys.exit(0)
    
    exit(main())