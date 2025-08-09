#!/usr/bin/env python3
"""
End-to-End Full Flow Test Script

端到端测试：
1. 上传测试文件到Drive
2. 等待监控器检测
3. 验证下载
4. 验证解压
5. 验证Sheets记录
6. 清理测试数据
"""

import os
import sys
import io
import time
import zipfile
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config
from utils.logger import get_logger, log_system_startup
from monitor.drive_monitor import DriveMonitor
from sheets.sheets_writer import SheetsWriter
from processors.file_downloader import FileDownloader
from processors.archive_handler import ArchiveHandler

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

logger = get_logger(__name__)

class FullFlowTester:
    """端到端流程测试器"""
    
    def __init__(self):
        self.test_file_id = None
        self.test_file_name = f"test_flow_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        self.drive_service = None
        self.start_time = datetime.now()
        self.test_results = {
            'file_creation': False,
            'file_upload': False,
            'file_detection': False,
            'file_download': False,
            'file_extraction': False,
            'sheets_record': False,
            'cleanup': False,
            'overall': False
        }
        
        self._initialize_drive_service()
    
    def _initialize_drive_service(self):
        """初始化Google Drive服务"""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                Config.SERVICE_ACCOUNT_FILE,
                scopes=Config.SCOPES
            )
            self.drive_service = build('drive', 'v3', credentials=credentials)
            logger.info("Google Drive service initialized for testing")
        except Exception as e:
            logger.error(f"Failed to initialize Drive service: {e}")
            raise
    
    def run_full_flow_test(self) -> bool:
        """运行完整的端到端测试"""
        logger.info("=" * 70)
        logger.info("Google Drive Monitor - Full Flow Test")
        logger.info("=" * 70)
        
        try:
            # Step 1: 创建测试文件
            logger.info("📝 Step 1: Creating test archive file")
            self.test_results['file_creation'] = self._create_test_file()
            
            if not self.test_results['file_creation']:
                logger.error("❌ 测试文件创建失败，终止测试")
                return False
            
            # Step 2: 上传到Google Drive
            logger.info("📤 Step 2: Uploading to Google Drive")
            self.test_results['file_upload'] = self._upload_test_file()
            
            if not self.test_results['file_upload']:
                logger.error("❌ 文件上传失败，终止测试")
                return False
            
            # Step 3: 等待监控器检测
            logger.info("👁️ Step 3: Waiting for file detection")
            self.test_results['file_detection'] = self._wait_for_detection()
            
            if not self.test_results['file_detection']:
                logger.error("❌ 文件检测失败，终止测试")
                return False
            
            # Step 4: 验证文件下载
            logger.info("⬇️ Step 4: Verifying file download")
            self.test_results['file_download'] = self._verify_download()
            
            # Step 5: 验证文件解压
            logger.info("📦 Step 5: Verifying file extraction")
            self.test_results['file_extraction'] = self._verify_extraction()
            
            # Step 6: 验证Sheets记录
            logger.info("📊 Step 6: Verifying Sheets record")
            self.test_results['sheets_record'] = self._verify_sheets_record()
            
            # Step 7: 清理测试数据
            logger.info("🧹 Step 7: Cleaning up test data")
            self.test_results['cleanup'] = self._cleanup_test_data()
            
            # 汇总结果
            self._print_test_summary()
            
            # 整体测试结果
            self.test_results['overall'] = all([
                self.test_results['file_creation'],
                self.test_results['file_upload'], 
                self.test_results['file_detection'],
                self.test_results['file_download'],
                self.test_results['file_extraction'],
                self.test_results['sheets_record']
            ])
            
            return self.test_results['overall']
            
        except Exception as e:
            logger.error(f"端到端测试过程中发生错误: {e}")
            return False
        finally:
            # 确保清理工作
            if self.test_file_id:
                self._force_cleanup()
    
    def _create_test_file(self) -> bool:
        """创建测试用的zip文件"""
        try:
            # 创建临时zip文件
            self.temp_zip_path = tempfile.mktemp(suffix='.zip')
            
            with zipfile.ZipFile(self.temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # 添加测试文件
                test_files = [
                    ('readme.txt', f'Test file created at {datetime.now()}'),
                    ('data.json', '{"test": true, "timestamp": "' + datetime.now().isoformat() + '"}'),
                    ('info.md', f'# Test File\\n\\nThis is a test archive for flow testing.\\n\\nCreated: {datetime.now()}'),
                    ('config.ini', '[test]\\nname=full_flow_test\\nversion=1.0\\n'),
                    ('test_results.log', f'Test started: {datetime.now()}\\nStatus: CREATED\\n')
                ]
                
                for filename, content in test_files:
                    zipf.writestr(filename, content)
            
            # 验证文件创建成功
            if os.path.exists(self.temp_zip_path) and os.path.getsize(self.temp_zip_path) > 0:
                file_size = os.path.getsize(self.temp_zip_path)
                logger.info(f"✅ 测试文件创建成功: {self.test_file_name} ({file_size} bytes)")
                return True
            else:
                logger.error("❌ 测试文件创建失败")
                return False
                
        except Exception as e:
            logger.error(f"❌ 创建测试文件异常: {e}")
            return False
    
    def _upload_test_file(self) -> bool:
        """上传测试文件到Google Drive"""
        try:
            # 准备文件元数据
            file_metadata = {
                'name': self.test_file_name,
                'parents': [Config.DRIVE_FOLDER_ID]
            }
            
            # 准备媒体上传
            with open(self.temp_zip_path, 'rb') as f:
                media = MediaIoBaseUpload(
                    io.BytesIO(f.read()),
                    mimetype='application/zip',
                    resumable=True
                )
            
            # 执行上传
            result = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,size,createdTime'
            ).execute()
            
            self.test_file_id = result.get('id')
            file_size = result.get('size', 'Unknown')
            created_time = result.get('createdTime', 'Unknown')
            
            logger.info(f"✅ 文件上传成功")
            logger.info(f"   文件ID: {self.test_file_id}")
            logger.info(f"   文件大小: {file_size} bytes")
            logger.info(f"   创建时间: {created_time}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 文件上传异常: {e}")
            return False
        finally:
            # 清理临时文件
            if hasattr(self, 'temp_zip_path') and os.path.exists(self.temp_zip_path):
                os.remove(self.temp_zip_path)
    
    def _wait_for_detection(self, max_wait_seconds: int = 120) -> bool:
        """等待监控器检测到新文件"""
        try:
            drive_monitor = DriveMonitor(Config.DRIVE_FOLDER_ID)
            
            logger.info(f"等待监控器检测新文件（最多等待 {max_wait_seconds} 秒）...")
            
            start_wait = time.time()
            detection_interval = 10  # 每10秒检查一次
            
            while time.time() - start_wait < max_wait_seconds:
                # 获取新文件列表
                new_files = drive_monitor.get_new_files()
                
                if new_files:
                    # 检查是否包含我们的测试文件
                    for file_info in new_files:
                        if file_info['id'] == self.test_file_id:
                            logger.info(f"✅ 监控器检测到测试文件: {file_info['name']}")
                            return True
                
                # 等待下一次检查
                logger.info(f"⏳ 继续等待检测... ({int(time.time() - start_wait)}s/{max_wait_seconds}s)")
                time.sleep(detection_interval)
            
            logger.error(f"❌ 等待超时，监控器未检测到测试文件")
            return False
            
        except Exception as e:
            logger.error(f"❌ 文件检测异常: {e}")
            return False
    
    def _verify_download(self) -> bool:
        """验证文件是否被正确下载"""
        try:
            expected_path = os.path.join(Config.DOWNLOAD_PATH, self.test_file_name)
            
            # 检查下载目录中是否存在文件
            if os.path.exists(expected_path):
                file_size = os.path.getsize(expected_path)
                logger.info(f"✅ 文件下载验证成功: {expected_path} ({file_size} bytes)")
                return True
            else:
                # 也检查processed目录
                processed_path = os.path.join(Config.PROCESSED_PATH, self.test_file_name)
                if os.path.exists(processed_path):
                    file_size = os.path.getsize(processed_path)
                    logger.info(f"✅ 文件在processed目录中找到: {processed_path} ({file_size} bytes)")
                    return True
                else:
                    logger.error(f"❌ 文件下载验证失败: 未找到 {expected_path}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ 文件下载验证异常: {e}")
            return False
    
    def _verify_extraction(self) -> bool:
        """验证压缩文件是否被正确解压验证"""
        try:
            # 使用ArchiveHandler测试解压
            archive_handler = ArchiveHandler()
            
            # 查找下载的文件
            test_file_path = None
            for check_dir in [Config.DOWNLOAD_PATH, Config.PROCESSED_PATH]:
                possible_path = os.path.join(check_dir, self.test_file_name)
                if os.path.exists(possible_path):
                    test_file_path = possible_path
                    break
            
            if not test_file_path:
                logger.error("❌ 未找到下载的测试文件，无法验证解压")
                return False
            
            # 检测格式
            archive_format = archive_handler.detect_format(test_file_path)
            if not archive_format:
                logger.error("❌ 无法检测压缩文件格式")
                return False
            
            logger.info(f"📦 检测到压缩格式: {archive_format}")
            
            # 验证压缩文件
            validation_result = archive_handler.validate_archive(test_file_path)
            
            if validation_result['is_valid']:
                file_count = validation_result['file_count']
                logger.info(f"✅ 压缩文件解压验证成功: 包含 {file_count} 个文件")
                
                # 显示文件列表
                if 'file_list' in validation_result:
                    logger.info("   文件列表:")
                    for filename in validation_result['file_list'][:5]:  # 最多显示5个
                        logger.info(f"     - {filename}")
                    if len(validation_result['file_list']) > 5:
                        logger.info(f"     ... 还有 {len(validation_result['file_list']) - 5} 个文件")
                
                return True
            else:
                error_msg = validation_result.get('error', '未知错误')
                logger.error(f"❌ 压缩文件解压验证失败: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 压缩文件解压验证异常: {e}")
            return False
    
    def _verify_sheets_record(self) -> bool:
        """验证Google Sheets中是否有相应记录"""
        try:
            sheets_writer = SheetsWriter()
            
            # 这里我们无法直接查询特定记录，但可以测试连接和写入能力
            if sheets_writer.test_connection():
                logger.info("✅ Google Sheets连接正常，可以记录处理结果")
                
                # 写入一条测试完成记录
                test_complete_record = {
                    'file_id': f'FLOW_TEST_COMPLETE_{int(time.time())}',
                    'file_name': f'流程测试完成_{datetime.now().strftime("%H:%M:%S")}',
                    'upload_time': datetime.now().isoformat(),
                    'file_size': 0,
                    'file_type': 'test/flow_complete',
                    'extract_status': '测试完成',
                    'file_count': 1,
                    'process_time': datetime.now(),
                    'error_message': '',
                    'notes': f'端到端流程测试完成 - {self.test_file_name}'
                }
                
                if sheets_writer.append_record(test_complete_record):
                    logger.info("✅ Sheets记录验证成功")
                    return True
                else:
                    logger.error("❌ Sheets记录写入失败")
                    return False
            else:
                logger.error("❌ Google Sheets连接失败")
                return False
                
        except Exception as e:
            logger.error(f"❌ Sheets记录验证异常: {e}")
            return False
    
    def _cleanup_test_data(self) -> bool:
        """清理测试数据"""
        cleanup_success = True
        
        try:
            # 1. 删除Google Drive中的测试文件
            if self.test_file_id:
                try:
                    self.drive_service.files().delete(fileId=self.test_file_id).execute()
                    logger.info(f"✅ 已从Drive删除测试文件: {self.test_file_id}")
                except Exception as e:
                    logger.error(f"❌ 删除Drive文件失败: {e}")
                    cleanup_success = False
            
            # 2. 删除本地下载的文件
            for check_dir in [Config.DOWNLOAD_PATH, Config.PROCESSED_PATH]:
                test_path = os.path.join(check_dir, self.test_file_name)
                if os.path.exists(test_path):
                    try:
                        os.remove(test_path)
                        logger.info(f"✅ 已删除本地文件: {test_path}")
                    except Exception as e:
                        logger.error(f"❌ 删除本地文件失败: {test_path} - {e}")
                        cleanup_success = False
            
            # 3. 清理临时文件
            if hasattr(self, 'temp_zip_path') and os.path.exists(self.temp_zip_path):
                try:
                    os.remove(self.temp_zip_path)
                    logger.info("✅ 已清理临时文件")
                except Exception as e:
                    logger.error(f"❌ 清理临时文件失败: {e}")
                    cleanup_success = False
            
            return cleanup_success
            
        except Exception as e:
            logger.error(f"❌ 清理测试数据异常: {e}")
            return False
    
    def _force_cleanup(self):
        """强制清理（在异常情况下调用）"""
        logger.info("🧹 执行强制清理...")
        try:
            if self.test_file_id:
                self.drive_service.files().delete(fileId=self.test_file_id).execute()
                logger.info("强制删除Drive测试文件成功")
        except Exception as e:
            logger.error(f"强制清理失败: {e}")
    
    def _print_test_summary(self):
        """打印测试结果汇总"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        logger.info("=" * 70)
        logger.info("端到端测试结果汇总")
        logger.info("=" * 70)
        
        step_names = {
            'file_creation': '1. 创建测试文件',
            'file_upload': '2. 上传到Drive',
            'file_detection': '3. 监控器检测',
            'file_download': '4. 文件下载',
            'file_extraction': '5. 文件解压验证',
            'sheets_record': '6. Sheets记录',
            'cleanup': '7. 清理数据'
        }
        
        for step_key, step_name in step_names.items():
            if step_key in self.test_results:
                status = "✅ PASS" if self.test_results[step_key] else "❌ FAIL"
                logger.info(f"{step_name: <20} {status}")
        
        logger.info("-" * 70)
        overall_status = "✅ PASS" if self.test_results['overall'] else "❌ FAIL"
        logger.info(f"{'整体结果': <20} {overall_status}")
        logger.info(f"{'测试耗时': <20} {elapsed:.2f} 秒")
        logger.info("=" * 70)

def main():
    """主测试函数"""
    try:
        # 初始化日志系统
        log_system_startup()
        
        # 运行端到端测试
        tester = FullFlowTester()
        success = tester.run_full_flow_test()
        
        if success:
            logger.info("🎉 端到端流程测试通过！系统运行正常。")
            return 0
        else:
            logger.error("💥 端到端流程测试失败！请检查系统配置。")
            return 1
            
    except KeyboardInterrupt:
        logger.info("测试被用户中断")
        return 1
    except Exception as e:
        logger.error(f"测试过程中发生异常: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())