import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    GOOGLE_CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json')
    GOOGLE_TOKEN_FILE = os.getenv('GOOGLE_TOKEN_FILE', 'token.json')
    
    SCOPES = [
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/drive.metadata.readonly'
    ]
    
    MONITORED_FOLDER_ID = os.getenv('MONITORED_FOLDER_ID')
    
    POLLING_INTERVAL = int(os.getenv('POLLING_INTERVAL', '60'))
    
    DOWNLOAD_DIRECTORY = os.getenv('DOWNLOAD_DIRECTORY', './downloads')
    
    SUPPORTED_FILE_TYPES = os.getenv('SUPPORTED_FILE_TYPES', 'pdf,docx,txt,jpg,png').split(',')
    
    MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', '100'))
    
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    @classmethod
    def validate(cls):
        if not cls.MONITORED_FOLDER_ID:
            raise ValueError("MONITORED_FOLDER_ID is required")
        
        if not os.path.exists(cls.GOOGLE_CREDENTIALS_FILE):
            raise ValueError(f"Google credentials file not found: {cls.GOOGLE_CREDENTIALS_FILE}")
        
        os.makedirs(cls.DOWNLOAD_DIRECTORY, exist_ok=True)
        
        return True