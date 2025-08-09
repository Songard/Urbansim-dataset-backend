#!/usr/bin/env python3
"""
文件下载器和压缩文件处理器使用示例

此脚本演示如何使用FileDownloader和ArchiveHandler类来下载和处理压缩文件。
根据requirements.md中2.2和2.3节的功能要求实现。
"""

import logging
import os
from pathlib import Path
from typing import List, Dict

from config import Config
from processors.file_downloader import FileDownloader
from processors.archive_handler import ArchiveHandler

# 设置日志
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

def download_progress_callback(downloaded: int, total: int):
    """下载进度回调函数"""
    if total > 0:
        percentage = (downloaded / total) * 100
        print(f"Progress: {percentage:.1f}% ({downloaded}/{total} bytes)")

def process_archive_file(file_path: str, archive_handler: ArchiveHandler) -> Dict:
    """
    处理单个压缩文件
    
    Args:
        file_path (str): 压缩文件路径
        archive_handler (ArchiveHandler): 压缩文件处理器实例
        
    Returns:
        Dict: 处理结果
    """
    logger.info(f"Processing archive: {Path(file_path).name}")
    
    result = {
        'file_path': file_path,
        'success': False,
        'format': None,
        'file_count': 0,
        'total_size': 0,
        'extract_path': None,
        'password_used': None,
        'error': None
    }
    
    try:
        # 获取压缩文件详细信息
        archive_info = archive_handler.get_archive_info(file_path)
        logger.info(f"Archive info: {archive_info}")
        
        result['format'] = archive_info.get('format')
        
        # 检查是否需要密码
        password = None
        if archive_info.get('is_password_protected'):
            logger.info("Archive is password protected, trying default passwords...")
            password = archive_handler.try_passwords(file_path)
            if password:
                result['password_used'] = password
                logger.info("Password found successfully")
            else:
                result['error'] = "No valid password found"
                return result
        
        # 验证压缩文件
        validation_result = archive_handler.validate_archive(file_path, password)
        logger.info(f"Validation result: {validation_result}")
        
        if not validation_result.get('is_valid'):
            result['error'] = validation_result.get('error', 'Archive validation failed')
            return result
        
        result['file_count'] = validation_result.get('file_count', 0)
        result['total_size'] = validation_result.get('total_size', 0)
        
        # 解压文件到处理目录
        extract_path = Path(Config.PROCESSED_PATH) / Path(file_path).stem
        extract_result = archive_handler.extract_archive(
            file_path, 
            str(extract_path), 
            password
        )
        
        if extract_result:
            result['extract_path'] = extract_result
            result['success'] = True
            logger.info(f"Successfully processed archive: {Path(file_path).name}")
        else:
            result['error'] = "Archive extraction failed"
            
    except Exception as e:
        logger.error(f"Error processing archive {file_path}: {e}")
        result['error'] = str(e)
    
    return result

def demonstrate_file_downloader():
    """演示文件下载器功能"""
    logger.info("=== File Downloader Demo ===")
    
    try:
        # 初始化下载器
        downloader = FileDownloader()
        
        # 获取下载器状态
        status = downloader.get_download_status()
        logger.info(f"Downloader status: {status}")
        
        # 示例：单文件下载
        # 注意：这里需要实际的Google Drive文件ID
        # file_id = "your_actual_file_id_here"
        # logger.info(f"Downloading single file: {file_id}")
        # download_path = downloader.download_file(file_id, progress_callback=download_progress_callback)
        # 
        # if download_path:
        #     logger.info(f"Download successful: {download_path}")
        #     return download_path
        # else:
        #     logger.error("Download failed")
        
        # 示例：批量下载
        # file_list = [
        #     {'id': 'file_id_1', 'name': 'archive1.zip'},
        #     {'id': 'file_id_2', 'name': 'archive2.rar'},
        # ]
        # 
        # logger.info(f"Starting batch download of {len(file_list)} files")
        # results = downloader.download_files_batch(file_list, download_progress_callback)
        # 
        # for result in results:
        #     if result['success']:
        #         logger.info(f"Downloaded: {result['file_name']} -> {result['download_path']}")
        #     else:
        #         logger.error(f"Failed to download {result['file_name']}: {result['error']}")
        
        # 清理临时文件
        downloader.cleanup_temp_files()
        
        logger.info("File downloader demo completed")
        
    except Exception as e:
        logger.error(f"Error in file downloader demo: {e}")

def demonstrate_archive_handler():
    """演示压缩文件处理器功能"""
    logger.info("=== Archive Handler Demo ===")
    
    try:
        # 初始化处理器
        handler = ArchiveHandler()
        
        # 查找下载目录中的压缩文件
        download_dir = Path(Config.DOWNLOAD_PATH)
        if not download_dir.exists():
            logger.warning(f"Download directory not found: {download_dir}")
            return
        
        # 支持的压缩文件扩展名
        archive_extensions = ['.zip', '.rar', '.7z', '.tar.gz', '.tar.bz2', '.tgz', '.tbz2']
        archive_files = []
        
        for ext in archive_extensions:
            archive_files.extend(download_dir.glob(f"*{ext}"))
        
        if not archive_files:
            logger.info("No archive files found in download directory")
            logger.info("Creating a test scenario...")
            
            # 创建一个示例文件用于演示格式检测
            test_file = download_dir / "test.txt"
            test_file.parent.mkdir(exist_ok=True)
            test_file.write_text("This is a test file for archive processing demo.")
            
            logger.info("Test file created. In a real scenario, you would have downloaded archive files here.")
            return
        
        logger.info(f"Found {len(archive_files)} archive files to process")
        
        # 处理每个压缩文件
        results = []
        for archive_file in archive_files:
            result = process_archive_file(str(archive_file), handler)
            results.append(result)
            
            # 显示处理结果
            if result['success']:
                logger.info(f"✓ {Path(result['file_path']).name}")
                logger.info(f"  Format: {result['format']}")
                logger.info(f"  Files: {result['file_count']}")
                logger.info(f"  Size: {result['total_size'] / (1024*1024):.2f} MB")
                if result['password_used']:
                    logger.info(f"  Password: {'*' * len(result['password_used'])}")
            else:
                logger.error(f"✗ {Path(result['file_path']).name}: {result['error']}")
        
        # 清理临时目录
        handler.cleanup_temp_dirs()
        
        # 汇总统计
        successful = sum(1 for r in results if r['success'])
        logger.info(f"Archive processing completed: {successful}/{len(results)} successful")
        
    except Exception as e:
        logger.error(f"Error in archive handler demo: {e}")

def demonstrate_format_detection():
    """演示格式检测功能"""
    logger.info("=== Format Detection Demo ===")
    
    try:
        handler = ArchiveHandler()
        
        # 测试各种文件格式检测
        test_files = [
            "example.zip",
            "example.rar", 
            "example.7z",
            "example.tar.gz",
            "example.tar.bz2",
            "unknown.abc"
        ]
        
        for file_name in test_files:
            detected_format = handler.detect_format(file_name)
            logger.info(f"{file_name:15} -> {detected_format or 'Unknown'}")
        
        # 显示支持的格式
        logger.info("Supported formats:")
        for ext, format_type in handler.SUPPORTED_FORMATS.items():
            logger.info(f"  {ext:10} -> {format_type}")
            
    except Exception as e:
        logger.error(f"Error in format detection demo: {e}")

def main():
    """主函数"""
    try:
        # 验证配置
        Config.validate()
        logger.info("Configuration validated successfully")
        
        # 演示格式检测
        demonstrate_format_detection()
        
        # 演示文件下载器
        demonstrate_file_downloader()
        
        # 演示压缩文件处理器
        demonstrate_archive_handler()
        
        logger.info("All demos completed successfully")
        
    except KeyboardInterrupt:
        logger.info("Demo stopped by user")
    except Exception as e:
        logger.error(f"Error in main: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())