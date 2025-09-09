"""
Hugging Face upload utilities for processed MetaCam data

This module handles uploading of final processed packages to Hugging Face repositories,
with support for organized directory structures and retry mechanisms.
"""

import os
import time
from pathlib import Path
from typing import Dict, Optional, Tuple, Any
from datetime import datetime

from config import Config
from utils.logger import get_logger

logger = get_logger(__name__)

# Graceful import of huggingface_hub with fallback
try:
    from huggingface_hub import HfApi, login, create_repo, hf_hub_download
    from huggingface_hub.utils import RepositoryNotFoundError, HfHubHTTPError
    HF_AVAILABLE = True
    logger.info("Hugging Face Hub library loaded successfully")
except ImportError as e:
    logger.warning(f"Hugging Face Hub library not available: {e}")
    logger.info("Install with: pip install huggingface_hub")
    HF_AVAILABLE = False
    HfApi = None
    RepositoryNotFoundError = Exception
    HfHubHTTPError = Exception


class HuggingFaceUploader:
    """Handles uploading processed packages to Hugging Face repositories"""
    
    def __init__(self):
        """Initialize the Hugging Face uploader"""
        self.api = None
        self.token = Config.HF_TOKEN
        self.repo_id = Config.HF_REPO_ID
        self.username = Config.HF_USERNAME
        self.initialized = False
        
        if not HF_AVAILABLE:
            logger.error("Hugging Face Hub library not available - upload functionality disabled")
            return
            
        if not self.token:
            logger.error("HF_TOKEN not found in environment variables - upload functionality disabled")
            return
            
        self._initialize_api()
    
    def _initialize_api(self) -> bool:
        """Initialize Hugging Face API with authentication"""
        try:
            logger.info("Initializing Hugging Face API...")
            
            # Login with token
            login(token=self.token, add_to_git_credential=False)
            self.api = HfApi(token=self.token)
            
            # Test connection
            user_info = self.api.whoami()
            logger.info(f"✓ Connected to Hugging Face as: {user_info['name']}")
            
            # Check if repository exists
            try:
                repo_info = self.api.repo_info(repo_id=self.repo_id, repo_type="dataset")
                logger.info(f"✓ Repository found: {self.repo_id}")
                logger.info(f"  Repository type: dataset")
                logger.info(f"  Repository private: {repo_info.private}")
            except RepositoryNotFoundError:
                logger.warning(f"Repository {self.repo_id} not found - will attempt to create it during first upload")
            
            self.initialized = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Hugging Face API: {e}")
            return False
    
    def _ensure_repository_exists(self) -> bool:
        """Ensure the target repository exists, create if necessary"""
        try:
            # Check if repository already exists
            try:
                self.api.repo_info(repo_id=self.repo_id, repo_type="dataset")
                logger.info(f"Repository {self.repo_id} already exists")
                return True
            except RepositoryNotFoundError:
                pass
            
            logger.info(f"Creating new dataset repository: {self.repo_id}")
            create_repo(
                repo_id=self.repo_id,
                repo_type="dataset",
                token=self.token,
                private=False,  # Set to True if you want private repository
                exist_ok=True
            )
            logger.info(f"✓ Repository created successfully: {self.repo_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create repository {self.repo_id}: {e}")
            return False
    
    def _determine_upload_path(self, file_id: str, scene_type: str, original_filename: str) -> str:
        """Determine the upload path within the repository"""
        if Config.HF_ORGANIZE_BY_SCENE:
            # Organize by scene type (indoor/outdoor)
            scene_subdir = "outdoor" if scene_type.lower() == "outdoor" else "indoor"
            
            if Config.HF_USE_FILE_ID_NAMING:
                # Use file ID as filename
                filename = f"{file_id}.zip"
            else:
                # Use original filename
                filename = original_filename
            
            upload_path = f"{scene_subdir}/{filename}"
        else:
            # Flat structure
            if Config.HF_USE_FILE_ID_NAMING:
                filename = f"{file_id}.zip"
            else:
                filename = original_filename
            
            upload_path = filename
        
        return upload_path
    
    def upload_package(
        self,
        package_path: str,
        file_id: str,
        scene_type: str = "outdoor",
        validation_score: float = None,
        processing_success: bool = True,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Upload a processed package to Hugging Face
        
        Args:
            package_path: Path to the package file to upload
            file_id: Google Drive file ID for naming and tracking
            scene_type: Scene type (indoor/outdoor) for directory organization
            validation_score: Validation score for quality filtering
            processing_success: Whether processing was successful
            metadata: Additional metadata to include in upload info
            
        Returns:
            Dict containing upload result information
        """
        if not Config.ENABLE_HF_UPLOAD:
            return {
                'success': False,
                'skipped': True,
                'reason': 'Hugging Face upload is disabled in configuration'
            }
        
        if not HF_AVAILABLE or not self.initialized:
            return {
                'success': False,
                'error': 'Hugging Face uploader not available or not initialized'
            }
        
        # Check upload conditions
        upload_check = self._should_upload_file(validation_score, processing_success)
        if not upload_check['should_upload']:
            return {
                'success': False,
                'skipped': True,
                'reason': upload_check['reason']
            }
        
        package_path = Path(package_path)
        if not package_path.exists():
            return {
                'success': False,
                'error': f'Package file not found: {package_path}'
            }
        
        logger.info(f"Starting Hugging Face upload for file ID: {file_id}")
        logger.info(f"Package path: {package_path}")
        logger.info(f"Scene type: {scene_type}")
        
        try:
            # Ensure repository exists
            if not self._ensure_repository_exists():
                return {
                    'success': False,
                    'error': 'Failed to create or access repository'
                }
            
            # Determine upload path
            upload_path = self._determine_upload_path(file_id, scene_type, package_path.name)
            logger.info(f"Upload path: {upload_path}")
            
            # Get file info
            file_size = package_path.stat().st_size
            file_size_mb = file_size / (1024 * 1024)
            logger.info(f"File size: {file_size_mb:.1f} MB")
            
            # Perform upload with retry mechanism
            upload_result = self._upload_with_retry(package_path, upload_path)
            
            if upload_result['success']:
                # Generate the direct file URL
                file_url = f"https://huggingface.co/datasets/{self.repo_id}/blob/main/{upload_path}"
                repo_url = f"https://huggingface.co/datasets/{self.repo_id}"
                
                # Create upload info for tracking
                upload_info = {
                    'success': True,
                    'upload_path': upload_path,
                    'file_url': file_url,
                    'repo_url': repo_url,
                    'file_size_mb': file_size_mb,
                    'upload_time': datetime.now().isoformat(),
                    'repo_id': self.repo_id,
                    'file_id': file_id,
                    'scene_type': scene_type,
                    'upload_duration': upload_result.get('duration', 0)
                }
                
                if metadata:
                    upload_info['metadata'] = metadata
                
                logger.success(f"✓ Upload completed: {upload_path}")
                logger.info(f"Repository: {repo_url}")
                logger.info(f"File URL: {file_url}")
                return upload_info
            else:
                return upload_result
                
        except Exception as e:
            error_msg = f"Upload failed with exception: {e}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def _should_upload_file(self, validation_score: float, processing_success: bool) -> Dict[str, Any]:
        """Check if file should be uploaded based on configured conditions"""
        
        # Check if all results should be uploaded
        if Config.HF_UPLOAD_ALL_RESULTS:
            return {'should_upload': True, 'reason': 'Upload all results enabled'}
        
        # Check processing success requirement
        if Config.HF_EXCLUDE_FAILED_PROCESSING and not processing_success:
            return {
                'should_upload': False,
                'reason': f'Processing failed and HF_EXCLUDE_FAILED_PROCESSING=True'
            }
        
        # Check validation score requirement
        if validation_score is not None and validation_score < Config.HF_MIN_VALIDATION_SCORE:
            return {
                'should_upload': False,
                'reason': f'Validation score {validation_score:.1f} below minimum {Config.HF_MIN_VALIDATION_SCORE}'
            }
        
        return {'should_upload': True, 'reason': 'Meets upload criteria'}
    
    def _upload_with_retry(self, package_path: Path, upload_path: str) -> Dict[str, Any]:
        """Upload file with retry mechanism"""
        max_retries = Config.HF_UPLOAD_RETRIES
        
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(f"Upload attempt {attempt + 1}/{max_retries + 1}")
                    time.sleep(min(2 ** attempt, 30))  # Exponential backoff
                
                upload_start = datetime.now()
                
                # Upload file to repository
                self.api.upload_file(
                    path_or_fileobj=str(package_path),
                    path_in_repo=upload_path,
                    repo_id=self.repo_id,
                    repo_type="dataset",
                    token=self.token
                )
                
                upload_duration = (datetime.now() - upload_start).total_seconds()
                
                return {
                    'success': True,
                    'duration': upload_duration,
                    'attempts': attempt + 1
                }
                
            except HfHubHTTPError as e:
                if attempt < max_retries:
                    logger.warning(f"Upload failed (attempt {attempt + 1}), retrying: {e}")
                    continue
                else:
                    return {
                        'success': False,
                        'error': f'Upload failed after {max_retries + 1} attempts: {e}',
                        'attempts': attempt + 1
                    }
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"Upload failed with unexpected error (attempt {attempt + 1}), retrying: {e}")
                    continue
                else:
                    return {
                        'success': False,
                        'error': f'Upload failed after {max_retries + 1} attempts: {e}',
                        'attempts': attempt + 1
                    }
        
        return {
            'success': False,
            'error': 'Upload failed - reached maximum retry attempts'
        }
    
    def list_uploaded_files(self, scene_type: str = None) -> Dict[str, Any]:
        """List files that have been uploaded to the repository"""
        if not self.initialized:
            return {'success': False, 'error': 'Uploader not initialized'}
        
        try:
            # Get repository file list
            repo_files = self.api.list_repo_files(repo_id=self.repo_id, repo_type="dataset")
            
            # Filter by scene type if specified
            if scene_type:
                scene_subdir = "outdoor" if scene_type.lower() == "outdoor" else "indoor"
                repo_files = [f for f in repo_files if f.startswith(f"{scene_subdir}/")]
            
            # Filter for ZIP files
            zip_files = [f for f in repo_files if f.endswith('.zip')]
            
            return {
                'success': True,
                'files': zip_files,
                'total_count': len(zip_files),
                'repo_url': f"https://huggingface.co/datasets/{self.repo_id}"
            }
            
        except Exception as e:
            logger.error(f"Failed to list uploaded files: {e}")
            return {'success': False, 'error': str(e)}
    
    def check_file_exists(self, file_id: str, scene_type: str) -> bool:
        """Check if a file with given ID already exists in the repository"""
        if not self.initialized:
            return False
        
        try:
            upload_path = self._determine_upload_path(file_id, scene_type, f"{file_id}.zip")
            
            # Try to get file info
            self.api.get_paths_info(
                paths=[upload_path],
                repo_id=self.repo_id,
                repo_type="dataset"
            )
            return True
            
        except Exception:
            return False


def upload_processed_package(
    package_path: str,
    file_id: str,
    scene_type: str = "outdoor",
    validation_score: float = None,
    processing_success: bool = True,
    metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Convenience function to upload a processed package
    
    Args:
        package_path: Path to the package file to upload
        file_id: Google Drive file ID for naming and tracking
        scene_type: Scene type (indoor/outdoor) for directory organization
        validation_score: Validation score for quality filtering
        processing_success: Whether processing was successful
        metadata: Additional metadata to include in upload info
        
    Returns:
        Dict containing upload result information
    """
    uploader = HuggingFaceUploader()
    return uploader.upload_package(
        package_path=package_path,
        file_id=file_id,
        scene_type=scene_type,
        validation_score=validation_score,
        processing_success=processing_success,
        metadata=metadata
    )