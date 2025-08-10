#!/usr/bin/env python3
"""
测试文件命名格式验证和文件大小检查功能
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.validators import validate_scene_naming, validate_extracted_file_size

def test_scene_naming():
    """测试场景命名验证功能"""
    print("=== 测试场景命名格式验证 ===")
    
    test_cases = [
        # Indoor格式测试
        ("Indoor_scene_001.zip", "indoor", True),
        ("indoor_test.zip", "indoor", True),
        ("INDOOR_DATA.zip", "indoor", True),
        ("I001.zip", "indoor", True),
        ("i_data.zip", "indoor", True),
        ("I-test.zip", "indoor", True),
        ("I 001.zip", "indoor", True),
        
        # Outdoor格式测试
        ("Outdoor_scene_001.zip", "outdoor", True),
        ("outdoor_test.zip", "outdoor", True),
        ("OUTDOOR_DATA.zip", "outdoor", True),
        ("O001.zip", "outdoor", True),
        ("o_data.zip", "outdoor", True),
        ("O-test.zip", "outdoor", True),
        ("O 001.zip", "outdoor", True),
        
        # 未知格式测试（警告级别，不是错误）
        ("test_scene.zip", "unknown", False),
        ("data001.zip", "unknown", False),
        ("scene_Indoor.zip", "unknown", False),
        ("image_data.zip", "unknown", False),
        ("", "unknown", False),
        ("Inside_data.zip", "unknown", False),  # 不是I开头
        ("Outside_data.zip", "unknown", False),  # 不是O开头
    ]
    
    passed = 0
    total = len(test_cases)
    
    for filename, expected_type, expected_valid in test_cases:
        result = validate_scene_naming(filename)
        actual_type = result['scene_type']
        actual_valid = result['is_valid_format']
        
        status = "PASS" if (actual_type == expected_type and actual_valid == expected_valid) else "FAIL"
        print(f"{status} {filename:25} -> {actual_type:8} (valid: {actual_valid})")
        
        if actual_type == expected_type and actual_valid == expected_valid:
            passed += 1
        else:
            print(f"     预期: {expected_type}, {expected_valid}")
            print(f"     实际: {actual_type}, {actual_valid}")
            if result.get('error_message'):
                print(f"     错误: {result['error_message']}")
    
    print(f"\n场景命名验证测试结果: {passed}/{total} 通过")
    return passed == total

def test_file_size_validation():
    """测试文件大小验证功能"""
    print("\n=== 测试文件大小验证 ===")
    
    test_cases = [
        # size_bytes, expected_status, expected_valid
        (0.5 * 1024**3, "warning_small", True),  # 0.5GB - 警告但可接受
        (0.8 * 1024**3, "warning_small", True),  # 0.8GB - 警告但可接受
        (1.0 * 1024**3, "optimal", True),       # 1.0GB - 最佳
        (1.5 * 1024**3, "optimal", True),       # 1.5GB - 最佳
        (2.0 * 1024**3, "optimal", True),       # 2.0GB - 最佳
        (3.0 * 1024**3, "optimal", True),       # 3.0GB - 最佳
        (3.5 * 1024**3, "warning_large", True), # 3.5GB - 警告但可接受
        (4.0 * 1024**3, "warning_large", True), # 4.0GB - 警告但可接受
        (0.3 * 1024**3, "error_too_small", False),  # 0.3GB - 过小
        (7.0 * 1024**3, "error_too_large", False),  # 7.0GB - 过大
    ]
    
    passed = 0
    total = len(test_cases)
    
    for size_bytes, expected_status, expected_valid in test_cases:
        result = validate_extracted_file_size(int(size_bytes))
        actual_status = result['size_status']
        actual_valid = result['is_valid_size']
        
        size_gb = result['size_gb']
        status = "PASS" if (actual_status == expected_status and actual_valid == expected_valid) else "FAIL"
        print(f"{status} {size_gb:5.2f}GB -> {actual_status:15} (valid: {actual_valid})")
        
        if actual_status == expected_status and actual_valid == expected_valid:
            passed += 1
        else:
            print(f"     预期: {expected_status}, {expected_valid}")
            print(f"     实际: {actual_status}, {actual_valid}")
            if result.get('error_message'):
                print(f"     信息: {result['error_message']}")
    
    print(f"\n文件大小验证测试结果: {passed}/{total} 通过")
    return passed == total

def main():
    """运行所有测试"""
    print("开始测试文件结构和命名规范检查功能...\n")
    
    all_tests_passed = True
    
    # 测试场景命名验证
    if not test_scene_naming():
        all_tests_passed = False
    
    # 测试文件大小验证
    if not test_file_size_validation():
        all_tests_passed = False
    
    print("\n" + "="*50)
    if all_tests_passed:
        print("PASS - 所有测试通过！文件结构和命名规范检查功能正常工作。")
        return 0
    else:
        print("FAIL - 部分测试失败！请检查实现。")
        return 1

if __name__ == "__main__":
    sys.exit(main())