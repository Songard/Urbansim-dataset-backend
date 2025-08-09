#!/usr/bin/env python3
"""
Data Format Validation Example Script

演示如何使用数据格式验证功能:
1. 创建测试目录结构
2. 运行数据格式验证
3. 展示验证结果
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils.logger import get_logger, log_system_startup
from utils.data_validator import DataFormatValidator, ValidationLevel
from processors.archive_handler import ArchiveHandler

logger = get_logger(__name__)

class DataValidationDemo:
    """数据格式验证演示器"""
    
    def __init__(self):
        self.validator = DataFormatValidator()
        self.archive_handler = ArchiveHandler()
        
    def create_test_structure(self, base_path: str, complete: bool = True) -> str:
        """
        创建测试目录结构
        
        Args:
            base_path (str): 基础路径
            complete (bool): 是否创建完整结构
            
        Returns:
            str: 测试目录路径
        """
        test_dir = os.path.join(base_path, f"test_metacam_{datetime.now().strftime('%H%M%S')}")
        os.makedirs(test_dir, exist_ok=True)
        
        try:
            logger.info(f"创建测试目录结构: {test_dir}")
            
            # 创建目录结构
            directories = [
                "camera",
                "camera/left", 
                "camera/right",
                "data",
                "info"
            ]
            
            for directory in directories:
                os.makedirs(os.path.join(test_dir, directory), exist_ok=True)
                logger.debug(f"创建目录: {directory}")
            
            # 创建必需文件
            required_files = [
                ("colorized-realtime.las", 2 * 1024 * 1024),  # 2MB
                ("points3D.ply", 5 * 1024 * 1024),           # 5MB
                ("Preview.jpg", 500 * 1024),                  # 500KB
                ("Preview.pcd", 10 * 1024 * 1024),           # 10MB
                ("data/data_0", 20 * 1024 * 1024)            # 20MB
            ]
            
            for file_path, size in required_files:
                full_path = os.path.join(test_dir, file_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                
                # 创建指定大小的测试文件
                with open(full_path, 'wb') as f:
                    f.write(b'0' * size)
                logger.debug(f"创建文件: {file_path} ({size} bytes)")
            
            # 创建YAML配置文件
            metadata_content = """
data_type: "MetaCam 3D Reconstruction"
timestamp: "2025-01-08T12:00:00Z"
location: 
  latitude: 39.9042
  longitude: 116.4074
  altitude: 50.5
camera_config:
  left_camera: "enabled"
  right_camera: "enabled"
processing_info:
  software_version: "v2.1.0"
  processing_time: "2025-01-08T11:30:00Z"
"""
            
            with open(os.path.join(test_dir, "metadata.yaml"), 'w', encoding='utf-8') as f:
                f.write(metadata_content)
            logger.debug("创建metadata.yaml")
            
            # 创建JSON配置文件
            info_files = {
                "info/calibration.json": {
                    "camera_matrix": [[1000, 0, 320], [0, 1000, 240], [0, 0, 1]],
                    "distortion_coeffs": [0.1, -0.2, 0, 0, 0]
                },
                "info/device_info.json": {
                    "device_id": "METACAM_001",
                    "firmware_version": "v1.2.3",
                    "serial_number": "MC20250108001"
                },
                "info/rtk_info.json": {
                    "status": "active",
                    "accuracy": "cm_level"
                }
            }
            
            import json
            for file_path, content in info_files.items():
                full_path = os.path.join(test_dir, file_path)
                with open(full_path, 'w', encoding='utf-8') as f:
                    json.dump(content, f, indent=2)
                logger.debug(f"创建JSON文件: {file_path}")
            
            if not complete:
                # 删除一些文件来测试不完整的结构
                os.remove(os.path.join(test_dir, "points3D.ply"))
                os.remove(os.path.join(test_dir, "info/rtk_info.json"))
                logger.info("创建不完整的测试结构（缺少部分文件）")
            
            logger.success(f"测试目录结构创建完成: {test_dir}")
            return test_dir
            
        except Exception as e:
            logger.error(f"创建测试结构失败: {e}")
            if os.path.exists(test_dir):
                shutil.rmtree(test_dir, ignore_errors=True)
            return None
    
    def run_validation_demo(self):
        """运行验证演示"""
        logger.info("=" * 60)
        logger.info("数据格式验证演示")
        logger.info("=" * 60)
        
        temp_base = tempfile.gettempdir()
        
        # 测试1: 完整结构验证
        logger.info("🧪 测试1: 完整结构验证 (标准模式)")
        complete_dir = self.create_test_structure(temp_base, complete=True)
        
        if complete_dir:
            result = self.validator.validate_directory(complete_dir, ValidationLevel.STANDARD)
            self._print_validation_result("完整结构", result)
            
            # 清理
            shutil.rmtree(complete_dir, ignore_errors=True)
        
        # 测试2: 不完整结构验证  
        logger.info("\n🧪 测试2: 不完整结构验证 (标准模式)")
        incomplete_dir = self.create_test_structure(temp_base, complete=False)
        
        if incomplete_dir:
            result = self.validator.validate_directory(incomplete_dir, ValidationLevel.STANDARD)
            self._print_validation_result("不完整结构", result)
            
            # 清理
            shutil.rmtree(incomplete_dir, ignore_errors=True)
        
        # 测试3: 严格模式验证
        logger.info("\n🧪 测试3: 完整结构验证 (严格模式)")
        strict_dir = self.create_test_structure(temp_base, complete=True)
        
        if strict_dir:
            result = self.validator.validate_directory(strict_dir, ValidationLevel.STRICT)
            self._print_validation_result("严格模式", result)
            
            # 清理
            shutil.rmtree(strict_dir, ignore_errors=True)
        
        # 测试4: 宽松模式验证
        logger.info("\n🧪 测试4: 不完整结构验证 (宽松模式)")
        lenient_dir = self.create_test_structure(temp_base, complete=False)
        
        if lenient_dir:
            result = self.validator.validate_directory(lenient_dir, ValidationLevel.LENIENT)
            self._print_validation_result("宽松模式", result)
            
            # 清理
            shutil.rmtree(lenient_dir, ignore_errors=True)
    
    def _print_validation_result(self, test_name: str, result):
        """打印验证结果"""
        logger.info(f"\n📊 {test_name} - 验证结果:")
        logger.info(f"   状态: {'✅ 通过' if result.is_valid else '❌ 失败'}")
        logger.info(f"   得分: {result.score:.1f}/100")
        logger.info(f"   级别: {result.validation_level.value}")
        
        if result.errors:
            logger.info(f"   错误 ({len(result.errors)}):")
            for error in result.errors[:5]:  # 只显示前5个错误
                logger.info(f"     - {error}")
            if len(result.errors) > 5:
                logger.info(f"     ... 还有 {len(result.errors) - 5} 个错误")
        
        if result.warnings:
            logger.info(f"   警告 ({len(result.warnings)}):")
            for warning in result.warnings[:3]:  # 只显示前3个警告
                logger.info(f"     - {warning}")
            if len(result.warnings) > 3:
                logger.info(f"     ... 还有 {len(result.warnings) - 3} 个警告")
        
        logger.info(f"   总结: {result.summary}")
    
    def test_archive_validation(self):
        """测试压缩文件验证"""
        logger.info("\n" + "=" * 60)
        logger.info("压缩文件数据格式验证演示")
        logger.info("=" * 60)
        
        # 注意：这里只是演示框架，实际需要真实的压缩文件进行测试
        logger.info("📦 压缩文件验证功能已集成到ArchiveHandler中")
        logger.info("💡 使用方法:")
        logger.info("   validation_result = archive_handler.validate_archive(file_path, validate_data_format=True)")
        logger.info("   数据验证结果将包含在 validation_result['data_validation'] 中")

def main():
    """主演示函数"""
    try:
        # 初始化日志系统
        log_system_startup()
        
        # 运行验证演示
        demo = DataValidationDemo()
        demo.run_validation_demo()
        demo.test_archive_validation()
        
        logger.success("🎉 数据格式验证演示完成！")
        logger.info("💡 提示: 检查上面的验证结果，了解不同验证级别的行为差异")
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("演示被用户中断")
        return 1
    except Exception as e:
        logger.error(f"演示过程中发生异常: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())