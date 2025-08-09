import os
import tempfile
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import zipfile
import rarfile
import py7zr
import tarfile
import gzip

from config import Config
from validation import ValidationManager, ValidationLevel

logger = logging.getLogger(__name__)

class ArchiveHandler:
    """
    压缩文件处理器
    
    功能:
    - 支持格式：.zip, .rar, .7z, .tar, .tar.gz, .tar.bz2
    - 自动检测压缩格式
    - 解压到临时目录进行验证
    - 验证解压是否成功（检查文件完整性）
    - 获取压缩包内文件列表
    - 处理密码保护的压缩文件（配置默认密码列表）
    """
    
    SUPPORTED_FORMATS = {
        '.zip': 'zip',
        '.rar': 'rar',
        '.7z': '7z',
        '.tar': 'tar',
        '.tar.gz': 'tar.gz',
        '.tar.bz2': 'tar.bz2',
        '.tgz': 'tar.gz',
        '.tbz2': 'tar.bz2',
        '.gz': 'gz'
    }
    
    def __init__(self):
        """初始化压缩文件处理器"""
        self.temp_extract_dir = None
        self.validation_manager = ValidationManager()
        logger.info("ArchiveHandler initialized with new validation system")
    
    def detect_format(self, file_path: str) -> Optional[str]:
        """
        自动检测压缩文件格式
        
        Args:
            file_path (str): 文件路径
            
        Returns:
            Optional[str]: 压缩格式，如果无法识别返回None
        """
        try:
            file_path_obj = Path(file_path)
            file_name = file_path_obj.name.lower()
            
            # 检查多级扩展名（如 .tar.gz）
            for ext, format_type in sorted(self.SUPPORTED_FORMATS.items(), key=lambda x: -len(x[0])):
                if file_name.endswith(ext):
                    logger.debug(f"Detected format: {format_type} for file: {file_name}")
                    return format_type
            
            # 尝试通过文件头检测
            format_by_header = self._detect_format_by_header(file_path)
            if format_by_header:
                logger.debug(f"Detected format by header: {format_by_header} for file: {file_name}")
                return format_by_header
            
            logger.warning(f"Unable to detect format for file: {file_name}")
            return None
            
        except Exception as e:
            logger.error(f"Error detecting archive format: {e}")
            return None
    
    def _detect_format_by_header(self, file_path: str) -> Optional[str]:
        """通过文件头检测格式"""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(10)
            
            # ZIP文件头
            if header.startswith(b'PK\x03\x04') or header.startswith(b'PK\x05\x06'):
                return 'zip'
            
            # RAR文件头
            if header.startswith(b'Rar!\x1a\x07\x00') or header.startswith(b'Rar!\x1a\x07\x01'):
                return 'rar'
            
            # 7Z文件头
            if header.startswith(b'7z\xbc\xaf\x27\x1c'):
                return '7z'
            
            # GZIP文件头
            if header.startswith(b'\x1f\x8b'):
                return 'gz'
            
            # TAR文件需要更复杂的检测
            try:
                with tarfile.open(file_path, 'r') as tar:
                    return 'tar'
            except:
                pass
            
            return None
            
        except Exception as e:
            logger.debug(f"Error detecting format by header: {e}")
            return None
    
    def get_file_list(self, file_path: str, password: str = None) -> List[str]:
        """
        获取压缩包内文件列表
        
        Args:
            file_path (str): 压缩文件路径
            password (str): 密码（可选）
            
        Returns:
            List[str]: 文件路径列表
        """
        try:
            format_type = self.detect_format(file_path)
            if not format_type:
                logger.error(f"Unsupported archive format: {file_path}")
                return []
            
            file_list = []
            
            if format_type == 'zip':
                with zipfile.ZipFile(file_path, 'r') as zip_file:
                    if password:
                        zip_file.setpassword(password.encode('utf-8'))
                    file_list = zip_file.namelist()
            
            elif format_type == 'rar':
                with rarfile.RarFile(file_path, 'r') as rar_file:
                    if password:
                        rar_file.setpassword(password)
                    file_list = rar_file.namelist()
            
            elif format_type == '7z':
                with py7zr.SevenZipFile(file_path, 'r', password=password) as sz_file:
                    file_list = sz_file.getnames()
            
            elif format_type in ['tar', 'tar.gz', 'tar.bz2']:
                mode = 'r'
                if format_type == 'tar.gz':
                    mode = 'r:gz'
                elif format_type == 'tar.bz2':
                    mode = 'r:bz2'
                
                with tarfile.open(file_path, mode) as tar_file:
                    file_list = tar_file.getnames()
            
            elif format_type == 'gz':
                # GZ文件通常只包含一个文件
                file_name = Path(file_path).stem
                file_list = [file_name]
            
            logger.info(f"Found {len(file_list)} files in archive: {Path(file_path).name}")
            return file_list
            
        except Exception as e:
            logger.error(f"Error getting file list from {file_path}: {e}")
            return []
    
    def extract_archive(self, file_path: str, extract_to: str = None, 
                       password: str = None) -> Optional[str]:
        """
        解压压缩文件
        
        Args:
            file_path (str): 压缩文件路径
            extract_to (str): 解压目标目录（可选）
            password (str): 密码（可选）
            
        Returns:
            Optional[str]: 解压目录路径，失败时返回None
        """
        try:
            format_type = self.detect_format(file_path)
            if not format_type:
                logger.error(f"Unsupported archive format: {file_path}")
                return None
            
            # 创建解压目录
            if extract_to is None:
                extract_to = tempfile.mkdtemp(prefix="archive_extract_")
                self.temp_extract_dir = extract_to
            else:
                os.makedirs(extract_to, exist_ok=True)
            
            logger.info(f"Extracting {Path(file_path).name} to {extract_to}")
            
            if format_type == 'zip':
                success = self._extract_zip(file_path, extract_to, password)
            elif format_type == 'rar':
                success = self._extract_rar(file_path, extract_to, password)
            elif format_type == '7z':
                success = self._extract_7z(file_path, extract_to, password)
            elif format_type in ['tar', 'tar.gz', 'tar.bz2']:
                success = self._extract_tar(file_path, extract_to, format_type)
            elif format_type == 'gz':
                success = self._extract_gz(file_path, extract_to)
            else:
                logger.error(f"Extraction not implemented for format: {format_type}")
                return None
            
            if success:
                logger.info(f"Successfully extracted archive to: {extract_to}")
                return extract_to
            else:
                logger.error(f"Failed to extract archive: {file_path}")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting archive {file_path}: {e}")
            return None
    
    def _extract_zip(self, file_path: str, extract_to: str, password: str = None) -> bool:
        """解压ZIP文件"""
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_file:
                if password:
                    zip_file.setpassword(password.encode('utf-8'))
                
                # 安全检查：防止目录遍历攻击
                for member in zip_file.namelist():
                    if os.path.isabs(member) or ".." in member:
                        logger.warning(f"Skipping potentially dangerous file: {member}")
                        continue
                
                zip_file.extractall(extract_to)
                return True
                
        except zipfile.BadZipFile:
            logger.error("Bad ZIP file")
            return False
        except RuntimeError as e:
            if "Bad password" in str(e):
                logger.error("Invalid password for ZIP file")
            else:
                logger.error(f"ZIP extraction error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error extracting ZIP: {e}")
            return False
    
    def _extract_rar(self, file_path: str, extract_to: str, password: str = None) -> bool:
        """解压RAR文件"""
        try:
            with rarfile.RarFile(file_path, 'r') as rar_file:
                if password:
                    rar_file.setpassword(password)
                
                # 安全检查
                for member in rar_file.namelist():
                    if os.path.isabs(member) or ".." in member:
                        logger.warning(f"Skipping potentially dangerous file: {member}")
                        continue
                
                rar_file.extractall(extract_to)
                return True
                
        except rarfile.BadRarFile:
            logger.error("Bad RAR file")
            return False
        except rarfile.PasswordRequired:
            logger.error("Password required for RAR file")
            return False
        except rarfile.WrongPassword:
            logger.error("Wrong password for RAR file")
            return False
        except Exception as e:
            logger.error(f"Unexpected error extracting RAR: {e}")
            return False
    
    def _extract_7z(self, file_path: str, extract_to: str, password: str = None) -> bool:
        """解压7Z文件"""
        try:
            with py7zr.SevenZipFile(file_path, 'r', password=password) as sz_file:
                # 安全检查
                for member in sz_file.getnames():
                    if os.path.isabs(member) or ".." in member:
                        logger.warning(f"Skipping potentially dangerous file: {member}")
                        continue
                
                sz_file.extractall(extract_to)
                return True
                
        except py7zr.Bad7zFile:
            logger.error("Bad 7Z file")
            return False
        except py7zr.PasswordRequired:
            logger.error("Password required for 7Z file")
            return False
        except py7zr.WrongPassword:
            logger.error("Wrong password for 7Z file")
            return False
        except Exception as e:
            logger.error(f"Unexpected error extracting 7Z: {e}")
            return False
    
    def _extract_tar(self, file_path: str, extract_to: str, format_type: str) -> bool:
        """解压TAR文件"""
        try:
            mode = 'r'
            if format_type == 'tar.gz':
                mode = 'r:gz'
            elif format_type == 'tar.bz2':
                mode = 'r:bz2'
            
            with tarfile.open(file_path, mode) as tar_file:
                # 安全检查
                for member in tar_file.getmembers():
                    if member.name.startswith('/') or ".." in member.name:
                        logger.warning(f"Skipping potentially dangerous file: {member.name}")
                        continue
                
                tar_file.extractall(extract_to)
                return True
                
        except tarfile.TarError:
            logger.error("Bad TAR file")
            return False
        except Exception as e:
            logger.error(f"Unexpected error extracting TAR: {e}")
            return False
    
    def _extract_gz(self, file_path: str, extract_to: str) -> bool:
        """解压GZ文件"""
        try:
            output_file = Path(extract_to) / Path(file_path).stem
            
            with gzip.open(file_path, 'rb') as gz_file:
                with open(output_file, 'wb') as out_file:
                    shutil.copyfileobj(gz_file, out_file)
            
            return True
            
        except Exception as e:
            logger.error(f"Unexpected error extracting GZ: {e}")
            return False
    
    def validate_archive(self, file_path: str, password: str = None, 
                        validate_data_format: bool = True) -> Dict:
        """
        验证压缩文件
        
        Args:
            file_path (str): 压缩文件路径
            password (str): 密码（可选）
            validate_data_format (bool): 是否验证数据格式
            
        Returns:
            Dict: 验证结果
            {
                'is_valid': bool,
                'format': str,
                'file_count': int,
                'total_size': int,
                'file_list': list,
                'error': str or None,
                'data_validation': dict or None
            }
        """
        result = {
            'is_valid': False,
            'format': None,
            'file_count': 0,
            'total_size': 0,
            'file_list': [],
            'error': None,
            'data_validation': None
        }
        
        try:
            # 检测格式
            format_type = self.detect_format(file_path)
            if not format_type:
                result['error'] = "Unsupported archive format"
                return result
            
            result['format'] = format_type
            
            # 获取文件列表
            file_list = self.get_file_list(file_path, password)
            if not file_list:
                result['error'] = "Unable to read archive contents"
                return result
            
            result['file_list'] = file_list
            result['file_count'] = len(file_list)
            
            # 尝试解压以验证完整性和数据格式
            temp_dir = tempfile.mkdtemp(prefix="validate_")
            try:
                extract_result = self.extract_archive(file_path, temp_dir, password)
                if extract_result:
                    # 计算总大小
                    total_size = 0
                    for root, dirs, files in os.walk(extract_result):
                        for file in files:
                            file_path_full = os.path.join(root, file)
                            if os.path.exists(file_path_full):
                                total_size += os.path.getsize(file_path_full)
                    result['total_size'] = total_size
                    
                    # 数据格式验证
                    if validate_data_format:
                        logger.info("开始验证数据格式...")
                        try:
                            validation_result = self.validation_manager.validate(
                                extract_result, 
                                ValidationLevel.STANDARD,
                                format_hint='metacam'
                            )
                            
                            result['data_validation'] = {
                                'is_valid': validation_result.is_valid,
                                'score': validation_result.score,
                                'errors': validation_result.errors,
                                'warnings': validation_result.warnings,
                                'missing_files': validation_result.missing_files,
                                'missing_directories': validation_result.missing_directories,
                                'summary': validation_result.summary,
                                'validator_type': validation_result.validator_type
                            }
                            
                            # 整体验证结果：压缩文件完整性 AND 数据格式验证
                            result['is_valid'] = validation_result.is_valid
                            
                            if not validation_result.is_valid:
                                result['error'] = f"数据格式验证失败: {validation_result.summary}"
                                logger.warning(f"数据格式验证失败: {len(validation_result.errors)}个错误")
                            else:
                                logger.info(f"数据格式验证通过: {validation_result.summary}")
                                
                        except Exception as e:
                            logger.error(f"数据格式验证异常: {e}")
                            result['data_validation'] = {
                                'is_valid': False,
                                'score': 0.0,
                                'errors': [f"Validation exception: {e}"],
                                'warnings': [],
                                'missing_files': [],
                                'missing_directories': [],
                                'summary': f"Validation failed: {e}",
                                'validator_type': 'unknown'
                            }
                            result['is_valid'] = False
                            result['error'] = f"数据格式验证异常: {e}"
                    else:
                        # 仅验证压缩文件完整性
                        result['is_valid'] = True
                        logger.info("跳过数据格式验证")
                else:
                    result['error'] = "Archive extraction failed"
                    
            finally:
                # 清理临时目录
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
            
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Error validating archive: {e}")
        
        return result
    
    def try_passwords(self, file_path: str, passwords: List[str] = None) -> Optional[str]:
        """
        尝试多个密码解压文件
        
        Args:
            file_path (str): 压缩文件路径
            passwords (List[str]): 密码列表（可选，默认使用配置中的密码）
            
        Returns:
            Optional[str]: 成功的密码，失败时返回None
        """
        if passwords is None:
            passwords = Config.DEFAULT_PASSWORDS
        
        logger.info(f"Trying {len(passwords)} passwords for {Path(file_path).name}")
        
        for password in passwords:
            try:
                logger.debug(f"Trying password: {'*' * len(password)}")
                
                # 尝试获取文件列表来测试密码
                file_list = self.get_file_list(file_path, password)
                if file_list:
                    logger.info(f"Password found for {Path(file_path).name}")
                    return password
                    
            except Exception as e:
                logger.debug(f"Password failed: {e}")
                continue
        
        logger.warning(f"No valid password found for {Path(file_path).name}")
        return None
    
    def cleanup_temp_dirs(self):
        """清理临时目录"""
        try:
            if self.temp_extract_dir and os.path.exists(self.temp_extract_dir):
                shutil.rmtree(self.temp_extract_dir, ignore_errors=True)
                logger.info(f"Cleaned up temporary directory: {self.temp_extract_dir}")
                self.temp_extract_dir = None
                
        except Exception as e:
            logger.error(f"Error cleaning up temp directories: {e}")
    
    def get_archive_info(self, file_path: str, password: str = None) -> Dict:
        """
        获取压缩文件详细信息
        
        Args:
            file_path (str): 压缩文件路径
            password (str): 密码（可选）
            
        Returns:
            Dict: 压缩文件信息
        """
        info = {
            'file_path': file_path,
            'file_name': Path(file_path).name,
            'file_size': 0,
            'format': None,
            'is_password_protected': False,
            'validation_result': None
        }
        
        try:
            # 获取文件大小
            if os.path.exists(file_path):
                info['file_size'] = os.path.getsize(file_path)
            
            # 检测格式
            info['format'] = self.detect_format(file_path)
            
            # 检查是否需要密码
            try:
                self.get_file_list(file_path)
            except Exception as e:
                if any(keyword in str(e).lower() for keyword in ['password', 'encrypted']):
                    info['is_password_protected'] = True
            
            # 验证压缩文件（包含数据格式验证）
            info['validation_result'] = self.validate_archive(file_path, password, validate_data_format=True)
            
        except Exception as e:
            logger.error(f"Error getting archive info: {e}")
            info['error'] = str(e)
        
        return info