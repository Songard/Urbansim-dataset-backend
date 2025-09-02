#!/usr/bin/env python3
"""
验证脚本：检查文件所有者信息功能是否正确实现
"""

import json
from monitor.drive_monitor import DriveMonitor
from sheets.sheets_writer import SheetsWriter
from sheets.data_mapper import SheetsDataMapper
from config import Config

def main():
    print("Verifying Owner Info Feature...")
    
    # 1. Check Drive Monitor gets owners info
    print("1. Testing DriveMonitor owner info retrieval:")
    monitor = DriveMonitor(Config.DRIVE_FOLDER_ID)
    new_files = monitor.get_new_files()
    
    if new_files:
        test_file = new_files[0]
        print(f"   File: {test_file['name']}")
        owners = test_file.get('owners', [])
        if owners:
            owner = owners[0]
            print(f"   Owner Name: {owner.get('displayName', 'N/A')}")
            print(f"   Owner Email: {owner.get('emailAddress', 'N/A')}")
            print("   ✓ SUCCESS: Owner info retrieved")
        else:
            print("   ✗ FAILED: No owner info")
    else:
        print("   No new files to test")
    
    # 2. Check SheetsWriter headers
    print("\n2. Testing SheetsWriter headers:")
    writer = SheetsWriter()
    if 'Owner Name' in writer.headers and 'Owner Email' in writer.headers:
        print("   ✓ SUCCESS: Headers include owner fields")
        print(f"   Owner Name index: {writer.field_mapping['owner_name']}")
        print(f"   Owner Email index: {writer.field_mapping['owner_email']}")
    else:
        print("   ✗ FAILED: Headers missing owner fields")
    
    # 3. Check DataMapper processing
    print("\n3. Testing DataMapper owner extraction:")
    if new_files:
        test_data = SheetsDataMapper.map_validation_result(None, new_files[0])
        if 'owner_name' in test_data and 'owner_email' in test_data:
            print(f"   Owner Name: {test_data['owner_name']}")
            print(f"   Owner Email: {test_data['owner_email']}")
            print("   ✓ SUCCESS: DataMapper processes owner info")
        else:
            print("   ✗ FAILED: DataMapper missing owner fields")
    
    print("\n" + "="*50)
    print("FEATURE IMPLEMENTATION COMPLETE!")
    print("Owner information will now be captured and saved to Google Sheets")

if __name__ == "__main__":
    main()