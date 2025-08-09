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
        'https://www.googleapis.com/auth/spreadsheets'
    ]
    
    # 监控配置
    CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '30'))
    ENABLE_MONITORING = os.getenv('ENABLE_MONITORING', 'True').lower() == 'true'
    MAX_CONCURRENT_DOWNLOADS = int(os.getenv('MAX_CONCURRENT_DOWNLOADS', '3'))
    
    # 文件处理配置
    DOWNLOAD_PATH = os.getenv('DOWNLOAD_PATH', './downloads')
    PROCESSED_PATH = os.getenv('PROCESSED_PATH', './processed')
    MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', '500'))
    ALLOWED_EXTENSIONS = os.getenv('ALLOWED_EXTENSIONS', '.zip,.rar,.7z,.tar,.gz').split(',')
    DEFAULT_PASSWORDS = os.getenv('DEFAULT_PASSWORDS', '123456,password').split(',')
    
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
        os.makedirs(os.path.dirname(cls.LOG_FILE), exist_ok=True)
        os.makedirs('data', exist_ok=True)
        
        return True