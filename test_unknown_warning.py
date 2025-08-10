#!/usr/bin/env python3
"""
测试unknown场景类型作为警告而不是错误的验证
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path
import zipfile

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from processors.archive_handler import ArchiveHandler
from utils.validators import validate_scene_naming

def create_test_archive(name: str, size_mb: int = 1500) -> str:
    """创建一个测试压缩文件"""
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, name)
    
    # 创建一个指定大小的测试文件
    test_file_path = os.path.join(temp_dir, "test_data.txt")
    with open(test_file_path, 'wb') as f:
        # 写入指定大小的数据
        data = b'0' * (size_mb * 1024 * 1024)
        f.write(data)
    
    # 创建zip文件
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.write(test_file_path, "test_data.txt")
    
    # 清理临时文件
    os.remove(test_file_path)
    
    return zip_path

def test_unknown_scene_type_warning():
    """测试unknown场景类型应该是警告而不是错误"""
    print("=== 测试unknown场景类型警告级别 ===")
    
    handler = ArchiveHandler()
    test_files = []
    
    try:
        # 创建一个命名不规范但大小合理的测试文件
        zip_path = create_test_archive("regular_data.zip", 1500)  # 1.5GB，合理大小
        test_files.append(zip_path)
        
        print(f"测试文件: regular_data.zip (1.5GB)")
        
        # 首先测试场景命名验证函数
        scene_result = validate_scene_naming("regular_data.zip")
        print(f"场景命名验证结果:")
        print(f"  场景类型: {scene_result['scene_type']}")
        print(f"  格式有效: {scene_result['is_valid_format']}")
        print(f"  错误信息: {scene_result.get('error_message', '无')}")
        
        # 测试整体验证（跳过数据格式验证，专注于命名和大小）
        validation_result = handler.validate_archive(zip_path, validate_data_format=False)
        
        print(f"\n整体验证结果:")
        print(f"  验证通过: {validation_result['is_valid']}")
        print(f"  文件大小: {validation_result['total_size'] / (1024*1024*1024):.2f}GB")
        print(f"  错误信息: {validation_result.get('error', '无')}")
        
        # 检查场景验证和大小验证详情
        scene_val = validation_result.get('scene_validation', {})
        size_val = validation_result.get('size_validation', {})
        
        print(f"\n详细验证结果:")
        print(f"  场景类型: {scene_val.get('scene_type', 'N/A')}")
        print(f"  大小状态: {size_val.get('size_status', 'N/A')}")
        print(f"  大小有效: {size_val.get('is_valid_size', 'N/A')}")
        
        # 验证逻辑：
        # 1. 场景类型应该是unknown
        # 2. 大小应该是optimal（1.5GB在合理范围内）
        # 3. 整体验证应该通过（因为unknown只是警告）
        
        success = True
        
        if scene_val.get('scene_type') != 'unknown':
            print(f"ERROR: 预期场景类型为unknown，实际为{scene_val.get('scene_type')}")
            success = False
            
        if size_val.get('size_status') != 'optimal':
            print(f"ERROR: 预期大小状态为optimal，实际为{size_val.get('size_status')}")
            success = False
            
        if not validation_result['is_valid']:
            print("ERROR: 整体验证应该通过，因为unknown场景类型只是警告")
            success = False
        
        if success:
            print("\nPASS - unknown场景类型正确作为警告处理，不影响整体验证结果")
        else:
            print("\nFAIL - unknown场景类型处理有问题")
            
        return success
        
    except Exception as e:
        print(f"测试异常: {e}")
        return False
    
    finally:
        # 清理测试文件
        for test_file in test_files:
            try:
                if os.path.exists(test_file):
                    os.remove(test_file)
                # 清理临时目录
                temp_dir = os.path.dirname(test_file)
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass
        
        # 清理ArchiveHandler的临时目录
        handler.cleanup_temp_dirs()

def test_known_vs_unknown_comparison():
    """对比测试已知类型和未知类型的验证结果"""
    print("\n=== 对比测试：已知类型 vs 未知类型 ===")
    
    handler = ArchiveHandler()
    test_files = []
    
    try:
        # 创建两个相同大小但命名不同的测试文件
        indoor_zip = create_test_archive("Indoor_test.zip", 1500)
        unknown_zip = create_test_archive("unknown_test.zip", 1500)
        test_files.extend([indoor_zip, unknown_zip])
        
        # 测试Indoor文件（已知类型）
        indoor_result = handler.validate_archive(indoor_zip, validate_data_format=False)
        
        # 测试unknown文件（未知类型）
        unknown_result = handler.validate_archive(unknown_zip, validate_data_format=False)
        
        print(f"Indoor文件验证:")
        print(f"  整体验证: {indoor_result['is_valid']}")
        print(f"  场景类型: {indoor_result.get('scene_validation', {}).get('scene_type')}")
        print(f"  错误信息: {indoor_result.get('error', '无')}")
        
        print(f"\nUnknown文件验证:")
        print(f"  整体验证: {unknown_result['is_valid']}")
        print(f"  场景类型: {unknown_result.get('scene_validation', {}).get('scene_type')}")
        print(f"  错误信息: {unknown_result.get('error', '无')}")
        
        # 两个文件都应该验证通过（因为大小都合理）
        if indoor_result['is_valid'] and unknown_result['is_valid']:
            print(f"\nPASS - 两个文件都验证通过，unknown类型不影响整体结果")
            return True
        else:
            print(f"\nFAIL - 验证结果不符合预期")
            return False
            
    except Exception as e:
        print(f"对比测试异常: {e}")
        return False
    
    finally:
        # 清理测试文件
        for test_file in test_files:
            try:
                if os.path.exists(test_file):
                    os.remove(test_file)
                temp_dir = os.path.dirname(test_file)
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass
        
        handler.cleanup_temp_dirs()

def main():
    """运行测试"""
    print("Unknown场景类型警告级别测试")
    print("=" * 50)
    
    success1 = test_unknown_scene_type_warning()
    success2 = test_known_vs_unknown_comparison()
    
    print("\n" + "=" * 50)
    if success1 and success2:
        print("PASS - 所有测试通过！unknown场景类型正确作为警告处理")
        return 0
    else:
        print("FAIL - 部分测试失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())