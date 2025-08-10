#!/usr/bin/env python3
"""
演示文件结构和命名规范检查功能
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.validators import validate_scene_naming, validate_extracted_file_size

def demo_scene_naming():
    """演示场景命名验证"""
    print("=== 场景命名验证演示 ===")
    print("支持的命名格式：")
    print("  Indoor: Indoor*, indoor*, INDOOR*, I*, i*")
    print("  Outdoor: Outdoor*, outdoor*, OUTDOOR*, O*, o*")
    print()
    
    test_files = [
        "Indoor_scene_001.zip",
        "I001.zip", 
        "Outdoor_park.zip",
        "O_street.zip",
        "test_data.zip",  # 无效
    ]
    
    for filename in test_files:
        result = validate_scene_naming(filename)
        scene_type = result['scene_type']
        is_valid = result['is_valid_format']
        
        status = "Valid" if is_valid else "Warning"  # unknown类型是警告不是错误
        print(f"  {filename:20} -> {scene_type:8} ({status})")
        if result.get('error_message'):
            level = "Warning" if scene_type == "unknown" else "Error"
            print(f"    {level}: {result['error_message']}")
    
    print()

def demo_file_size_validation():
    """演示文件大小验证"""
    print("=== 文件大小验证演示 ===")
    print("合理范围：1GB - 3GB")
    print("警告范围：0.8GB - 3.5GB")
    print("异常大小：< 0.5GB 或 > 6GB")
    print()
    
    test_sizes = [
        0.3,  # 过小
        0.8,  # 警告小
        1.5,  # 最佳
        2.8,  # 最佳
        3.2,  # 警告大
        7.0,  # 过大
    ]
    
    for size_gb in test_sizes:
        size_bytes = int(size_gb * 1024**3)
        result = validate_extracted_file_size(size_bytes)
        
        status = result['size_status']
        is_valid = result['is_valid_size']
        
        validity = "Valid" if is_valid else "Invalid"
        print(f"  {size_gb:4.1f}GB -> {status:15} ({validity})")
        if result.get('error_message'):
            print(f"    Info: {result['error_message']}")
    
    print()

def main():
    """运行演示"""
    print("文件结构和命名规范检查功能演示")
    print("=" * 50)
    print()
    
    demo_scene_naming()
    demo_file_size_validation()
    
    print("演示完成！")
    print()
    print("功能说明：")
    print("1. 场景命名验证：")
    print("   - 识别Indoor/I开头的文件为indoor类型")
    print("   - 识别Outdoor/O开头的文件为outdoor类型") 
    print("   - 其他格式标记为unknown类型")
    print()
    print("2. 文件大小验证：")
    print("   - 检查解压后文件总大小是否在合理范围内")
    print("   - 提供优化、警告、错误等不同状态")
    print("   - 自动标记异常大小的文件")
    print()
    print("3. 集成到处理流程：")
    print("   - 在压缩文件验证过程中自动执行")
    print("   - 结果记录到Google Sheets中")
    print("   - 提供详细的验证日志")
    print()
    print("重要说明：")
    print("- 场景类型unknown只是警告，不会导致验证失败")
    print("- 只有数据格式错误和文件过小/过大才会导致验证失败")
    print("- 系统支持处理任意命名的文件，但推荐使用规范命名")

if __name__ == "__main__":
    main()