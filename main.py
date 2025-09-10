import os
import sys
import argparse
import signal
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from config import Config
from utils.logger import get_logger, log_system_startup, log_system_shutdown, log_error_with_context
from utils.validators import validate_environment
# 邮件通知模块导入（可选）
try:
    from utils.email_notifier import EmailNotifier
    EMAIL_MODULE_AVAILABLE = True
except ImportError as e:
    print(f"警告: 邮件通知模块不可用: {e}")
    print("系统将在无邮件通知的情况下运行")
    EmailNotifier = None
    EMAIL_MODULE_AVAILABLE = False
from monitor.drive_monitor import DriveMonitor
from monitor.file_tracker import FileTracker
from monitor.file_downloader import FileDownloader
from monitor.archive_handler import ArchiveHandler
from sheets.sheets_writer import SheetsWriter
from validation.manager import ValidationManager
from processors.data_processor import DataProcessor
from utils.error_formatter import ErrorFormatter
from utils.huggingface_uploader import upload_processed_package

logger = get_logger(__name__)

class GoogleDriveMonitorSystem:
    """
    Google Drive 自动监控系统主程序
    
    功能流程：
    1. 初始化配置和日志
    2. 验证Google API连接
    3. 创建必要的目录
    4. 加载已处理文件记录
    5. 启动监控循环
    6. 处理新文件：
       a. 下载文件
       b. 验证格式
       c. 解压测试
       d. 写入Sheets
       e. 更新记录
    7. 清理临时文件
    8. 优雅退出处理
    """
    
    def __init__(self, args=None):
        self.args = args or argparse.Namespace()
        self.drive_monitor = None
        self.file_tracker = None
        self.file_downloader = None
        self.archive_handler = None
        self.sheets_writer = None
        self.email_notifier = None
        self.validation_manager = None
        self.data_processor = None
        self.running = True
        self.stats = {
            'files_processed': 0,
            'files_failed': 0,
            'start_time': datetime.now()
        }
        
        # 注册信号处理器
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """处理退出信号"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False
        Config.ENABLE_MONITORING = False
    
    def initialize_system(self) -> bool:
        """初始化系统组件"""
        try:
            logger.info("Initializing Google Drive Monitor System...")
            
            # 验证环境和配置
            if not validate_environment():
                logger.error("Environment validation failed")
                return False
            
            # 验证配置
            Config.validate()
            
            # 初始化组件
            self.drive_monitor = DriveMonitor(Config.DRIVE_FOLDER_ID, Config.SERVICE_ACCOUNT_FILE)
            self.file_tracker = FileTracker()
            self.file_downloader = FileDownloader()
            self.archive_handler = ArchiveHandler()
            self.sheets_writer = SheetsWriter()
            self.validation_manager = ValidationManager()
            self.data_processor = DataProcessor()
            
            # 初始化邮件通知器（如果启用且可用）
            if Config.EMAIL_NOTIFICATIONS_ENABLED and EMAIL_MODULE_AVAILABLE:
                self.email_notifier = EmailNotifier()
                logger.info("Email notifications enabled")
            elif Config.EMAIL_NOTIFICATIONS_ENABLED and not EMAIL_MODULE_AVAILABLE:
                logger.warning("Email notifications requested but module not available")
                self.email_notifier = None
            else:
                logger.info("Email notifications disabled")
            
            # 测试连接
            if not self._test_connections():
                logger.error("Connection tests failed")
                return False
            
            logger.success("System initialization completed successfully")
            return True
            
        except Exception as e:
            log_error_with_context(e, {'phase': 'initialization'})
            # 发送系统错误通知
            if hasattr(self, 'email_notifier') and self.email_notifier:
                self.email_notifier.notify_error("System Initialization Error", str(e), {'phase': 'initialization'})
            return False
    
    def _test_connections(self) -> bool:
        """测试各组件连接"""
        try:
            logger.info("Testing component connections...")
            
            # 测试Drive连接
            status = self.drive_monitor.get_status()
            logger.info(f"Drive Monitor: folder_id={status['folder_id']}, processed={status['processed_count']}")
            
            # 测试Sheets连接
            if not self.sheets_writer.test_connection():
                logger.error("Sheets connection test failed")
                return False
            
            # 测试下载器
            downloader_status = self.file_downloader.get_download_status()
            logger.info(f"File Downloader: max_concurrent={downloader_status['max_concurrent']}")
            
            # 测试邮件通知（如果启用）
            if self.email_notifier:
                if self.email_notifier.test_connection():
                    logger.info("Email notifications: connection test passed")
                else:
                    logger.warning("Email notifications: connection test failed")
            
            logger.success("All connection tests passed")
            return True
            
        except Exception as e:
            log_error_with_context(e, {'phase': 'connection_test'})
            return False
    
    def process_file(self, file_info: Dict[str, Any]) -> bool:
        """
        处理单个文件
        
        Args:
            file_info (Dict): 文件信息
            
        Returns:
            bool: 处理是否成功
        """
        file_id = file_info['id']
        file_name = file_info['name']
        process_start_time = datetime.now()
        
        try:
            logger.info(f"开始处理文件: {file_name} ({file_info.get('size', 0) / (1024*1024):.2f} MB)")
            
            # 1. 下载文件
            logger.info(f"正在下载文件: {file_name}")
            download_path = self.file_downloader.download_file(file_id, file_name)
            
            if not download_path:
                error_msg = f"File download failed: {file_name}"
                logger.error(error_msg)
                self._record_failed_processing(file_info, error_msg, process_start_time)
                return False
            
            # 2. 验证和解压（如果是压缩文件）
            extract_status = "N/A"
            file_count = ""
            error_message = ""
            validation_score = ""
            
            try:
                # 检测是否为压缩文件
                archive_format = self.archive_handler.detect_format(download_path)
                
                if archive_format:
                    logger.info(f"检测到压缩文件格式: {archive_format}")
                    
                    # 验证压缩文件（包含数据格式验证的完整pipeline validation）
                    archive_validation_result = self.archive_handler.validate_archive(download_path, validate_data_format=True)
                    
                    # 从archive_validation_result中提取data_validation结果
                    data_validation_result = archive_validation_result.get('data_validation') if archive_validation_result else None
                    
                    # 详细记录验证结果（如果存在）
                    if data_validation_result:
                        # 检查data_validation_result是否为ValidationResult对象还是字典
                        if hasattr(data_validation_result, 'summary'):
                            logger.info(f"Data validation completed: {data_validation_result.summary}")
                            
                            # 详细记录验证错误和警告
                            if hasattr(data_validation_result, 'errors') and data_validation_result.errors:
                                logger.warning(f"Validation ERRORS ({len(data_validation_result.errors)}):")
                                for i, error in enumerate(data_validation_result.errors, 1):
                                    logger.warning(f"  [{i}] {error}")
                            
                            if hasattr(data_validation_result, 'warnings') and data_validation_result.warnings:
                                logger.info(f"Validation WARNINGS ({len(data_validation_result.warnings)}):")
                                for i, warning in enumerate(data_validation_result.warnings, 1):
                                    logger.info(f"  [{i}] {warning}")
                            
                            # 记录缺失文件和目录信息
                            if hasattr(data_validation_result, 'missing_files') and data_validation_result.missing_files:
                                logger.warning(f"Missing files: {data_validation_result.missing_files}")
                            if hasattr(data_validation_result, 'missing_directories') and data_validation_result.missing_directories:
                                logger.warning(f"Missing directories: {data_validation_result.missing_directories}")
                            
                            if hasattr(data_validation_result, 'metadata'):
                                logger.info(f"Validation metadata: {data_validation_result.metadata}")
                            logger.debug(f"Validation result type: {type(data_validation_result)}")
                        else:
                            # 如果是字典格式，尝试提取基本信息
                            logger.info(f"Data validation result (dict format): {data_validation_result}")
                            logger.debug(f"Validation result type: {type(data_validation_result)}")
                    else:
                        logger.info("Data validation was skipped or failed in archive validation")
                        
                    validation_result = archive_validation_result
                    
                    if validation_result['is_valid']:
                        extract_status = "Success"
                        file_count = validation_result['file_count']
                        
                        # 检查数据格式验证结果
                        if data_validation_result:
                            # 处理字典格式的data_validation_result
                            score = data_validation_result.get('score') if isinstance(data_validation_result, dict) else getattr(data_validation_result, 'score', None)
                            is_valid = data_validation_result.get('is_valid') if isinstance(data_validation_result, dict) else getattr(data_validation_result, 'is_valid', None)
                            
                            if score is not None:
                                validation_score = f"{score:.1f}/100"
                                if is_valid:
                                    logger.success(f"Archive and data format validation successful: {file_count} files, score: {score:.1f}/100")
                                    extract_status = f"Success (Data Validation: {score:.1f}/100)"
                                else:
                                    summary = data_validation_result.get('summary') if isinstance(data_validation_result, dict) else getattr(data_validation_result, 'summary', 'Unknown validation issue')
                                    logger.warning(f"Archive integrity OK, but data format validation failed: {summary}")
                                    errors = data_validation_result.get('errors', []) if isinstance(data_validation_result, dict) else getattr(data_validation_result, 'errors', [])
                                    errors_count = len(errors)
                                    extract_status = f"Partial Success (Data Format Issues: {errors_count} errors)"
                                    # Generate standardized English error message
                                    error_message = self._create_validation_error_message(data_validation_result)
                            else:
                                validation_score = "N/A (Parse Failed)"
                                logger.warning(f"Failed to parse data validation result")
                        else:
                            validation_score = "N/A (Validation Skipped)"
                            logger.success(f"Archive validation successful: {file_count} files (data format validation skipped)")
                    else:
                        extract_status = "Failed"
                        error_message = validation_result.get('error', 'Unknown error')
                        logger.warning(f"Archive validation failed: {error_message}")
                        
                        # 尝试用默认密码
                        if "password" in error_message.lower():
                            logger.info("Attempting extraction with default passwords...")
                            correct_password = self.archive_handler.try_passwords(download_path)
                            if correct_password:
                                validation_result = self.archive_handler.validate_archive(download_path, correct_password, validate_data_format=True)
                                if validation_result['is_valid']:
                                    extract_status = "Success"
                                    file_count = validation_result['file_count']
                                    error_message = ""
                                    
                                    # 更新data_validation_result
                                    data_validation_result = validation_result.get('data_validation')
                                    
                                    # 检查数据格式验证结果
                                    if data_validation_result and hasattr(data_validation_result, 'score'):
                                        validation_score = f"{data_validation_result.score:.1f}/100"
                                        if hasattr(data_validation_result, 'is_valid') and data_validation_result.is_valid:
                                            logger.success(f"Password extraction successful, data format validation passed: {file_count} files, score: {data_validation_result.score:.1f}/100")
                                            extract_status = f"Success (Password + Data Validation: {data_validation_result.score:.1f}/100)"
                                        else:
                                            summary = getattr(data_validation_result, 'summary', 'Unknown validation issue')
                                            logger.warning(f"Password extraction successful, but data format validation failed: {summary}")
                                            extract_status = f"Partial Success (Password Success, Data Format Issues)"
                                            # Generate standardized English error message
                                            error_message = self._create_validation_error_message(data_validation_result)
                                    else:
                                        validation_score = "N/A (Validation Skipped)"
                                        logger.success(f"Password extraction successful: {file_count} files")
                
            except Exception as e:
                extract_status = "Failed"
                error_message = str(e)
                logger.warning(f"Archive processing error: {e}")
            
            # 3. 提取场景类型、大小状态、PCD尺度和Transient检测信息
            scene_type = ''
            size_status = ''
            pcd_scale = ''
            transient_decision = ''
            wdd = ''
            wpo = ''
            sai = ''
            
            # 从archive validation结果中提取这些信息
            if 'validation_result' in locals() and validation_result:
                scene_validation = validation_result.get('scene_validation', {})
                size_validation = validation_result.get('size_validation', {})
                pcd_validation = validation_result.get('pcd_validation', {})
                
                scene_type = scene_validation.get('scene_type', 'unknown')
                size_status = size_validation.get('size_status', 'unknown')
                
                # PCD Scale显示尺度数值而不是状态
                if pcd_validation and pcd_validation.get('scale_status') != 'not_found':
                    width_m = pcd_validation.get('width_m', 0)
                    height_m = pcd_validation.get('height_m', 0)
                    depth_m = pcd_validation.get('depth_m', 0)
                    pcd_scale = f"{width_m:.1f}×{height_m:.1f}×{depth_m:.1f}m"
                elif pcd_validation and pcd_validation.get('scale_status') == 'not_found':
                    pcd_scale = 'PCD Not Found'
                else:
                    pcd_scale = 'Parse Failed'
            
            # 从data_validation_result中提取transient检测信息
            logger.debug(f"Debug: data_validation_result type = {type(data_validation_result)}")
            logger.debug(f"Debug: data_validation_result keys = {list(data_validation_result.keys()) if isinstance(data_validation_result, dict) else 'Not a dict'}")
            
            if data_validation_result:
                # 获取metadata - 可能是字典中的键或对象的属性
                metadata = data_validation_result.get('metadata') if isinstance(data_validation_result, dict) else getattr(data_validation_result, 'metadata', None)
                logger.debug(f"Debug: metadata type = {type(metadata)}, keys = {list(metadata.keys()) if isinstance(metadata, dict) and metadata else 'None or not dict'}")
                
                if metadata:
                    transient_data = metadata.get('transient_validation', {})
                    logger.debug(f"Debug: transient_data keys = {list(transient_data.keys()) if transient_data else 'Empty'}")
                    transient_detection = transient_data.get('transient_detection', {})
                    logger.debug(f"Debug: transient_detection = {transient_detection}")
                    
                    if transient_detection:
                        transient_decision = transient_detection.get('decision', 'N/A')
                        metrics = transient_detection.get('metrics', {})
                        wdd = f"{metrics.get('WDD', 0):.3f}" if metrics.get('WDD') is not None else 'N/A'
                        wpo = f"{metrics.get('WPO', 0):.1f}%" if metrics.get('WPO') is not None else 'N/A'
                        sai = f"{metrics.get('SAI', 0):.1f}%" if metrics.get('SAI') is not None else 'N/A'
                        
                        logger.debug(f"验证结果提取: scene_type={scene_type}, size_status={size_status}, pcd_scale={pcd_scale}")
                        logger.debug(f"Transient检测结果: decision={transient_decision}, WDD={wdd}, WPO={wpo}, SAI={sai}")
                    else:
                        transient_decision = 'N/A'
                        wdd = wpo = sai = 'N/A'
                        logger.debug("Debug: No transient_detection data found in metadata")
                else:
                    transient_decision = 'N/A'
                    wdd = wpo = sai = 'N/A'
                    logger.debug("Debug: No metadata found in data_validation_result")
            else:
                transient_decision = 'N/A'
                wdd = wpo = sai = 'N/A'
                logger.debug("Debug: No data_validation_result found")

            # 4. 写入Google Sheets
            # ===== SHEETS记录契约 =====
            # 这个字典必须符合SheetsRecordContract定义
            #
            # 【添加新字段完整流程 - 关键检查点】
            # 如果要添加新字段，必须同时更新以下5个位置：
            # 1. monitor/drive_monitor.py - 确保API请求包含新字段
            # 2. 此处sheets_record字典 - 从file_info提取新字段数据
            # 3. sheets/sheets_writer.py - 添加表头和field_mapping
            # 4. sheets/data_mapper.py - 添加提取逻辑和默认值
            # 5. _record_failed_processing方法 - 同步更新失败记录
            #
            # 【本次Owner/Uploader字段问题分析】
            # 问题：虽然1、3、4都完成了，但遗漏了步骤2和5
            # 症状：表头有Owner/Uploader列，但数据为空
            # 根因：file_info中的owners数据没有传递到sheets_record
            # 解决：下面的'owners'字段是修复的关键
            #
            sheets_record = {
                'file_id': file_id,
                'file_name': file_name,
                'upload_time': file_info.get('createdTime', ''),
                'owners': file_info.get('owners', []),  # 【关键修复】传递owners数据到mapper
                'file_size': file_info.get('size', 0),
                'file_type': file_info.get('mimeType', ''),
                'extract_status': extract_status,
                'file_count': file_count,
                'process_time': process_start_time,
                'validation_score': validation_score,
                'validation_result': data_validation_result,  # 添加validation结果
                'scene_type': scene_type,     # 添加场景类型
                'size_status': size_status,   # 添加大小状态
                'pcd_scale': pcd_scale,      # 添加PCD尺度（显示尺寸）
                # 添加Transient检测相关字段
                'transient_decision': transient_decision,  # 添加移动障碍物检测决策
                'wdd': wdd,                   # 加权检测密度
                'wpo': wpo,                   # 加权人员占用率
                'sai': sai,                   # 场景活动指数
                # 添加状态信息用于颜色格式化
                'size_status_level': size_validation.get('size_status', 'unknown') if 'validation_result' in locals() and validation_result else 'unknown',
                'pcd_scale_status': pcd_validation.get('scale_status', 'unknown') if 'validation_result' in locals() and validation_result and pcd_validation else 'unknown',
                'error_message': error_message,
                'notes': f"Download path: {download_path}"
            }
            
            
            # 4. 数据处理阶段（在验证通过后自动启动）
            processing_results = None
            processing_status = "未执行"
            
            if Config.AUTO_START_PROCESSING and data_validation_result and data_validation_result.get('is_valid', False):
                logger.info(f"开始数据处理: {file_name}")
                try:
                    # 准备处理结果字典
                    validation_for_processing = {
                        'is_valid': data_validation_result.get('is_valid', False),
                        'score': data_validation_result.get('score', 0),
                        'metadata': data_validation_result.get('metadata', {}),
                        'validation_type': data_validation_result.get('validator_type', 'unknown')
                    }
                    
                    # 确定处理的数据路径
                    # 如果是压缩文件，使用解压后的路径；否则使用下载路径
                    processing_path = None
                    if 'validation_result' in locals() and validation_result and validation_result.get('is_valid'):
                        # 从archive_handler的验证结果中获取解压路径
                        # 需要重新解压或使用临时解压路径
                        temp_extract_path = self.archive_handler.extract_archive(download_path)
                        if temp_extract_path:
                            processing_path = temp_extract_path
                            logger.info(f"使用解压路径进行处理: {processing_path}")
                        else:
                            logger.warning("无法解压文件用于数据处理")
                    
                    if processing_path:
                        # 保存原始解压路径，用于后续包创建时查找原始文件
                        original_extracted_path = processing_path
                        
                        processing_results = self.data_processor.process_validated_data(
                            processing_path, validation_for_processing, file_id
                        )
                        
                        if processing_results['overall_success']:
                            processing_status = "成功"
                            logger.success(f"数据处理完成: {file_name}")
                            
                            # 记录处理步骤信息
                            post_processing_result = None
                            for step in processing_results.get('processing_steps', []):
                                step_name = step.get('step', 'unknown')
                                step_result = step.get('result', {})
                                step_success = step_result.get('success', False)
                                step_duration = step_result.get('duration', 0)
                                
                                # Keep track of post_processing result for package creation
                                if step_name == 'post_processing':
                                    post_processing_result = step_result
                                
                                # Format duration display
                                if step_duration >= 3600:  # >= 1 hour
                                    hours = int(step_duration // 3600)
                                    minutes = int((step_duration % 3600) // 60)
                                    duration_str = f"{hours}h {minutes}m"
                                elif step_duration >= 60:  # >= 1 minute
                                    minutes = int(step_duration // 60)
                                    seconds = step_duration % 60
                                    duration_str = f"{minutes}m {seconds:.1f}s"
                                else:
                                    duration_str = f"{step_duration:.2f}s"
                                
                                status_icon = "✓" if step_success else "✗"
                                logger.info(f"  {step_name}: {status_icon} ({duration_str})")
                            
                            # Create final package if post-processing found output files
                            if post_processing_result and post_processing_result.get('success') and post_processing_result.get('output'):
                                try:
                                    import ast
                                    from package_creator import create_final_package
                                    
                                    # Parse output files dictionary from post-processing result
                                    output_files_str = post_processing_result.get('output', '{}')
                                    output_files = ast.literal_eval(output_files_str)
                                    
                                    if output_files.get('colorized_las') and output_files.get('transforms_json'):
                                        logger.info("Creating final processed package...")
                                        
                                        # Extract scene type from validation result (use same logic as sheet upload)
                                        scene_type = "outdoor"  # default fallback
                                        
                                        # Use the same validation_result that was used for sheet upload
                                        if 'validation_result' in locals() and validation_result:
                                            scene_validation = validation_result.get('scene_validation', {})
                                            scene_type = scene_validation.get('scene_type', 'outdoor')
                                            logger.info(f"Scene type from validation_result: {scene_type}")
                                        else:
                                            logger.warning("No validation_result available, using default outdoor")
                                        
                                        logger.info(f"Detected scene type: {scene_type}")
                                        
                                        # Use the original_extracted_path (未处理的解压路径) for finding original files
                                        package_result = create_final_package(
                                            original_path=original_extracted_path,
                                            output_files=output_files,
                                            package_name=Path(original_extracted_path).name,
                                            file_id=file_id,
                                            output_dir="./processed",
                                            scene_type=scene_type
                                        )
                                        
                                        if package_result['success']:
                                            final_package_path = package_result['package_path']
                                            package_size_mb = package_result['package_size_mb']
                                            compression_duration = package_result['compression_duration']
                                            
                                            logger.success(f"Final processed package created: {final_package_path}")
                                            logger.info(f"Package size: {package_size_mb:.1f} MB (compressed in {compression_duration:.1f}s)")
                                            processing_results['final_package_path'] = final_package_path
                                            
                                            # Store complete package result including COLMAP info for data_mapper
                                            processing_results['final_package_result'] = package_result
                                            
                                            # Upload to Hugging Face if enabled
                                            hf_upload_result = self._upload_to_huggingface(
                                                package_path=final_package_path,
                                                file_id=file_id,
                                                scene_type=scene_type,
                                                validation_score=validation_score if isinstance(validation_score, (int, float)) else None,
                                                processing_success=True,
                                                metadata={
                                                    'file_name': file_name,
                                                    'upload_time': file_info.get('createdTime', ''),
                                                    'compression_duration': compression_duration,
                                                    'colmap_result': package_result.get('colmap_result', {})
                                                }
                                            )
                                            processing_results['hf_upload_result'] = hf_upload_result
                                            
                                            # Check if HuggingFace upload was successful and delete source file if configured
                                            if (Config.AUTO_DELETE_SOURCE_FILES and 
                                                hf_upload_result and 
                                                hf_upload_result.get('success', False) and
                                                (not Config.DELETE_ONLY_AFTER_HF_SUCCESS or hf_upload_result.get('success', False))):
                                                
                                                logger.info("HuggingFace upload successful, attempting to delete source file from Google Drive...")
                                                delete_success = self.drive_monitor.delete_file(file_id)
                                                
                                                if delete_success:
                                                    logger.success(f"Successfully deleted source file {file_name} from Google Drive")
                                                    # Add deletion info to processing results for potential logging
                                                    processing_results['source_file_deleted'] = True
                                                else:
                                                    logger.warning(f"Failed to delete source file {file_name} from Google Drive")
                                                    processing_results['source_file_deleted'] = False
                                        else:
                                            error_msg = package_result.get('error', 'Unknown package creation error')
                                            logger.error(f"Failed to create final package: {error_msg}")
                                            
                                            # Store failed package result for data_mapper
                                            processing_results['final_package_result'] = package_result
                                    else:
                                        logger.warning("Cannot create final package: required output files not found")
                                except Exception as e:
                                    logger.error(f"Error creating final package: {e}")
                        else:
                            processing_status = "失败"
                            errors = processing_results.get('errors', [])
                            logger.error(f"数据处理失败: {'; '.join(errors)}")
                    else:
                        processing_status = "跳过（无法获取数据路径）"
                        logger.warning("跳过数据处理：无法确定数据路径")
                        
                except Exception as e:
                    processing_status = f"异常: {str(e)}"
                    logger.error(f"数据处理过程中出现异常: {e}")
            else:
                if not Config.AUTO_START_PROCESSING:
                    processing_status = "已禁用"
                    logger.info("数据处理已禁用")
                elif not data_validation_result or not data_validation_result.get('is_valid', False):
                    processing_status = "跳过（验证未通过）"
                    logger.info("跳过数据处理：数据验证未通过")
                else:
                    processing_status = "跳过（条件不满足）"
                    logger.info("跳过数据处理：条件不满足")
            
            # 更新sheets记录以包含处理状态（如果需要的话）
            # 注意：这里可以选择再次更新Sheets记录以包含处理结果
            
            # 发送成功通知邮件
            if self.email_notifier and Config.NOTIFY_ON_SUCCESS:
                # 检查是否为大文件
                is_large_file = file_info.get('size', 0) / (1024 * 1024) > Config.LARGE_FILE_THRESHOLD_MB
                if Config.NOTIFY_ON_LARGE_FILES and is_large_file:
                    self.email_notifier.notify_file_processed(file_info, True)
                elif not is_large_file:  # 普通文件根据配置发送
                    self.email_notifier.notify_file_processed(file_info, True)
            
            # 5. 更新sheets_record以包含处理结果，并写入Google Sheets
            if processing_results:
                # 将处理结果添加到validation_result的metadata中，供data_mapper提取文件收集状态
                if data_validation_result and isinstance(data_validation_result, dict):
                    if 'metadata' not in data_validation_result:
                        data_validation_result['metadata'] = {}
                    data_validation_result['metadata']['processing_pipeline'] = processing_results
                
                # 更新sheets_record的validation_result
                sheets_record['validation_result'] = data_validation_result
            
            # 写入Google Sheets（包含处理结果信息）
            if self.sheets_writer.append_record_v2(sheets_record):
                logger.success(f"Written to Sheets: {file_name}")
            else:
                logger.warning(f"Sheets write failed, but file processed successfully: {file_name}")
            
            # 6. 更新文件追踪记录（包含处理状态）
            self.file_tracker.add_processed_file(
                file_id, 
                file_name, 
                status="success",
                metadata={
                    'download_path': str(download_path),
                    'extract_status': extract_status,
                    'file_count': file_count,
                    'process_time': (datetime.now() - process_start_time).total_seconds(),
                    'processing_status': processing_status,
                    'processing_results': processing_results,
                    'processing_pipeline': processing_results  # 添加处理管道结果供data_mapper提取文件收集状态
                }
            )
            
            # 7. 移动文件到processed目录
            if Config.CLEAN_TEMP_FILES:
                processed_path = Path(Config.PROCESSED_PATH) / file_name
                try:
                    Path(download_path).rename(processed_path)
                    logger.debug(f"文件已移动到: {processed_path}")
                except Exception as e:
                    logger.warning(f"移动文件失败: {e}")
            
            # Final check for source file deletion after all processing
            self._check_and_delete_source_file(file_id, file_name, processing_results)
            
            self.stats['files_processed'] += 1
            process_time = (datetime.now() - process_start_time).total_seconds()
            from utils.error_formatter import ErrorFormatter
            formatted_time = ErrorFormatter.format_duration_seconds(process_time)
            logger.success(f"文件处理完成: {file_name} (耗时 {formatted_time})")
            
            return True
            
        except Exception as e:
            error_context = {
                'file_id': file_id,
                'file_name': file_name,
                'phase': 'file_processing'
            }
            log_error_with_context(e, error_context)
            self._record_failed_processing(file_info, str(e), process_start_time)
            return False
        
        finally:
            # 清理临时文件
            self.archive_handler.cleanup_temp_dirs()
    
    def _check_and_delete_source_file(self, file_id: str, file_name: str, processing_results: Dict = None):
        """
        Check if source file should be deleted based on HuggingFace upload success
        
        Args:
            file_id: Google Drive file ID
            file_name: File name for logging
            processing_results: Processing results containing HF upload status
        """
        try:
            # Only proceed if auto-delete is enabled
            if not Config.AUTO_DELETE_SOURCE_FILES:
                return
            
            # Check if we need to wait for HuggingFace success
            if Config.DELETE_ONLY_AFTER_HF_SUCCESS:
                if not processing_results:
                    logger.debug("No processing results available, skipping source file deletion")
                    return
                
                hf_upload_result = processing_results.get('hf_upload_result')
                if not hf_upload_result or not hf_upload_result.get('success', False):
                    logger.info(f"HuggingFace upload not successful, keeping source file: {file_name}")
                    return
                
                # Check if file was already deleted during processing
                if processing_results.get('source_file_deleted', False):
                    logger.debug(f"Source file {file_name} already deleted during processing")
                    return
            
            # Attempt to delete the source file
            logger.info(f"Attempting to delete source file from Google Drive: {file_name}")
            delete_success = self.drive_monitor.delete_file(file_id)
            
            if delete_success:
                logger.success(f"Successfully deleted source file {file_name} from Google Drive")
            else:
                logger.warning(f"Failed to delete source file {file_name} from Google Drive")
                
        except Exception as e:
            logger.error(f"Error in source file deletion check for {file_name}: {e}")
    
    def _upload_to_huggingface(self, package_path: str, file_id: str, scene_type: str, 
                               validation_score: float = None, processing_success: bool = True,
                               metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Upload processed package to Hugging Face repository
        
        Args:
            package_path: Path to the processed package file
            file_id: Google Drive file ID
            scene_type: Scene type (indoor/outdoor)
            validation_score: Validation score for quality filtering
            processing_success: Whether processing was successful
            metadata: Additional metadata for upload tracking
            
        Returns:
            Dict containing upload result information
        """
        try:
            logger.info(f"Initiating Hugging Face upload for file: {file_id}")
            
            upload_result = upload_processed_package(
                package_path=package_path,
                file_id=file_id,
                scene_type=scene_type,
                validation_score=validation_score,
                processing_success=processing_success,
                metadata=metadata
            )
            
            if upload_result.get('success'):
                upload_path = upload_result.get('upload_path', 'unknown')
                upload_duration = upload_result.get('upload_duration', 0)
                logger.success(f"✓ Upload completed: {upload_path} (took {upload_duration:.1f}s)")
            elif upload_result.get('skipped'):
                reason = upload_result.get('reason', 'Unknown reason')
                logger.info(f"Upload skipped: {reason}")
            else:
                error = upload_result.get('error', 'Unknown upload error')
                logger.warning(f"Upload failed: {error}")
            
            return upload_result
            
        except Exception as e:
            error_msg = f"Hugging Face upload error: {e}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def _record_failed_processing(self, file_info: Dict, error_msg: str, start_time: datetime):
        """记录处理失败的文件"""
        try:
            # 写入Sheets
            # 【重要】失败记录也必须包含所有字段，确保与成功记录格式一致
            # 这里必须与process_file()方法中的sheets_record保持同步更新
            sheets_record = {
                'file_id': file_info['id'],
                'file_name': file_info['name'],
                'upload_time': file_info.get('createdTime', ''),
                'owners': file_info.get('owners', []),  # 【同步修复】确保失败记录也包含owners信息
                'file_size': file_info.get('size', 0),
                'file_type': file_info.get('mimeType', ''),
                'extract_status': 'Failed',
                'file_count': '',
                'file_collection_status': 'NOT_CHECKED',  # 失败时设为NOT_CHECKED
                'process_time': start_time,
                'validation_score': 'N/A (Failed)',
                'scene_type': 'unknown',          # 失败时设为unknown
                'size_status': 'unknown',         # 失败时设为unknown
                'pcd_scale': 'unknown',           # 失败时设为unknown
                'transient_decision': 'N/A',      # 失败时设为N/A
                'wdd': 'N/A',                     # 失败时设为N/A
                'wpo': 'N/A',                     # 失败时设为N/A
                'sai': 'N/A',                     # 失败时设为N/A
                'error_message': error_msg,
                'notes': 'Processing failed'
            }
            self.sheets_writer.append_record_v2(sheets_record)
            
            # 发送失败通知邮件
            if self.email_notifier and Config.NOTIFY_ON_ERROR:
                self.email_notifier.notify_file_processed(file_info, False, error_msg)
            
            # 更新文件追踪
            self.file_tracker.add_processed_file(
                file_info['id'],
                file_info['name'],
                status="failed",
                metadata={'error': error_msg}
            )
            
            self.stats['files_failed'] += 1
            
        except Exception as e:
            logger.error(f"记录失败信息时出错: {e}")
    
    def process_new_files(self, new_files: List[Dict]) -> None:
        """处理新文件列表"""
        if not new_files:
            return
        
        logger.info(f"开始处理 {len(new_files)} 个新文件")
        
        for i, file_info in enumerate(new_files, 1):
            if not self.running:
                logger.info("收到停止信号，中断文件处理")
                break
            
            logger.info(f"处理进度: {i}/{len(new_files)}")
            
            try:
                success = self.process_file(file_info)
                
                # 标记为已处理（无论成功失败）
                self.drive_monitor.mark_as_processed(file_info['id'])
                
                if success:
                    logger.info(f"✅ 文件处理成功: {file_info['name']}")
                else:
                    logger.error(f"❌ 文件处理失败: {file_info['name']}")
                
            except Exception as e:
                logger.error(f"处理文件时发生异常: {file_info['name']} - {e}")
                self.drive_monitor.mark_as_processed(file_info['id'])
        
        # 批量清理
        if Config.CLEAN_TEMP_FILES:
            self.file_downloader.cleanup_temp_files()
        
        logger.info(f"批处理完成: 成功 {self.stats['files_processed']}, 失败 {self.stats['files_failed']}")
    
    def run_once(self) -> bool:
        """运行一次检查和处理"""
        try:
            logger.info("执行一次性文件检查...")
            
            # 获取新文件
            new_files = self.drive_monitor.get_new_files()
            
            if new_files:
                self.process_new_files(new_files)
            else:
                logger.info("未发现新文件")
            
            return True
            
        except Exception as e:
            log_error_with_context(e, {'phase': 'run_once'})
            return False
    
    def start_monitoring(self):
        """启动持续监控"""
        logger.info("启动持续监控模式...")
        
        try:
            self.drive_monitor.start_monitoring(self.process_new_files)
            
        except KeyboardInterrupt:
            logger.info("用户中断监控")
        except Exception as e:
            log_error_with_context(e, {'phase': 'monitoring'})
        finally:
            self.shutdown()
    
    def _create_validation_error_message(self, data_validation_result) -> str:
        """Create clear, specific error message explaining actual validation problems"""
        try:
            if not data_validation_result:
                return ""
            
            # Extract validation details
            errors = []
            score = None
            summary = ""
            
            if hasattr(data_validation_result, 'errors'):
                errors = data_validation_result.errors
                score = getattr(data_validation_result, 'score', None)
                summary = getattr(data_validation_result, 'summary', '')
            elif isinstance(data_validation_result, dict):
                errors = data_validation_result.get('errors', [])
                score = data_validation_result.get('score')
                summary = data_validation_result.get('summary', '')
            else:
                summary = str(data_validation_result)
            
            # Create specific, actionable error message
            specific_errors = []
            
            # Parse actual errors instead of relying on summary
            for error in errors[:5]:  # Show up to 5 specific errors
                error_str = str(error).strip()
                if error_str:
                    # Clean up error text and make it more readable
                    error_str = self._format_specific_error(error_str)
                    specific_errors.append(error_str)
            
            # If we have specific errors, use them
            if specific_errors:
                error_message = "; ".join(specific_errors)
                if len(errors) > 5:
                    error_message += f" (and {len(errors) - 5} more issues)"
                return error_message
            
            # Fallback: try to extract meaningful info from pipeline validation
            if "Pipeline Validation:" in summary and "Basic(" in summary and "Transient(" in summary:
                try:
                    basic_score = float(summary.split("Basic(")[1].split(")")[0])
                    transient_score = float(summary.split("Transient(")[1].split(")")[0])
                    
                    issues = []
                    if basic_score < 50:
                        issues.append(f"File structure/format issues (score: {basic_score:.1f}/100)")
                    if transient_score < 50:
                        issues.append(f"Data quality issues (score: {transient_score:.1f}/100)")
                    
                    if issues:
                        return "; ".join(issues)
                    else:
                        return f"Validation standards not met (Basic: {basic_score:.1f}/100, Data Quality: {transient_score:.1f}/100)"
                except:
                    pass
            
            # Final fallback
            if score is not None:
                return f"Data validation failed with score {score:.1f}/100 - check file structure and content quality"
            else:
                return "Data validation failed - check logs for details"
                    
        except Exception as e:
            logger.warning(f"Failed to create validation error message: {e}")
            return "Data validation failed - unable to parse error details"
    
    def _format_specific_error(self, error_str: str) -> str:
        """Format specific error messages to be more user-friendly"""
        # Remove redundant prefixes
        error_str = error_str.replace("Error:", "").replace("error:", "").strip()
        
        # Make common errors more readable
        if "missing required file" in error_str.lower():
            return error_str.replace("Missing required file:", "Missing file:")
        elif "missing required directory" in error_str.lower():
            return error_str.replace("Missing required directory:", "Missing folder:")
        elif "file too small" in error_str.lower():
            return error_str.replace("too small", "is too small")
        elif "file too large" in error_str.lower():
            return error_str.replace("too large", "is too large")
        elif "invalid" in error_str.lower() and "format" in error_str.lower():
            return error_str.replace("Invalid", "Invalid format in")
        
        return error_str
    
    def get_system_stats(self) -> Dict:
        """获取系统统计信息"""
        uptime = datetime.now() - self.stats['start_time']
        file_stats = self.file_tracker.get_statistics()
        
        return {
            'uptime_seconds': uptime.total_seconds(),
            'files_processed_session': self.stats['files_processed'],
            'files_failed_session': self.stats['files_failed'],
            'total_files_processed': file_stats.get('total_processed', 0),
            'success_rate': file_stats.get('success_count', 0) / max(1, file_stats.get('total_processed', 1)) * 100,
            'last_processed': file_stats.get('last_processed'),
            'data_file_size': file_stats.get('data_file_size', 0)
        }
    
    def cleanup_old_records(self):
        """清理过期记录"""
        try:
            cleaned_count = self.file_tracker.cleanup_old_records()
            if cleaned_count > 0:
                logger.info(f"清理了 {cleaned_count} 条过期记录")
        except Exception as e:
            logger.error(f"清理过期记录时出错: {e}")
    
    def shutdown(self):
        """系统关闭"""
        logger.info("正在关闭系统...")
        
        try:
            # 停止监控
            if self.drive_monitor:
                self.drive_monitor.stop_monitoring()
            
            # 清理临时文件
            if Config.CLEAN_TEMP_FILES:
                if self.file_downloader:
                    self.file_downloader.cleanup_temp_files()
                if self.archive_handler:
                    self.archive_handler.cleanup_temp_dirs()
            
            # 清理过期记录
            self.cleanup_old_records()
            
            # 输出统计信息
            stats = self.get_system_stats()
            logger.info("会话统计:")
            logger.info(f"  运行时间: {stats['uptime_seconds']:.1f}s")
            logger.info(f"  处理文件: {stats['files_processed_session']}")
            logger.info(f"  失败文件: {stats['files_failed_session']}")
            logger.info(f"  总计处理: {stats['total_files_processed']}")
            logger.info(f"  成功率: {stats['success_rate']:.1f}%")
            
            # 发送系统状态报告邮件
            if self.email_notifier and Config.NOTIFY_DAILY_REPORT:
                self.email_notifier.notify_system_status(stats)
            
        except Exception as e:
            logger.error(f"关闭系统时出错: {e}")

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="Google Drive 文件监控系统")
    
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    parser.add_argument('--once', action='store_true', help='运行一次后退出')
    parser.add_argument('--interval', type=int, help='设置检查间隔（秒）')
    parser.add_argument('--dry-run', action='store_true', help='模拟运行，不实际下载处理')
    parser.add_argument('--config', type=str, help='指定配置文件路径')
    parser.add_argument('--cleanup', action='store_true', help='清理过期记录后退出')
    parser.add_argument('--stats', action='store_true', help='显示统计信息后退出')
    
    return parser.parse_args()

def main():
    """主程序入口"""
    args = parse_arguments()
    
    try:
        # 调整配置（基于命令行参数）
        if args.debug:
            Config.LOG_LEVEL = 'DEBUG'
        
        if args.interval:
            Config.CHECK_INTERVAL = args.interval
        
        if args.dry_run:
            logger.warning("运行在模拟模式，不会实际下载文件")
        
        # 启动日志系统
        log_system_startup()
        
        # 创建监控系统实例
        monitor_system = GoogleDriveMonitorSystem(args)
        
        # 初始化系统
        if not monitor_system.initialize_system():
            logger.error("系统初始化失败")
            return 1
        
        # 根据参数执行不同操作
        if args.stats:
            stats = monitor_system.get_system_stats()
            print("\n=== 系统统计信息 ===")
            for key, value in stats.items():
                print(f"{key}: {value}")
            return 0
        
        elif args.cleanup:
            monitor_system.cleanup_old_records()
            return 0
        
        elif args.once:
            success = monitor_system.run_once()
            return 0 if success else 1
        
        else:
            # 默认：启动持续监控
            monitor_system.start_monitoring()
            return 0
            
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
        return 0
        
    except Exception as e:
        log_error_with_context(e, {'phase': 'main'})
        return 1
        
    finally:
        log_system_shutdown()

if __name__ == "__main__":
    sys.exit(main())