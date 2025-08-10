#!/usr/bin/env python3
"""
测试PCD点云尺度验证功能
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.validators import validate_pcd_scale, read_pcd_header, parse_pcd_points

def create_test_pcd(file_path: str, width: float = 100.0, height: float = 80.0, points: int = 1000):
    """
    创建一个测试PCD文件
    
    Args:
        file_path (str): 输出文件路径
        width (float): X方向尺度（米）
        height (float): Y方向尺度（米）
        points (int): 点数
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            # 写PCD头部
            f.write("# .PCD v0.7 - Point Cloud Data file format\n")
            f.write("VERSION 0.7\n")
            f.write("FIELDS x y z\n")
            f.write("SIZE 4 4 4\n")
            f.write("TYPE F F F\n")
            f.write("COUNT 1 1 1\n")
            f.write(f"WIDTH {points}\n")
            f.write("HEIGHT 1\n")
            f.write("VIEWPOINT 0 0 0 1 0 0 0\n")
            f.write(f"POINTS {points}\n")
            f.write("DATA ascii\n")
            
            # 生成点云数据
            import random
            for i in range(points):
                x = random.uniform(0, width)
                y = random.uniform(0, height)
                z = random.uniform(0, 10)  # 10米高度范围
                f.write(f"{x:.6f} {y:.6f} {z:.6f}\n")
                
        return True
    except Exception as e:
        print(f"创建测试PCD文件失败: {e}")
        return False

def test_pcd_header_parsing():
    """测试PCD头部解析功能"""
    print("=== 测试PCD头部解析 ===")
    
    temp_dir = tempfile.mkdtemp()
    pcd_file = os.path.join(temp_dir, "test.pcd")
    
    try:
        # 创建测试文件
        if not create_test_pcd(pcd_file, 120.0, 90.0, 5000):
            return False
        
        # 测试头部解析
        header = read_pcd_header(pcd_file)
        
        print(f"版本: {header.get('version')}")
        print(f"字段: {header.get('fields')}")
        print(f"宽度: {header.get('width')}")
        print(f"高度: {header.get('height')}")
        print(f"点数: {header.get('points')}")
        print(f"数据类型: {header.get('data_type')}")
        print(f"错误: {header.get('error', '无')}")
        
        success = (
            header.get('version') == '0.7' and
            header.get('fields') == ['x', 'y', 'z'] and
            header.get('points') == 5000 and
            header.get('data_type') == 'ascii' and
            not header.get('error')
        )
        
        if success:
            print("PASS - PCD头部解析功能正常")
        else:
            print("FAIL - PCD头部解析有问题")
            
        return success
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_pcd_points_parsing():
    """测试PCD点数据解析功能"""
    print("\n=== 测试PCD点数据解析 ===")
    
    temp_dir = tempfile.mkdtemp()
    pcd_file = os.path.join(temp_dir, "test.pcd")
    
    try:
        # 创建测试文件（已知尺度）
        expected_width = 150.0
        expected_height = 100.0
        if not create_test_pcd(pcd_file, expected_width, expected_height, 2000):
            return False
        
        # 测试点数据解析
        point_data = parse_pcd_points(pcd_file, max_points=10000)
        
        print(f"解析点数: {point_data.get('points_parsed')}")
        print(f"X范围: {point_data.get('min_x', 0):.2f} ~ {point_data.get('max_x', 0):.2f}")
        print(f"Y范围: {point_data.get('min_y', 0):.2f} ~ {point_data.get('max_y', 0):.2f}")
        print(f"Z范围: {point_data.get('min_z', 0):.2f} ~ {point_data.get('max_z', 0):.2f}")
        print(f"计算尺度: {point_data.get('width', 0):.2f}m × {point_data.get('height', 0):.2f}m")
        print(f"错误: {point_data.get('error', '无')}")
        
        # 验证尺度计算是否正确（允许一些误差）
        calculated_width = point_data.get('width', 0)
        calculated_height = point_data.get('height', 0)
        
        width_ok = abs(calculated_width - expected_width) < 5.0  # 允许5米误差
        height_ok = abs(calculated_height - expected_height) < 5.0
        points_ok = point_data.get('points_parsed', 0) > 0
        
        success = width_ok and height_ok and points_ok and not point_data.get('error')
        
        if success:
            print("PASS - PCD点数据解析功能正常")
        else:
            print("FAIL - PCD点数据解析有问题")
            
        return success
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_pcd_scale_validation():
    """测试PCD尺度验证功能"""
    print("\n=== 测试PCD尺度验证 ===")
    
    test_cases = [
        # (width, height, expected_status)
        (100.0, 80.0, "optimal"),      # 理想尺度
        (120.0, 90.0, "optimal"),      # 理想尺度
        (40.0, 30.0, "warning_small"), # 偏小
        (250.0, 180.0, "warning_large"), # 偏大
        (8.0, 6.0, "error_too_small"),   # 过小
        (600.0, 400.0, "error_too_large"), # 过大
    ]
    
    temp_dir = tempfile.mkdtemp()
    passed = 0
    total = len(test_cases)
    
    try:
        for i, (width, height, expected_status) in enumerate(test_cases):
            pcd_file = os.path.join(temp_dir, f"test_{i}.pcd")
            
            # 创建测试文件
            if not create_test_pcd(pcd_file, width, height, 1000):
                continue
            
            # 验证尺度
            result = validate_pcd_scale(pcd_file)
            actual_status = result['scale_status']
            is_valid = result['is_valid_scale']
            
            status_match = actual_status == expected_status
            validity_expected = expected_status not in ['error_too_small', 'error_too_large']
            validity_match = is_valid == validity_expected
            
            test_result = "PASS" if (status_match and validity_match) else "FAIL"
            print(f"{test_result} {width:.0f}m×{height:.0f}m -> {actual_status} (valid: {is_valid})")
            
            if not status_match:
                print(f"     预期状态: {expected_status}, 实际: {actual_status}")
            if not validity_match:
                print(f"     预期有效性: {validity_expected}, 实际: {is_valid}")
            if result.get('error_message'):
                print(f"     信息: {result['error_message']}")
            
            if status_match and validity_match:
                passed += 1
        
        print(f"\nPCD尺度验证测试结果: {passed}/{total} 通过")
        return passed == total
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_missing_pcd_file():
    """测试缺失PCD文件的处理"""
    print("\n=== 测试缺失PCD文件处理 ===")
    
    non_existent_file = "/path/to/nonexistent/file.pcd"
    result = validate_pcd_scale(non_existent_file)
    
    print(f"文件不存在时的状态: {result['scale_status']}")
    print(f"错误信息: {result.get('error_message', '无')}")
    
    # 应该有错误信息，但不应该crash
    success = result.get('error_message') and 'PCD文件不存在' in result['error_message']
    
    if success:
        print("PASS - 缺失文件处理正常")
    else:
        print("FAIL - 缺失文件处理有问题")
        
    return success

def test_invalid_pcd_format():
    """测试无效PCD格式的处理"""
    print("\n=== 测试无效PCD格式处理 ===")
    
    temp_dir = tempfile.mkdtemp()
    invalid_pcd = os.path.join(temp_dir, "invalid.pcd")
    
    try:
        # 创建无效的PCD文件
        with open(invalid_pcd, 'w') as f:
            f.write("This is not a valid PCD file\n")
            f.write("It has no proper header\n")
            f.write("And no point data\n")
        
        result = validate_pcd_scale(invalid_pcd)
        
        print(f"无效格式时的状态: {result['scale_status']}")
        print(f"错误信息: {result.get('error_message', '无')}")
        
        # 应该有错误信息，但不应该crash
        success = result.get('error_message') is not None
        
        if success:
            print("PASS - 无效格式处理正常")
        else:
            print("FAIL - 无效格式处理有问题")
            
        return success
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def main():
    """运行所有测试"""
    print("PCD点云尺度验证功能测试")
    print("=" * 50)
    
    all_tests_passed = True
    
    # 运行所有测试
    tests = [
        test_pcd_header_parsing,
        test_pcd_points_parsing,
        test_pcd_scale_validation,
        test_missing_pcd_file,
        test_invalid_pcd_format
    ]
    
    for test_func in tests:
        try:
            if not test_func():
                all_tests_passed = False
        except Exception as e:
            print(f"测试异常: {e}")
            all_tests_passed = False
    
    print("\n" + "=" * 50)
    if all_tests_passed:
        print("PASS - 所有PCD测试通过！点云尺度验证功能正常工作。")
        return 0
    else:
        print("FAIL - 部分PCD测试失败！请检查实现。")
        return 1

if __name__ == "__main__":
    sys.exit(main())