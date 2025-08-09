import os
import json
import logging
import time
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

from config import Config

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GoogleDriveMonitor:
    def __init__(self):
        self.service = None
        self.last_check_time = datetime.now().isoformat()
        self.processed_files = set()
        self._load_processed_files()
        
    def _load_processed_files(self):
        """Load previously processed files from cache"""
        cache_file = Path('processed_files.json')
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    self.processed_files = set(json.load(f))
                logger.info(f"Loaded {len(self.processed_files)} previously processed files")
            except Exception as e:
                logger.error(f"Error loading processed files cache: {e}")
    
    def _save_processed_files(self):
        """Save processed files to cache"""
        try:
            with open('processed_files.json', 'w') as f:
                json.dump(list(self.processed_files), f)
        except Exception as e:
            logger.error(f"Error saving processed files cache: {e}")
    
    def authenticate(self):
        """Authenticate with Google Drive API"""
        creds = None
        
        if os.path.exists(Config.GOOGLE_TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(Config.GOOGLE_TOKEN_FILE, Config.SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    Config.GOOGLE_CREDENTIALS_FILE, Config.SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(Config.GOOGLE_TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
        
        self.service = build('drive', 'v3', credentials=creds)
        logger.info("Successfully authenticated with Google Drive")
    
    def get_new_files(self):
        """Get new files from the monitored folder"""
        try:
            query = f"'{Config.MONITORED_FOLDER_ID}' in parents and trashed=false"
            
            results = self.service.files().list(
                q=query,
                fields="nextPageToken, files(id, name, size, mimeType, createdTime, modifiedTime)",
                orderBy="createdTime desc"
            ).execute()
            
            files = results.get('files', [])
            new_files = []
            
            for file in files:
                if file['id'] not in self.processed_files:
                    file_size_mb = int(file.get('size', 0)) / (1024 * 1024)
                    file_ext = Path(file['name']).suffix.lower().lstrip('.')
                    
                    if (file_ext in Config.SUPPORTED_FILE_TYPES and 
                        file_size_mb <= Config.MAX_FILE_SIZE_MB):
                        new_files.append(file)
                    else:
                        logger.info(f"Skipping file {file['name']}: unsupported type or too large")
                        self.processed_files.add(file['id'])
            
            logger.info(f"Found {len(new_files)} new files to process")
            return new_files
            
        except Exception as e:
            logger.error(f"Error retrieving files: {e}")
            return []
    
    def download_file(self, file):
        """Download a file from Google Drive"""
        try:
            file_id = file['id']
            file_name = file['name']
            
            request = self.service.files().get_media(fileId=file_id)
            
            download_path = Path(Config.DOWNLOAD_DIRECTORY) / file_name
            
            with open(download_path, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                    if status:
                        logger.debug(f"Download progress: {int(status.progress() * 100)}%")
            
            logger.info(f"Downloaded: {file_name} to {download_path}")
            return download_path
            
        except Exception as e:
            logger.error(f"Error downloading file {file['name']}: {e}")
            return None
    
    def process_file(self, file, file_path):
        """Process the downloaded file (customize this method)"""
        try:
            file_name = file['name']
            file_ext = Path(file_name).suffix.lower()
            
            logger.info(f"Processing file: {file_name}")
            
            if file_ext in ['.txt']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    logger.info(f"Text file content preview: {content[:100]}...")
            
            elif file_ext in ['.pdf']:
                logger.info(f"PDF file processed: {file_name}")
            
            elif file_ext in ['.jpg', '.png']:
                logger.info(f"Image file processed: {file_name}")
            
            elif file_ext in ['.docx']:
                logger.info(f"Word document processed: {file_name}")
            
            else:
                logger.info(f"File processed with default handler: {file_name}")
            
            self.processed_files.add(file['id'])
            logger.info(f"Successfully processed: {file_name}")
            
        except Exception as e:
            logger.error(f"Error processing file {file['name']}: {e}")
    
    def monitor_folder(self):
        """Main monitoring loop"""
        logger.info("Starting Google Drive folder monitoring...")
        
        while True:
            try:
                new_files = self.get_new_files()
                
                for file in new_files:
                    logger.info(f"Processing new file: {file['name']}")
                    
                    file_path = self.download_file(file)
                    if file_path:
                        self.process_file(file, file_path)
                
                self._save_processed_files()
                
                logger.debug(f"Sleeping for {Config.POLLING_INTERVAL} seconds...")
                time.sleep(Config.POLLING_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(Config.POLLING_INTERVAL)

def main():
    try:
        Config.validate()
        
        monitor = GoogleDriveMonitor()
        monitor.authenticate()
        monitor.monitor_folder()
        
    except Exception as e:
        logger.error(f"Application error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())