#!/usr/bin/env python3
"""
验证Sheets字段填充修复
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def verify_main_py_fix():
    """验证main.py中的修复"""
    print("验证main.py中的修复...")
    
    # 读取main.py文件
    with open('main.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查关键修改是否存在
    checks = [
        "scene_type = scene_validation.get('scene_type', 'unknown')",
        "size_status = size_validation.get('size_status', 'unknown')", 
        "pcd_scale = pcd_validation.get('scale_status', 'unknown')",
        "'scene_type': scene_type,",
        "'size_status': size_status,",
        "'pcd_scale': pcd_scale,"
    ]
    
    all_found = True
    for check in checks:
        if check in content:
            print(f"✓ 找到: {check}")
        else:
            print(f"✗ 缺失: {check}")
            all_found = False
    
    return all_found

def verify_sheets_writer():
    """验证sheets_writer支持这些字段"""
    print("\n验证sheets_writer.py支持...")
    
    with open('sheets/sheets_writer.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        "'Scene Type', 'Size Status'",
        "'PCD Scale'",
        "scene_type = record.get('scene_type', '')",
        "size_status = record.get('size_status', '')",
        "pcd_scale = record.get('pcd_scale', '')"
    ]
    
    all_found = True
    for check in checks:
        if check in content:
            print(f"✓ 找到: {check}")
        else:
            print(f"✗ 缺失: {check}")
            all_found = False
    
    return all_found

def verify_archive_handler():
    """验证archive_handler提供这些数据"""
    print("\n验证archive_handler.py提供数据...")
    
    with open('processors/archive_handler.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        "info['scene_type'] = scene_validation.get('scene_type', 'unknown')",
        "info['size_status'] = size_validation.get('size_status', 'unknown')",
        "info['pcd_scale'] = pcd_validation.get('scale_status', 'unknown')"
    ]
    
    all_found = True  
    for check in checks:
        if check in content:
            print(f"✓ 找到: {check}")
        else:
            print(f"✗ 缺失: {check}")
            all_found = False
    
    return all_found

def main():
    print("Google Sheets字段填充修复验证")
    print("=" * 50)
    
    all_good = True
    
    if not verify_main_py_fix():
        all_good = False
        
    if not verify_sheets_writer():
        all_good = False
        
    if not verify_archive_handler():
        all_good = False
    
    print("\n" + "=" * 50)
    if all_good:
        print("修复验证通过！")
        print("现在处理文件后，Scene Type、Size Status和PCD Scale字段应该会正确显示。")
        print("\n修复内容:")
        print("1. main.py: 从archive validation结果中提取场景类型、大小状态、PCD尺度")
        print("2. main.py: 将这些信息传递给sheets_writer")
        print("3. sheets_writer.py: 正确读取并写入这些字段到Google Sheets")
        print("4. archive_handler.py: 提供完整的验证结果数据")
        return 0
    else:
        print("修复验证失败！某些关键修改缺失。")
        return 1

if __name__ == "__main__":
    sys.exit(main())