#!/usr/bin/env python3
"""
演示PCD点云尺度验证功能
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.validators import validate_pcd_scale

def create_demo_pcd(file_path: str, width: float, height: float, description: str):
    """创建演示PCD文件"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            # PCD头部
            f.write("# .PCD v0.7 - Point Cloud Data file format\n")
            f.write(f"# Demo PCD: {description}\n")
            f.write("VERSION 0.7\n")
            f.write("FIELDS x y z\n")
            f.write("SIZE 4 4 4\n")
            f.write("TYPE F F F\n")
            f.write("COUNT 1 1 1\n")
            f.write("WIDTH 1000\n")
            f.write("HEIGHT 1\n")
            f.write("VIEWPOINT 0 0 0 1 0 0 0\n")
            f.write("POINTS 1000\n")
            f.write("DATA ascii\n")
            
            # 生成点云数据
            import random
            for i in range(1000):
                x = random.uniform(0, width)
                y = random.uniform(0, height)
                z = random.uniform(0, 5)
                f.write(f"{x:.6f} {y:.6f} {z:.6f}\n")
                
        return True
    except Exception as e:
        print(f"创建演示文件失败: {e}")
        return False

def demo_pcd_scale_validation():
    """演示PCD点云尺度验证功能"""
    print("=== PCD点云尺度验证演示 ===")
    print("合理范围：长宽约100m左右")
    print("警告范围：50m-200m")
    print("异常范围：< 10m 或 > 500m")
    print()
    
    test_scenarios = [
        (100, 80, "理想尺度的城市场景"),
        (150, 120, "较大的公园场景"),
        (30, 25, "小型室内场景"),
        (300, 200, "大型广场场景"),
        (8, 5, "异常小的测试场景"),
        (600, 400, "异常大的区域场景")
    ]
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        for i, (width, height, description) in enumerate(test_scenarios):
            print(f"--- 场景 {i+1}: {description} ---")
            
            # 创建测试文件
            pcd_file = os.path.join(temp_dir, f"demo_{i}.pcd")
            if not create_demo_pcd(pcd_file, width, height, description):
                continue
            
            # 验证尺度
            result = validate_pcd_scale(pcd_file)
            
            status_map = {
                'optimal': 'GOOD 最佳',
                'warning_small': 'WARN 偏小',
                'warning_large': 'WARN 偏大',
                'warning_narrow': 'WARN 狭长',
                'error_too_small': 'ERROR 过小',
                'error_too_large': 'ERROR 过大',
                'unknown': 'UNKNOWN 未知'
            }
            
            status_display = status_map.get(result['scale_status'], result['scale_status'])
            
            print(f"  预设尺度: {width}m × {height}m")
            print(f"  实际尺度: {result['width_m']:.1f}m × {result['height_m']:.1f}m")
            print(f"  覆盖面积: {result['area_sqm']:.0f} 平方米")
            print(f"  解析点数: {result['points_parsed']}")
            print(f"  验证状态: {status_display}")
            print(f"  验证结果: {'通过' if result['is_valid_scale'] else '需要注意'}")
            
            if result.get('error_message'):
                print(f"  详细信息: {result['error_message']}")
            
            print()
    
    except Exception as e:
        print(f"演示过程中出错: {e}")
    
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def demo_integration_example():
    """演示集成到系统中的效果"""
    print("=== 系统集成效果演示 ===")
    print()
    print("在实际使用中，PCD尺度验证会：")
    print("1. 自动查找解压后的Preview.pcd文件")
    print("2. 解析点云数据并计算长宽尺度")
    print("3. 根据尺度范围给出验证状态：")
    print("   - optimal: 100m左右，理想尺度")
    print("   - warning_small/large: 50-200m，可接受但有警告")
    print("   - error_too_small/large: <10m或>500m，异常尺度")
    print("4. 将验证结果记录到Google Sheets的'PCD Scale'列")
    print("5. 提供详细的日志信息用于问题排查")
    print()
    print("重要说明：")
    print("- PCD尺度验证是警告级别，不会导致文件处理失败")
    print("- 如果找不到Preview.pcd文件，系统会跳过此项验证")
    print("- 支持在解压后的根目录或子目录中查找PCD文件")
    print("- 验证过程只解析前100,000个点，避免内存问题")

def main():
    """运行演示"""
    print("PCD点云尺度验证功能演示")
    print("=" * 50)
    print()
    
    demo_pcd_scale_validation()
    demo_integration_example()
    
    print()
    print("演示完成！")
    print()
    print("新增PCD验证功能特点：")
    print("- 自动解析PCD文件头部和点云数据")
    print("- 计算点云的空间尺度（长x宽x高）")
    print("- 基于100m基准进行合理性判断")
    print("- 提供多级验证状态（最佳/警告/异常）")
    print("- 完全集成到现有验证流程中")
    print("- Google Sheets中新增PCD Scale列")

if __name__ == "__main__":
    main()