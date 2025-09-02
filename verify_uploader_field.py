#!/usr/bin/env python3
"""
验证Uploader Email字段名修改
"""

from monitor.drive_monitor import DriveMonitor
from sheets.sheets_writer import SheetsWriter
from sheets.data_mapper import SheetsDataMapper
from config import Config

def verify_uploader_field():
    print("=== Verifying Uploader Email Field Rename ===")
    
    # 1. Check SheetsWriter headers
    writer = SheetsWriter()
    print("Headers:")
    for i, header in enumerate(writer.headers):
        if 'owner' in header.lower() or 'uploader' in header.lower():
            print(f"  [{i}] {header}")
    
    # 2. Check field mapping
    print("\nField Mapping:")
    for field, index in writer.field_mapping.items():
        if 'owner' in field or 'uploader' in field:
            print(f"  {field} -> {index}")
    
    # 3. Test data mapping
    monitor = DriveMonitor(Config.DRIVE_FOLDER_ID)
    if hasattr(monitor, 'processed_files') and monitor.processed_files:
        test_file_id = list(monitor.processed_files)[0]
        file_metadata = monitor.get_file_metadata(test_file_id)
        
        if file_metadata and file_metadata.get('owners'):
            test_record = {
                'file_id': file_metadata['id'],
                'file_name': file_metadata['name'],
                'owners': file_metadata.get('owners', [])
            }
            
            mapped_data = SheetsDataMapper.map_validation_result(None, test_record)
            
            print(f"\nMapped Data:")
            print(f"  owner_name: '{mapped_data.get('owner_name', 'MISSING')}'")
            print(f"  uploader_email: '{mapped_data.get('uploader_email', 'MISSING')}'")
            
            # Check if old field still exists (should not)
            old_field_exists = 'owner_email' in mapped_data
            print(f"  owner_email (old field): {'EXISTS' if old_field_exists else 'REMOVED'}")
            
            success = (
                'Uploader Email' in writer.headers and
                'uploader_email' in writer.field_mapping and
                'uploader_email' in mapped_data and
                not old_field_exists
            )
            
            print("\n" + "="*50)
            if success:
                print("SUCCESS: Field rename completed!")
                print("- Headers updated to 'Uploader Email'")
                print("- Field mapping updated to 'uploader_email'") 
                print("- Data extraction working correctly")
                print("- Old 'owner_email' field removed")
            else:
                print("FAILED: Some issues remain")
                
            return success
    
    print("No test data available")
    return False

if __name__ == "__main__":
    verify_uploader_field()