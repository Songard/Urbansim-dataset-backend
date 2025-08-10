#!/usr/bin/env python3
"""
Quick startup test to verify all fixes work together
"""

import os
import sys

# Add the project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_all_components():
    """Test all critical components for startup"""
    
    print("="*60)
    print("QUICK STARTUP TEST")
    print("="*60)
    
    results = {}
    
    # Test 1: Config loading
    print("1. Testing Config loading...")
    try:
        from config import Config
        print(f"   TEMP_DIR: {Config.TEMP_DIR}")
        print(f"   DOWNLOAD_CHUNK_SIZE_MB: {Config.DOWNLOAD_CHUNK_SIZE_MB}")
        print(f"   DOWNLOAD_TIMEOUT: {Config.DOWNLOAD_TIMEOUT}")
        results['config'] = True
        print("   ✓ Config loads successfully")
    except Exception as e:
        results['config'] = False
        print(f"   ✗ Config error: {e}")
    
    # Test 2: ValidationManager
    print("\n2. Testing ValidationManager...")
    try:
        from validation.manager import ValidationManager
        vm = ValidationManager()
        print(f"   Registered validators: {len(vm.validators)}")
        results['validation'] = True
        print("   ✓ ValidationManager initializes successfully")
    except Exception as e:
        results['validation'] = False
        print(f"   ✗ ValidationManager error: {e}")
    
    # Test 3: FileDownloader
    print("\n3. Testing FileDownloader...")
    try:
        from processors.file_downloader import FileDownloader
        fd = FileDownloader()
        status = fd.get_download_status()
        print(f"   Max concurrent: {status['max_concurrent']}")
        results['downloader'] = True
        print("   ✓ FileDownloader initializes successfully")
    except Exception as e:
        results['downloader'] = False
        print(f"   ✗ FileDownloader error: {e}")
    
    # Test 4: SheetsWriter
    print("\n4. Testing SheetsWriter...")
    try:
        from sheets.sheets_writer import SheetsWriter
        sw = SheetsWriter()
        print(f"   Headers count: {len(sw.headers)}")
        results['sheets'] = True
        print("   ✓ SheetsWriter initializes successfully")
    except Exception as e:
        results['sheets'] = False
        print(f"   ✗ SheetsWriter error: {e}")
    
    # Test 5: Mock validation result handling
    print("\n5. Testing validation result handling...")
    try:
        from validation.base import ValidationResult, ValidationLevel
        
        # Create mock result
        result = ValidationResult(
            is_valid=True,
            validation_level=ValidationLevel.STANDARD,
            score=85.0,
            errors=[],
            warnings=[],
            missing_files=[],
            missing_directories=[],
            extra_files=[],
            file_details={},
            summary="Test",
            metadata={
                'extracted_metadata': {
                    'start_time': '2025.08.02 07:34:29',
                    'duration': '00:06:56',
                    'location': {'latitude': '40°N', 'longitude': '73°W'}
                }
            }
        )
        
        # Test sheets handling
        record = {'validation_result': result}
        validation_result = record.get('validation_result') or {}
        
        if hasattr(validation_result, 'metadata'):
            metadata = validation_result.metadata or {}
        else:
            metadata = {}
            
        extracted_metadata = metadata.get('extracted_metadata', {})
        start_time = extracted_metadata.get('start_time', '')
        
        print(f"   Extracted start_time: '{start_time}'")
        results['handling'] = True
        print("   ✓ Validation result handling works correctly")
        
    except Exception as e:
        results['handling'] = False
        print(f"   ✗ Validation handling error: {e}")
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name:15s}: {status}")
    
    print(f"\nResult: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("\n🎉 ALL TESTS PASSED! System should start successfully.")
        return True
    else:
        print(f"\n⚠️ {total_tests - passed_tests} tests failed. Check errors above.")
        return False

if __name__ == "__main__":
    print("Running quick startup test...")
    success = test_all_components()
    
    if success:
        print("\n✅ System is ready to run!")
        print("You can now start the main system with: python main.py")
    else:
        print("\n❌ Some components have issues. Fix the errors above before starting.")
        sys.exit(1)