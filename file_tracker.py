#!/usr/bin/env python3
"""
简化的Google Drive文件信息记录工具
监控Google Drive，快速记录新文件的基本信息和场景类型，无需下载
"""

import os
import json
import time
import logging
import signal
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from config import Config
from monitor.drive_monitor import DriveMonitor
from utils.validators import validate_scene_naming

# Create independent logger for file_tracker to avoid conflicts with main.py
import logging
from logging.handlers import RotatingFileHandler

def setup_tracker_logger():
    """Setup independent logger for file tracker"""
    logger = logging.getLogger('file_tracker')

    # Avoid duplicate handlers if logger already exists
    if logger.handlers:
        return logger

    # Set log level based on Config
    log_level = getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)

    # Create logs directory if it doesn't exist
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)

    # File handler with rotation (separate from main.py log)
    file_handler = RotatingFileHandler(
        log_dir / 'file_tracker.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)

    # Formatter
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Add success method
    def success(self, message, *args, **kwargs):
        if self.isEnabledFor(25):  # SUCCESS level
            self._log(25, message, args, **kwargs)

    logging.addLevelName(25, "SUCCESS")
    logging.Logger.success = success

    return logger

logger = setup_tracker_logger()

class SimpleFileTracker:
    """
    简化的文件追踪器
    
    功能：
    1. 监控Google Drive新文件
    2. 快速记录文件基本信息（无需下载）
    3. 基于文件名判断场景类型
    4. 避免重复记录
    5. 保存到本地JSON文件
    """
    
    def __init__(self):
        self.drive_monitor = None
        self.running = True
        self.records_file = "file_records.json"
        self.recorded_files = set()
        self.records = []
        
        # 注册信号处理器
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # 加载已记录文件
        self._load_existing_records()
    
    def _signal_handler(self, signum, frame):
        """处理退出信号"""
        logger.info(f"收到信号 {signum}，准备退出...")
        self.running = False
    
    def _load_existing_records(self):
        """加载已记录的文件"""
        try:
            if os.path.exists(self.records_file):
                with open(self.records_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.records = data.get('records', [])
                    # 构建已记录文件ID集合
                    self.recorded_files = {record['file_id'] for record in self.records}
                    logger.info(f"加载了 {len(self.recorded_files)} 条已记录文件")
            else:
                logger.info("未找到现有记录文件，从头开始")
        except Exception as e:
            logger.error(f"加载记录文件失败: {e}")
    
    def _save_records(self):
        """保存记录到文件"""
        try:
            data = {
                'last_updated': datetime.now().isoformat(),
                'total_records': len(self.records),
                'records': self.records
            }
            
            with open(self.records_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"记录已保存到 {self.records_file}")
        except Exception as e:
            logger.error(f"保存记录失败: {e}")
    
    def _extract_file_info(self, file_info: Dict) -> Dict[str, Any]:
        """提取并处理文件信息"""
        file_id = file_info['id']
        file_name = file_info['name']
        
        # 基于文件名判断场景类型
        scene_validation = validate_scene_naming(file_name)
        scene_type = scene_validation.get('scene_type', 'unknown')
        
        # 提取上传者信息
        owners = file_info.get('owners', [])
        uploader_info = {
            'name': '',
            'email': ''
        }
        
        if owners:
            owner = owners[0]  # 通常第一个是主要上传者
            uploader_info['name'] = owner.get('displayName', '')
            uploader_info['email'] = owner.get('emailAddress', '')
        
        # 构建记录
        record = {
            'file_id': file_id,
            'file_name': file_name,
            'upload_time': file_info.get('createdTime', ''),
            'modified_time': file_info.get('modifiedTime', ''),
            'file_size': file_info.get('size', 0),
            'file_size_mb': round(int(file_info.get('size', 0)) / (1024 * 1024), 2),
            'mime_type': file_info.get('mimeType', ''),
            'scene_type': scene_type,
            'scene_validation': scene_validation,
            'uploader_name': uploader_info['name'],
            'uploader_email': uploader_info['email'],
            'recorded_at': datetime.now().isoformat(),
            'source': 'simple_tracker'
        }
        
        return record
    
    def _process_new_files(self, new_files: List[Dict]):
        """处理新文件列表"""
        if not new_files:
            return
        
        logger.info(f"发现 {len(new_files)} 个新文件")
        
        new_records_count = 0
        for file_info in new_files:
            file_id = file_info['id']
            file_name = file_info['name']
            
            # 检查是否已记录
            if file_id in self.recorded_files:
                logger.debug(f"文件已记录，跳过: {file_name}")
                continue
            
            try:
                # 提取文件信息
                record = self._extract_file_info(file_info)
                
                # 添加到记录
                self.records.append(record)
                self.recorded_files.add(file_id)
                new_records_count += 1
                
                # 日志输出
                scene_info = f"[{record['scene_type'].upper()}]" if record['scene_type'] != 'unknown' else "[未知场景]"
                size_info = f"{record['file_size_mb']:.1f}MB"
                uploader_info = record['uploader_name'] or record['uploader_email'] or '未知用户'
                
                logger.info(f"已记录: {file_name} {scene_info} {size_info} - {uploader_info}")
                
            except Exception as e:
                logger.error(f"处理文件失败 {file_name}: {e}")
                continue
        
        if new_records_count > 0:
            # 保存记录
            self._save_records()
            logger.success(f"本次新增 {new_records_count} 条记录，总计 {len(self.records)} 条")
        else:
            logger.info("未发现需要记录的新文件")
    
    def initialize(self) -> bool:
        """初始化系统"""
        try:
            logger.info("初始化简化文件追踪器...")
            
            # 初始化Drive监控器，但我们自己实现文件获取逻辑
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            
            credentials = service_account.Credentials.from_service_account_file(
                Config.SERVICE_ACCOUNT_FILE,
                scopes=Config.SCOPES
            )
            self.service = build('drive', 'v3', credentials=credentials)
            logger.info("Google Drive服务初始化成功")
            
            logger.success("初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            return False
    
    def _get_all_files_from_drive(self):
        """直接从Drive获取所有文件，绕过DriveMonitor的过滤"""
        try:
            all_files = []
            page_token = None
            
            while True:
                query = f"'{Config.DRIVE_FOLDER_ID}' in parents and trashed=false"
                
                results = self.service.files().list(
                    q=query,
                    fields="nextPageToken, files(id, name, size, mimeType, createdTime, modifiedTime, parents, owners)",
                    orderBy="createdTime desc",
                    pageSize=1000,
                    pageToken=page_token
                ).execute()
                
                files = results.get('files', [])
                all_files.extend(files)
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
            
            logger.info(f"从Drive获取到 {len(all_files)} 个文件")
            return all_files
            
        except Exception as e:
            logger.error(f"获取Drive文件失败: {e}")
            return []

    def run_once(self) -> bool:
        """执行一次检查"""
        try:
            logger.info("执行一次文件检查...")
            
            # 直接获取所有文件
            all_files = self._get_all_files_from_drive()
            
            # 过滤出新文件（未记录的）
            new_files = []
            for file in all_files:
                if file['id'] not in self.recorded_files:
                    new_files.append(file)
            
            logger.info(f"发现 {len(new_files)} 个新文件（总共 {len(all_files)} 个文件）")
            
            # 处理新文件
            self._process_new_files(new_files)
            
            return True
            
        except Exception as e:
            logger.error(f"检查文件时出错: {e}")
            return False
    
    def start_monitoring(self, interval: int = 30):
        """启动持续监控"""
        logger.info(f"启动持续监控模式 (间隔: {interval}秒)...")
        
        try:
            while self.running:
                # 执行一次检查
                self.run_once()
                
                # 等待间隔时间
                for i in range(interval):
                    if not self.running:
                        break
                    time.sleep(1)
            
            logger.info("监控已停止")
            
        except KeyboardInterrupt:
            logger.info("用户中断监控")
        except Exception as e:
            logger.error(f"监控过程中出错: {e}")
        finally:
            self.shutdown()
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        scene_stats = {}
        for record in self.records:
            scene_type = record['scene_type']
            scene_stats[scene_type] = scene_stats.get(scene_type, 0) + 1
        
        total_size_mb = sum(record.get('file_size_mb', 0) for record in self.records)
        
        return {
            'total_files': len(self.records),
            'scene_distribution': scene_stats,
            'total_size_mb': round(total_size_mb, 2),
            'records_file': self.records_file,
            'last_updated': datetime.now().isoformat()
        }
    
    def show_recent_files(self, limit: int = 10):
        """显示最近记录的文件"""
        logger.info(f"最近 {min(limit, len(self.records))} 个文件:")
        
        recent_records = sorted(self.records, key=lambda x: x['recorded_at'], reverse=True)[:limit]
        
        for i, record in enumerate(recent_records, 1):
            scene_info = f"[{record['scene_type'].upper()}]"
            size_info = f"{record['file_size_mb']:.1f}MB"
            uploader_info = record['uploader_name'] or record['uploader_email'] or '未知'
            
            print(f"{i:2d}. {record['file_name'][:50]:<50} {scene_info:<10} {size_info:<10} - {uploader_info}")
    
    def shutdown(self):
        """关闭系统"""
        logger.info("正在关闭系统...")
        
        try:
            # 保存最终记录
            self._save_records()
            
            # 显示统计信息
            stats = self.get_statistics()
            logger.info("会话统计:")
            logger.info(f"  总记录数: {stats['total_files']}")
            logger.info(f"  总大小: {stats['total_size_mb']:.1f} MB")
            logger.info(f"  场景分布: {stats['scene_distribution']}")
            logger.info(f"  记录文件: {stats['records_file']}")
            
        except Exception as e:
            logger.error(f"关闭时出错: {e}")

def main():
    """主程序"""
    import argparse
    
    parser = argparse.ArgumentParser(description="简化的Google Drive文件信息记录工具")
    parser.add_argument('--once', action='store_true', help='运行一次后退出')
    parser.add_argument('--interval', type=int, default=30, help='检查间隔（秒）')
    parser.add_argument('--stats', action='store_true', help='显示统计信息后退出')
    parser.add_argument('--recent', type=int, help='显示最近N个文件后退出')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.debug:
        Config.LOG_LEVEL = 'DEBUG'
    
    try:
        # 创建追踪器
        tracker = SimpleFileTracker()
        
        # 初始化
        if not tracker.initialize():
            logger.error("初始化失败")
            return 1
        
        # 根据参数执行不同操作
        if args.stats:
            stats = tracker.get_statistics()
            print("\n=== 文件记录统计 ===")
            print(f"总记录数: {stats['total_files']}")
            print(f"总大小: {stats['total_size_mb']:.1f} MB")
            print(f"场景分布: {stats['scene_distribution']}")
            print(f"记录文件: {stats['records_file']}")
            return 0
        
        elif args.recent:
            tracker.show_recent_files(args.recent)
            return 0
        
        elif args.once:
            success = tracker.run_once()
            return 0 if success else 1
        
        else:
            # 默认：持续监控
            tracker.start_monitoring(args.interval)
            return 0
    
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
        return 0
    except Exception as e:
        logger.error(f"程序执行失败: {e}")
        return 1

if __name__ == "__main__":
    exit(main())