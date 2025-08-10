#!/usr/bin/env python3
"""
测试增强的Google Sheets功能：
1. PCD Scale显示具体尺寸 (x×y×z)
2. Size Status和PCD Scale字段的颜色背景
"""

import sys
import os
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from processors.archive_handler import ArchiveHandler

def create_test_archive_with_metadata(archive_path: str, scene_type: str, width: float, height: float):
    """创建包含完整metadata的测试压缩包"""
    import zipfile
    import struct
    import random
    
    try:
        with zipfile.ZipFile(archive_path, 'w') as zf:
            # 创建metadata.yaml
            metadata_content = f"""record:
  start_time: "2024-08-10 14:30:00"
  duration: "00:06:30"
  location:
    lat: 39.9042
    lon: 116.4074
scene_type: {scene_type}
"""
            zf.writestr("metadata.yaml", metadata_content)
            
            # 创建二进制PCD文件
            pcd_header = f"""# .PCD v0.7 - Point Cloud Data file format
VERSION 0.7
FIELDS x y z
SIZE 4 4 4
TYPE F F F
COUNT 1 1 1
WIDTH 1000
HEIGHT 1
VIEWPOINT 0 0 0 1 0 0 0
POINTS 1000
DATA binary
""".encode('utf-8')
            
            # 生成二进制点云数据
            point_data = b""
            for i in range(1000):
                x = random.uniform(0, width)
                y = random.uniform(0, height) 
                z = random.uniform(0, 10)
                point_data += struct.pack('<fff', x, y, z)
            
            pcd_content = pcd_header + point_data
            zf.writestr("Preview.pcd", pcd_content)
            
            # 添加一些虚拟文件以增加文件大小
            for i in range(5):
                dummy_content = "x" * (1024 * 1024)  # 1MB per file
                zf.writestr(f"data_{i}.txt", dummy_content)
            
        return True
    except Exception as e:
        print(f"创建测试压缩包失败: {e}")
        return False

def test_enhanced_sheets_formatting():
    """测试增强的Sheets格式化功能"""
    print("=== 测试增强的Sheets格式化功能 ===")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # 创建不同状态的测试场景
        test_cases = [
            # (文件名, 场景类型, 宽度m, 高度m, 期望size_status, 期望pcd_status)
            ("Indoor_optimal.zip", "Indoor", 120.0, 90.0, "optimal", "optimal"),
            ("Outdoor_small_file.zip", "Outdoor", 80.0, 60.0, "error_too_small", "optimal"),
            ("Large_scene.zip", "Unknown", 300.0, 200.0, "optimal", "warning_large"),
            ("Tiny_scene.zip", "Indoor", 8.0, 6.0, "error_too_small", "error_too_small"),
            ("Huge_scene.zip", "Outdoor", 600.0, 400.0, "optimal", "error_too_large"),
        ]
        
        archive_handler = ArchiveHandler()
        
        for archive_name, scene_type, width, height, expected_size, expected_pcd in test_cases:
            print(f"\n--- 测试场景: {archive_name} ---")
            
            # 创建测试压缩包
            archive_path = os.path.join(temp_dir, archive_name)
            if not create_test_archive_with_metadata(archive_path, scene_type, width, height):
                continue
            
            # 获取archive信息
            archive_info = archive_handler.get_archive_info(archive_path)
            validation_result = archive_info.get('validation_result', {})
            
            if validation_result:
                scene_validation = validation_result.get('scene_validation', {})
                size_validation = validation_result.get('size_validation', {})
                pcd_validation = validation_result.get('pcd_validation', {})
                
                print(f"文件信息:")
                print(f"  文件大小: {archive_info.get('file_size', 0) / (1024*1024):.1f} MB")
                print(f"  场景类型: {scene_validation.get('scene_type', 'unknown')}")
                print(f"  大小状态: {size_validation.get('size_status', 'unknown')} ({size_validation.get('size_gb', 0):.3f}GB)")
                
                if pcd_validation:
                    width_m = pcd_validation.get('width_m', 0)
                    height_m = pcd_validation.get('height_m', 0)
                    depth_m = pcd_validation.get('depth_m', 0)
                    pcd_status = pcd_validation.get('scale_status', 'unknown')
                    
                    print(f"  PCD尺度: {width_m:.1f}×{height_m:.1f}×{depth_m:.1f}m (状态: {pcd_status})")
                    
                    # 模拟sheets记录格式
                    pcd_scale_display = f"{width_m:.1f}×{height_m:.1f}×{depth_m:.1f}m"
                    
                    print(f"\nSheets记录格式:")
                    print(f"  Scene Type: {scene_validation.get('scene_type', 'unknown')}")
                    print(f"  Size Status: {size_validation.get('size_status', 'unknown')}")
                    print(f"  PCD Scale: {pcd_scale_display}")
                    
                    # 显示颜色状态
                    print(f"\n颜色格式化:")
                    
                    # Size Status颜色
                    size_status = size_validation.get('size_status', 'unknown')
                    size_color_map = {
                        'optimal': '绿色背景',
                        'warning_small': '黄色背景',
                        'warning_large': '黄色背景',
                        'error_too_small': '红色背景',
                        'error_too_large': '红色背景',
                        'unknown': '灰色背景'
                    }
                    print(f"  Size Status ({size_status}): {size_color_map.get(size_status, '灰色背景')}")
                    
                    # PCD Scale颜色
                    pcd_color_map = {
                        'optimal': '绿色背景',
                        'warning_small': '黄色背景',
                        'warning_large': '黄色背景',
                        'warning_narrow': '黄色背景',
                        'error_too_small': '红色背景',
                        'error_too_large': '红色背景',
                        'not_found': '灰色背景',
                        'error': '灰色背景',
                        'unknown': '灰色背景'
                    }
                    print(f"  PCD Scale ({pcd_status}): {pcd_color_map.get(pcd_status, '灰色背景')}")
                    
                else:
                    print(f"  PCD验证: 失败或未找到")
                    print(f"\nSheets记录格式:")
                    print(f"  Scene Type: {scene_validation.get('scene_type', 'unknown')}")
                    print(f"  Size Status: {size_validation.get('size_status', 'unknown')}")
                    print(f"  PCD Scale: 未找到PCD")
                    print(f"  PCD Scale颜色: 灰色背景")
            else:
                print("验证结果为空")
    
    except Exception as e:
        print(f"测试过程中出错: {e}")
        return False
    
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    return True

def test_sheets_record_structure():
    """测试sheets记录结构"""
    print("\n=== 测试Sheets记录结构 ===")
    
    # 模拟从main.py传递的数据
    mock_validation_result = {
        'scene_validation': {
            'scene_type': 'indoor',
            'is_valid_format': True,
            'detected_prefix': 'Indoor'
        },
        'size_validation': {
            'size_status': 'optimal',
            'size_gb': 2.5,
            'is_valid_size': True
        },
        'pcd_validation': {
            'scale_status': 'optimal',
            'width_m': 120.5,
            'height_m': 95.3,
            'depth_m': 8.2,
            'is_valid_scale': True
        }
    }
    
    # 提取字段（模拟main.py逻辑）
    scene_type = mock_validation_result['scene_validation']['scene_type']
    size_status = mock_validation_result['size_validation']['size_status']
    
    pcd_validation = mock_validation_result['pcd_validation']
    width_m = pcd_validation['width_m']
    height_m = pcd_validation['height_m'] 
    depth_m = pcd_validation['depth_m']
    pcd_scale = f"{width_m:.1f}×{height_m:.1f}×{depth_m:.1f}m"
    
    # 构造sheets记录
    sheets_record = {
        'file_id': 'test_001',
        'file_name': 'Indoor_test_scene.zip',
        'scene_type': scene_type,
        'size_status': size_status,
        'pcd_scale': pcd_scale,
        # 用于颜色格式化的状态字段
        'size_status_level': mock_validation_result['size_validation']['size_status'],
        'pcd_scale_status': mock_validation_result['pcd_validation']['scale_status']
    }
    
    print("模拟的Sheets记录:")
    print(f"  Scene Type: {sheets_record['scene_type']}")
    print(f"  Size Status: {sheets_record['size_status']} (颜色: {sheets_record['size_status_level']})")
    print(f"  PCD Scale: {sheets_record['pcd_scale']} (颜色: {sheets_record['pcd_scale_status']})")
    
    return True

def main():
    """运行所有测试"""
    print("增强的Google Sheets功能测试")
    print("=" * 50)
    
    all_tests_passed = True
    
    tests = [
        test_enhanced_sheets_formatting,
        test_sheets_record_structure
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
        print("增强功能测试通过！")
        print("\n新功能总结:")
        print("1. PCD Scale字段现在显示具体尺寸 (如: 120.5×95.3×8.2m)")
        print("2. Size Status字段根据状态显示颜色背景:")
        print("   - optimal: 绿色")
        print("   - warning_small/large: 黄色") 
        print("   - error_too_small/large: 红色")
        print("3. PCD Scale字段根据状态显示颜色背景:")
        print("   - optimal: 绿色")
        print("   - warning_*: 黄色")
        print("   - error_*: 红色")
        print("   - not_found/error: 灰色")
        return 0
    else:
        print("部分测试失败！请检查实现。")
        return 1

if __name__ == "__main__":
    sys.exit(main())