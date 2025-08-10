import os
import sys
import argparse
import signal
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from config import Config
from utils.logger import get_logger, log_system_startup, log_system_shutdown, log_error_with_context
from utils.validators import validate_environment
# 邮件通知模块导入（可选）
try:
    from utils.email_notifier import EmailNotifier
    EMAIL_MODULE_AVAILABLE = True
except ImportError as e:
    print(f"警告: 邮件通知模块不可用: {e}")
    print("系统将在无邮件通知的情况下运行")
    EmailNotifier = None
    EMAIL_MODULE_AVAILABLE = False
from monitor.drive_monitor import DriveMonitor
from monitor.file_tracker import FileTracker
from processors.file_downloader import FileDownloader
from processors.archive_handler import ArchiveHandler
from sheets.sheets_writer import SheetsWriter
from validation.manager import ValidationManager

logger = get_logger(__name__)

class GoogleDriveMonitorSystem:
    """
    Google Drive 自动监控系统主程序
    
    功能流程：
    1. 初始化配置和日志
    2. 验证Google API连接
    3. 创建必要的目录
    4. 加载已处理文件记录
    5. 启动监控循环
    6. 处理新文件：
       a. 下载文件
       b. 验证格式
       c. 解压测试
       d. 写入Sheets
       e. 更新记录
    7. 清理临时文件
    8. 优雅退出处理
    """
    
    def __init__(self, args=None):
        self.args = args or argparse.Namespace()
        self.drive_monitor = None
        self.file_tracker = None
        self.file_downloader = None
        self.archive_handler = None
        self.sheets_writer = None
        self.email_notifier = None
        self.validation_manager = None
        self.running = True
        self.stats = {
            'files_processed': 0,
            'files_failed': 0,
            'start_time': datetime.now()
        }
        
        # 注册信号处理器
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """处理退出信号"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False
        Config.ENABLE_MONITORING = False
    
    def initialize_system(self) -> bool:
        """初始化系统组件"""
        try:
            logger.info("Initializing Google Drive Monitor System...")
            
            # 验证环境和配置
            if not validate_environment():
                logger.error("Environment validation failed")
                return False
            
            # 验证配置
            Config.validate()
            
            # 初始化组件
            self.drive_monitor = DriveMonitor(Config.DRIVE_FOLDER_ID, Config.SERVICE_ACCOUNT_FILE)
            self.file_tracker = FileTracker()
            self.file_downloader = FileDownloader()
            self.archive_handler = ArchiveHandler()
            self.sheets_writer = SheetsWriter()
            self.validation_manager = ValidationManager()
            
            # 初始化邮件通知器（如果启用且可用）
            if Config.EMAIL_NOTIFICATIONS_ENABLED and EMAIL_MODULE_AVAILABLE:
                self.email_notifier = EmailNotifier()
                logger.info("Email notifications enabled")
            elif Config.EMAIL_NOTIFICATIONS_ENABLED and not EMAIL_MODULE_AVAILABLE:
                logger.warning("Email notifications requested but module not available")
                self.email_notifier = None
            else:
                logger.info("Email notifications disabled")
            
            # 测试连接
            if not self._test_connections():
                logger.error("Connection tests failed")
                return False
            
            logger.success("System initialization completed successfully")
            return True
            
        except Exception as e:
            log_error_with_context(e, {'phase': 'initialization'})
            # 发送系统错误通知
            if hasattr(self, 'email_notifier') and self.email_notifier:
                self.email_notifier.notify_error("System Initialization Error", str(e), {'phase': 'initialization'})
            return False
    
    def _test_connections(self) -> bool:
        """测试各组件连接"""
        try:
            logger.info("Testing component connections...")
            
            # 测试Drive连接
            status = self.drive_monitor.get_status()
            logger.info(f"Drive Monitor: folder_id={status['folder_id']}, processed={status['processed_count']}")
            
            # 测试Sheets连接
            if not self.sheets_writer.test_connection():
                logger.error("Sheets connection test failed")
                return False
            
            # 测试下载器
            downloader_status = self.file_downloader.get_download_status()
            logger.info(f"File Downloader: max_concurrent={downloader_status['max_concurrent']}")
            
            # 测试邮件通知（如果启用）
            if self.email_notifier:
                if self.email_notifier.test_connection():
                    logger.info("Email notifications: connection test passed")
                else:
                    logger.warning("Email notifications: connection test failed")
            
            logger.success("All connection tests passed")
            return True
            
        except Exception as e:
            log_error_with_context(e, {'phase': 'connection_test'})
            return False
    
    def process_file(self, file_info: Dict[str, Any]) -> bool:
        """
        处理单个文件
        
        Args:
            file_info (Dict): 文件信息
            
        Returns:
            bool: 处理是否成功
        """
        file_id = file_info['id']
        file_name = file_info['name']
        process_start_time = datetime.now()
        
        try:
            logger.info(f"开始处理文件: {file_name} ({file_info.get('size', 0) / (1024*1024):.2f} MB)")
            
            # 1. 下载文件
            logger.info(f"正在下载文件: {file_name}")
            download_path = self.file_downloader.download_file(file_id, file_name)
            
            if not download_path:
                error_msg = f"文件下载失败: {file_name}"
                logger.error(error_msg)
                self._record_failed_processing(file_info, error_msg, process_start_time)
                return False
            
            # 2. 验证和解压（如果是压缩文件）
            extract_status = "不适用"
            file_count = ""
            error_message = ""
            validation_score = ""
            
            try:
                # 检测是否为压缩文件
                archive_format = self.archive_handler.detect_format(download_path)
                
                if archive_format:
                    logger.info(f"检测到压缩文件格式: {archive_format}")
                    
                    # 尝试验证压缩文件（包含数据格式验证）
                    archive_validation_result = self.archive_handler.validate_archive(download_path, validate_data_format=True)
                    
                    # 使用新的validation系统进行额外的数据验证
                    data_validation_result = None
                    try:
                        # 尝试对解压后的数据进行validation
                        if archive_validation_result['is_valid']:
                            # 创建临时解压目录进行验证
                            temp_extract_dir = os.path.join(Config.TEMP_DIR, f"validation_{file_id}")
                            os.makedirs(temp_extract_dir, exist_ok=True)
                            
                            # 解压文件进行验证
                            if self.archive_handler.extract_archive(download_path, temp_extract_dir):
                                data_validation_result = self.validation_manager.validate(temp_extract_dir)
                                logger.info(f"Data validation completed: {data_validation_result.summary}")
                                logger.debug(f"Validation result type: {type(data_validation_result)}")
                                
                                # 清理临时目录
                                import shutil
                                try:
                                    shutil.rmtree(temp_extract_dir)
                                except Exception as cleanup_e:
                                    logger.warning(f"Failed to cleanup temp directory: {cleanup_e}")
                    except Exception as e:
                        logger.warning(f"Data validation failed: {e}")
                        # validation失败时，设置为None
                        data_validation_result = None
                        
                    validation_result = archive_validation_result
                    
                    if validation_result['is_valid']:
                        extract_status = "成功"
                        file_count = validation_result['file_count']
                        
                        # 检查数据格式验证结果
                        if validation_result.get('data_validation'):
                            data_val = validation_result['data_validation']
                            validation_score = f"{data_val['score']:.1f}/100"
                            if data_val['is_valid']:
                                logger.success(f"压缩文件和数据格式验证成功: {file_count} 个文件, 得分: {data_val['score']:.1f}/100")
                                extract_status = f"成功 (数据验证: {data_val['score']:.1f}/100)"
                            else:
                                logger.warning(f"压缩文件完整，但数据格式验证失败: {data_val['summary']}")
                                extract_status = f"部分成功 (数据格式问题: {len(data_val['errors'])}个错误)"
                                error_message = f"数据格式问题: {', '.join(data_val['errors'][:3])}"
                        else:
                            validation_score = "N/A (跳过验证)"
                            logger.success(f"压缩文件验证成功: {file_count} 个文件 (跳过数据格式验证)")
                    else:
                        extract_status = "失败"
                        error_message = validation_result.get('error', '未知错误')
                        logger.warning(f"压缩文件验证失败: {error_message}")
                        
                        # 尝试用默认密码
                        if "password" in error_message.lower():
                            logger.info("尝试使用默认密码解压...")
                            correct_password = self.archive_handler.try_passwords(download_path)
                            if correct_password:
                                validation_result = self.archive_handler.validate_archive(download_path, correct_password, validate_data_format=True)
                                if validation_result['is_valid']:
                                    extract_status = "成功"
                                    file_count = validation_result['file_count']
                                    error_message = ""
                                    
                                    # 检查数据格式验证结果
                                    if validation_result.get('data_validation'):
                                        data_val = validation_result['data_validation']
                                        validation_score = f"{data_val['score']:.1f}/100"
                                        if data_val['is_valid']:
                                            logger.success(f"使用密码解压成功，数据格式验证通过: {file_count} 个文件, 得分: {data_val['score']:.1f}/100")
                                            extract_status = f"成功 (密码+数据验证: {data_val['score']:.1f}/100)"
                                        else:
                                            logger.warning(f"使用密码解压成功，但数据格式验证失败: {data_val['summary']}")
                                            extract_status = f"部分成功 (密码成功，数据格式问题)"
                                            error_message = f"数据格式问题: {', '.join(data_val['errors'][:3])}"
                                    else:
                                        validation_score = "N/A (跳过验证)"
                                        logger.success(f"使用密码解压成功: {file_count} 个文件")
                
            except Exception as e:
                extract_status = "失败"
                error_message = str(e)
                logger.warning(f"压缩文件处理出错: {e}")
            
            # 3. 提取场景类型、大小状态和PCD尺度信息
            scene_type = ''
            size_status = ''
            pcd_scale = ''
            
            # 从archive validation结果中提取这些信息
            if 'validation_result' in locals() and validation_result:
                scene_validation = validation_result.get('scene_validation', {})
                size_validation = validation_result.get('size_validation', {})
                pcd_validation = validation_result.get('pcd_validation', {})
                
                scene_type = scene_validation.get('scene_type', 'unknown')
                size_status = size_validation.get('size_status', 'unknown')
                
                # PCD Scale显示尺度数值而不是状态
                if pcd_validation and pcd_validation.get('scale_status') != 'not_found':
                    width_m = pcd_validation.get('width_m', 0)
                    height_m = pcd_validation.get('height_m', 0)
                    depth_m = pcd_validation.get('depth_m', 0)
                    pcd_scale = f"{width_m:.1f}×{height_m:.1f}×{depth_m:.1f}m"
                elif pcd_validation and pcd_validation.get('scale_status') == 'not_found':
                    pcd_scale = '未找到PCD'
                else:
                    pcd_scale = '解析失败'
                
                logger.debug(f"验证结果提取: scene_type={scene_type}, size_status={size_status}, pcd_scale={pcd_scale}")

            # 4. 写入Google Sheets
            sheets_record = {
                'file_id': file_id,
                'file_name': file_name,
                'upload_time': file_info.get('createdTime', ''),
                'file_size': file_info.get('size', 0),
                'file_type': file_info.get('mimeType', ''),
                'extract_status': extract_status,
                'file_count': file_count,
                'process_time': process_start_time,
                'validation_score': validation_score,
                'validation_result': data_validation_result,  # 添加validation结果
                'scene_type': scene_type,     # 添加场景类型
                'size_status': size_status,   # 添加大小状态
                'pcd_scale': pcd_scale,      # 添加PCD尺度（显示尺寸）
                # 添加状态信息用于颜色格式化
                'size_status_level': size_validation.get('size_status', 'unknown') if 'validation_result' in locals() and validation_result else 'unknown',
                'pcd_scale_status': pcd_validation.get('scale_status', 'unknown') if 'validation_result' in locals() and validation_result and pcd_validation else 'unknown',
                'error_message': error_message,
                'notes': f"Download path: {download_path}"
            }
            
            
            if self.sheets_writer.append_record(sheets_record):
                logger.success(f"已写入Sheets: {file_name}")
            else:
                logger.warning(f"Sheets写入失败，但文件处理成功: {file_name}")
            
            # 发送成功通知邮件
            if self.email_notifier and Config.NOTIFY_ON_SUCCESS:
                # 检查是否为大文件
                is_large_file = file_info.get('size', 0) / (1024 * 1024) > Config.LARGE_FILE_THRESHOLD_MB
                if Config.NOTIFY_ON_LARGE_FILES and is_large_file:
                    self.email_notifier.notify_file_processed(file_info, True)
                elif not is_large_file:  # 普通文件根据配置发送
                    self.email_notifier.notify_file_processed(file_info, True)
            
            # 4. 更新文件追踪记录
            self.file_tracker.add_processed_file(
                file_id, 
                file_name, 
                status="success",
                metadata={
                    'download_path': str(download_path),
                    'extract_status': extract_status,
                    'file_count': file_count,
                    'process_time': (datetime.now() - process_start_time).total_seconds()
                }
            )
            
            # 5. 移动文件到processed目录
            if Config.CLEAN_TEMP_FILES:
                processed_path = Path(Config.PROCESSED_PATH) / file_name
                try:
                    Path(download_path).rename(processed_path)
                    logger.debug(f"文件已移动到: {processed_path}")
                except Exception as e:
                    logger.warning(f"移动文件失败: {e}")
            
            self.stats['files_processed'] += 1
            process_time = (datetime.now() - process_start_time).total_seconds()
            logger.success(f"文件处理完成: {file_name} (耗时 {process_time:.2f}s)")
            
            return True
            
        except Exception as e:
            error_context = {
                'file_id': file_id,
                'file_name': file_name,
                'phase': 'file_processing'
            }
            log_error_with_context(e, error_context)
            self._record_failed_processing(file_info, str(e), process_start_time)
            return False
        
        finally:
            # 清理临时文件
            self.archive_handler.cleanup_temp_dirs()
    
    def _record_failed_processing(self, file_info: Dict, error_msg: str, start_time: datetime):
        """记录处理失败的文件"""
        try:
            # 写入Sheets
            sheets_record = {
                'file_id': file_info['id'],
                'file_name': file_info['name'],
                'upload_time': file_info.get('createdTime', ''),
                'file_size': file_info.get('size', 0),
                'file_type': file_info.get('mimeType', ''),
                'extract_status': 'Failed',
                'file_count': '',
                'process_time': start_time,
                'validation_score': 'N/A (Failed)',
                'scene_type': 'unknown',      # 失败时设为unknown
                'size_status': 'unknown',     # 失败时设为unknown
                'pcd_scale': 'unknown',       # 失败时设为unknown
                'error_message': error_msg,
                'notes': 'Processing failed'
            }
            self.sheets_writer.append_record(sheets_record)
            
            # 发送失败通知邮件
            if self.email_notifier and Config.NOTIFY_ON_ERROR:
                self.email_notifier.notify_file_processed(file_info, False, error_msg)
            
            # 更新文件追踪
            self.file_tracker.add_processed_file(
                file_info['id'],
                file_info['name'],
                status="failed",
                metadata={'error': error_msg}
            )
            
            self.stats['files_failed'] += 1
            
        except Exception as e:
            logger.error(f"记录失败信息时出错: {e}")
    
    def process_new_files(self, new_files: List[Dict]) -> None:
        """处理新文件列表"""
        if not new_files:
            return
        
        logger.info(f"开始处理 {len(new_files)} 个新文件")
        
        for i, file_info in enumerate(new_files, 1):
            if not self.running:
                logger.info("收到停止信号，中断文件处理")
                break
            
            logger.info(f"处理进度: {i}/{len(new_files)}")
            
            try:
                success = self.process_file(file_info)
                
                # 标记为已处理（无论成功失败）
                self.drive_monitor.mark_as_processed(file_info['id'])
                
                if success:
                    logger.info(f"✅ 文件处理成功: {file_info['name']}")
                else:
                    logger.error(f"❌ 文件处理失败: {file_info['name']}")
                
            except Exception as e:
                logger.error(f"处理文件时发生异常: {file_info['name']} - {e}")
                self.drive_monitor.mark_as_processed(file_info['id'])
        
        # 批量清理
        if Config.CLEAN_TEMP_FILES:
            self.file_downloader.cleanup_temp_files()
        
        logger.info(f"批处理完成: 成功 {self.stats['files_processed']}, 失败 {self.stats['files_failed']}")
    
    def run_once(self) -> bool:
        """运行一次检查和处理"""
        try:
            logger.info("执行一次性文件检查...")
            
            # 获取新文件
            new_files = self.drive_monitor.get_new_files()
            
            if new_files:
                self.process_new_files(new_files)
            else:
                logger.info("未发现新文件")
            
            return True
            
        except Exception as e:
            log_error_with_context(e, {'phase': 'run_once'})
            return False
    
    def start_monitoring(self):
        """启动持续监控"""
        logger.info("启动持续监控模式...")
        
        try:
            self.drive_monitor.start_monitoring(self.process_new_files)
            
        except KeyboardInterrupt:
            logger.info("用户中断监控")
        except Exception as e:
            log_error_with_context(e, {'phase': 'monitoring'})
        finally:
            self.shutdown()
    
    def get_system_stats(self) -> Dict:
        """获取系统统计信息"""
        uptime = datetime.now() - self.stats['start_time']
        file_stats = self.file_tracker.get_statistics()
        
        return {
            'uptime_seconds': uptime.total_seconds(),
            'files_processed_session': self.stats['files_processed'],
            'files_failed_session': self.stats['files_failed'],
            'total_files_processed': file_stats.get('total_processed', 0),
            'success_rate': file_stats.get('success_count', 0) / max(1, file_stats.get('total_processed', 1)) * 100,
            'last_processed': file_stats.get('last_processed'),
            'data_file_size': file_stats.get('data_file_size', 0)
        }
    
    def cleanup_old_records(self):
        """清理过期记录"""
        try:
            cleaned_count = self.file_tracker.cleanup_old_records()
            if cleaned_count > 0:
                logger.info(f"清理了 {cleaned_count} 条过期记录")
        except Exception as e:
            logger.error(f"清理过期记录时出错: {e}")
    
    def shutdown(self):
        """系统关闭"""
        logger.info("正在关闭系统...")
        
        try:
            # 停止监控
            if self.drive_monitor:
                self.drive_monitor.stop_monitoring()
            
            # 清理临时文件
            if Config.CLEAN_TEMP_FILES:
                if self.file_downloader:
                    self.file_downloader.cleanup_temp_files()
                if self.archive_handler:
                    self.archive_handler.cleanup_temp_dirs()
            
            # 清理过期记录
            self.cleanup_old_records()
            
            # 输出统计信息
            stats = self.get_system_stats()
            logger.info("会话统计:")
            logger.info(f"  运行时间: {stats['uptime_seconds']:.1f}s")
            logger.info(f"  处理文件: {stats['files_processed_session']}")
            logger.info(f"  失败文件: {stats['files_failed_session']}")
            logger.info(f"  总计处理: {stats['total_files_processed']}")
            logger.info(f"  成功率: {stats['success_rate']:.1f}%")
            
            # 发送系统状态报告邮件
            if self.email_notifier and Config.NOTIFY_DAILY_REPORT:
                self.email_notifier.notify_system_status(stats)
            
        except Exception as e:
            logger.error(f"关闭系统时出错: {e}")

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="Google Drive 文件监控系统")
    
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    parser.add_argument('--once', action='store_true', help='运行一次后退出')
    parser.add_argument('--interval', type=int, help='设置检查间隔（秒）')
    parser.add_argument('--dry-run', action='store_true', help='模拟运行，不实际下载处理')
    parser.add_argument('--config', type=str, help='指定配置文件路径')
    parser.add_argument('--cleanup', action='store_true', help='清理过期记录后退出')
    parser.add_argument('--stats', action='store_true', help='显示统计信息后退出')
    
    return parser.parse_args()

def main():
    """主程序入口"""
    args = parse_arguments()
    
    try:
        # 调整配置（基于命令行参数）
        if args.debug:
            Config.LOG_LEVEL = 'DEBUG'
        
        if args.interval:
            Config.CHECK_INTERVAL = args.interval
        
        if args.dry_run:
            logger.warning("运行在模拟模式，不会实际下载文件")
        
        # 启动日志系统
        log_system_startup()
        
        # 创建监控系统实例
        monitor_system = GoogleDriveMonitorSystem(args)
        
        # 初始化系统
        if not monitor_system.initialize_system():
            logger.error("系统初始化失败")
            return 1
        
        # 根据参数执行不同操作
        if args.stats:
            stats = monitor_system.get_system_stats()
            print("\n=== 系统统计信息 ===")
            for key, value in stats.items():
                print(f"{key}: {value}")
            return 0
        
        elif args.cleanup:
            monitor_system.cleanup_old_records()
            return 0
        
        elif args.once:
            success = monitor_system.run_once()
            return 0 if success else 1
        
        else:
            # 默认：启动持续监控
            monitor_system.start_monitoring()
            return 0
            
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
        return 0
        
    except Exception as e:
        log_error_with_context(e, {'phase': 'main'})
        return 1
        
    finally:
        log_system_shutdown()

if __name__ == "__main__":
    sys.exit(main())