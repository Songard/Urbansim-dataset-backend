import os
import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum

from config import Config
from utils.logger import get_logger

logger = get_logger(__name__)

class ValidationLevel(Enum):
    """验证级别"""
    STRICT = "strict"
    STANDARD = "standard" 
    LENIENT = "lenient"

@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    validation_level: ValidationLevel
    score: float  # 验证得分 0-100
    errors: List[str]
    warnings: List[str]
    missing_files: List[str]
    missing_directories: List[str]
    extra_files: List[str]
    file_details: Dict[str, Dict[str, Any]]
    summary: str

class DataFormatValidator:
    """
    数据格式验证器
    
    功能:
    - 根据YAML规范验证解压后的数据结构
    - 支持多种验证级别（严格/标准/宽松）
    - 检查文件和目录存在性
    - 验证文件大小和扩展名
    - 验证JSON/YAML文件内容
    - 处理外层文件夹的情况
    """
    
    def __init__(self, schema_file: str = None):
        """
        初始化数据格式验证器
        
        Args:
            schema_file (str): 验证规范文件路径
        """
        self.schema_file = schema_file or self._get_default_schema_file()
        self.schema = None
        self.load_schema()
        
        logger.info(f"DataFormatValidator initialized with schema: {self.schema_file}")
    
    def _get_default_schema_file(self) -> str:
        """获取默认Schema文件路径"""
        return os.path.join(os.path.dirname(__file__), '..', 'data_schemas', 'metacam_schema.yaml')
    
    def load_schema(self) -> bool:
        """加载验证规范"""
        try:
            if not os.path.exists(self.schema_file):
                logger.error(f"Schema文件不存在: {self.schema_file}")
                return False
            
            with open(self.schema_file, 'r', encoding='utf-8') as f:
                self.schema = yaml.safe_load(f)
            
            logger.info(f"成功加载Schema: {self.schema.get('schema_name', 'Unknown')} v{self.schema.get('schema_version', '1.0')}")
            return True
            
        except Exception as e:
            logger.error(f"加载Schema文件失败: {e}")
            return False
    
    def validate_directory(self, directory_path: str, 
                         validation_level: ValidationLevel = ValidationLevel.STANDARD) -> ValidationResult:
        """
        验证目录结构
        
        Args:
            directory_path (str): 要验证的目录路径
            validation_level (ValidationLevel): 验证级别
            
        Returns:
            ValidationResult: 验证结果
        """
        if not self.schema:
            logger.error("Schema未加载，无法进行验证")
            return ValidationResult(
                is_valid=False,
                validation_level=validation_level,
                score=0.0,
                errors=["Schema未加载"],
                warnings=[],
                missing_files=[],
                missing_directories=[],
                extra_files=[],
                file_details={},
                summary="Schema加载失败"
            )
        
        try:
            logger.info(f"开始验证目录: {directory_path} (级别: {validation_level.value})")
            
            # 确定实际的根目录（处理外层文件夹情况）
            actual_root = self._find_actual_root(directory_path)
            if not actual_root:
                return ValidationResult(
                    is_valid=False,
                    validation_level=validation_level,
                    score=0.0,
                    errors=["无法找到有效的数据根目录"],
                    warnings=[],
                    missing_files=[],
                    missing_directories=[],
                    extra_files=[],
                    file_details={},
                    summary="找不到数据根目录"
                )
            
            logger.info(f"实际数据根目录: {actual_root}")
            
            # 执行各项验证
            errors = []
            warnings = []
            missing_files = []
            missing_directories = []
            extra_files = []
            file_details = {}
            
            # 1. 验证目录结构
            self._validate_directories(actual_root, errors, warnings, missing_directories)
            
            # 2. 验证必需文件
            self._validate_required_files(actual_root, errors, warnings, missing_files, file_details)
            
            # 3. 验证可选文件
            self._validate_optional_files(actual_root, warnings, file_details)
            
            # 4. 检查额外文件
            if validation_level != ValidationLevel.LENIENT:
                self._check_extra_files(actual_root, warnings, extra_files)
            
            # 5. 验证文件内容
            self._validate_file_contents(actual_root, errors, warnings, file_details)
            
            # 计算验证分数
            score = self._calculate_score(errors, warnings, missing_files, missing_directories)
            
            # 判断是否验证通过
            is_valid = self._determine_validity(validation_level, errors, missing_files, missing_directories)
            
            # 生成总结
            summary = self._generate_summary(is_valid, score, len(errors), len(warnings))
            
            result = ValidationResult(
                is_valid=is_valid,
                validation_level=validation_level,
                score=score,
                errors=errors,
                warnings=warnings,
                missing_files=missing_files,
                missing_directories=missing_directories,
                extra_files=extra_files,
                file_details=file_details,
                summary=summary
            )
            
            logger.info(f"验证完成: {summary}")
            return result
            
        except Exception as e:
            logger.error(f"验证过程中出错: {e}")
            return ValidationResult(
                is_valid=False,
                validation_level=validation_level,
                score=0.0,
                errors=[f"验证异常: {e}"],
                warnings=[],
                missing_files=[],
                missing_directories=[],
                extra_files=[],
                file_details={},
                summary="验证过程异常"
            )
    
    def _find_actual_root(self, directory_path: str) -> Optional[str]:
        """查找实际的数据根目录"""
        directory_path = os.path.abspath(directory_path)
        
        # 检查当前目录是否包含关键文件
        if self._is_valid_root(directory_path):
            return directory_path
        
        # 检查是否有单个子目录包含数据
        try:
            items = os.listdir(directory_path)
            directories = [item for item in items if os.path.isdir(os.path.join(directory_path, item))]
            
            # 如果只有一个目录，检查它是否是数据根目录
            if len(directories) == 1:
                potential_root = os.path.join(directory_path, directories[0])
                if self._is_valid_root(potential_root):
                    return potential_root
            
            # 检查所有子目录
            for directory in directories:
                potential_root = os.path.join(directory_path, directory)
                if self._is_valid_root(potential_root):
                    return potential_root
                    
        except Exception as e:
            logger.error(f"查找根目录时出错: {e}")
        
        return None
    
    def _is_valid_root(self, path: str) -> bool:
        """检查路径是否是有效的数据根目录"""
        # 检查是否存在关键标识文件或目录
        key_indicators = ['metadata.yaml', 'camera', 'data', 'info']
        
        found_indicators = 0
        for indicator in key_indicators:
            indicator_path = os.path.join(path, indicator)
            if os.path.exists(indicator_path):
                found_indicators += 1
        
        # 至少要有2个关键标识
        return found_indicators >= 2
    
    def _validate_directories(self, root_path: str, errors: List[str], 
                            warnings: List[str], missing_directories: List[str]):
        """验证目录结构"""
        required_dirs = self.schema.get('required_directories', [])
        
        for dir_info in required_dirs:
            dir_path = os.path.join(root_path, dir_info['path'])
            
            if not os.path.exists(dir_path):
                error_msg = f"缺少必需目录: {dir_info['path']}"
                errors.append(error_msg)
                missing_directories.append(dir_info['path'])
                logger.warning(error_msg)
            else:
                logger.debug(f"找到目录: {dir_info['path']}")
                
                # 检查子目录
                subdirs = dir_info.get('subdirectories', [])
                for subdir_info in subdirs:
                    subdir_path = os.path.join(root_path, subdir_info['path'])
                    
                    if not os.path.exists(subdir_path):
                        if not subdir_info.get('optional', False):
                            error_msg = f"缺少必需子目录: {subdir_info['path']}"
                            errors.append(error_msg)
                            missing_directories.append(subdir_info['path'])
                        else:
                            warnings.append(f"缺少可选子目录: {subdir_info['path']}")
    
    def _validate_required_files(self, root_path: str, errors: List[str], 
                               warnings: List[str], missing_files: List[str], 
                               file_details: Dict[str, Dict[str, Any]]):
        """验证必需文件"""
        # 验证根目录必需文件
        self._validate_file_list(root_path, self.schema.get('required_files', []), 
                                errors, warnings, missing_files, file_details, True)
        
        # 验证data目录文件
        self._validate_file_list(root_path, self.schema.get('data_directory_files', []),
                                errors, warnings, missing_files, file_details, True)
        
        # 验证info目录文件  
        self._validate_file_list(root_path, self.schema.get('info_directory_files', []),
                                errors, warnings, missing_files, file_details, True)
    
    def _validate_optional_files(self, root_path: str, warnings: List[str], 
                               file_details: Dict[str, Dict[str, Any]]):
        """验证可选文件"""
        optional_files = self.schema.get('optional_files', [])
        self._validate_file_list(root_path, optional_files, [], warnings, [], file_details, False)
    
    def _validate_file_list(self, root_path: str, file_list: List[Dict], 
                          errors: List[str], warnings: List[str], missing_files: List[str],
                          file_details: Dict[str, Dict[str, Any]], is_required: bool):
        """验证文件列表"""
        for file_info in file_list:
            file_path = os.path.join(root_path, file_info['path'])
            relative_path = file_info['path']
            
            if not os.path.exists(file_path):
                if is_required:
                    error_msg = f"缺少必需文件: {relative_path}"
                    errors.append(error_msg)
                    missing_files.append(relative_path)
                    logger.warning(error_msg)
                else:
                    warnings.append(f"缺少可选文件: {relative_path}")
                continue
            
            # 文件存在，验证详细信息
            file_detail = self._validate_single_file(file_path, file_info, errors, warnings)
            file_details[relative_path] = file_detail
            logger.debug(f"验证文件: {relative_path} - {file_detail['status']}")
    
    def _validate_single_file(self, file_path: str, file_info: Dict[str, Any],
                            errors: List[str], warnings: List[str]) -> Dict[str, Any]:
        """验证单个文件"""
        detail = {
            'path': file_path,
            'exists': True,
            'size': 0,
            'status': 'valid'
        }
        
        try:
            # 获取文件大小
            file_size = os.path.getsize(file_path)
            detail['size'] = file_size
            
            # 检查文件大小
            min_size = file_info.get('min_size', 0)
            max_size = file_info.get('max_size', float('inf'))
            
            if file_size < min_size:
                error_msg = f"文件 {file_info['path']} 过小: {file_size} < {min_size}"
                errors.append(error_msg)
                detail['status'] = 'too_small'
            elif file_size > max_size:
                error_msg = f"文件 {file_info['path']} 过大: {file_size} > {max_size}"
                errors.append(error_msg)
                detail['status'] = 'too_large'
            
            # 检查扩展名
            expected_extensions = file_info.get('extensions', [])
            if expected_extensions:
                file_ext = Path(file_path).suffix.lower()
                if file_ext not in expected_extensions:
                    error_msg = f"文件 {file_info['path']} 扩展名不符合要求: {file_ext} not in {expected_extensions}"
                    warnings.append(error_msg)
                    detail['status'] = 'wrong_extension'
            
        except Exception as e:
            error_msg = f"验证文件 {file_info['path']} 时出错: {e}"
            errors.append(error_msg)
            detail['status'] = 'error'
        
        return detail
    
    def _check_extra_files(self, root_path: str, warnings: List[str], extra_files: List[str]):
        """检查额外文件"""
        # 获取所有预期的文件和目录
        expected_items = set()
        
        # 添加必需目录
        for dir_info in self.schema.get('required_directories', []):
            expected_items.add(dir_info['path'])
            for subdir_info in dir_info.get('subdirectories', []):
                expected_items.add(subdir_info['path'])
        
        # 添加必需文件
        for file_info in self.schema.get('required_files', []):
            expected_items.add(file_info['path'])
        for file_info in self.schema.get('optional_files', []):
            expected_items.add(file_info['path'])
        for file_info in self.schema.get('data_directory_files', []):
            expected_items.add(file_info['path'])
        for file_info in self.schema.get('info_directory_files', []):
            expected_items.add(file_info['path'])
        
        # 遍历实际文件
        try:
            for root, dirs, files in os.walk(root_path):
                for item in files + dirs:
                    relative_path = os.path.relpath(os.path.join(root, item), root_path)
                    relative_path = relative_path.replace('\\', '/')  # 统一路径分隔符
                    
                    if relative_path not in expected_items:
                        extra_files.append(relative_path)
            
            if extra_files:
                warnings.append(f"发现额外文件: {', '.join(extra_files[:10])}")
                
        except Exception as e:
            logger.error(f"检查额外文件时出错: {e}")
    
    def _validate_file_contents(self, root_path: str, errors: List[str], 
                              warnings: List[str], file_details: Dict[str, Dict[str, Any]]):
        """验证文件内容"""
        content_validation = self.schema.get('content_validation', {})
        
        # 验证JSON文件
        json_files = content_validation.get('json_files', [])
        for json_file_info in json_files:
            file_path = os.path.join(root_path, json_file_info['path'])
            if os.path.exists(file_path):
                self._validate_json_content(file_path, json_file_info, errors, warnings)
        
        # 验证YAML文件
        yaml_files = content_validation.get('yaml_files', [])
        for yaml_file_info in yaml_files:
            file_path = os.path.join(root_path, yaml_file_info['path'])
            if os.path.exists(file_path):
                self._validate_yaml_content(file_path, yaml_file_info, errors, warnings)
    
    def _validate_json_content(self, file_path: str, validation_info: Dict,
                             errors: List[str], warnings: List[str]):
        """验证JSON文件内容"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            required_keys = validation_info.get('required_keys', [])
            for key in required_keys:
                if key not in data:
                    error_msg = f"JSON文件 {validation_info['path']} 缺少必需字段: {key}"
                    errors.append(error_msg)
                    
        except json.JSONDecodeError as e:
            error_msg = f"JSON文件 {validation_info['path']} 格式错误: {e}"
            errors.append(error_msg)
        except Exception as e:
            error_msg = f"验证JSON文件 {validation_info['path']} 时出错: {e}"
            errors.append(error_msg)
    
    def _validate_yaml_content(self, file_path: str, validation_info: Dict,
                             errors: List[str], warnings: List[str]):
        """验证YAML文件内容"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            required_keys = validation_info.get('required_keys', [])
            for key in required_keys:
                if key not in data:
                    error_msg = f"YAML文件 {validation_info['path']} 缺少必需字段: {key}"
                    errors.append(error_msg)
                    
        except yaml.YAMLError as e:
            error_msg = f"YAML文件 {validation_info['path']} 格式错误: {e}"
            errors.append(error_msg)
        except Exception as e:
            error_msg = f"验证YAML文件 {validation_info['path']} 时出错: {e}"
            errors.append(error_msg)
    
    def _calculate_score(self, errors: List[str], warnings: List[str], 
                        missing_files: List[str], missing_directories: List[str]) -> float:
        """计算验证分数"""
        # 基础分数
        base_score = 100.0
        
        # 每个错误扣分更多
        error_penalty = len(errors) * 15
        
        # 每个警告扣分较少
        warning_penalty = len(warnings) * 3
        
        # 缺失文件和目录额外扣分
        missing_penalty = (len(missing_files) + len(missing_directories)) * 10
        
        # 计算最终分数
        final_score = max(0.0, base_score - error_penalty - warning_penalty - missing_penalty)
        
        return final_score
    
    def _determine_validity(self, validation_level: ValidationLevel, errors: List[str],
                          missing_files: List[str], missing_directories: List[str]) -> bool:
        """根据验证级别判断是否通过验证"""
        if validation_level == ValidationLevel.STRICT:
            # 严格模式：不允许任何错误或缺失
            return len(errors) == 0 and len(missing_files) == 0 and len(missing_directories) == 0
        
        elif validation_level == ValidationLevel.STANDARD:
            # 标准模式：允许少量缺失，但不能有严重错误
            critical_errors = [e for e in errors if 'JSON' in e or '过小' in e or '过大' in e]
            return len(critical_errors) == 0 and len(missing_files) <= 2
        
        else:  # LENIENT
            # 宽松模式：只要有基本的文件结构即可
            return len(errors) <= 5
    
    def _generate_summary(self, is_valid: bool, score: float, 
                         error_count: int, warning_count: int) -> str:
        """生成验证结果摘要"""
        status = "通过" if is_valid else "失败"
        return f"验证{status} - 得分: {score:.1f}/100, 错误: {error_count}, 警告: {warning_count}"
    
    def get_validation_report(self, result: ValidationResult) -> str:
        """生成详细的验证报告"""
        report_lines = []
        report_lines.append("=" * 60)
        report_lines.append("数据格式验证报告")
        report_lines.append("=" * 60)
        report_lines.append(f"验证结果: {'✅ 通过' if result.is_valid else '❌ 失败'}")
        report_lines.append(f"验证级别: {result.validation_level.value}")
        report_lines.append(f"验证得分: {result.score:.1f}/100")
        report_lines.append("")
        
        if result.errors:
            report_lines.append("🚫 错误:")
            for error in result.errors:
                report_lines.append(f"  - {error}")
            report_lines.append("")
        
        if result.warnings:
            report_lines.append("⚠️ 警告:")
            for warning in result.warnings:
                report_lines.append(f"  - {warning}")
            report_lines.append("")
        
        if result.missing_files:
            report_lines.append("📄 缺失文件:")
            for file in result.missing_files:
                report_lines.append(f"  - {file}")
            report_lines.append("")
        
        if result.missing_directories:
            report_lines.append("📁 缺失目录:")
            for directory in result.missing_directories:
                report_lines.append(f"  - {directory}")
            report_lines.append("")
        
        if result.extra_files:
            report_lines.append("📎 额外文件:")
            for file in result.extra_files[:10]:  # 最多显示10个
                report_lines.append(f"  - {file}")
            if len(result.extra_files) > 10:
                report_lines.append(f"  ... 还有 {len(result.extra_files) - 10} 个文件")
            report_lines.append("")
        
        report_lines.append("📋 总结:")
        report_lines.append(f"  {result.summary}")
        report_lines.append("=" * 60)
        
        return "\n".join(report_lines)