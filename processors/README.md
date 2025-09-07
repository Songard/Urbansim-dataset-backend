# Processors Directory

This directory contains Windows executable packages for MetaCam 3D reconstruction processing and the complete processing pipeline implementation.

## Structure

```
processors/
├── data_processor.py           # Main processing pipeline orchestrator
├── file_downloader.py          # Google Drive file download management  
├── archive_handler.py          # Archive extraction and validation
├── README.md                   # This documentation
└── exe_packages/               # Windows executable files for processing
    ├── validation_generator.exe  # Data validation executable
    ├── metacam_cli.exe          # 3D reconstruction executable
    ├── processed/               # Processing workspace (created at runtime)
    │   └── output/              # Executable output directory
    └── env/                     # Python environment (if needed by executables)
```

## Required Executables

### 1. validation_generator.exe
**Purpose**: Initial data validation and file listing
**Usage**: `validation_generator.exe <data_path>`
**Output**: Lists processed data files in format `file: No.X: <path>`

### 2. metacam_cli.exe
**Purpose**: Main 3D reconstruction processing
**Usage**: `metacam_cli.exe -i <input> -o <output> -s <scene> -color <0|1> -mode <0|1>`
**Parameters**:
- `-i`: Input data path
- `-o`: Output directory path  
- `-s`: Scene type (0=Balance, 1=Open/Outdoor, 2=Narrow/Indoor)
- `-color`: Enable coloring (0=No, 1=Yes)
- `-mode`: Processing mode (0=Fast, 1=Precision)

## Automatic Scene Detection

The system automatically determines scene type based on validation results:

- **Open (1)**: Detected outdoor scenes
- **Narrow (2)**: Indoor scenes with max dimension < 30m
- **Balance (0)**: All other cases (default)

## Configuration

Set processing parameters in `config.py` or environment variables:

```python
# Processing mode (0=fast, 1=precision)
METACAM_CLI_MODE = "0"  

# Enable coloring (0=no, 1=yes)
METACAM_CLI_COLOR = "1"

# Processing timeout (1 hour default)
METACAM_CLI_TIMEOUT_SECONDS = 3600

# Scale threshold for narrow scenes  
INDOOR_SCALE_THRESHOLD_M = 30.0
```

## Processing Flow

The complete processing pipeline consists of four main stages:

### 1. Pre-Processing
- **Directory Standardization**: Ensures MetaCam-compatible structure with `data/` subdirectory
- **Path Validation**: Verifies all required files and directories exist
- **Scene Analysis**: Analyzes validation metadata to determine optimal processing parameters

### 2. Validation Generator Phase
- **Executable**: `validation_generator.exe`
- **Purpose**: Data preparation and format validation
- **Input**: Standardized data package root directory
- **Output**: File listing and validation status
- **Monitoring**: Real-time output monitoring with progress tracking

### 3. MetaCam CLI Phase
- **Executable**: `metacam_cli.exe`
- **Purpose**: 3D reconstruction processing
- **Input**: Same standardized data package root directory
- **Parameters**: Automatically determined based on scene analysis:
  - Scene type (Balance/Open/Narrow)
  - Processing mode (Fast/Precision)
  - Color processing (enabled/disabled)
- **Timeout**: Extended timeout (1 hour default) for heavy processing
- **Output**: Generated in multiple possible locations

### 4. Post-Processing Phase
- **Output File Search**: Multi-location search for required processing results:
  - `colorized.las` - Final 3D point cloud with color information
  - `transforms.json` - Camera transformation matrices and poses
- **Search Locations**:
  - Configured output directory (`PROCESSING_OUTPUT_PATH`)
  - Executable-relative paths (`./processed/output/`)
  - Alternative naming patterns (`o_{package_name}_output`)
- **Final Package Assembly**: Creates `{package_name}_processed.zip` containing:
  - Processing results (colorized.las, transforms.json)
  - Preserved original files (metadata.yaml, Preview.jpg, camera/)
- **Package Verification**: Validates final package contents and integrity

## Output

### Intermediate Processing Output
Raw executable outputs may appear in various locations:
```
# Configured output location
processed/output/{package_name}_output/

# Executable-relative locations  
processors/exe_packages/processed/output/o_{package_name}_output/
processors/exe_packages/output/{package_name}_output/
```

### Final Processed Package
The system creates final processed packages at:
```
processed/output/{package_name}_processed.zip
```

**Package Contents:**
```
{package_name}_processed.zip
├── colorized.las          # 3D point cloud with color data
├── transforms.json        # Camera transformation matrices
├── metadata.yaml          # Original metadata (preserved)
├── Preview.jpg            # Original preview (preserved)
└── camera/                # Camera calibration data (preserved)
    ├── left/              # Left camera data
    └── right/             # Right camera data
```

### Processing Logs
Detailed processing logs include:
- Real-time executable output with progress tracking
- Processing duration and performance metrics  
- **Comprehensive file search logging**:
  - All search locations with existence checks
  - Directory contents listing for debugging
  - Pattern matching attempts with results
  - Detailed success/failure reporting
- Package assembly status with step-by-step progress
- Error diagnostics and troubleshooting information

**Example Search Log Output:**
```
=== Starting search for output files (colorized.las & transforms.json) ===
Package name: 8428bay16st
Will search in 5 locations:
  1. ./processed/output/8428bay16st_output
  2. ./processors/exe_packages/processed/output/o_8428bay16st_output
  3. ./processors/exe_packages/output/8428bay16st_output
  4. ./processors/exe_packages/output
  5. ./processors/exe_packages/processed/output

[1/5] Checking location: ./processed/output/8428bay16st_output
  → Directory does not exist, skipping

[2/5] Checking location: ./processors/exe_packages/processed/output/o_8428bay16st_output
  → Directory exists, searching for files...
  → Found 3 items in directory:
    - [FILE] colorized.las
    - [FILE] transforms.json  
    - [FILE] processing_log.txt
  → Searching for colorized.las...
    - Trying pattern: colorized.las
    ✓ FOUND colorized.las at: ./processors/exe_packages/processed/output/o_8428bay16st_output/colorized.las
  → Searching for transforms.json...
    - Trying pattern: transforms.json
    ✓ FOUND transforms.json at: ./processors/exe_packages/processed/output/o_8428bay16st_output/transforms.json

🎉 SUCCESS: Both required files found in location 2: ./processors/exe_packages/processed/output/o_8428bay16st_output

=== Search completed ===
✅ SEARCH SUCCESS: Both required files found!
  • colorized.las: ./processors/exe_packages/processed/output/o_8428bay16st_output/colorized.las
  • transforms.json: ./processors/exe_packages/processed/output/o_8428bay16st_output/transforms.json
```

## Installation

1. Copy your Windows executables to `exe_packages/`:
   ```
   processors/exe_packages/
   ├── validation_generator.exe
   └── metacam_cli.exe
   ```

2. Ensure executables are compatible with your Windows environment

3. The system will automatically detect and use them

## Error Handling & Recovery

### Robust Processing
The system is designed to handle various failure scenarios:

- **Executable Crashes**: Processing continues with post-processing even if executables exit abnormally
- **Timeout Handling**: Configurable timeouts prevent indefinite hanging
- **Output Search**: Multi-location search ensures files are found even if output paths change
- **Resource Cleanup**: Automatic cleanup of temporary files and directories
- **Detailed Logging**: Comprehensive error reporting for troubleshooting

### Troubleshooting

**Common Issues:**

1. **Missing Output Files**
   - Check configured `PROCESSING_OUTPUT_PATH`
   - Verify executable permissions and dependencies
   - Review processing logs for silent exits
   - **Check detailed search logs**: Look for the search section in logs to see exactly where the system looked and what it found

2. **Processing Timeouts**
   - Increase `METACAM_CLI_TIMEOUT_SECONDS` for large datasets
   - Monitor system resources (CPU, memory, disk space)
   - Check for antivirus interference

3. **Package Assembly Failures**
   - Verify original package contains required files
   - Check disk space in output directory
   - Ensure proper file permissions

**Diagnostic Commands:**
```python
# Test processing system status
from processors.data_processor import DataProcessor
processor = DataProcessor()
status = processor.get_processing_status()
print(status)

# Validate executable accessibility
exe_status = processor.validate_executables()
print(exe_status)

# Test file search for a specific package
package_name = "your_package_name"  # Replace with actual package name
output_files = processor._find_processing_output_files(package_name)
print(f"Search results: {output_files}")
```

### Real-time Log Monitoring

To watch the file search process in real-time:

```bash
# Monitor all processing logs
tail -f logs/monitor.log

# Filter for file search activities only  
tail -f logs/monitor.log | grep -E "(Starting search|Checking location|FOUND|SUCCESS|FAILED)"

# Monitor specific package processing
tail -f logs/monitor.log | grep "package_name_here"

# Watch for processing completion
tail -f logs/monitor.log | grep -E "(Post-processing|final package|SUCCESS|ERROR)"
```

**Key log patterns to look for:**
- `=== Starting search for output files ===` - File search begins
- `[X/Y] Checking location:` - Current search location
- `✓ FOUND colorized.las at:` - File found successfully  
- `🎉 SUCCESS: Both required files found` - Search completed successfully
- `❌ SEARCH FAILED: Missing files:` - Files not found

## Configuration Reference

### Key Configuration Options

```python
# Processing executable paths
PROCESSORS_EXE_PATH = "./processors/exe_packages"

# Processing timeouts (seconds)
PROCESSING_TIMEOUT_SECONDS = 600        # validation_generator timeout
METACAM_CLI_TIMEOUT_SECONDS = 3600      # metacam_cli timeout (1 hour)

# Output directories  
PROCESSING_OUTPUT_PATH = "./processed/output"

# Processing behavior
AUTO_START_PROCESSING = True             # Auto-start after validation
PROCESSING_RETRY_ATTEMPTS = 2            # Retry attempts on failure
KEEP_ORIGINAL_DATA = True                # Preserve original files

# MetaCam CLI parameters
METACAM_CLI_MODE = "0"                   # 0=fast, 1=precision
METACAM_CLI_COLOR = "1"                  # 0=disable, 1=enable
INDOOR_SCALE_THRESHOLD_M = 30.0          # Narrow scene threshold
```

## Notes

- All .exe files in this directory are ignored by git for security
- Processing can take significant time (hours for large datasets) 
- System includes comprehensive timeout protection and detailed logging
- Failed processing attempts are logged with full error details and diagnostic information
- Post-processing occurs regardless of exe exit status to maximize data recovery