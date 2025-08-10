#!/usr/bin/env python3
"""
测试阶段清理工具 - 清空已处理文件记录并清理下载的文件，恢复到初始状态

使用方法:
python clear_processed.py [--files-only] [--records-only]

选项:
--files-only    只清理下载的文件，保留处理记录
--records-only  只清理处理记录，保留下载的文件
"""

import json
import os
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from config import Config
from monitor.file_tracker import FileTracker

def clear_processed_files():
    """清空所有已处理文件记录"""
    try:
        # 方法1: 直接重置JSON文件
        initial_data = {
            "processed_files": [],
            "last_check_time": None,
            "total_processed": 0,
            "created_time": datetime.now().isoformat(),
            "version": "1.0"
        }
        
        json_file = Config.PROCESSED_FILES_JSON
        os.makedirs(os.path.dirname(json_file), exist_ok=True)
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(initial_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 已清空处理记录文件: {json_file}")
        
        # 方法2: 使用FileTracker类的方法
        tracker = FileTracker()
        stats = tracker.get_statistics()
        print(f"📊 清理前统计: {stats.get('total_processed', 0)} 个文件")
        
        return True
        
    except Exception as e:
        print(f"❌ 清理失败: {e}")
        return False

def backup_processed_files():
    """备份当前已处理文件记录"""
    try:
        json_file = Config.PROCESSED_FILES_JSON
        if os.path.exists(json_file):
            backup_file = f"{json_file}.backup.{int(datetime.now().timestamp())}"
            
            with open(json_file, 'r', encoding='utf-8') as src:
                with open(backup_file, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())
            
            print(f"💾 已备份到: {backup_file}")
            return backup_file
        else:
            print("⚠️  处理记录文件不存在，无需备份")
            return None
            
    except Exception as e:
        print(f"❌ 备份失败: {e}")
        return None

def clear_downloaded_files():
    """清理已下载的文件"""
    try:
        cleaned_count = 0
        total_size = 0
        
        # 清理下载目录
        download_dir = Path(Config.DOWNLOAD_PATH)
        if download_dir.exists():
            print(f"🗂️  清理下载目录: {download_dir}")
            for item in download_dir.iterdir():
                if item.is_file():
                    size = item.stat().st_size
                    total_size += size
                    item.unlink()
                    cleaned_count += 1
                    print(f"   删除: {item.name} ({size / 1024 / 1024:.1f} MB)")
                elif item.is_dir():
                    size = sum(f.stat().st_size for f in item.rglob('*') if f.is_file())
                    total_size += size
                    shutil.rmtree(item)
                    cleaned_count += 1
                    print(f"   删除目录: {item.name} ({size / 1024 / 1024:.1f} MB)")
        
        # 清理已处理文件目录
        processed_dir = Path(Config.PROCESSED_PATH)
        if processed_dir.exists():
            print(f"🗂️  清理已处理文件目录: {processed_dir}")
            for item in processed_dir.iterdir():
                if item.is_file():
                    size = item.stat().st_size
                    total_size += size
                    item.unlink()
                    cleaned_count += 1
                    print(f"   删除: {item.name} ({size / 1024 / 1024:.1f} MB)")
                elif item.is_dir():
                    size = sum(f.stat().st_size for f in item.rglob('*') if f.is_file())
                    total_size += size
                    shutil.rmtree(item)
                    cleaned_count += 1
                    print(f"   删除目录: {item.name} ({size / 1024 / 1024:.1f} MB)")
        
        # 清理临时目录
        temp_dir = Path(Config.TEMP_DIR)
        if temp_dir.exists():
            print(f"🗂️  清理临时目录: {temp_dir}")
            for item in temp_dir.iterdir():
                if item.is_file():
                    size = item.stat().st_size
                    total_size += size
                    item.unlink()
                    cleaned_count += 1
                    print(f"   删除: {item.name} ({size / 1024 / 1024:.1f} MB)")
                elif item.is_dir():
                    size = sum(f.stat().st_size for f in item.rglob('*') if f.is_file())
                    total_size += size
                    shutil.rmtree(item)
                    cleaned_count += 1
                    print(f"   删除目录: {item.name} ({size / 1024 / 1024:.1f} MB)")
        
        print(f"✅ 文件清理完成: 删除 {cleaned_count} 个项目，释放 {total_size / 1024 / 1024:.1f} MB 空间")
        return True
        
    except Exception as e:
        print(f"❌ 文件清理失败: {e}")
        return False

def get_directory_size(directory):
    """获取目录大小"""
    try:
        total_size = 0
        if os.path.exists(directory):
            for dirpath, dirnames, filenames in os.walk(directory):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)
        return total_size
    except Exception:
        return 0

def show_cleanup_preview():
    """显示清理预览"""
    print("📋 清理预览:")
    
    # 检查处理记录
    json_file = Config.PROCESSED_FILES_JSON
    if os.path.exists(json_file):
        try:
            tracker = FileTracker()
            stats = tracker.get_statistics()
            print(f"   处理记录: {stats.get('total_processed', 0)} 个文件")
        except:
            print("   处理记录: 无法读取")
    else:
        print("   处理记录: 不存在")
    
    # 检查下载文件
    dirs_to_check = [
        ("下载目录", Config.DOWNLOAD_PATH),
        ("已处理目录", Config.PROCESSED_PATH), 
        ("临时目录", Config.TEMP_DIR)
    ]
    
    total_size = 0
    total_files = 0
    
    for name, path in dirs_to_check:
        if os.path.exists(path):
            size = get_directory_size(path)
            total_size += size
            
            file_count = 0
            try:
                for root, dirs, files in os.walk(path):
                    file_count += len(files)
                    file_count += len(dirs)
            except:
                file_count = 0
                
            total_files += file_count
            print(f"   {name}: {file_count} 个项目, {size / 1024 / 1024:.1f} MB")
        else:
            print(f"   {name}: 不存在")
    
    print(f"   总计: {total_files} 个项目, {total_size / 1024 / 1024:.1f} MB")
    return total_files > 0 or os.path.exists(Config.PROCESSED_FILES_JSON)

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="清理已处理文件和下载文件")
    parser.add_argument('--files-only', action='store_true', help='只清理下载的文件，保留处理记录')
    parser.add_argument('--records-only', action='store_true', help='只清理处理记录，保留下载的文件')
    parser.add_argument('--preview', action='store_true', help='预览要清理的内容，不实际清理')
    parser.add_argument('--yes', action='store_true', help='跳过确认提示')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_arguments()
    
    print("清理工具 - 文件和记录清理")
    print("=" * 50)
    
    # 预览模式
    if args.preview:
        show_cleanup_preview()
        exit(0)
    
    # 显示清理预览
    if not show_cleanup_preview():
        print("✨ 没有需要清理的内容")
        exit(0)
    
    # 确认清理
    if not args.yes:
        print("\n⚠️  此操作将永久删除文件，无法恢复！")
        confirm = input("确定要继续吗？(y/N): ").lower().strip()
        if confirm not in ['y', 'yes', '是']:
            print("❌ 已取消清理操作")
            exit(0)
    
    print("\n🧹 开始清理...")
    
    success_count = 0
    total_operations = 0
    
    # 清理文件
    if not args.records_only:
        total_operations += 1
        print("\n1️⃣ 清理下载的文件...")
        if clear_downloaded_files():
            success_count += 1
    
    # 清理记录
    if not args.files_only:
        total_operations += 1
        print(f"\n2️⃣ 清理处理记录...")
        
        # 先备份
        backup_file = backup_processed_files()
        
        # 清理
        if clear_processed_files():
            success_count += 1
            
            # 验证清理结果
            try:
                tracker = FileTracker()
                stats = tracker.get_statistics()
                print(f"📊 清理后统计: {stats.get('total_processed', 0)} 个文件")
            except:
                pass
        else:
            if backup_file and os.path.exists(backup_file):
                print(f"💾 可从备份恢复: {backup_file}")
    
    # 总结
    print(f"\n✨ 清理完成！({success_count}/{total_operations} 项操作成功)")
    
    if success_count == total_operations:
        print("🎉 系统已恢复到初始状态")
    elif success_count > 0:
        print("⚠️  部分清理操作失败")
    else:
        print("❌ 清理操作失败")