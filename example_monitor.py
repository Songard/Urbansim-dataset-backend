#!/usr/bin/env python3
"""
Google Drive监控模块使用示例

此脚本演示如何使用DriveMonitor类来监控Google Drive文件夹中的新文件。
根据requirements.md中2.1节的功能要求实现。
"""

import logging
from typing import List, Dict

from config import Config
from monitor.drive_monitor import DriveMonitor

# 设置日志
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

def process_new_files(files: List[Dict]):
    """
    处理新文件的回调函数
    
    Args:
        files (List[Dict]): 新文件列表
    """
    logger.info(f"Processing {len(files)} new files")
    
    for file_info in files:
        try:
            file_id = file_info['id']
            file_name = file_info['name']
            file_size = file_info['size']
            created_time = file_info['createdTime']
            
            logger.info(f"New file detected: {file_name}")
            logger.info(f"  - ID: {file_id}")
            logger.info(f"  - Size: {file_size / (1024*1024):.2f} MB")
            logger.info(f"  - Created: {created_time}")
            logger.info(f"  - MIME Type: {file_info['mimeType']}")
            
            # 这里可以添加具体的文件处理逻辑
            # 例如：下载文件、解压验证、写入Google Sheets等
            
            # 处理完成后标记为已处理
            monitor.mark_as_processed(file_id)
            logger.info(f"Marked file {file_name} as processed")
            
        except Exception as e:
            logger.error(f"Error processing file {file_info.get('name', 'Unknown')}: {e}")

def main():
    """主函数"""
    try:
        # 验证配置
        Config.validate()
        logger.info("Configuration validated successfully")
        
        # 初始化监控器
        monitor = DriveMonitor(
            folder_id=Config.DRIVE_FOLDER_ID,
            credentials_file=Config.SERVICE_ACCOUNT_FILE
        )
        
        # 显示监控状态
        status = monitor.get_status()
        logger.info("Monitor Status:")
        for key, value in status.items():
            logger.info(f"  {key}: {value}")
        
        # 单次检查示例
        logger.info("Performing single check for new files...")
        new_files = monitor.get_new_files()
        if new_files:
            process_new_files(new_files)
        else:
            logger.info("No new files found")
        
        # 开始持续监控（注释掉以避免无限循环）
        # logger.info("Starting continuous monitoring...")
        # monitor.start_monitoring(process_new_files)
        
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
    except Exception as e:
        logger.error(f"Error in main: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())