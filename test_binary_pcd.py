#!/usr/bin/env python3
"""
测试二进制PCD格式支持
"""

import sys
import os
import tempfile
import shutil
import struct
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.validators import validate_pcd_scale, read_pcd_header, parse_pcd_points

def create_test_binary_pcd(file_path: str, width: float = 100.0, height: float = 80.0, points: int = 1000):
    """
    创建一个测试二进制PCD文件
    
    Args:
        file_path (str): 输出文件路径
        width (float): X方向尺度（米）
        height (float): Y方向尺度（米）
        points (int): 点数
    """
    try:
        with open(file_path, 'wb') as f:
            # 写PCD头部（文本格式）
            header = f"""# .PCD v0.7 - Point Cloud Data file format
VERSION 0.7
FIELDS x y z
SIZE 4 4 4
TYPE F F F
COUNT 1 1 1
WIDTH {points}
HEIGHT 1
VIEWPOINT 0 0 0 1 0 0 0
POINTS {points}
DATA binary
""".encode('utf-8')
            
            f.write(header)
            
            # 生成二进制点云数据
            import random
            for i in range(points):
                x = random.uniform(0, width)
                y = random.uniform(0, height)
                z = random.uniform(0, 10)  # 10米高度范围
                
                # 写入32位浮点数（小端序）
                f.write(struct.pack('<fff', x, y, z))
                
        return True
    except Exception as e:
        print(f"创建测试二进制PCD文件失败: {e}")
        return False

def test_binary_pcd_header_parsing():
    """测试二进制PCD头部解析功能"""
    print("=== 测试二进制PCD头部解析 ===")
    
    temp_dir = tempfile.mkdtemp()
    pcd_file = os.path.join(temp_dir, "test_binary.pcd")
    
    try:
        # 创建测试文件
        if not create_test_binary_pcd(pcd_file, 120.0, 90.0, 5000):
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
            header.get('data_type') == 'binary' and
            not header.get('error')
        )
        
        if success:
            print("PASS - 二进制PCD头部解析功能正常")
        else:
            print("FAIL - 二进制PCD头部解析有问题")
            
        return success
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_binary_pcd_points_parsing():
    """测试二进制PCD点数据解析功能"""
    print("\n=== 测试二进制PCD点数据解析 ===")
    
    temp_dir = tempfile.mkdtemp()
    pcd_file = os.path.join(temp_dir, "test_binary.pcd")
    
    try:
        # 创建测试文件（已知尺度）
        expected_width = 150.0
        expected_height = 100.0
        if not create_test_binary_pcd(pcd_file, expected_width, expected_height, 2000):
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
            print("PASS - 二进制PCD点数据解析功能正常")
        else:
            print("FAIL - 二进制PCD点数据解析有问题")
            if not width_ok:
                print(f"     宽度误差过大: 预期{expected_width}, 实际{calculated_width}")
            if not height_ok:
                print(f"     高度误差过大: 预期{expected_height}, 实际{calculated_height}")
            
        return success
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_binary_pcd_scale_validation():
    """测试二进制PCD尺度验证功能"""
    print("\n=== 测试二进制PCD尺度验证 ===")
    
    test_cases = [
        # (width, height, expected_status)
        (100.0, 80.0, "optimal"),      # 理想尺度
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
            pcd_file = os.path.join(temp_dir, f"test_binary_{i}.pcd")
            
            # 创建测试文件
            if not create_test_binary_pcd(pcd_file, width, height, 1000):
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
        
        print(f"\n二进制PCD尺度验证测试结果: {passed}/{total} 通过")
        return passed == total
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def main():
    """运行所有测试"""
    print("二进制PCD格式支持测试")
    print("=" * 50)
    
    all_tests_passed = True
    
    # 运行所有测试
    tests = [
        test_binary_pcd_header_parsing,
        test_binary_pcd_points_parsing, 
        test_binary_pcd_scale_validation
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
        print("PASS - 所有二进制PCD测试通过！二进制格式支持正常工作。")
        return 0
    else:
        print("FAIL - 部分二进制PCD测试失败！请检查实现。")
        return 1

if __name__ == "__main__":
    sys.exit(main())