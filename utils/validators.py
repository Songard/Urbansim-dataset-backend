import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse
from config import Config
from utils.logger import get_logger

logger = get_logger(__name__)

def validate_environment() -> bool:
    """
    验证运行环境和依赖
    
    Returns:
        bool: 环境验证是否通过
    """
    logger.info("开始验证运行环境...")
    
    try:
        # 检查Python版本
        if not _check_python_version():
            return False
        
        # 检查必要的依赖包
        if not _check_required_packages():
            return False
        
        # 检查文件权限
        if not _check_file_permissions():
            return False
        
        # 检查网络连接
        if not _check_network_connectivity():
            return False
        
        # 检查Google服务账号文件
        if not _check_service_account_file():
            return False
        
        logger.success("环境验证通过")
        return True
        
    except Exception as e:
        logger.error(f"环境验证过程中出错: {e}")
        return False

def _check_python_version() -> bool:
    """检查Python版本"""
    try:
        version = sys.version_info
        required_version = (3, 7)
        
        if version < required_version:
            logger.error(f"Python版本过低: 当前 {version.major}.{version.minor}, 需要 >= {required_version[0]}.{required_version[1]}")
            return False
        
        logger.info(f"Python版本检查通过: {version.major}.{version.minor}.{version.micro}")
        return True
        
    except Exception as e:
        logger.error(f"Python版本检查失败: {e}")
        return False

def _check_required_packages() -> bool:
    """检查必要的Python包"""
    # 映射pip包名到Python模块名
    required_packages = {
        'google-api-python-client': 'googleapiclient',
        'google-auth': 'google.auth',
        'google-auth-oauthlib': 'google_auth_oauthlib',
        'google-auth-httplib2': 'google_auth_httplib2',
        'python-dotenv': 'dotenv',
        'requests': 'requests',
        'colorama': 'colorama'
    }
    
    optional_packages = {
        'rarfile': 'rarfile',
        'py7zr': 'py7zr',
        'patool': 'patoollib'
    }
    
    missing_required = []
    missing_optional = []
    
    for pip_name, module_name in required_packages.items():
        try:
            __import__(module_name)
        except ImportError:
            missing_required.append(pip_name)
    
    for pip_name, module_name in optional_packages.items():
        try:
            __import__(module_name)
        except ImportError:
            missing_optional.append(pip_name)
    
    if missing_required:
        logger.error(f"缺少必要依赖包: {', '.join(missing_required)}")
        logger.error("请运行: pip install -r requirements.txt")
        return False
    
    if missing_optional:
        logger.warning(f"缺少可选依赖包: {', '.join(missing_optional)}")
        logger.warning("部分压缩格式可能不被支持")
    
    logger.info("依赖包检查通过")
    return True

def _check_file_permissions() -> bool:
    """检查文件权限"""
    try:
        # 检查日志目录权限
        log_dir = os.path.dirname(Config.LOG_FILE)
        if not _check_directory_permissions(log_dir, create=True):
            logger.error(f"日志目录权限不足: {log_dir}")
            return False
        
        # 检查下载目录权限
        if not _check_directory_permissions(Config.DOWNLOAD_PATH, create=True):
            logger.error(f"下载目录权限不足: {Config.DOWNLOAD_PATH}")
            return False
        
        # 检查处理目录权限
        if not _check_directory_permissions(Config.PROCESSED_PATH, create=True):
            logger.error(f"处理目录权限不足: {Config.PROCESSED_PATH}")
            return False
        
        # 检查数据目录权限
        data_dir = os.path.dirname(Config.PROCESSED_FILES_JSON)
        if not _check_directory_permissions(data_dir, create=True):
            logger.error(f"数据目录权限不足: {data_dir}")
            return False
        
        logger.info("文件权限检查通过")
        return True
        
    except Exception as e:
        logger.error(f"文件权限检查失败: {e}")
        return False

def _check_directory_permissions(directory: str, create: bool = False) -> bool:
    """检查目录权限"""
    try:
        if create:
            os.makedirs(directory, exist_ok=True)
        
        if not os.path.exists(directory):
            return False
        
        # 检查读写权限
        if not os.access(directory, os.R_OK | os.W_OK):
            return False
        
        # 测试写入
        test_file = os.path.join(directory, '.permission_test')
        try:
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            return True
        except:
            return False
            
    except Exception:
        return False

def _check_network_connectivity() -> bool:
    """检查网络连接"""
    try:
        import socket
        
        # 检查Google服务连接
        test_hosts = [
            ('www.googleapis.com', 443),
            ('sheets.googleapis.com', 443),
            ('drive.googleapis.com', 443)
        ]
        
        for host, port in test_hosts:
            try:
                socket.create_connection((host, port), timeout=10)
                logger.debug(f"网络连接正常: {host}:{port}")
            except (socket.timeout, socket.error) as e:
                logger.warning(f"无法连接到 {host}:{port} - {e}")
                return False
        
        logger.info("网络连接检查通过")
        return True
        
    except Exception as e:
        logger.error(f"网络连接检查失败: {e}")
        return False

def _check_service_account_file() -> bool:
    """检查Google服务账号文件"""
    try:
        if not os.path.exists(Config.SERVICE_ACCOUNT_FILE):
            logger.error(f"服务账号文件不存在: {Config.SERVICE_ACCOUNT_FILE}")
            return False
        
        # 检查文件格式
        import json
        with open(Config.SERVICE_ACCOUNT_FILE, 'r') as f:
            service_account_info = json.load(f)
        
        required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
        for field in required_fields:
            if field not in service_account_info:
                logger.error(f"服务账号文件缺少必要字段: {field}")
                return False
        
        if service_account_info.get('type') != 'service_account':
            logger.error("服务账号文件类型错误")
            return False
        
        logger.info("服务账号文件检查通过")
        return True
        
    except json.JSONDecodeError:
        logger.error("服务账号文件JSON格式错误")
        return False
    except Exception as e:
        logger.error(f"服务账号文件检查失败: {e}")
        return False

def validate_file_name(file_name: str) -> bool:
    """
    验证文件名是否安全
    
    Args:
        file_name (str): 文件名
        
    Returns:
        bool: 文件名是否安全
    """
    try:
        if not file_name or len(file_name.strip()) == 0:
            return False
        
        # 检查危险字符
        dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\0']
        for char in dangerous_chars:
            if char in file_name:
                return False
        
        # 检查路径遍历
        if '..' in file_name or file_name.startswith('/') or file_name.startswith('\\'):
            return False
        
        # 检查Windows保留名称
        reserved_names = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 
                         'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4', 
                         'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9']
        
        name_without_ext = Path(file_name).stem.upper()
        if name_without_ext in reserved_names:
            return False
        
        # 检查长度
        if len(file_name) > 255:
            return False
        
        return True
        
    except Exception:
        return False

def validate_file_size(file_size: int) -> bool:
    """
    验证文件大小是否在允许范围内
    
    Args:
        file_size (int): 文件大小（字节）
        
    Returns:
        bool: 文件大小是否合法
    """
    try:
        if file_size < 0:
            return False
        
        max_size_bytes = Config.MAX_FILE_SIZE_MB * 1024 * 1024
        return file_size <= max_size_bytes
        
    except Exception:
        return False

def validate_file_extension(file_name: str) -> bool:
    """
    验证文件扩展名是否被允许
    
    Args:
        file_name (str): 文件名
        
    Returns:
        bool: 扩展名是否被允许
    """
    try:
        if not Config.ALLOWED_EXTENSIONS:
            return True  # 如果没有限制，则允许所有格式
        
        file_ext = Path(file_name).suffix.lower()
        return file_ext in Config.ALLOWED_EXTENSIONS
        
    except Exception:
        return False

def validate_google_drive_id(drive_id: str) -> bool:
    """
    验证Google Drive ID格式
    
    Args:
        drive_id (str): Google Drive ID
        
    Returns:
        bool: ID格式是否正确
    """
    try:
        if not drive_id or len(drive_id.strip()) == 0:
            return False
        
        # Google Drive ID通常是33个字符的字母数字字符串
        # 包含字母、数字、短划线和下划线
        if not re.match(r'^[a-zA-Z0-9_-]{25,35}$', drive_id):
            return False
        
        return True
        
    except Exception:
        return False

def validate_spreadsheet_id(spreadsheet_id: str) -> bool:
    """
    验证Google Sheets ID格式
    
    Args:
        spreadsheet_id (str): Google Sheets ID
        
    Returns:
        bool: ID格式是否正确
    """
    try:
        if not spreadsheet_id or len(spreadsheet_id.strip()) == 0:
            return False
        
        # Google Sheets ID格式类似Drive ID
        if not re.match(r'^[a-zA-Z0-9_-]{40,50}$', spreadsheet_id):
            return False
        
        return True
        
    except Exception:
        return False

def sanitize_file_name(file_name: str) -> str:
    """
    清理文件名，移除危险字符
    
    Args:
        file_name (str): 原始文件名
        
    Returns:
        str: 清理后的文件名
    """
    try:
        if not file_name:
            return "untitled"
        
        # 移除危险字符
        dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\0', '/', '\\']
        sanitized = file_name
        
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '_')
        
        # 移除连续的点
        sanitized = re.sub(r'\.{2,}', '.', sanitized)
        
        # 移除开头和结尾的空格和点
        sanitized = sanitized.strip(' .')
        
        # 确保不为空
        if not sanitized:
            sanitized = "untitled"
        
        # 限制长度
        if len(sanitized) > 200:
            name_part = Path(sanitized).stem[:190]
            ext_part = Path(sanitized).suffix
            sanitized = name_part + ext_part
        
        return sanitized
        
    except Exception:
        return "untitled"

def validate_config() -> List[str]:
    """
    验证配置参数
    
    Returns:
        List[str]: 验证错误列表
    """
    errors = []
    
    try:
        # 验证Drive文件夹ID
        if not validate_google_drive_id(Config.DRIVE_FOLDER_ID):
            errors.append(f"无效的Drive文件夹ID: {Config.DRIVE_FOLDER_ID}")
        
        # 验证Sheets ID
        if not validate_spreadsheet_id(Config.SPREADSHEET_ID):
            errors.append(f"无效的Spreadsheet ID: {Config.SPREADSHEET_ID}")
        
        # 验证文件大小限制
        if Config.MAX_FILE_SIZE_MB <= 0 or Config.MAX_FILE_SIZE_MB > 5000:
            errors.append(f"文件大小限制无效: {Config.MAX_FILE_SIZE_MB}MB")
        
        # 验证检查间隔
        if Config.CHECK_INTERVAL < 10 or Config.CHECK_INTERVAL > 3600:
            errors.append(f"检查间隔无效: {Config.CHECK_INTERVAL}秒")
        
        # 验证并发下载数
        if Config.MAX_CONCURRENT_DOWNLOADS < 1 or Config.MAX_CONCURRENT_DOWNLOADS > 10:
            errors.append(f"并发下载数无效: {Config.MAX_CONCURRENT_DOWNLOADS}")
        
        # 验证重试次数
        if Config.MAX_RETRY_ATTEMPTS < 1 or Config.MAX_RETRY_ATTEMPTS > 10:
            errors.append(f"重试次数无效: {Config.MAX_RETRY_ATTEMPTS}")
        
        # 验证日志级别
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if Config.LOG_LEVEL.upper() not in valid_log_levels:
            errors.append(f"日志级别无效: {Config.LOG_LEVEL}")
        
    except Exception as e:
        errors.append(f"配置验证过程中出错: {e}")
    
    return errors

def check_disk_space(path: str, required_mb: int = 1000) -> bool:
    """
    检查磁盘空间是否足够
    
    Args:
        path (str): 检查路径
        required_mb (int): 所需空间（MB）
        
    Returns:
        bool: 空间是否足够
    """
    try:
        import shutil
        free_bytes = shutil.disk_usage(path).free
        free_mb = free_bytes / (1024 * 1024)
        
        return free_mb >= required_mb
        
    except Exception as e:
        logger.error(f"检查磁盘空间失败: {e}")
        return False

def validate_json_structure(json_data: Dict, required_fields: List[str]) -> Tuple[bool, List[str]]:
    """
    验证JSON数据结构
    
    Args:
        json_data (Dict): JSON数据
        required_fields (List[str]): 必需字段列表
        
    Returns:
        Tuple[bool, List[str]]: (验证结果, 错误消息列表)
    """
    errors = []
    
    try:
        if not isinstance(json_data, dict):
            return False, ["数据不是有效的字典格式"]
        
        for field in required_fields:
            if field not in json_data:
                errors.append(f"缺少必需字段: {field}")
        
        return len(errors) == 0, errors
        
    except Exception as e:
        return False, [f"JSON结构验证失败: {e}"]

def is_safe_path(path: str, base_path: str = None) -> bool:
    """
    检查路径是否安全（防止路径遍历攻击）
    
    Args:
        path (str): 要检查的路径
        base_path (str): 基础路径
        
    Returns:
        bool: 路径是否安全
    """
    try:
        if base_path is None:
            base_path = os.getcwd()
        
        # 规范化路径
        abs_base = os.path.abspath(base_path)
        abs_path = os.path.abspath(os.path.join(abs_base, path))
        
        # 检查是否在基础路径内
        return abs_path.startswith(abs_base)
        
    except Exception:
        return False