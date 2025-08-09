#!/usr/bin/env python3
"""
Email Notification Test Script

测试邮件通知功能:
1. 连接测试
2. 成功通知测试
3. 失败通知测试
4. 系统状态报告测试
5. 错误警报测试
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config
from utils.logger import get_logger, log_system_startup
from utils.email_notifier import EmailNotifier

logger = get_logger(__name__)

class EmailTester:
    """邮件功能测试器"""
    
    def __init__(self):
        self.email_notifier = None
        self.test_results = {
            'connection': False,
            'success_notification': False,
            'error_notification': False,
            'status_report': False,
            'error_alert': False,
            'overall': False
        }
    
    def run_email_tests(self) -> bool:
        """运行所有邮件测试"""
        logger.info("=" * 60)
        logger.info("Google Drive Monitor - Email Tests")
        logger.info("=" * 60)
        
        try:
            # 检查邮件配置
            if not Config.EMAIL_NOTIFICATIONS_ENABLED:
                logger.warning("⚠️ 邮件通知功能已禁用")
                logger.info("要启用邮件通知，请在.env文件中设置 EMAIL_NOTIFICATIONS_ENABLED=True")
                return False
            
            if not Config.RECIPIENT_EMAILS:
                logger.error("❌ 未配置收件人邮箱")
                logger.info("请在.env文件中设置 RECIPIENT_EMAILS")
                return False
            
            logger.info(f"📧 邮件配置:")
            logger.info(f"   SMTP服务器: {Config.SMTP_SERVER}:{Config.SMTP_PORT}")
            logger.info(f"   发送者: {Config.SENDER_EMAIL}")
            logger.info(f"   收件人: {', '.join(Config.RECIPIENT_EMAILS)}")
            logger.info(f"   TLS/SSL: TLS={Config.SMTP_USE_TLS}, SSL={Config.SMTP_USE_SSL}")
            
            # 初始化邮件通知器
            self.email_notifier = EmailNotifier()
            
            # Test 1: 连接测试
            logger.info("🔌 Test 1: Connection Test")
            self.test_results['connection'] = self._test_connection()
            
            if not self.test_results['connection']:
                logger.error("❌ 邮件连接失败，终止后续测试")
                return False
            
            # Test 2: 成功通知测试
            logger.info("✅ Test 2: Success Notification")
            self.test_results['success_notification'] = self._test_success_notification()
            
            # Test 3: 错误通知测试
            logger.info("❌ Test 3: Error Notification")
            self.test_results['error_notification'] = self._test_error_notification()
            
            # Test 4: 系统状态报告测试
            logger.info("📊 Test 4: System Status Report")
            self.test_results['status_report'] = self._test_status_report()
            
            # Test 5: 错误警报测试
            logger.info("🚨 Test 5: Error Alert")
            self.test_results['error_alert'] = self._test_error_alert()
            
            # 汇总结果
            self._print_test_summary()
            
            # 整体测试结果
            self.test_results['overall'] = all([
                self.test_results['connection'],
                self.test_results['success_notification'],
                self.test_results['error_notification'],
                self.test_results['status_report'],
                self.test_results['error_alert']
            ])
            
            return self.test_results['overall']
            
        except Exception as e:
            logger.error(f"邮件测试过程中发生错误: {e}")
            return False
    
    def _test_connection(self) -> bool:
        """测试邮件连接"""
        try:
            return self.email_notifier.test_connection()
        except Exception as e:
            logger.error(f"连接测试异常: {e}")
            return False
    
    def _test_success_notification(self) -> bool:
        """测试成功通知"""
        try:
            test_file_info = {
                'id': 'TEST_SUCCESS_001',
                'name': f'测试成功通知_{datetime.now().strftime("%H%M%S")}.zip',
                'size': 1024 * 1024 * 5,  # 5MB
                'mimeType': 'application/zip',
                'createdTime': datetime.now().isoformat(),
                'extract_status': '成功',
                'file_count': 10
            }
            
            success = self.email_notifier.notify_file_processed(test_file_info, True)
            if success:
                logger.info("✅ 成功通知邮件发送成功")
            else:
                logger.error("❌ 成功通知邮件发送失败")
            return success
            
        except Exception as e:
            logger.error(f"成功通知测试异常: {e}")
            return False
    
    def _test_error_notification(self) -> bool:
        """测试错误通知"""
        try:
            test_file_info = {
                'id': 'TEST_ERROR_001',
                'name': f'测试错误通知_{datetime.now().strftime("%H%M%S")}.zip',
                'size': 1024 * 1024 * 2,  # 2MB
                'mimeType': 'application/zip',
                'createdTime': datetime.now().isoformat()
            }
            
            error_message = "这是一个测试错误消息：文件损坏无法解压"
            
            success = self.email_notifier.notify_file_processed(
                test_file_info, False, error_message
            )
            if success:
                logger.info("✅ 错误通知邮件发送成功")
            else:
                logger.error("❌ 错误通知邮件发送失败")
            return success
            
        except Exception as e:
            logger.error(f"错误通知测试异常: {e}")
            return False
    
    def _test_status_report(self) -> bool:
        """测试系统状态报告"""
        try:
            test_stats = {
                'uptime_seconds': 3600 * 8,  # 8小时
                'files_processed_session': 15,
                'files_failed_session': 2,
                'total_files_processed': 156,
                'success_rate': 92.3,
                'last_processed': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'data_file_size': 8192
            }
            
            success = self.email_notifier.notify_system_status(test_stats)
            if success:
                logger.info("✅ 系统状态报告邮件发送成功")
            else:
                logger.error("❌ 系统状态报告邮件发送失败")
            return success
            
        except Exception as e:
            logger.error(f"状态报告测试异常: {e}")
            return False
    
    def _test_error_alert(self) -> bool:
        """测试错误警报"""
        try:
            error_type = "连接测试错误"
            error_message = "这是一个测试错误警报：数据库连接超时"
            context = {
                'component': 'database',
                'timeout': '30s',
                'retry_count': 3,
                'last_attempt': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            success = self.email_notifier.notify_error(error_type, error_message, context)
            if success:
                logger.info("✅ 错误警报邮件发送成功")
            else:
                logger.error("❌ 错误警报邮件发送失败")
            return success
            
        except Exception as e:
            logger.error(f"错误警报测试异常: {e}")
            return False
    
    def _print_test_summary(self):
        """打印测试结果汇总"""
        logger.info("=" * 60)
        logger.info("邮件测试结果汇总")
        logger.info("=" * 60)
        
        test_names = {
            'connection': '连接测试',
            'success_notification': '成功通知',
            'error_notification': '错误通知',
            'status_report': '状态报告',
            'error_alert': '错误警报'
        }
        
        for test_key, test_name in test_names.items():
            if test_key in self.test_results:
                status = "✅ PASS" if self.test_results[test_key] else "❌ FAIL"
                logger.info(f"{test_name: <15} {status}")
        
        logger.info("-" * 60)
        overall_status = "✅ PASS" if self.test_results['overall'] else "❌ FAIL"
        logger.info(f"{'整体结果': <15} {overall_status}")
        logger.info("=" * 60)

def main():
    """主测试函数"""
    try:
        # 初始化日志系统
        log_system_startup()
        
        # 运行邮件测试
        tester = EmailTester()
        success = tester.run_email_tests()
        
        if success:
            logger.info("🎉 所有邮件功能测试通过！")
            logger.info("💌 请检查您的收件箱确认收到测试邮件。")
            return 0
        else:
            logger.error("💥 邮件功能测试失败！请检查邮件配置。")
            return 1
            
    except KeyboardInterrupt:
        logger.info("测试被用户中断")
        return 1
    except Exception as e:
        logger.error(f"测试过程中发生异常: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())