import os
import sys
import re
import struct
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

def validate_scene_naming(file_name: str) -> Dict[str, Any]:
    """
    验证场景文件命名格式并确定场景类型
    
    Args:
        file_name (str): 文件名
        
    Returns:
        Dict[str, Any]: 验证结果
        {
            'is_valid_format': bool,  # 命名格式是否正确
            'scene_type': str,        # 'indoor', 'outdoor', 'unknown'
            'detected_prefix': str,   # 检测到的前缀
            'error_message': str      # 错误信息（如果有）
        }
    """
    result = {
        'is_valid_format': False,
        'scene_type': 'unknown',
        'detected_prefix': '',
        'error_message': ''
    }
    
    try:
        if not file_name or len(file_name.strip()) == 0:
            result['error_message'] = '文件名为空'
            return result
        
        # 获取文件名（不包含路径）
        base_name = Path(file_name).name
        
        # 转换为小写进行匹配
        base_name_lower = base_name.lower()
        
        # 检查Indoor格式
        if base_name_lower.startswith('indoor'):
            result['is_valid_format'] = True
            result['scene_type'] = 'indoor'
            result['detected_prefix'] = 'Indoor'
        elif base_name_lower.startswith('i') and len(base_name) > 1:
            # 检查是否是单独的I开头（不是其他单词的一部分）
            if base_name[1].isdigit() or base_name[1] in ['_', '-', '.', ' ']:
                result['is_valid_format'] = True
                result['scene_type'] = 'indoor'
                result['detected_prefix'] = 'I'
        
        # 检查Outdoor格式
        elif base_name_lower.startswith('outdoor'):
            result['is_valid_format'] = True
            result['scene_type'] = 'outdoor'
            result['detected_prefix'] = 'Outdoor'
        elif base_name_lower.startswith('o') and len(base_name) > 1:
            # 检查是否是单独的O开头（不是其他单词的一部分）
            if base_name[1].isdigit() or base_name[1] in ['_', '-', '.', ' ']:
                result['is_valid_format'] = True
                result['scene_type'] = 'outdoor'
                result['detected_prefix'] = 'O'
        
        # 如果没有匹配到任何格式，这是警告而不是错误
        if not result['is_valid_format']:
            result['error_message'] = f"场景类型未知: 建议以Indoor/I或Outdoor/O开头以便自动识别"
        
        logger.debug(f"场景命名验证: {file_name} -> {result['scene_type']} ({result['detected_prefix']})")
        return result
        
    except Exception as e:
        result['error_message'] = f"命名格式验证异常: {e}"
        logger.error(f"场景命名验证失败: {e}")
        return result

def validate_extracted_file_size(total_size_bytes: int) -> Dict[str, Any]:
    """
    验证解压后文件大小合理性
    
    Args:
        total_size_bytes (int): 解压后总文件大小（字节）
        
    Returns:
        Dict[str, Any]: 验证结果
        {
            'is_valid_size': bool,     # 大小是否合理
            'size_status': str,        # 'optimal', 'warning_small', 'warning_large', 'error_too_small', 'error_too_large'
            'size_mb': float,          # 大小（MB）
            'size_gb': float,          # 大小（GB）
            'error_message': str       # 错误信息（如果有）
        }
    """
    result = {
        'is_valid_size': False,
        'size_status': 'unknown',
        'size_mb': 0.0,
        'size_gb': 0.0,
        'error_message': ''
    }
    
    try:
        if total_size_bytes < 0:
            result['error_message'] = '文件大小不能为负数'
            return result
        
        # 转换为MB和GB
        size_mb = total_size_bytes / (1024 * 1024)
        size_gb = total_size_bytes / (1024 * 1024 * 1024)
        
        result['size_mb'] = round(size_mb, 2)
        result['size_gb'] = round(size_gb, 3)
        
        # 定义合理范围：1GB ≤ 场景大小 ≤ 3GB
        MIN_SIZE_GB = 1.0
        MAX_SIZE_GB = 3.0
        
        # 警告阈值
        WARNING_MIN_GB = 0.8  # 低于0.8GB警告
        WARNING_MAX_GB = 3.5  # 高于3.5GB警告
        
        if size_gb < WARNING_MIN_GB:
            if size_gb < MIN_SIZE_GB * 0.5:  # 小于0.5GB视为异常
                result['size_status'] = 'error_too_small'
                result['error_message'] = f'文件过小: {size_gb:.2f}GB (期望 ≥ {MIN_SIZE_GB}GB)'
            else:
                result['size_status'] = 'warning_small'
                result['error_message'] = f'文件可能偏小: {size_gb:.2f}GB (建议 ≥ {MIN_SIZE_GB}GB)'
                result['is_valid_size'] = True
        elif size_gb > WARNING_MAX_GB:
            if size_gb > MAX_SIZE_GB * 2:  # 大于6GB视为异常
                result['size_status'] = 'error_too_large'
                result['error_message'] = f'文件过大: {size_gb:.2f}GB (期望 ≤ {MAX_SIZE_GB}GB)'
            else:
                result['size_status'] = 'warning_large'
                result['error_message'] = f'文件可能偏大: {size_gb:.2f}GB (建议 ≤ {MAX_SIZE_GB}GB)'
                result['is_valid_size'] = True
        elif MIN_SIZE_GB <= size_gb <= MAX_SIZE_GB:
            result['size_status'] = 'optimal'
            result['is_valid_size'] = True
        else:
            result['size_status'] = 'warning_small' if size_gb < MIN_SIZE_GB else 'warning_large'
            result['is_valid_size'] = True
            if size_gb < MIN_SIZE_GB:
                result['error_message'] = f'文件偏小: {size_gb:.2f}GB (建议 ≥ {MIN_SIZE_GB}GB)'
            else:
                result['error_message'] = f'文件偏大: {size_gb:.2f}GB (建议 ≤ {MAX_SIZE_GB}GB)'
        
        logger.debug(f"文件大小验证: {size_gb:.2f}GB -> {result['size_status']}")
        return result
        
    except Exception as e:
        result['error_message'] = f"文件大小验证异常: {e}"
        logger.error(f"文件大小验证失败: {e}")
        return result

def read_pcd_header(pcd_file_path: str) -> Dict[str, Any]:
    """
    读取PCD文件头部信息
    
    Args:
        pcd_file_path (str): PCD文件路径
        
    Returns:
        Dict[str, Any]: PCD文件信息
        {
            'version': str,     # PCD版本
            'width': int,       # 点数
            'height': int,      # 高度（通常为1）
            'points': int,      # 总点数
            'fields': List[str], # 字段列表
            'viewpoint': str,   # 视点信息
            'data_type': str    # 数据类型（ascii/binary）
        }
    """
    result = {
        'version': '',
        'width': 0,
        'height': 1,
        'points': 0,
        'fields': [],
        'viewpoint': '',
        'data_type': 'ascii',
        'error': None
    }
    
    try:
        with open(pcd_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                    
                if line.startswith('VERSION'):
                    result['version'] = line.split()[1] if len(line.split()) > 1 else '0.7'
                elif line.startswith('FIELDS'):
                    result['fields'] = line.split()[1:]
                elif line.startswith('SIZE'):
                    # 字段大小信息
                    pass
                elif line.startswith('TYPE'):
                    # 字段类型信息
                    pass
                elif line.startswith('COUNT'):
                    # 字段计数信息
                    pass
                elif line.startswith('WIDTH'):
                    result['width'] = int(line.split()[1])
                elif line.startswith('HEIGHT'):
                    result['height'] = int(line.split()[1])
                elif line.startswith('VIEWPOINT'):
                    result['viewpoint'] = ' '.join(line.split()[1:])
                elif line.startswith('POINTS'):
                    result['points'] = int(line.split()[1])
                elif line.startswith('DATA'):
                    result['data_type'] = line.split()[1]
                    break  # DATA标记后面就是实际数据了
                    
        return result
        
    except Exception as e:
        result['error'] = f"读取PCD文件头部失败: {e}"
        logger.error(f"读取PCD文件头部失败 {pcd_file_path}: {e}")
        return result

def parse_pcd_points(pcd_file_path: str, max_points: int = 100000) -> Dict[str, Any]:
    """
    解析PCD文件的点云数据并计算边界框
    
    Args:
        pcd_file_path (str): PCD文件路径
        max_points (int): 最大解析点数（避免内存问题）
        
    Returns:
        Dict[str, Any]: 点云边界框信息
        {
            'min_x': float, 'max_x': float,
            'min_y': float, 'max_y': float, 
            'min_z': float, 'max_z': float,
            'width': float,  # X方向尺度
            'height': float, # Y方向尺度
            'depth': float,  # Z方向尺度
            'points_parsed': int, # 实际解析的点数
            'error': str
        }
    """
    result = {
        'min_x': float('inf'), 'max_x': float('-inf'),
        'min_y': float('inf'), 'max_y': float('-inf'),
        'min_z': float('inf'), 'max_z': float('-inf'),
        'width': 0.0, 'height': 0.0, 'depth': 0.0,
        'points_parsed': 0,
        'error': None
    }
    
    try:
        # 先读取头部信息
        header = read_pcd_header(pcd_file_path)
        if header.get('error'):
            result['error'] = header['error']
            return result
        
        # 检查是否有XYZ字段
        fields = header.get('fields', [])
        if 'x' not in [f.lower() for f in fields]:
            result['error'] = "PCD文件缺少X坐标字段"
            return result
        
        # 找到XYZ字段的索引
        field_indices = {}
        for i, field in enumerate(fields):
            if field.lower() in ['x', 'y', 'z']:
                field_indices[field.lower()] = i
        
        if len(field_indices) < 2:  # 至少需要X,Y字段
            result['error'] = "PCD文件缺少足够的坐标字段"
            return result
        
        data_type = header.get('data_type', 'ascii').lower()
        total_points = header.get('points', 0)
        points_to_parse = min(max_points, total_points)
        
        with open(pcd_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            # 跳过头部，找到DATA行
            data_started = False
            points_parsed = 0
            
            for line in f:
                line = line.strip()
                if not data_started:
                    if line.startswith('DATA'):
                        data_started = True
                    continue
                
                if points_parsed >= points_to_parse:
                    break
                
                # 解析点数据
                try:
                    if data_type == 'ascii':
                        parts = line.split()
                        if len(parts) >= len(fields):
                            x = float(parts[field_indices.get('x', 0)])
                            y = float(parts[field_indices.get('y', 1)])
                            z = float(parts[field_indices.get('z', 2)]) if 'z' in field_indices else 0.0
                            
                            # 更新边界框
                            result['min_x'] = min(result['min_x'], x)
                            result['max_x'] = max(result['max_x'], x)
                            result['min_y'] = min(result['min_y'], y)
                            result['max_y'] = max(result['max_y'], y)
                            result['min_z'] = min(result['min_z'], z)
                            result['max_z'] = max(result['max_z'], z)
                            
                            points_parsed += 1
                    else:
                        # 处理二进制格式
                        logger.info(f"检测到二进制PCD格式，切换到二进制解析: {pcd_file_path}")
                        return _parse_binary_pcd_points(pcd_file_path, header, max_points)
                        
                except (ValueError, IndexError) as e:
                    # 跳过无法解析的行
                    continue
            
            result['points_parsed'] = points_parsed
            
            # 计算尺度
            if result['min_x'] != float('inf'):  # 有有效点
                result['width'] = result['max_x'] - result['min_x']
                result['height'] = result['max_y'] - result['min_y']
                result['depth'] = result['max_z'] - result['min_z']
            else:
                result['error'] = "未找到有效的点云数据"
                
        return result
        
    except Exception as e:
        result['error'] = f"解析PCD文件失败: {e}"
        logger.error(f"解析PCD文件失败 {pcd_file_path}: {e}")
        return result

def _parse_binary_pcd_points(pcd_file_path: str, header: Dict[str, Any], max_points: int = 100000) -> Dict[str, Any]:
    """
    解析二进制PCD文件的点云数据
    
    Args:
        pcd_file_path (str): PCD文件路径
        header (Dict[str, Any]): PCD文件头部信息
        max_points (int): 最大解析点数
        
    Returns:
        Dict[str, Any]: 点云边界框信息
    """
    result = {
        'min_x': float('inf'), 'max_x': float('-inf'),
        'min_y': float('inf'), 'max_y': float('-inf'),
        'min_z': float('inf'), 'max_z': float('-inf'),
        'width': 0.0, 'height': 0.0, 'depth': 0.0,
        'points_parsed': 0,
        'error': None
    }
    
    try:
        fields = header.get('fields', [])
        data_type = header.get('data_type', 'binary').lower()
        total_points = header.get('points', 0)
        points_to_parse = min(max_points, total_points)
        
        # 检查是否有XYZ字段
        if 'x' not in [f.lower() for f in fields]:
            result['error'] = "PCD文件缺少X坐标字段"
            return result
        
        # 找到XYZ字段的索引
        field_indices = {}
        for i, field in enumerate(fields):
            if field.lower() in ['x', 'y', 'z']:
                field_indices[field.lower()] = i
        
        if len(field_indices) < 2:
            result['error'] = "PCD文件缺少足够的坐标字段"
            return result
        
        # 计算每个点的字节大小（假设每个字段4字节float）
        field_count = len(fields)
        point_size = field_count * 4  # 4 bytes per float
        
        with open(pcd_file_path, 'rb') as f:
            # 跳过头部，找到DATA行的位置
            content = f.read()
            data_marker = b'DATA binary\n'
            if data_marker not in content:
                data_marker = b'DATA binary_compressed\n'
                if data_marker not in content:
                    result['error'] = "未找到二进制数据标记"
                    return result
                else:
                    result['error'] = "暂不支持压缩的二进制PCD格式"
                    return result
            
            data_start_pos = content.find(data_marker) + len(data_marker)
            f.seek(data_start_pos)
            
            points_parsed = 0
            x_idx = field_indices.get('x', 0)
            y_idx = field_indices.get('y', 1) 
            z_idx = field_indices.get('z', 2)
            
            while points_parsed < points_to_parse:
                try:
                    # 读取一个点的数据
                    point_data = f.read(point_size)
                    if len(point_data) < point_size:
                        break  # 文件结束
                    
                    # 解析浮点数（小端序）
                    values = struct.unpack(f'<{field_count}f', point_data)
                    
                    x = values[x_idx] if x_idx < len(values) else 0.0
                    y = values[y_idx] if y_idx < len(values) else 0.0
                    z = values[z_idx] if z_idx < len(values) and 'z' in field_indices else 0.0
                    
                    # 更新边界框
                    result['min_x'] = min(result['min_x'], x)
                    result['max_x'] = max(result['max_x'], x)
                    result['min_y'] = min(result['min_y'], y)
                    result['max_y'] = max(result['max_y'], y)
                    result['min_z'] = min(result['min_z'], z)
                    result['max_z'] = max(result['max_z'], z)
                    
                    points_parsed += 1
                    
                except struct.error as e:
                    logger.warning(f"跳过无法解析的二进制点数据: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"二进制点解析错误: {e}")
                    break
            
            result['points_parsed'] = points_parsed
            
            # 计算尺度
            if result['min_x'] != float('inf'):
                result['width'] = result['max_x'] - result['min_x']
                result['height'] = result['max_y'] - result['min_y'] 
                result['depth'] = result['max_z'] - result['min_z']
            else:
                result['error'] = "未找到有效的二进制点云数据"
                
        logger.info(f"二进制PCD解析完成: {points_parsed} 点, 尺度 {result['width']:.1f}×{result['height']:.1f}×{result['depth']:.1f}")
        return result
        
    except Exception as e:
        result['error'] = f"二进制PCD解析失败: {e}"
        logger.error(f"二进制PCD解析失败 {pcd_file_path}: {e}")
        return result

def validate_pcd_scale(pcd_file_path: str, scene_type: str = 'outdoor') -> Dict[str, Any]:
    """
    验证PCD点云的尺度是否合理
    
    Args:
        pcd_file_path (str): PCD文件路径
        scene_type (str): 场景类型 ('indoor', 'outdoor', 'unknown')
        
    Returns:
        Dict[str, Any]: 验证结果
        {
            'is_valid_scale': bool,    # 尺度是否合理
            'scale_status': str,       # 'optimal', 'warning_small', 'warning_large', 'error_too_small', 'error_too_large'
            'width_m': float,          # X方向尺度（米）
            'height_m': float,         # Y方向尺度（米）
            'depth_m': float,          # Z方向尺度（米）
            'area_sqm': float,         # 覆盖面积（平方米）
            'points_parsed': int,      # 解析的点数
            'error_message': str       # 错误信息（如果有）
        }
    """
    result = {
        'is_valid_scale': False,
        'scale_status': 'unknown',
        'width_m': 0.0,
        'height_m': 0.0,
        'depth_m': 0.0,
        'area_sqm': 0.0,
        'points_parsed': 0,
        'error_message': ''
    }
    
    try:
        if not os.path.exists(pcd_file_path):
            result['error_message'] = f"PCD文件不存在: {pcd_file_path}"
            return result
        
        # 解析点云数据
        point_data = parse_pcd_points(pcd_file_path)
        if point_data.get('error'):
            result['error_message'] = point_data['error']
            return result
        
        if point_data['points_parsed'] == 0:
            result['error_message'] = "PCD文件中没有有效的点云数据"
            return result
        
        # 提取尺度信息（假设单位是米）
        width_m = abs(point_data['width'])
        height_m = abs(point_data['height'])
        depth_m = abs(point_data['depth'])
        area_sqm = width_m * height_m
        
        result['width_m'] = round(width_m, 2)
        result['height_m'] = round(height_m, 2)
        result['depth_m'] = round(depth_m, 2)
        result['area_sqm'] = round(area_sqm, 2)
        result['points_parsed'] = point_data['points_parsed']
        
        # 根据场景类型定义合理范围
        if scene_type.lower() == 'indoor':
            # 室内场景：阈值为室外场景的一半
            OPTIMAL_SIZE = 50.0   # 50米（室外100米的一半）
            WARNING_MIN = 25.0    # 25米以下警告（室外50米的一半）
            WARNING_MAX = 100.0   # 100米以上警告（室外200米的一半）
            ERROR_MIN = 5.0       # 5米以下异常（室外10米的一半）
            ERROR_MAX = 250.0     # 250米以上异常（室外500米的一半）
        else:
            # 室外场景（默认）或未知场景：保持原有标准
            OPTIMAL_SIZE = 100.0  # 100米
            WARNING_MIN = 50.0    # 50米以下警告
            WARNING_MAX = 200.0   # 200米以上警告
            ERROR_MIN = 10.0      # 10米以下异常
            ERROR_MAX = 500.0     # 500米以上异常
        
        # 使用长宽中的最大值作为主要判断标准
        max_dimension = max(width_m, height_m)
        min_dimension = min(width_m, height_m)
        
        if max_dimension < ERROR_MIN:
            result['scale_status'] = 'error_too_small'
            result['error_message'] = f'点云尺度过小: {max_dimension:.1f}m (期望约{OPTIMAL_SIZE}m)'
        elif max_dimension > ERROR_MAX:
            result['scale_status'] = 'error_too_large'
            result['error_message'] = f'点云尺度过大: {max_dimension:.1f}m (期望约{OPTIMAL_SIZE}m)'
        elif max_dimension < WARNING_MIN:
            result['scale_status'] = 'warning_small'
            result['error_message'] = f'点云尺度偏小: {max_dimension:.1f}m (建议约{OPTIMAL_SIZE}m)'
            result['is_valid_scale'] = True
        elif max_dimension > WARNING_MAX:
            result['scale_status'] = 'warning_large'
            result['error_message'] = f'点云尺度偏大: {max_dimension:.1f}m (建议约{OPTIMAL_SIZE}m)'
            result['is_valid_scale'] = True
        else:
            result['scale_status'] = 'optimal'
            result['is_valid_scale'] = True
        
        # 额外检查：如果一个维度合理但另一个维度异常，也给出警告
        if result['scale_status'] == 'optimal':
            if min_dimension < WARNING_MIN / 2:  # 如果较小维度过小
                result['scale_status'] = 'warning_narrow'
                result['error_message'] = f'点云过于狭长: {width_m:.1f}m × {height_m:.1f}m'
                result['is_valid_scale'] = True
        
        logger.debug(f"PCD尺度验证({scene_type}): {pcd_file_path} -> {width_m:.1f}m × {height_m:.1f}m ({result['scale_status']})")
        return result
        
    except Exception as e:
        result['error_message'] = f"PCD尺度验证异常: {e}"
        logger.error(f"PCD尺度验证失败: {e}")
        return result