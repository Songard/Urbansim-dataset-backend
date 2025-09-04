"""
新Validator开发模板

这个模板确保所有新的validator都遵循数据契约，避免数据传递错误。

使用方法：
1. 复制这个文件并重命名为你的validator
2. 替换所有的"NewValidator"为你的validator名称
3. 实现具体的验证逻辑
4. 更新sheets相关组件（参考VALIDATOR_DEVELOPMENT_GUIDE.md）
"""

import os
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

from .base import BaseValidator, ValidationResult, ValidationLevel
from .data_contracts import ValidationDecisionContract, validate_metadata_contract
from utils.logger import get_logger

logger = get_logger(__name__)


class NewValidator(BaseValidator):
    """
    新验证器模板
    
    ===== 数据契约说明 =====
    这个validator必须返回符合以下契约的ValidationResult：
    
    1. metadata结构：
    {
        "newvalidator_validation": {
            "decision": str,              # 来自ValidationDecisionContract
            "confidence": float,          # 0.0-1.0
            "timestamp": str,             # ISO格式
            "metrics": {
                "custom_metric1": float,  # 你的自定义指标
                "custom_metric2": int,
                # ... 更多指标
            },
            "problems_found": List[str],
            "processing_time_ms": float,
            "details": {
                # validator特定的详细信息
            }
        }
    }
    
    2. 如果需要在sheets中显示数据，必须同时更新：
       - validation/data_contracts.py (SheetsRecordContract)
       - sheets/sheets_writer.py (headers, field_mapping)  
       - sheets/data_mapper.py (提取逻辑)
       - main.py (sheets_record字段)
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        # 重要：validator_type必须与metadata键对应
        self.validator_type = "NewValidator"
        
        # 你的初始化代码
        self.custom_config = config.get('custom_setting', 'default_value') if config else 'default_value'
    
    def get_supported_formats(self) -> List[str]:
        """定义这个validator支持的格式"""
        return ["your_format", "another_format"]
    
    def validate(self, target_path: str, validation_level: ValidationLevel = ValidationLevel.STANDARD) -> ValidationResult:
        """
        执行验证逻辑
        
        ===== 重要：必须遵循数据契约 =====
        """
        logger.info(f"Starting NewValidator validation for: {target_path}")
        start_time = datetime.now()
        
        # 初始化结果容器
        errors = []
        warnings = []
        missing_files = []
        missing_directories = []
        extra_files = []
        file_details = {}
        
        try:
            # ===== 1. 执行你的验证逻辑 =====
            validation_successful = self._perform_custom_validation(target_path)
            custom_metrics = self._calculate_custom_metrics(target_path)
            
            # ===== 2. 根据结果确定决策 =====
            if validation_successful:
                decision = ValidationDecisionContract.PASS
                confidence = 0.95
            else:
                decision = ValidationDecisionContract.FAIL
                confidence = 0.80
                errors.append("Custom validation failed")
            
            # ===== 3. 计算处理时间 =====
            processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            # ===== 4. 构建符合契约的metadata =====
            metadata = {
                # 重要：键名必须是 {validator_type.lower()}_validation
                "newvalidator_validation": {
                    "decision": decision,                    # 必须来自ValidationDecisionContract
                    "confidence": confidence,               # 0.0-1.0
                    "timestamp": datetime.now().isoformat(), # ISO格式时间戳
                    "metrics": {
                        # 你的自定义指标 - 这些可以在sheets中显示
                        "custom_score": custom_metrics.get('score', 0.0),
                        "items_processed": custom_metrics.get('count', 0),
                        "success_rate": custom_metrics.get('success_rate', 0.0),
                        # 添加更多你需要的指标
                    },
                    "problems_found": errors + warnings,   # 发现的所有问题
                    "processing_time_ms": processing_time_ms,
                    "details": {
                        # validator特定的详细信息
                        "config_used": self.custom_config,
                        "target_path": target_path,
                        # 添加更多详细信息
                    }
                }
            }
            
            # ===== 5. 验证metadata契约 =====
            contract_issues = validate_metadata_contract(metadata, "NewValidator")
            if contract_issues:
                logger.warning(f"Metadata contract violations: {contract_issues}")
                errors.extend([f"Contract violation: {issue}" for issue in contract_issues])
            
            # ===== 6. 计算最终分数 =====
            score = self._calculate_final_score(custom_metrics, len(errors), len(warnings))
            
            # ===== 7. 确定最终有效性 =====
            is_valid = (decision == ValidationDecisionContract.PASS and 
                       len(errors) == 0 and 
                       score >= self._get_minimum_score(validation_level))
            
            # ===== 8. 生成摘要 =====
            summary = self._generate_summary(is_valid, decision, score, len(errors), len(warnings))
            
            # ===== 9. 返回ValidationResult =====
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
                summary=summary,
                validator_type=self.validator_type,
                metadata=metadata  # 符合契约的metadata
            )
            
            logger.info(f"NewValidator validation completed: {summary}")
            return result
            
        except Exception as e:
            # 异常处理 - 返回ERROR决策
            error_msg = f"NewValidator validation exception: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
            
            # 异常情况下的metadata
            metadata = {
                "newvalidator_validation": {
                    "decision": ValidationDecisionContract.ERROR,
                    "confidence": 0.0,
                    "timestamp": datetime.now().isoformat(),
                    "metrics": {},
                    "problems_found": [error_msg],
                    "processing_time_ms": (datetime.now() - start_time).total_seconds() * 1000,
                    "details": {"exception": str(e)}
                }
            }
            
            return ValidationResult(
                is_valid=False,
                validation_level=validation_level,
                score=0.0,
                errors=errors,
                warnings=warnings,
                missing_files=missing_files,
                missing_directories=missing_directories,
                extra_files=extra_files,
                file_details=file_details,
                summary=f"NewValidator FAILED - {error_msg}",
                validator_type=self.validator_type,
                metadata=metadata
            )
    
    def _perform_custom_validation(self, target_path: str) -> bool:
        """
        执行你的自定义验证逻辑
        
        Returns:
            bool: 验证是否成功
        """
        # TODO: 实现你的验证逻辑
        # 例如：检查文件存在性、格式、内容等
        
        # 示例逻辑
        if os.path.exists(target_path):
            # 执行一些检查
            return True
        else:
            return False
    
    def _calculate_custom_metrics(self, target_path: str) -> Dict[str, Any]:
        """
        计算你的自定义指标
        
        Returns:
            Dict: 包含各种指标的字典
        """
        # TODO: 实现你的指标计算
        # 这些指标可以在sheets中显示
        
        return {
            'score': 85.5,
            'count': 10,
            'success_rate': 95.0
            # 添加更多指标
        }
    
    def _calculate_final_score(self, metrics: Dict[str, Any], error_count: int, warning_count: int) -> float:
        """计算最终分数"""
        base_score = metrics.get('score', 0.0)
        
        # 根据错误和警告调整分数
        penalty = error_count * 10 + warning_count * 3
        final_score = max(0.0, base_score - penalty)
        
        return final_score
    
    def _get_minimum_score(self, validation_level: ValidationLevel) -> float:
        """根据验证级别返回最低分数要求"""
        if validation_level == ValidationLevel.STRICT:
            return 90.0
        elif validation_level == ValidationLevel.STANDARD:
            return 70.0
        else:  # LENIENT
            return 50.0
    
    def _generate_summary(self, is_valid: bool, decision: str, score: float, 
                         error_count: int, warning_count: int) -> str:
        """生成验证摘要"""
        status = "PASS" if is_valid else "FAIL"
        return (f"NewValidator {status} - Score: {score:.1f}/100, "
                f"Decision: {decision}, Errors: {error_count}, Warnings: {warning_count}")


