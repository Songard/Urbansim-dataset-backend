# MetaCam Data Processing System

A complete end-to-end system for monitoring Google Drive uploads, performing comprehensive data validation, and executing automated 3D reconstruction processing of MetaCam data packages with real-time results tracking in Google Sheets.

## System Overview

This system provides end-to-end processing of MetaCam data packages from Google Drive upload to final 3D reconstruction output, featuring:

- **Automated Google Drive Monitoring**: Real-time detection of new data uploads
- **Comprehensive Data Validation**: Multi-stage validation pipeline ensuring data quality
- **AI-Powered Quality Assessment**: YOLO11-based transient object detection
- **Automated 3D Reconstruction Processing**: Integrated Windows executable pipeline
- **Intelligent Scene Detection**: Automatic scene type determination for optimal processing
- **Post-Processing Package Creation**: Automatic assembly of final processed packages
- **Real-time Results Tracking**: Automated Google Sheets integration with detailed metrics
- **Email Notifications**: Optional alerts for processing status and system health
- **Robust Error Handling**: Detailed error reporting and graceful failure recovery

## Architecture

### Core Components

```
MetaCam Data Processing System
├── 📁 Main System (main.py)
│   ├── Google Drive Monitor
│   ├── File Downloader  
│   ├── Archive Handler
│   └── Results Tracker
├── 📁 Validation Pipeline
│   ├── MetaCam Format Validator
│   ├── Transient Object Detector
│   └── Quality Metrics Calculator
├── 📁 Processing Pipeline
│   ├── Data Processor Orchestrator
│   ├── validation_generator.exe
│   ├── metacam_cli.exe
│   ├── Scene Type Detection
│   └── Post-Processing Package Creator
├── 📁 Data Output
│   ├── Google Sheets Writer
│   ├── Error Formatter
│   └── Email Notifier
└── 📁 Configuration
    ├── Environment Settings
    ├── Data Schemas
    └── Logging System
```

### Data Flow

```
Google Drive Upload → Download → Extract → Validate → Process → Package → Report
                                     ↓
                            [MetaCam Validator]
                                     ↓
                            [Transient Detector] 
                                     ↓
                            [Quality Assessment]
                                     ↓
                          [✓ Validation Passed?]
                                     ↓
                          [Auto Data Processing]
                                     ↓
                         [validation_generator.exe]
                                     ↓
                           [Scene Type Detection]
                                     ↓
                            [metacam_cli.exe]
                                     ↓
                         [3D Reconstruction Output]
                                     ↓
                          [Post-Processing Search]
                                     ↓
                        [Final Package Assembly]
                                     ↓
                           [Package Compression]
                                     ↓
                            [Google Sheets Update]
```

## Features

### 🔄 Automated Processing
- **Continuous Monitoring**: Real-time Google Drive folder monitoring
- **Smart Download Management**: Optimized chunked downloads with retry logic
- **Archive Processing**: Support for multiple compression formats (.zip, .rar, .7z, etc.)
- **Password Handling**: Automatic password attempts for protected archives
- **Automated 3D Reconstruction**: Coordinated execution of validation_generator.exe and metacam_cli.exe
- **Intelligent Scene Detection**: Automatic outdoor/indoor/narrow scene classification for optimal processing
- **Unified Path Management**: Both processing tools receive the same data package root directory
- **Post-Processing Package Assembly**: Automatic creation of final packages combining processing results with original metadata
- **Robust Output File Search**: Multi-location search for processing outputs ensuring reliability
- **Package Verification**: Automatic validation of final package contents and structure

### 🔍 Advanced Validation
- **Schema Validation**: MetaCam data package structure verification
- **File Integrity Checks**: Size, format, and content validation
- **Duration Analysis**: Recording time validation with optimal range detection
- **Point Cloud Scale Validation**: Spatial scale analysis for reconstruction quality
- **Device Information Extraction**: Automatic device ID generation from metadata

### 🤖 AI-Powered Quality Control
- **Transient Object Detection**: YOLO11-based moving obstacle identification
- **Scene Activity Analysis**: Automated calculation of quality metrics (WDD, WPO, SAI)
- **Smart Decision Making**: Pass/Review/Reject recommendations based on AI analysis
- **Adaptive Processing**: Flexible sampling rates for different dataset sizes

### 📊 Real-time Reporting
- **Google Sheets Integration**: Automatic results upload with color-coded status
- **Detailed Metrics**: Duration, file size, validation scores, and quality indicators
- **Error Categorization**: Clear, actionable error messages for easy troubleshooting
- **Progress Tracking**: Complete processing history with timestamps

### 💬 Communication & Alerting
- **Email Notifications**: Configurable alerts for processing events and system status
- **Detailed Logging**: Comprehensive system logs with multiple verbosity levels
- **Status Monitoring**: Real-time system health and performance metrics

## Installation

### Prerequisites

- **Python 3.8+**
- **Google Cloud Project** with Drive API and Sheets API enabled
- **Service Account** with appropriate permissions
- **YOLO Models** (automatically downloaded on first use)

### Setup Steps

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd Urbansim
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Google Cloud APIs**
   - Create a Google Cloud Project
   - Enable Google Drive API and Google Sheets API
   - Create a Service Account
   - Download the service account JSON key as `service-account.json`
   - Grant the service account access to your target Drive folder and Google Sheet

4. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Set Up Directory Structure**
   ```bash
   mkdir -p downloads processed temp logs
   ```

## Configuration

### Environment Variables

Create a `.env` file with the following configuration:

```bash
# Google API Configuration
DRIVE_FOLDER_ID=your_google_drive_folder_id
SPREADSHEET_ID=your_google_sheets_id
SERVICE_ACCOUNT_FILE=service-account.json

# Monitoring Settings
CHECK_INTERVAL=30                    # Check interval in seconds
ENABLE_MONITORING=True               # Enable continuous monitoring
MAX_CONCURRENT_DOWNLOADS=3           # Concurrent download limit

# File Processing
DOWNLOAD_PATH=./downloads            # Downloaded files directory
PROCESSED_PATH=./processed           # Processed files archive
TEMP_DIR=./temp                      # Temporary processing directory
MAX_FILE_SIZE_MB=500                 # Maximum file size limit
ALLOWED_EXTENSIONS=.zip,.rar,.7z     # Supported archive formats
DEFAULT_PASSWORDS=123456,password    # Default passwords for archives

# Download Optimization
DOWNLOAD_CHUNK_SIZE_MB=32            # Download chunk size
DOWNLOAD_TIMEOUT=300                 # Download timeout (seconds)
DOWNLOAD_RETRIES=3                   # Maximum retry attempts

# Logging
LOG_LEVEL=INFO                       # Logging level (DEBUG, INFO, WARNING, ERROR)
LOG_FILE=logs/monitor.log            # Log file path
LOG_MAX_SIZE=10485760               # Max log file size (10MB)
LOG_BACKUP_COUNT=5                   # Number of backup log files

# Data Processing Pipeline
PROCESSORS_EXE_PATH=./processors/exe_packages  # Path to processing executables
PROCESSING_TIMEOUT_SECONDS=600       # General processing timeout (10 minutes)
METACAM_CLI_TIMEOUT_SECONDS=3600     # MetaCam CLI specific timeout (1 hour)
PROCESSING_OUTPUT_PATH=./processed/output     # Processing results output directory
AUTO_START_PROCESSING=True           # Automatically start processing after validation
PROCESSING_RETRY_ATTEMPTS=2          # Number of retry attempts on failure
KEEP_ORIGINAL_DATA=True              # Preserve original data after processing

# MetaCam CLI Configuration
METACAM_CLI_MODE=0                   # Processing mode: 0=fast, 1=precision
METACAM_CLI_COLOR=1                  # Color processing: 0=No, 1=Yes
INDOOR_SCALE_THRESHOLD_M=30          # Scale threshold for narrow scene detection

# Google Sheets
SHEET_NAME=Sheet1                    # Target sheet name
BATCH_WRITE_SIZE=10                  # Batch size for sheet updates

# Email Notifications (Optional)
ENABLE_EMAIL_NOTIFICATIONS=False     # Enable email alerts
SMTP_SERVER=smtp.gmail.com           # SMTP server
SMTP_PORT=587                        # SMTP port
EMAIL_USERNAME=your_email@gmail.com  # Sender email
EMAIL_PASSWORD=your_app_password     # Email password/app password
NOTIFICATION_RECIPIENTS=admin@company.com  # Recipient emails
```

### Google Drive Setup

1. **Get Folder ID**:
   - Open the target Google Drive folder in your browser
   - Copy the folder ID from the URL: 
     ```
     https://drive.google.com/drive/folders/1ABC123DEF456GHI789JKL
     Folder ID: 1ABC123DEF456GHI789JKL
     ```

2. **Share Folder**: Grant your service account email "Viewer" access to the Drive folder

3. **Prepare Google Sheet**: Create a Google Sheet and grant your service account "Editor" access

## Usage

### Basic Usage

1. **Start the System**
   ```bash
   python main.py
   ```

2. **Monitor Processing**: The system will:
   - Monitor the specified Google Drive folder
   - Automatically download new files
   - Process and validate data packages
   - Update Google Sheets with results
   - Send notifications (if configured)

### Command Line Options

```bash
python main.py [options]

Options:
  --once              Run once and exit (no continuous monitoring)
  --config FILE       Use custom configuration file
  --log-level LEVEL   Set logging level (DEBUG, INFO, WARNING, ERROR)
  --test-connection   Test Google API connections and exit
```

### Manual Processing

```bash
# Process a specific file
python main.py --file /path/to/archive.zip

# Test validation only
python -m validation.manager /path/to/extracted/data

# Check system connectivity
python main.py --test-connection
```

## Processing Results

### Final Processed Packages

After successful 3D reconstruction processing, the system automatically creates final processed packages containing:

**Package Structure (`{original_name}_processed.zip`):**
```
{package_name}_processed.zip
├── colorized.las          # Processed 3D point cloud with color data
├── transforms.json        # 3D transformation matrices and camera poses  
├── metadata.yaml          # Original recording metadata (preserved)
├── Preview.jpg            # Original preview image (preserved)
└── camera/                # Complete camera calibration data (preserved)
    ├── left/              # Left camera data and calibration
    └── right/             # Right camera data and calibration
```

**Key Output Files:**
- **`colorized.las`**: Final 3D reconstruction result with color information from camera data
- **`transforms.json`**: Camera transformation matrices, coordinate system information, and 3D alignment data
- **Preserved Files**: Essential metadata and calibration data from the original package for reference

**Output Location**: Final packages are saved to the configured `PROCESSING_OUTPUT_PATH` directory (default: `./processed/output/`)

**Package Search Logic**: The system searches multiple locations for processing outputs to ensure reliability:
- Configured output directory
- Executable-relative output paths  
- Alternative naming patterns (e.g., `o_{package_name}_output`)

### Processing Status Tracking

The system tracks processing through multiple stages:
1. **Pre-Processing**: Directory standardization and validation
2. **Generator Phase**: `validation_generator.exe` execution
3. **Reconstruction Phase**: `metacam_cli.exe` execution with scene-appropriate settings
4. **Post-Processing**: Output file search and final package assembly
5. **Verification**: Package content validation and integrity checks

## Data Validation

The system performs comprehensive validation of MetaCam data packages. For detailed information about validation checks and requirements, see [Validation Documentation](validation/VALIDATION_CHECKS.md).

### Quick Validation Overview

| Validation Type | Purpose | Fail Conditions |
|----------------|---------|-----------------|
| **File Structure** | Ensures required directories and files exist | Missing critical files/folders |
| **Metadata** | Validates recording information and duration | Invalid duration (<3min or >9min) |
| **Point Cloud Scale** | Verifies spatial scale for reconstruction | Scale outside acceptable range |
| **Transient Detection** | AI analysis for moving obstacles | High obstacle density (configurable) |
| **Device Information** | Extracts and validates device metadata | Missing device info |

### Validation Results

The system provides color-coded validation results in Google Sheets:

- 🟢 **Green**: Validation passed, data ready for processing
- 🟡 **Yellow**: Warnings detected, manual review recommended  
- 🔴 **Red**: Critical errors, data rejected
- ⚪ **Gray**: Processing incomplete or unknown status

## Google Sheets Output

The system automatically updates a Google Sheet with the following information:

| Column | Description | Color Coding |
|--------|-------------|--------------|
| Entry ID | Unique identifier | - |
| Validation Status | Overall status | Pass/Warning/Error |
| Validation Score | Combined quality score (0-100) | Gradient |
| File ID | Google Drive file identifier | - |
| File Name | Original filename | - |
| Upload Time | When file was uploaded to Drive | - |
| Device ID | Extracted device identifier | - |
| File Size | Archive size in MB | - |
| File Type | Archive format | - |
| Extract Status | Extraction result | Success/Failed |
| File Count | Number of extracted files | - |
| Process Time | When processing occurred | - |
| Start Time | Recording start time | - |
| Duration | Recording duration | Optimal/Warning/Error |
| Location | GPS coordinates | - |
| Scene Type | Detected scene type | - |
| Size Status | Point cloud scale status | Optimal/Warning/Error |
| PCD Scale | Spatial dimensions | Color-coded by range |
| Transient Detection | AI analysis result | Pass/Review/Reject |
| WDD | Weighted Detection Density | Metric value |
| WPO | Weighted Person Occupancy | Percentage |
| SAI | Scene Activity Index | Activity level |
| Error Message | Specific error details | - |
| Warning Message | Warning details | - |
| Notes | Additional information | - |

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Verify `service-account.json` file exists and is valid
   - Check service account permissions for Drive folder and Sheet
   - Ensure APIs are enabled in Google Cloud Console

2. **Download Failures**
   - Check internet connectivity
   - Verify file permissions in Google Drive
   - Increase timeout settings for large files

3. **Validation Failures**
   - Review validation error messages in Google Sheets
   - Check data package structure against MetaCam schema
   - Verify file formats and sizes

4. **Processing Errors**
   - Check available disk space
   - Verify archive passwords are correct
   - Review system logs for detailed error information

### Log Analysis

System logs are located in the `logs/` directory:

```bash
# View recent activity
tail -f logs/monitor.log

# Search for errors
grep "ERROR" logs/monitor.log

# Filter specific processing
grep "file_id_here" logs/monitor.log
```

### Performance Optimization

For better performance with large files:

1. **Increase Chunk Size**: Set `DOWNLOAD_CHUNK_SIZE_MB=64` for faster downloads
2. **Adjust Concurrency**: Increase `MAX_CONCURRENT_DOWNLOADS` for multiple simultaneous downloads
3. **Optimize Check Interval**: Reduce `CHECK_INTERVAL` for more responsive monitoring
4. **Use SSD Storage**: Store temporary files on fast storage

## Development

### Project Structure

```
Urbansim/
├── main.py                          # Main application entry point
├── config.py                        # Configuration management
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment variables template
├── service-account.json             # Google API credentials (not in repo)
├── 
├── monitor/                         # Drive monitoring components
│   ├── drive_monitor.py            # Google Drive API interface
│   └── file_tracker.py             # Processed file tracking
├── 
├── processors/                      # File processing components  
│   ├── file_downloader.py          # Download management
│   ├── archive_handler.py          # Archive extraction and validation
│   └── data_processor.py           # 3D reconstruction processing pipeline
├── 
├── validation/                      # Data validation system
│   ├── manager.py                  # Validation pipeline coordinator
│   ├── base.py                     # Base validation framework
│   ├── metacam.py                  # MetaCam format validator
│   └── transient_validator.py      # AI-based quality assessment
├── 
├── detection/                       # AI detection components
│   ├── transient_detector.py       # YOLO-based object detection
│   ├── yolo_detector.py            # YOLO model interface
│   ├── metrics_calculator.py       # Quality metrics computation
│   ├── quality_decision.py         # Decision logic
│   ├── region_manager.py           # Spatial analysis
│   └── sampling_optimizer.py       # Adaptive sampling
├── 
├── sheets/                          # Google Sheets integration
│   ├── sheets_writer.py            # Sheets API interface
│   └── data_mapper.py              # Data formatting and mapping
├── 
├── utils/                           # Utility components
│   ├── logger.py                   # Logging system
│   ├── email_notifier.py           # Email notifications
│   ├── error_formatter.py          # Error message formatting
│   └── validators.py               # Environment validation
├── 
├── data_schemas/                    # Data validation schemas
│   ├── metacam_schema.yaml         # MetaCam package format definition
│   └── processed_metacam_schema.yaml  # Processed package format definition
├── 
├── logs/                           # System logs (created at runtime)
├── downloads/                      # Downloaded files (created at runtime)  
├── processed/                      # Archive of processed files
└── temp/                          # Temporary processing files
```

### Adding New Validators

To add a new validation component:

1. Create a new validator class inheriting from `BaseValidator`
2. Implement required validation methods
3. Register the validator in `validation/manager.py`
4. Update `data_schemas/` with any new schema requirements
5. Modify `sheets/data_mapper.py` to handle new output fields

### Extending AI Detection

To enhance the AI detection capabilities:

1. Modify `detection/transient_detector.py` for new detection logic
2. Update `detection/metrics_calculator.py` for new quality metrics
3. Adjust decision thresholds in `detection/quality_decision.py`
4. Update Google Sheets output columns in `sheets/sheets_writer.py`

## License

This project is intended for research and development purposes. Please ensure compliance with Google API terms of service and data privacy regulations when processing user data.

## Support

For technical support or questions:

1. Check the [Validation Documentation](validation/VALIDATION_CHECKS.md) for detailed validation requirements
2. Review system logs in the `logs/` directory
3. Verify configuration settings in `.env`
4. Test Google API connectivity with `python main.py --test-connection`

---

*Last Updated: 2025-09-07*  
*Version: 3.2 - Added comprehensive post-processing pipeline with final package assembly, multi-location output search, and enhanced documentation*