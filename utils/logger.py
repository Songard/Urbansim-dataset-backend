import os
import sys
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime
import colorama
from colorama import Fore, Back, Style
from config import Config

# Initialize colorama for Windows compatibility
colorama.init()

class ColoredFormatter(logging.Formatter):
    """自定义彩色日志格式化器"""
    
    # 颜色映射
    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT,
        'SUCCESS': Fore.GREEN + Style.BRIGHT
    }
    
    def __init__(self, fmt=None):
        super().__init__()
        self.fmt = fmt or '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s'
        self.datefmt = '%Y-%m-%d %H:%M:%S'
    
    def format(self, record):
        # 创建副本避免修改原始记录
        log_color = self.COLORS.get(record.levelname, '')
        record_copy = logging.makeLogRecord(record.__dict__)
        
        # 为控制台添加颜色
        if hasattr(record_copy, 'console_output'):
            record_copy.levelname = f"{log_color}{record_copy.levelname}{Style.RESET_ALL}"
            record_copy.name = f"{Fore.BLUE}{record_copy.name}{Style.RESET_ALL}"
        
        formatter = logging.Formatter(self.fmt, self.datefmt)
        return formatter.format(record_copy)

class FileFormatter(logging.Formatter):
    """文件日志格式化器（无颜色）"""
    
    def __init__(self):
        super().__init__(
            fmt='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

class StructuredLogger:
    """结构化日志管理器"""
    
    def __init__(self):
        self.loggers = {}
        self.setup_logging()
    
    def setup_logging(self):
        """设置全局日志配置"""
        # 确保日志目录存在
        log_dir = os.path.dirname(Config.LOG_FILE)
        os.makedirs(log_dir, exist_ok=True)
        
        # 设置根日志级别
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO))
        
        # 清除已有的处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 创建文件处理器（支持轮转）
        try:
            # 使用基于时间的轮转，更稳定
            file_handler = TimedRotatingFileHandler(
                Config.LOG_FILE,
                when='midnight',
                interval=1,
                backupCount=Config.LOG_BACKUP_COUNT,
                encoding='utf-8',
                delay=True
            )
            file_handler.suffix = "%Y-%m-%d"
        except (PermissionError, OSError) as e:
            try:
                # 尝试大小轮转
                file_handler = RotatingFileHandler(
                    Config.LOG_FILE,
                    maxBytes=Config.LOG_MAX_SIZE,
                    backupCount=Config.LOG_BACKUP_COUNT,
                    encoding='utf-8',
                    delay=True
                )
            except (PermissionError, OSError) as e2:
                # 如果轮转文件处理器失败，则使用普通文件处理器
                print(f"Warning: Cannot create rotating log handler: {e}, {e2}")
                file_handler = logging.FileHandler(
                    Config.LOG_FILE,
                    encoding='utf-8'
                )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(FileFormatter())
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO))
        console_formatter = ColoredFormatter()
        console_handler.setFormatter(console_formatter)
        
        # 为控制台输出添加标记
        class ConsoleFilter(logging.Filter):
            def filter(self, record):
                record.console_output = True
                return True
        
        console_handler.addFilter(ConsoleFilter())
        
        # 添加处理器到根日志器
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        # 设置第三方库的日志级别
        self._configure_third_party_loggers()
    
    def _configure_third_party_loggers(self):
        """配置第三方库的日志级别"""
        # 降低Google API库的日志级别
        logging.getLogger('googleapiclient').setLevel(logging.WARNING)
        logging.getLogger('google.auth').setLevel(logging.WARNING)
        logging.getLogger('google_auth_httplib2').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)
    
    def get_logger(self, name: str) -> logging.Logger:
        """获取或创建指定名称的日志器"""
        if name not in self.loggers:
            logger = logging.getLogger(name)
            
            # 为特定模块添加成功级别
            self._add_success_level(logger)
            
            self.loggers[name] = logger
        
        return self.loggers[name]
    
    def _add_success_level(self, logger):
        """为日志器添加SUCCESS级别"""
        SUCCESS_LEVEL = 25  # 介于INFO(20)和WARNING(30)之间
        logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")
        
        def success(self, message, *args, **kwargs):
            if self.isEnabledFor(SUCCESS_LEVEL):
                self._log(SUCCESS_LEVEL, message, args, **kwargs)
        
        logger.success = success.__get__(logger, logger.__class__)
    
    def log_system_info(self):
        """记录系统信息"""
        logger = self.get_logger('system')
        logger.info("="*60)
        logger.info("Google Drive Monitor System Starting")
        logger.info("="*60)
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Working directory: {os.getcwd()}")
        logger.info(f"Log file: {Config.LOG_FILE}")
        logger.info(f"Log level: {Config.LOG_LEVEL}")
        logger.info(f"Drive folder ID: {Config.DRIVE_FOLDER_ID}")
        logger.info(f"Spreadsheet ID: {Config.SPREADSHEET_ID}")
        logger.info("="*60)
    
    def log_configuration(self):
        """记录配置信息"""
        logger = self.get_logger('config')
        logger.info("Current configuration:")
        logger.info(f"  Check interval: {Config.CHECK_INTERVAL}s")
        logger.info(f"  Max file size: {Config.MAX_FILE_SIZE_MB}MB")
        logger.info(f"  Max concurrent downloads: {Config.MAX_CONCURRENT_DOWNLOADS}")
        logger.info(f"  Allowed extensions: {', '.join(Config.ALLOWED_EXTENSIONS)}")
        logger.info(f"  Retry attempts: {Config.MAX_RETRY_ATTEMPTS}")
        logger.info(f"  Keep processed days: {Config.KEEP_PROCESSED_DAYS}")
    
    def close_handlers(self):
        """关闭所有日志处理器"""
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            handler.close()

# 全局日志管理器实例
_structured_logger = None

def get_logger(name: str = None) -> logging.Logger:
    """
    获取日志器实例
    
    Args:
        name (str): 日志器名称，默认使用调用者的模块名
        
    Returns:
        logging.Logger: 日志器实例
    """
    global _structured_logger
    
    if _structured_logger is None:
        _structured_logger = StructuredLogger()
    
    if name is None:
        # 自动获取调用者的模块名
        import inspect
        frame = inspect.currentframe()
        try:
            caller_frame = frame.f_back
            name = caller_frame.f_globals.get('__name__', 'unknown')
        finally:
            del frame
    
    return _structured_logger.get_logger(name)

def log_system_startup():
    """记录系统启动信息"""
    global _structured_logger
    if _structured_logger is None:
        _structured_logger = StructuredLogger()
    
    _structured_logger.log_system_info()
    _structured_logger.log_configuration()

def log_system_shutdown():
    """记录系统关闭信息"""
    logger = get_logger('system')
    logger.info("="*60)
    logger.info("Google Drive Monitor System Shutting Down")
    logger.info(f"Shutdown time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*60)
    
    # 关闭处理器
    global _structured_logger
    if _structured_logger:
        _structured_logger.close_handlers()

def log_performance(func_name: str, execution_time: float, **kwargs):
    """记录性能信息"""
    logger = get_logger('performance')
    from utils.error_formatter import ErrorFormatter
    formatted_time = ErrorFormatter.format_duration_seconds(execution_time)
    extra_info = ' '.join([f"{k}={v}" for k, v in kwargs.items()])
    logger.info(f"{func_name} completed in {formatted_time} {extra_info}")

def log_error_with_context(error: Exception, context: dict = None):
    """记录带上下文的错误信息"""
    logger = get_logger('error')
    logger.error(f"Error occurred: {type(error).__name__}: {error}")
    
    if context:
        logger.error("Context information:")
        for key, value in context.items():
            logger.error(f"  {key}: {value}")
    
    # 记录堆栈跟踪
    import traceback
    logger.debug("Stack trace:", exc_info=True)

# 装饰器：自动记录函数执行时间
def log_execution_time(logger_name: str = None):
    """装饰器：记录函数执行时间"""
    def decorator(func):
        import functools
        import time
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                log_performance(func.__name__, execution_time)
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                context = {
                    'function': func.__name__,
                    'execution_time': f"{execution_time:.3f}s",
                    'args_count': len(args),
                    'kwargs_count': len(kwargs)
                }
                log_error_with_context(e, context)
                raise
        
        return wrapper
    return decorator

# 上下文管理器：临时改变日志级别
class LogLevel:
    """上下文管理器：临时改变日志级别"""
    
    def __init__(self, logger_name: str, level: str):
        self.logger = get_logger(logger_name)
        self.new_level = getattr(logging, level.upper())
        self.original_level = self.logger.level
    
    def __enter__(self):
        self.logger.setLevel(self.new_level)
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.setLevel(self.original_level)