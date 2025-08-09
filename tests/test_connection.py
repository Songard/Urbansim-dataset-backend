#!/usr/bin/env python3
"""
Connection and Authentication Test Script

Tests:
1. Service Account认证
2. Drive API连接和权限  
3. Sheets API连接和写入权限
4. 网络连接
5. 本地目录权限
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config
from utils.logger import get_logger, log_system_startup
from utils.validators import validate_environment
from utils.email_notifier import EmailNotifier
from monitor.drive_monitor import DriveMonitor
from sheets.sheets_writer import SheetsWriter
from processors.file_downloader import FileDownloader

logger = get_logger(__name__)

class ConnectionTester:
    """连接测试器"""
    
    def __init__(self):
        self.test_results = {
            'service_account': False,
            'drive_api': False,
            'sheets_api': False,
            'email_notifications': False,
            'network': False,
            'directories': False,
            'overall': False
        }
        self.start_time = datetime.now()
    
    def run_all_tests(self) -> bool:
        """运行所有连接测试"""
        logger.info("=" * 60)
        logger.info("Google Drive Monitor - Connection Tests")
        logger.info("=" * 60)
        
        try:
            # Test 1: 环境验证（包含Service Account和网络）
            logger.info("📋 Test 1: Environment Validation")
            self.test_results['service_account'] = self._test_environment()
            
            # Test 2: Google Drive API连接
            logger.info("📁 Test 2: Google Drive API Connection")
            self.test_results['drive_api'] = self._test_drive_api()
            
            # Test 3: Google Sheets API连接
            logger.info("📊 Test 3: Google Sheets API Connection")
            self.test_results['sheets_api'] = self._test_sheets_api()
            
            # Test 4: 邮件通知测试
            logger.info("📧 Test 4: Email Notifications")
            self.test_results['email_notifications'] = self._test_email_notifications()
            
            # Test 5: 文件下载测试
            logger.info("⬇️ Test 5: File Download System")
            self.test_results['network'] = self._test_file_download()
            
            # Test 6: 目录权限测试
            logger.info("📂 Test 6: Directory Permissions")
            self.test_results['directories'] = self._test_directories()
            
            # 汇总结果
            self._print_summary()
            
            # 整体测试是否通过
            self.test_results['overall'] = all([
                self.test_results['service_account'],
                self.test_results['drive_api'],
                self.test_results['sheets_api'],
                self.test_results['directories']
            ])
            
            return self.test_results['overall']
            
        except Exception as e:
            logger.error(f"测试过程中发生错误: {e}")
            return False
    
    def _test_environment(self) -> bool:
        """测试环境验证"""
        try:
            result = validate_environment()
            if result:
                logger.info("✅ 环境验证通过")
            else:
                logger.error("❌ 环境验证失败")
            return result
        except Exception as e:
            logger.error(f"❌ 环境验证异常: {e}")
            return False
    
    def _test_drive_api(self) -> bool:
        """测试Google Drive API连接"""
        try:
            # 初始化Drive监控器
            drive_monitor = DriveMonitor(Config.DRIVE_FOLDER_ID)
            
            # 获取文件夹状态
            status = drive_monitor.get_status()
            logger.info(f"📁 Drive文件夹ID: {status['folder_id']}")
            logger.info(f"📁 已处理文件数: {status['processed_count']}")
            
            # 尝试获取文件列表
            new_files = drive_monitor.get_new_files()
            logger.info(f"📁 当前文件数: {len(new_files) if new_files is not None else 'Error'}")
            
            if new_files is not None:
                logger.info("✅ Google Drive API连接成功")
                return True
            else:
                logger.error("❌ Google Drive API连接失败")
                return False
                
        except Exception as e:
            logger.error(f"❌ Google Drive API测试异常: {e}")
            return False
    
    def _test_sheets_api(self) -> bool:
        """测试Google Sheets API连接"""
        try:
            # 初始化Sheets写入器
            sheets_writer = SheetsWriter()
            
            # 测试连接
            if sheets_writer.test_connection():
                logger.info("✅ Google Sheets API连接成功")
                
                # 测试写入（写入测试记录）
                test_record = {
                    'file_id': 'TEST_CONNECTION',
                    'file_name': f'连接测试_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
                    'upload_time': datetime.now().isoformat(),
                    'file_size': 0,
                    'file_type': 'test/connection',
                    'extract_status': '测试',
                    'file_count': 1,
                    'process_time': datetime.now(),
                    'error_message': '',
                    'notes': '这是一条连接测试记录，可以安全删除'
                }
                
                if sheets_writer.append_record(test_record):
                    logger.info("✅ Google Sheets写入测试成功")
                    return True
                else:
                    logger.error("❌ Google Sheets写入测试失败")
                    return False
            else:
                logger.error("❌ Google Sheets API连接失败")
                return False
                
        except Exception as e:
            logger.error(f"❌ Google Sheets API测试异常: {e}")
            return False
    
    def _test_email_notifications(self) -> bool:
        """测试邮件通知功能"""
        try:
            if not Config.EMAIL_NOTIFICATIONS_ENABLED:
                logger.info("⏭️ 邮件通知功能已禁用，跳过测试")
                return True
            
            if not Config.RECIPIENT_EMAILS:
                logger.warning("⚠️ 未配置收件人邮箱，跳过邮件测试")
                return True
            
            # 初始化邮件通知器
            email_notifier = EmailNotifier()
            
            # 测试邮件连接
            if email_notifier.test_connection():
                logger.info("✅ 邮件通知功能测试成功")
                return True
            else:
                logger.error("❌ 邮件通知功能测试失败")
                return False
                
        except Exception as e:
            logger.error(f"❌ 邮件通知测试异常: {e}")
            return False
    
    def _test_file_download(self) -> bool:
        """测试文件下载系统"""
        try:
            # 初始化下载器
            downloader = FileDownloader()
            
            # 获取下载器状态
            status = downloader.get_download_status()
            logger.info(f"⬇️ 最大并发下载: {status['max_concurrent']}")
            logger.info(f"⬇️ 下载路径: {status['download_path']}")
            logger.info(f"⬇️ 重试次数: {status['retry_attempts']}")
            
            logger.info("✅ 文件下载系统初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ 文件下载系统测试异常: {e}")
            return False
    
    def _test_directories(self) -> bool:
        """测试目录权限"""
        test_dirs = [
            Config.DOWNLOAD_PATH,
            Config.PROCESSED_PATH,
            os.path.dirname(Config.LOG_FILE),
            os.path.dirname(Config.PROCESSED_FILES_JSON)
        ]
        
        all_success = True
        
        for dir_path in test_dirs:
            try:
                # 创建目录
                os.makedirs(dir_path, exist_ok=True)
                
                # 测试写入
                test_file = os.path.join(dir_path, f'test_{int(time.time())}.tmp')
                with open(test_file, 'w') as f:
                    f.write('test')
                
                # 清理测试文件
                os.remove(test_file)
                
                logger.info(f"✅ 目录权限正常: {dir_path}")
                
            except Exception as e:
                logger.error(f"❌ 目录权限异常: {dir_path} - {e}")
                all_success = False
        
        return all_success
    
    def _print_summary(self):
        """打印测试结果汇总"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        logger.info("=" * 60)
        logger.info("测试结果汇总")
        logger.info("=" * 60)
        
        for test_name, result in self.test_results.items():
            if test_name == 'overall':
                continue
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"{test_name.replace('_', ' ').title(): <25} {status}")
        
        logger.info("-" * 60)
        overall_status = "✅ PASS" if self.test_results['overall'] else "❌ FAIL"
        logger.info(f"{'Overall Result': <25} {overall_status}")
        logger.info(f"{'Test Duration': <25} {elapsed:.2f} seconds")
        logger.info("=" * 60)

def main():
    """主测试函数"""
    try:
        # 初始化日志系统
        log_system_startup()
        
        # 运行连接测试
        tester = ConnectionTester()
        success = tester.run_all_tests()
        
        if success:
            logger.info("🎉 所有连接测试通过！系统可以正常运行。")
            return 0
        else:
            logger.error("💥 连接测试失败！请检查配置和网络连接。")
            return 1
            
    except KeyboardInterrupt:
        logger.info("测试被用户中断")
        return 1
    except Exception as e:
        logger.error(f"测试过程中发生异常: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())