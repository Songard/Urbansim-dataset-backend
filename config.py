import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Google API配置
    DRIVE_FOLDER_ID = os.getenv('DRIVE_FOLDER_ID', '1NXEAm1QWAKpyZLYWHYzBNdt3kZlMV3hK')
    SPREADSHEET_ID = os.getenv('SPREADSHEET_ID', '1l26xiptV_rYxy0YKMJXhBHUeDyRS24HfrZTopWNmFiw')
    SERVICE_ACCOUNT_FILE = os.getenv('SERVICE_ACCOUNT_FILE', 'service-account.json')
    
    SCOPES = [
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/drive.file',  # 添加文件删除权限
        'https://www.googleapis.com/auth/spreadsheets'
    ]
    
    # 监控配置
    CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '30'))
    ENABLE_MONITORING = os.getenv('ENABLE_MONITORING', 'True').lower() == 'true'
    MAX_CONCURRENT_DOWNLOADS = int(os.getenv('MAX_CONCURRENT_DOWNLOADS', '3'))
    
    # 文件处理配置
    DOWNLOAD_PATH = os.getenv('DOWNLOAD_PATH', './downloads')
    PROCESSED_PATH = os.getenv('PROCESSED_PATH', './processed')
    TEMP_DIR = os.getenv('TEMP_DIR', './temp')  # 临时目录配置
    MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', '500'))
    ALLOWED_EXTENSIONS = os.getenv('ALLOWED_EXTENSIONS', '.zip,.rar,.7z,.tar,.gz').split(',')
    DEFAULT_PASSWORDS = os.getenv('DEFAULT_PASSWORDS', '123456,password').split(',')
    
    # 支持的点云文件扩展名, '.laz', '.ply', '.pcd', '.xyz'
    SUPPORTED_POINT_CLOUD_EXTENSIONS = ['.las',]
    
    # 下载优化配置
    DOWNLOAD_CHUNK_SIZE_MB = int(os.getenv('DOWNLOAD_CHUNK_SIZE_MB', '32'))  # 32MB chunks for better speed
    DOWNLOAD_TIMEOUT = int(os.getenv('DOWNLOAD_TIMEOUT', '300'))  # 5 minutes timeout
    DOWNLOAD_RETRIES = int(os.getenv('DOWNLOAD_RETRIES', '3'))  # Maximum retry attempts
    ENABLE_HTTP2 = os.getenv('ENABLE_HTTP2', 'True').lower() == 'true'  # HTTP/2 for better performance
    
    # 日志配置
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'logs/monitor.log')
    LOG_MAX_SIZE = int(os.getenv('LOG_MAX_SIZE', str(10 * 1024 * 1024)))  # 10MB
    LOG_BACKUP_COUNT = int(os.getenv('LOG_BACKUP_COUNT', '5'))
    
    # 重试配置
    MAX_RETRY_ATTEMPTS = int(os.getenv('MAX_RETRY_ATTEMPTS', '3'))
    RETRY_DELAY = int(os.getenv('RETRY_DELAY', '5'))
    
    # Sheets配置
    SHEET_NAME = os.getenv('SHEET_NAME', 'Sheet1')
    BATCH_WRITE_SIZE = int(os.getenv('BATCH_WRITE_SIZE', '10'))
    
    # 清理配置
    KEEP_PROCESSED_DAYS = int(os.getenv('KEEP_PROCESSED_DAYS', '30'))
    CLEAN_TEMP_FILES = os.getenv('CLEAN_TEMP_FILES', 'True').lower() == 'true'
    
    # Google Drive 文件删除配置
    AUTO_DELETE_SOURCE_FILES = os.getenv('AUTO_DELETE_SOURCE_FILES', 'False').lower() == 'true'
    DELETE_ONLY_AFTER_HF_SUCCESS = os.getenv('DELETE_ONLY_AFTER_HF_SUCCESS', 'True').lower() == 'true'
    
    # 数据存储路径
    PROCESSED_FILES_JSON = os.path.join('data', 'processed_files.json')
    
    # 邮件通知配置
    EMAIL_NOTIFICATIONS_ENABLED = os.getenv('EMAIL_NOTIFICATIONS_ENABLED', 'False').lower() == 'true'
    
    # SMTP服务器配置
    SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
    SMTP_USE_TLS = os.getenv('SMTP_USE_TLS', 'True').lower() == 'true'
    SMTP_USE_SSL = os.getenv('SMTP_USE_SSL', 'False').lower() == 'true'
    
    # 邮件认证
    SMTP_USERNAME = os.getenv('SMTP_USERNAME', '')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
    
    # 发送者信息
    SENDER_EMAIL = os.getenv('SENDER_EMAIL', os.getenv('SMTP_USERNAME', ''))
    SENDER_NAME = os.getenv('SENDER_NAME', 'Google Drive Monitor')
    
    # 收件人列表（逗号分隔）
    RECIPIENT_EMAILS = [email.strip() for email in os.getenv('RECIPIENT_EMAILS', '').split(',') if email.strip()]
    
    # 邮件通知策略
    NOTIFY_ON_SUCCESS = os.getenv('NOTIFY_ON_SUCCESS', 'True').lower() == 'true'
    NOTIFY_ON_ERROR = os.getenv('NOTIFY_ON_ERROR', 'True').lower() == 'true'
    NOTIFY_DAILY_REPORT = os.getenv('NOTIFY_DAILY_REPORT', 'False').lower() == 'true'
    NOTIFY_ON_LARGE_FILES = os.getenv('NOTIFY_ON_LARGE_FILES', 'True').lower() == 'true'
    LARGE_FILE_THRESHOLD_MB = int(os.getenv('LARGE_FILE_THRESHOLD_MB', '100'))
    
    # ================================
    # 验证器配置参数
    # ================================
    
    # 基础验证配置
    VALIDATION_ERROR_WEIGHT = int(os.getenv('VALIDATION_ERROR_WEIGHT', '15'))
    VALIDATION_WARNING_WEIGHT = int(os.getenv('VALIDATION_WARNING_WEIGHT', '3'))
    VALIDATION_MISSING_WEIGHT = int(os.getenv('VALIDATION_MISSING_WEIGHT', '10'))
    VALIDATION_BASE_SCORE = float(os.getenv('VALIDATION_BASE_SCORE', '100.0'))
    
    # 验证级别容差配置
    VALIDATION_STANDARD_MAX_MISSING_FILES = int(os.getenv('VALIDATION_STANDARD_MAX_MISSING_FILES', '2'))
    VALIDATION_LENIENT_MAX_ERRORS = int(os.getenv('VALIDATION_LENIENT_MAX_ERRORS', '5'))
    
    # MetaCam验证配置
    METACAM_MIN_INDICATORS_REQUIRED = int(os.getenv('METACAM_MIN_INDICATORS_REQUIRED', '2'))
    METACAM_DURATION_MIN_SECONDS = int(os.getenv('METACAM_DURATION_MIN_SECONDS', '180'))  # 3分钟
    METACAM_DURATION_MAX_SECONDS = int(os.getenv('METACAM_DURATION_MAX_SECONDS', '540'))  # 9分钟
    METACAM_DURATION_WARNING_MIN_SECONDS = int(os.getenv('METACAM_DURATION_WARNING_MIN_SECONDS', '300'))  # 5分钟
    METACAM_DURATION_WARNING_MAX_SECONDS = int(os.getenv('METACAM_DURATION_WARNING_MAX_SECONDS', '450'))  # 7.5分钟
    
    # 移动障碍物检测配置 (Transient Object Detection Configuration)
    # YOLO模型配置 (YOLO Model Configuration)
    YOLO_MODEL_NAME = os.getenv('YOLO_MODEL_NAME', 'yolo11n.pt')  # YOLO model file name
    YOLO_CONF_THRESHOLD = float(os.getenv('YOLO_CONF_THRESHOLD', '0.35'))  # Detection confidence threshold (0.0-1.0)
    YOLO_DEVICE = os.getenv('YOLO_DEVICE', 'cpu')  # Compute device: 'cpu', 'cuda', or specific GPU ID
    
    # 检测处理配置
    DETECTION_TARGET_DETECTION_FRAMES = int(os.getenv('DETECTION_TARGET_DETECTION_FRAMES', '100'))
    DETECTION_TARGET_SEGMENTATION_FRAMES = int(os.getenv('DETECTION_TARGET_SEGMENTATION_FRAMES', '50'))
    DETECTION_ENABLE_EARLY_TERMINATION = os.getenv('DETECTION_ENABLE_EARLY_TERMINATION', 'True').lower() == 'true'
    DETECTION_MAX_WORKERS = int(os.getenv('DETECTION_MAX_WORKERS', '2'))
    DETECTION_MEMORY_LIMIT_MB = int(os.getenv('DETECTION_MEMORY_LIMIT_MB', '1024'))
    DETECTION_EARLY_TERMINATION_THRESHOLD = float(os.getenv('DETECTION_EARLY_TERMINATION_THRESHOLD', '0.2'))
    
    # 区域管理配置
    REGION_SELF_AREA_THRESHOLD = float(os.getenv('REGION_SELF_AREA_THRESHOLD', '0.02'))  # 自身入镜区域面积阈值2%
    REGION_MASK_SAMPLE_RATIO = float(os.getenv('REGION_MASK_SAMPLE_RATIO', '0.1'))  # 掩码采样比例10%
    REGION_MASK_THRESHOLD = float(os.getenv('REGION_MASK_THRESHOLD', '0.5'))  # 掩码阈值
    
    # 自身入镜评分权重
    REGION_SELF_POSITION_WEIGHT = float(os.getenv('REGION_SELF_POSITION_WEIGHT', '0.4'))  # 位置权重40%
    REGION_SELF_SIZE_WEIGHT = float(os.getenv('REGION_SELF_SIZE_WEIGHT', '0.3'))  # 大小权重30%
    REGION_SELF_CENTRALITY_WEIGHT = float(os.getenv('REGION_SELF_CENTRALITY_WEIGHT', '0.2'))  # 中心性权重20%
    REGION_SELF_ZONE_BONUS = float(os.getenv('REGION_SELF_ZONE_BONUS', '0.1'))  # 自身区域额外10%
    
    # 自身入镜位置和大小参数
    REGION_SELF_POSITION_THRESHOLD = float(os.getenv('REGION_SELF_POSITION_THRESHOLD', '0.6'))  # 下方60%区域
    REGION_SELF_MIN_AREA_RATIO = float(os.getenv('REGION_SELF_MIN_AREA_RATIO', '0.01'))  # 最小1%画面
    REGION_SELF_OPTIMAL_AREA_RATIO = float(os.getenv('REGION_SELF_OPTIMAL_AREA_RATIO', '0.05'))  # 5%时达到满分
    REGION_SELF_MAX_GOOD_AREA_RATIO = float(os.getenv('REGION_SELF_MAX_GOOD_AREA_RATIO', '0.15'))  # 15%内为合理
    REGION_SELF_PENALTY_AREA_RATIO = float(os.getenv('REGION_SELF_PENALTY_AREA_RATIO', '0.35'))  # 超过15%后惩罚范围
    
    # 质量判定阈值配置 (Quality Decision Thresholds)
    # 
    # Core Metrics Explanation:
    # WDD (Weighted Detection Density): Measures density of person/dog detections weighted by image regions
    #     - Higher values = more frequent/dense detection of moving objects
    #     - Used to assess overall activity level that could affect 3D reconstruction
    # 
    # WPO (Weighted Pixel Occupancy): Percentage of image pixels occupied by person/dog objects  
    #     - Higher values = larger portion of image covered by moving objects
    #     - Critical for determining if objects block important scene features
    #
    # SAI (Self-Appearance Index): Percentage indicating photographer appearing in their own capture
    #     - Higher values = more self-appearance (photographer visible in images)
    #     - Important for 3D reconstruction quality as it creates unwanted artifacts
    
    # 严重超标直接拒绝的阈值 (Critical rejection thresholds - immediate REJECT)
    QUALITY_REJECT_WDD_THRESHOLD = float(os.getenv('QUALITY_REJECT_WDD_THRESHOLD', '8.0'))  # WDD > 8.0 = too many moving objects
    QUALITY_REJECT_WPO_THRESHOLD = float(os.getenv('QUALITY_REJECT_WPO_THRESHOLD', '5.0'))  # WPO > 5% = too much pixel coverage
    QUALITY_REJECT_SAI_THRESHOLD = float(os.getenv('QUALITY_REJECT_SAI_THRESHOLD', '15.0'))  # SAI > 15% = excessive self-appearance
    
    # 问题指标阈值（两个或以上问题指标需复核）(Problem thresholds - NEED_REVIEW if 2+ metrics exceed)
    QUALITY_PROBLEM_WDD_THRESHOLD = float(os.getenv('QUALITY_PROBLEM_WDD_THRESHOLD', '1.0'))  # WDD > 1.0 = moderate activity
    QUALITY_PROBLEM_WPO_THRESHOLD = float(os.getenv('QUALITY_PROBLEM_WPO_THRESHOLD', '1.0'))  # WPO > 1% = noticeable coverage  
    QUALITY_PROBLEM_SAI_THRESHOLD = float(os.getenv('QUALITY_PROBLEM_SAI_THRESHOLD', '3.0'))  # SAI > 3% = some self-appearance
    
    # 指标等级阈值配置 (Quality Level Thresholds)
    # WDD 阈值 (WDD - Weighted Detection Density thresholds)
    WDD_EXCELLENT_THRESHOLD = float(os.getenv('WDD_EXCELLENT_THRESHOLD', '0.2'))  # < 0.2 = excellent (minimal activity)
    WDD_ACCEPTABLE_THRESHOLD = float(os.getenv('WDD_ACCEPTABLE_THRESHOLD', '0.8'))  # < 0.8 = acceptable 
    WDD_REVIEW_THRESHOLD = float(os.getenv('WDD_REVIEW_THRESHOLD', '2.0'))  # < 2.0 = needs review
    
    # WPO 阈值 (WPO - Weighted Pixel Occupancy thresholds)  
    WPO_EXCELLENT_THRESHOLD = float(os.getenv('WPO_EXCELLENT_THRESHOLD', '0.1'))  # < 0.1% = excellent (minimal coverage)
    WPO_ACCEPTABLE_THRESHOLD = float(os.getenv('WPO_ACCEPTABLE_THRESHOLD', '0.5'))  # < 0.5% = acceptable
    WPO_REVIEW_THRESHOLD = float(os.getenv('WPO_REVIEW_THRESHOLD', '1.5'))  # < 1.5% = needs review
    
    # SAI 阈值 (SAI - Self-Appearance Index thresholds)
    SAI_EXCELLENT_THRESHOLD = float(os.getenv('SAI_EXCELLENT_THRESHOLD', '0.5'))  # < 0.5% = excellent (no self-appearance)
    SAI_ACCEPTABLE_THRESHOLD = float(os.getenv('SAI_ACCEPTABLE_THRESHOLD', '2.0'))  # < 2% = acceptable  
    SAI_REVIEW_THRESHOLD = float(os.getenv('SAI_REVIEW_THRESHOLD', '5.0'))  # < 5% = needs review
    
    # 室内场景阈值（更严格）
    # 室内WDD阈值
    INDOOR_WDD_EXCELLENT_THRESHOLD = float(os.getenv('INDOOR_WDD_EXCELLENT_THRESHOLD', '0.1'))
    INDOOR_WDD_ACCEPTABLE_THRESHOLD = float(os.getenv('INDOOR_WDD_ACCEPTABLE_THRESHOLD', '0.5'))
    INDOOR_WDD_REVIEW_THRESHOLD = float(os.getenv('INDOOR_WDD_REVIEW_THRESHOLD', '1.2'))
    
    # 室内WPO阈值
    INDOOR_WPO_EXCELLENT_THRESHOLD = float(os.getenv('INDOOR_WPO_EXCELLENT_THRESHOLD', '0.05'))
    INDOOR_WPO_ACCEPTABLE_THRESHOLD = float(os.getenv('INDOOR_WPO_ACCEPTABLE_THRESHOLD', '0.3'))
    INDOOR_WPO_REVIEW_THRESHOLD = float(os.getenv('INDOOR_WPO_REVIEW_THRESHOLD', '0.8'))
    
    # 室内SAI阈值
    INDOOR_SAI_EXCELLENT_THRESHOLD = float(os.getenv('INDOOR_SAI_EXCELLENT_THRESHOLD', '0.3'))
    INDOOR_SAI_ACCEPTABLE_THRESHOLD = float(os.getenv('INDOOR_SAI_ACCEPTABLE_THRESHOLD', '1.5'))
    INDOOR_SAI_REVIEW_THRESHOLD = float(os.getenv('INDOOR_SAI_REVIEW_THRESHOLD', '3.5'))
    
    # 室外场景阈值（相对宽松）
    # 室外WDD阈值
    OUTDOOR_WDD_EXCELLENT_THRESHOLD = float(os.getenv('OUTDOOR_WDD_EXCELLENT_THRESHOLD', '0.3'))
    OUTDOOR_WDD_ACCEPTABLE_THRESHOLD = float(os.getenv('OUTDOOR_WDD_ACCEPTABLE_THRESHOLD', '1.0'))
    OUTDOOR_WDD_REVIEW_THRESHOLD = float(os.getenv('OUTDOOR_WDD_REVIEW_THRESHOLD', '2.5'))
    
    # 室外WPO阈值
    OUTDOOR_WPO_EXCELLENT_THRESHOLD = float(os.getenv('OUTDOOR_WPO_EXCELLENT_THRESHOLD', '0.15'))
    OUTDOOR_WPO_ACCEPTABLE_THRESHOLD = float(os.getenv('OUTDOOR_WPO_ACCEPTABLE_THRESHOLD', '0.6'))
    OUTDOOR_WPO_REVIEW_THRESHOLD = float(os.getenv('OUTDOOR_WPO_REVIEW_THRESHOLD', '2.0'))
    
    # 室外SAI阈值
    OUTDOOR_SAI_EXCELLENT_THRESHOLD = float(os.getenv('OUTDOOR_SAI_EXCELLENT_THRESHOLD', '0.8'))
    OUTDOOR_SAI_ACCEPTABLE_THRESHOLD = float(os.getenv('OUTDOOR_SAI_ACCEPTABLE_THRESHOLD', '2.5'))
    OUTDOOR_SAI_REVIEW_THRESHOLD = float(os.getenv('OUTDOOR_SAI_REVIEW_THRESHOLD', '6.0'))
    
    # 移动障碍物评分权重配置
    TRANSIENT_REJECT_SCORE_PENALTY = float(os.getenv('TRANSIENT_REJECT_SCORE_PENALTY', '50.0'))
    TRANSIENT_REVIEW_SCORE_PENALTY = float(os.getenv('TRANSIENT_REVIEW_SCORE_PENALTY', '25.0'))
    TRANSIENT_ERROR_SCORE_PENALTY = float(os.getenv('TRANSIENT_ERROR_SCORE_PENALTY', '60.0'))
    
    # WDD指标评分影响
    TRANSIENT_WDD_SEVERE_THRESHOLD = float(os.getenv('TRANSIENT_WDD_SEVERE_THRESHOLD', '8.0'))
    TRANSIENT_WDD_SEVERE_PENALTY = float(os.getenv('TRANSIENT_WDD_SEVERE_PENALTY', '30.0'))
    TRANSIENT_WDD_HIGH_THRESHOLD = float(os.getenv('TRANSIENT_WDD_HIGH_THRESHOLD', '5.0'))
    TRANSIENT_WDD_HIGH_PENALTY = float(os.getenv('TRANSIENT_WDD_HIGH_PENALTY', '15.0'))
    TRANSIENT_WDD_MEDIUM_THRESHOLD = float(os.getenv('TRANSIENT_WDD_MEDIUM_THRESHOLD', '2.0'))
    TRANSIENT_WDD_MEDIUM_PENALTY = float(os.getenv('TRANSIENT_WDD_MEDIUM_PENALTY', '5.0'))
    
    # WPO指标评分影响
    TRANSIENT_WPO_SEVERE_THRESHOLD = float(os.getenv('TRANSIENT_WPO_SEVERE_THRESHOLD', '30.0'))
    TRANSIENT_WPO_SEVERE_PENALTY = float(os.getenv('TRANSIENT_WPO_SEVERE_PENALTY', '25.0'))
    TRANSIENT_WPO_HIGH_THRESHOLD = float(os.getenv('TRANSIENT_WPO_HIGH_THRESHOLD', '20.0'))
    TRANSIENT_WPO_HIGH_PENALTY = float(os.getenv('TRANSIENT_WPO_HIGH_PENALTY', '12.0'))
    TRANSIENT_WPO_MEDIUM_THRESHOLD = float(os.getenv('TRANSIENT_WPO_MEDIUM_THRESHOLD', '10.0'))
    TRANSIENT_WPO_MEDIUM_PENALTY = float(os.getenv('TRANSIENT_WPO_MEDIUM_PENALTY', '3.0'))
    
    # SAI指标评分影响
    TRANSIENT_SAI_SEVERE_THRESHOLD = float(os.getenv('TRANSIENT_SAI_SEVERE_THRESHOLD', '25.0')) # debug：75.0
    TRANSIENT_SAI_SEVERE_PENALTY = float(os.getenv('TRANSIENT_SAI_SEVERE_PENALTY', '20.0'))
    TRANSIENT_SAI_HIGH_THRESHOLD = float(os.getenv('TRANSIENT_SAI_HIGH_THRESHOLD', '15.0'))
    TRANSIENT_SAI_HIGH_PENALTY = float(os.getenv('TRANSIENT_SAI_HIGH_PENALTY', '10.0'))
    TRANSIENT_SAI_MEDIUM_THRESHOLD = float(os.getenv('TRANSIENT_SAI_MEDIUM_THRESHOLD', '5.0'))
    TRANSIENT_SAI_MEDIUM_PENALTY = float(os.getenv('TRANSIENT_SAI_MEDIUM_PENALTY', '2.0'))
    
    # ========================================
    # 数据处理配置 (Data Processing Configuration)
    # ========================================
    
    # 处理程序路径配置
    PROCESSORS_EXE_PATH = os.getenv('PROCESSORS_EXE_PATH', './processors/exe_packages')
    
    # 处理超时配置（秒）
    PROCESSING_TIMEOUT_SECONDS = int(os.getenv('PROCESSING_TIMEOUT_SECONDS', '600'))  # 10分钟
    
    # 是否在验证通过后自动启动数据处理
    AUTO_START_PROCESSING = os.getenv('AUTO_START_PROCESSING', 'True').lower() == 'true'
    
    # 处理失败时的重试次数
    PROCESSING_RETRY_ATTEMPTS = int(os.getenv('PROCESSING_RETRY_ATTEMPTS', '2'))
    
    # 处理完成后是否保留原始数据
    KEEP_ORIGINAL_DATA = os.getenv('KEEP_ORIGINAL_DATA', 'True').lower() == 'true'
    
    # 处理输出目录
    PROCESSING_OUTPUT_PATH = os.getenv('PROCESSING_OUTPUT_PATH', './processed/output')
    
    # Metacam CLI 处理配置
    METACAM_CLI_MODE = os.getenv('METACAM_CLI_MODE', '1')  # 0=fast, 1=precision
    METACAM_CLI_COLOR = os.getenv('METACAM_CLI_COLOR', '1')  # 0=No, 1=Yes
    METACAM_CLI_TIMEOUT_SECONDS = int(os.getenv('METACAM_CLI_TIMEOUT_SECONDS', '7200'))  # 2小时超时

    # 场景类型判断阈值（用于自动选择scene参数）
    INDOOR_SCALE_THRESHOLD_M = float(os.getenv('INDOOR_SCALE_THRESHOLD_M', '30'))  # 30米以下认为是narrow场景
    
    # ========================================
    # COLMAP 格式生成配置 (COLMAP Format Generation Configuration)
    # ========================================
    
    # 是否启用COLMAP格式生成
    ENABLE_COLMAP_GENERATION = os.getenv('ENABLE_COLMAP_GENERATION', 'True').lower() == 'true'
    
    # 相机轨迹分割配置（用于train/val分割）- 多级阈值
    COLMAP_SPLIT_DISTANCE_GOOD = float(os.getenv('COLMAP_SPLIT_DISTANCE_GOOD', '0.5'))  # 良好分割阈值(米) - 绿色
    COLMAP_SPLIT_DISTANCE_WARNING = float(os.getenv('COLMAP_SPLIT_DISTANCE_WARNING', '1.0'))  # 警告分割阈值(米) - 黄色  
    COLMAP_MIN_PAUSE_FRAMES = int(os.getenv('COLMAP_MIN_PAUSE_FRAMES', '2'))  # 最小暂停帧数
    
    # 向后兼容
    COLMAP_ORIGIN_DISTANCE_THRESHOLD = COLMAP_SPLIT_DISTANCE_GOOD
    
    # 世界坐标系变换矩阵（参考metacam.py示例）
    COLMAP_GLOBAL_TRANSFORM = [
        [0, 1, 0, 0],
        [-1, 0, 0, 0], 
        [0, 0, 1, 0],
        [0, 0, 0, 1]
    ]
    
    COLMAP_GLOBAL_ROTATION = [
        [1, 0, 0],
        [0, -1, 0],
        [0, 0, -1]
    ]
    
    # 点云处理配置
    COLMAP_POINTCLOUD_DOWNSAMPLE_METHOD = os.getenv('COLMAP_POINTCLOUD_DOWNSAMPLE_METHOD', 'uniform')  # uniform or voxel
    COLMAP_POINTCLOUD_EVERY_K_POINTS = int(os.getenv('COLMAP_POINTCLOUD_EVERY_K_POINTS', '1'))  # 均匀采样间隔
    COLMAP_POINTCLOUD_VOXEL_SIZE = float(os.getenv('COLMAP_POINTCLOUD_VOXEL_SIZE', '0.02'))  # 体素下采样大小
    COLMAP_VISUALIZATION_SAMPLE_POINTS = int(os.getenv('COLMAP_VISUALIZATION_SAMPLE_POINTS', '4000'))  # 可视化采样点数
    
    # COLMAP 输出格式配置
    COLMAP_OUTPUT_FORMAT = os.getenv('COLMAP_OUTPUT_FORMAT', '.bin')  # '.txt' or '.bin' - 输出格式选择
    
    # 最终打包内容配置
    PACKAGE_INCLUDE_ORIGINAL_FILES = os.getenv('PACKAGE_INCLUDE_ORIGINAL_FILES', 'False').lower() == 'true'  # 是否包含原始文件
    PACKAGE_INCLUDE_PROCESSING_OUTPUTS = os.getenv('PACKAGE_INCLUDE_PROCESSING_OUTPUTS', 'False').lower() == 'true'  # 是否包含处理输出文件
    PACKAGE_INCLUDE_COLMAP_FILES = os.getenv('PACKAGE_INCLUDE_COLMAP_FILES', 'True').lower() == 'true'  # 是否包含COLMAP文件
    PACKAGE_INCLUDE_CAMERA_IMAGES = os.getenv('PACKAGE_INCLUDE_CAMERA_IMAGES', 'False').lower() == 'true'  # 是否包含相机图像文件
    PACKAGE_INCLUDE_PREVIEW_IMAGE = os.getenv('PACKAGE_INCLUDE_PREVIEW_IMAGE', 'True').lower() == 'true'  # 是否包含预览图
    PACKAGE_INCLUDE_VISUALIZATION = os.getenv('PACKAGE_INCLUDE_VISUALIZATION', 'False').lower() == 'true'  # 是否包含可视化文件
    
    # ========================================
    # 图像遮挡（人脸/车牌）处理配置 (Image Masking Configuration)
    # ========================================
    IMAGE_MASKING_ENABLED = os.getenv('IMAGE_MASKING_ENABLED', 'True').lower() == 'true'
    IMAGE_MASK_FACE_MODEL_PATH = os.getenv('IMAGE_MASK_FACE_MODEL_PATH', '')
    IMAGE_MASK_LP_MODEL_PATH = os.getenv('IMAGE_MASK_LP_MODEL_PATH', '')
    IMAGE_MASK_FACE_MODEL_SCORE_THRESHOLD = float(os.getenv('IMAGE_MASK_FACE_MODEL_SCORE_THRESHOLD', '0.8'))
    IMAGE_MASK_LP_MODEL_SCORE_THRESHOLD = float(os.getenv('IMAGE_MASK_LP_MODEL_SCORE_THRESHOLD', '0.8'))
    IMAGE_MASK_NMS_IOU_THRESHOLD = float(os.getenv('IMAGE_MASK_NMS_IOU_THRESHOLD', '0.3'))
    IMAGE_MASK_SCALE_FACTOR_DETECTIONS = float(os.getenv('IMAGE_MASK_SCALE_FACTOR_DETECTIONS', '1.05'))
    # 可识别为原始鱼眼与去畸变图像所在目录名（在数据包 data/ 目录下的子目录名）
    # 原始鱼眼图像目录名（通常是 "images"）
    IMAGE_MASK_FISHEYE_DIR_NAME = os.getenv('IMAGE_MASK_FISHEYE_DIR_NAME', 'images')
    # 去畸变图像目录名（通常是 "undistorted"）
    IMAGE_MASK_UNDISTORTED_DIR_NAME = os.getenv('IMAGE_MASK_UNDISTORTED_DIR_NAME', 'undistorted')

    # ========================================
    # Hugging Face 上传配置 (Hugging Face Upload Configuration)  
    # ========================================
    
    # 是否启用 Hugging Face 上传
    ENABLE_HF_UPLOAD = os.getenv('ENABLE_HF_UPLOAD', 'True').lower() == 'true'
    
    # Hugging Face 认证配置
    HF_TOKEN = os.getenv('HF_TOKEN', '')  # Hugging Face Access Token
    HF_USERNAME = os.getenv('HF_USERNAME', 'Songard')  # Hugging Face 用户名
    HF_REPO_ID = os.getenv('HF_REPO_ID', 'ai4ce/UrbanSim_raw')  # Repository ID
    
    # 上传配置
    HF_UPLOAD_TIMEOUT = int(os.getenv('HF_UPLOAD_TIMEOUT', '3600'))  # 上传超时时间(秒) - 1小时
    HF_UPLOAD_RETRIES = int(os.getenv('HF_UPLOAD_RETRIES', '3'))  # 上传重试次数
    HF_CHUNK_SIZE_MB = int(os.getenv('HF_CHUNK_SIZE_MB', '64'))  # 分块上传大小(MB)
    
    # 文件组织配置
    HF_ORGANIZE_BY_SCENE = os.getenv('HF_ORGANIZE_BY_SCENE', 'True').lower() == 'true'  # 是否按场景类型组织目录
    HF_USE_FILE_ID_NAMING = os.getenv('HF_USE_FILE_ID_NAMING', 'True').lower() == 'true'  # 是否使用文件ID命名
    
    # 上传条件配置
    HF_UPLOAD_ALL_RESULTS = os.getenv('HF_UPLOAD_ALL_RESULTS', 'True').lower() == 'true'  # 是否上传所有结果
    HF_MIN_VALIDATION_SCORE = float(os.getenv('HF_MIN_VALIDATION_SCORE', '60.0'))  # 最小验证分数要求
    HF_EXCLUDE_FAILED_PROCESSING = os.getenv('HF_EXCLUDE_FAILED_PROCESSING', 'False').lower() == 'true'  # 是否排除处理失败的文件
    HF_EXCLUDE_UNMASKED_IMAGES = os.getenv('HF_EXCLUDE_UNMASKED_IMAGES', 'True').lower() == 'true'  # 是否排除未遮挡的原始图像(camera/和undistorted/)
    
    # 获取场景特定阈值的辅助方法
    @classmethod
    def get_scene_thresholds(cls, scene_type: str) -> dict:
        """获取场景特定的阈值配置"""
        if scene_type.lower() == "indoor":
            return {
                "WDD": {
                    "excellent": cls.INDOOR_WDD_EXCELLENT_THRESHOLD,
                    "acceptable": cls.INDOOR_WDD_ACCEPTABLE_THRESHOLD,
                    "review": cls.INDOOR_WDD_REVIEW_THRESHOLD
                },
                "WPO": {
                    "excellent": cls.INDOOR_WPO_EXCELLENT_THRESHOLD,
                    "acceptable": cls.INDOOR_WPO_ACCEPTABLE_THRESHOLD,
                    "review": cls.INDOOR_WPO_REVIEW_THRESHOLD
                },
                "SAI": {
                    "excellent": cls.INDOOR_SAI_EXCELLENT_THRESHOLD,
                    "acceptable": cls.INDOOR_SAI_ACCEPTABLE_THRESHOLD,
                    "review": cls.INDOOR_SAI_REVIEW_THRESHOLD
                }
            }
        elif scene_type.lower() == "outdoor":
            return {
                "WDD": {
                    "excellent": cls.OUTDOOR_WDD_EXCELLENT_THRESHOLD,
                    "acceptable": cls.OUTDOOR_WDD_ACCEPTABLE_THRESHOLD,
                    "review": cls.OUTDOOR_WDD_REVIEW_THRESHOLD
                },
                "WPO": {
                    "excellent": cls.OUTDOOR_WPO_EXCELLENT_THRESHOLD,
                    "acceptable": cls.OUTDOOR_WPO_ACCEPTABLE_THRESHOLD,
                    "review": cls.OUTDOOR_WPO_REVIEW_THRESHOLD
                },
                "SAI": {
                    "excellent": cls.OUTDOOR_SAI_EXCELLENT_THRESHOLD,
                    "acceptable": cls.OUTDOOR_SAI_ACCEPTABLE_THRESHOLD,
                    "review": cls.OUTDOOR_SAI_REVIEW_THRESHOLD
                }
            }
        else:  # default
            return {
                "WDD": {
                    "excellent": cls.WDD_EXCELLENT_THRESHOLD,
                    "acceptable": cls.WDD_ACCEPTABLE_THRESHOLD,
                    "review": cls.WDD_REVIEW_THRESHOLD
                },
                "WPO": {
                    "excellent": cls.WPO_EXCELLENT_THRESHOLD,
                    "acceptable": cls.WPO_ACCEPTABLE_THRESHOLD,
                    "review": cls.WPO_REVIEW_THRESHOLD
                },
                "SAI": {
                    "excellent": cls.SAI_EXCELLENT_THRESHOLD,
                    "acceptable": cls.SAI_ACCEPTABLE_THRESHOLD,
                    "review": cls.SAI_REVIEW_THRESHOLD
                }
            }
    
    @classmethod
    def get_reject_thresholds(cls) -> dict:
        """获取拒绝阈值配置"""
        return {
            "WDD": cls.QUALITY_REJECT_WDD_THRESHOLD,
            "WPO": cls.QUALITY_REJECT_WPO_THRESHOLD,
            "SAI": cls.QUALITY_REJECT_SAI_THRESHOLD
        }
    
    @classmethod
    def get_problem_thresholds(cls) -> dict:
        """获取问题阈值配置"""
        return {
            "WDD": cls.QUALITY_PROBLEM_WDD_THRESHOLD,
            "WPO": cls.QUALITY_PROBLEM_WPO_THRESHOLD,
            "SAI": cls.QUALITY_PROBLEM_SAI_THRESHOLD
        }
    
    @classmethod
    def validate(cls):
        """验证配置有效性"""
        if not cls.DRIVE_FOLDER_ID:
            raise ValueError("DRIVE_FOLDER_ID is required")
        
        if not cls.SPREADSHEET_ID:
            raise ValueError("SPREADSHEET_ID is required")
            
        if not os.path.exists(cls.SERVICE_ACCOUNT_FILE):
            raise ValueError(f"Service account file not found: {cls.SERVICE_ACCOUNT_FILE}")
        
        # 创建必要的目录
        os.makedirs(cls.DOWNLOAD_PATH, exist_ok=True)
        os.makedirs(cls.PROCESSED_PATH, exist_ok=True)
        os.makedirs(cls.PROCESSING_OUTPUT_PATH, exist_ok=True)
        os.makedirs(cls.PROCESSORS_EXE_PATH, exist_ok=True)
        os.makedirs(os.path.dirname(cls.LOG_FILE), exist_ok=True)
        os.makedirs('data', exist_ok=True)
        
        return True