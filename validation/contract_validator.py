"""
数据契约验证工具

这个工具用于验证ValidationResult和sheets记录是否符合数据契约，
帮助开发者在开发过程中早期发现问题。

使用方法：
1. 在validator开发时调用validate_validation_result()
2. 在sheets记录传递前调用validate_sheets_record()
3. 在CI/CD中运行全面验证检查
"""

from typing import Dict, Any, List, Optional, Union
import json
from pathlib import Path

from .data_contracts import (
    STANDARD_METADATA_FORMAT,
    SHEETS_COLUMNS_CONTRACT, 
    SheetsRecordContract,
    ValidationDecisionContract,
    validate_metadata_contract,
    validate_sheets_record_contract
)
from .base import ValidationResult


class ContractValidator:
    """数据契约验证器"""
    
    @staticmethod
    def validate_validation_result(result: ValidationResult, 
                                 expected_validator_name: str = None) -> List[str]:
        """
        验证ValidationResult是否符合契约
        
        Args:
            result: 要验证的ValidationResult
            expected_validator_name: 期望的validator名称
            
        Returns:
            违反契约的问题列表
        """
        issues = []
        
        # 基础类型检查
        if not isinstance(result, ValidationResult):
            issues.append(f"Expected ValidationResult, got {type(result)}")
            return issues
        
        # 必需字段检查
        if result.metadata is None:
            issues.append("ValidationResult.metadata cannot be None")
            return issues
        
        # metadata契约检查
        if expected_validator_name:
            metadata_issues = validate_metadata_contract(result.metadata, expected_validator_name)
            issues.extend(metadata_issues)
        
        # 分数范围检查
        if not (0.0 <= result.score <= 100.0):
            issues.append(f"Score must be 0.0-100.0, got {result.score}")
        
        # validator_type检查
        if not result.validator_type or result.validator_type == "unknown":
            issues.append("validator_type must be set and not 'unknown'")
        
        # 检查validator特定的metadata
        if expected_validator_name:
            validator_key = f"{expected_validator_name.lower()}_validation"
            if validator_key not in result.metadata:
                issues.append(f"Missing expected metadata key: {validator_key}")
            else:
                validator_data = result.metadata[validator_key]
                if not isinstance(validator_data, dict):
                    issues.append(f"Validator data must be dict: {validator_key}")
                else:
                    # 检查必需的子字段
                    required_fields = ["decision"]
                    for field in required_fields:
                        if field not in validator_data:
                            issues.append(f"Missing required field {field} in {validator_key}")
                        elif field == "decision" and validator_data[field] not in ValidationDecisionContract.ALL_DECISIONS:
                            issues.append(f"Invalid decision value: {validator_data[field]}")
        
        return issues
    
    @staticmethod  
    def validate_sheets_record(record: Dict[str, Any]) -> List[str]:
        """
        验证sheets记录是否符合契约
        
        Args:
            record: 要验证的sheets记录字典
            
        Returns:
            违反契约的问题列表
        """
        return validate_sheets_record_contract(record)
    
    @staticmethod
    def validate_sheets_headers_consistency() -> List[str]:
        """
        验证sheets headers与契约的一致性
        
        Returns:
            不一致的问题列表
        """
        issues = []
        
        try:
            from ..sheets.sheets_writer import SheetsWriter
            writer = SheetsWriter()
            
            # 检查headers数量
            expected_count = len(SHEETS_COLUMNS_CONTRACT)
            actual_count = len(writer.headers)
            if expected_count != actual_count:
                issues.append(f"Header count mismatch: expected {expected_count}, got {actual_count}")
            
            # 检查field_mapping一致性
            if hasattr(writer, 'field_mapping'):
                for field, index in writer.field_mapping.items():
                    if index >= len(writer.headers):
                        issues.append(f"field_mapping index out of range: {field} -> {index}")
                    
                    # 检查索引是否与契约一致
                    # 这里可以添加更详细的检查逻辑
            
        except ImportError as e:
            issues.append(f"Could not import SheetsWriter for validation: {e}")
        
        return issues
    
    @staticmethod
    def validate_data_flow(validation_result: ValidationResult, 
                          archive_result: Dict[str, Any],
                          sheets_record: Dict[str, Any]) -> List[str]:
        """
        验证完整的数据流契约
        
        Args:
            validation_result: 原始ValidationResult
            archive_result: archive_handler处理后的结果
            sheets_record: 传递给sheets的记录
            
        Returns:
            数据流问题列表
        """
        issues = []
        
        # 1. ValidationResult -> archive_result
        if 'data_validation' not in archive_result:
            issues.append("archive_result missing 'data_validation' key")
        else:
            data_validation = archive_result['data_validation']
            
            # 检查metadata是否完整传递
            if 'metadata' not in data_validation:
                issues.append("archive_result['data_validation'] missing 'metadata'")
            elif validation_result.metadata != data_validation['metadata']:
                issues.append("metadata not preserved in archive_result conversion")
        
        # 2. archive_result -> sheets_record
        if 'validation_result' not in sheets_record:
            issues.append("sheets_record missing 'validation_result' key")
        
        # 3. transient数据传递检查
        if validation_result.metadata:
            transient_data = validation_result.metadata.get('transient_validation', {}).get('transient_detection', {})
            if transient_data:
                # 检查transient字段是否正确传递到sheets_record
                transient_fields = ['transient_decision', 'wdd', 'wpo', 'sai']
                for field in transient_fields:
                    if field not in sheets_record or not sheets_record[field] or sheets_record[field] == 'N/A':
                        issues.append(f"Transient data not properly extracted to sheets_record: {field}")
        
        return issues
    
    @staticmethod
    def generate_contract_report(output_file: Optional[str] = None) -> str:
        """
        生成完整的契约验证报告
        
        Args:
            output_file: 可选的输出文件路径
            
        Returns:
            报告内容
        """
        report_lines = []
        report_lines.append("=== 数据契约验证报告 ===")
        report_lines.append("")
        
        # 1. Headers一致性检查
        report_lines.append("1. Sheets Headers一致性检查:")
        header_issues = ContractValidator.validate_sheets_headers_consistency()
        if header_issues:
            for issue in header_issues:
                report_lines.append(f"   ❌ {issue}")
        else:
            report_lines.append("   ✅ Headers与契约一致")
        report_lines.append("")
        
        # 2. 契约定义摘要
        report_lines.append("2. 数据契约定义摘要:")
        report_lines.append(f"   - Sheets列数: {len(SHEETS_COLUMNS_CONTRACT)}")
        report_lines.append(f"   - 支持的决策值: {', '.join(ValidationDecisionContract.ALL_DECISIONS)}")
        report_lines.append("")
        
        # 3. 推荐的验证流程
        report_lines.append("3. 推荐的开发流程:")
        report_lines.append("   a. 使用validator_template.py创建新的validator")
        report_lines.append("   b. 在validator中调用validate_validation_result()进行自检")
        report_lines.append("   c. 如需sheets显示，同时更新所有相关组件")
        report_lines.append("   d. 运行contract_validator进行全面检查")
        report_lines.append("")
        
        # 4. 常见问题和解决方案
        report_lines.append("4. 常见问题和解决方案:")
        report_lines.append("   - metadata缺失: 确保在ValidationResult中设置完整的metadata")
        report_lines.append("   - 字段映射错误: 检查sheets_writer.py中的field_mapping")
        report_lines.append("   - 数据路径错误: 遵循metadata.{validator}_validation.{field}格式")
        report_lines.append("   - 决策值无效: 只使用ValidationDecisionContract中定义的值")
        
        report_content = "\n".join(report_lines)
        
        if output_file:
            Path(output_file).write_text(report_content, encoding='utf-8')
        
        return report_content
    
    @staticmethod
    def debug_metadata_structure(metadata: Dict[str, Any], validator_name: str = None) -> None:
        """
        调试metadata结构，打印详细信息
        
        Args:
            metadata: 要调试的metadata
            validator_name: validator名称（用于特定检查）
        """
        print("=== Metadata结构调试 ===")
        print(f"类型: {type(metadata)}")
        print(f"顶级键: {list(metadata.keys()) if isinstance(metadata, dict) else 'Not a dict'}")
        print("")
        
        if not isinstance(metadata, dict):
            print("❌ metadata必须是字典类型")
            return
        
        # 检查标准字段
        standard_fields = ["manager_version", "selected_validator", "auto_selected"]
        for field in standard_fields:
            if field in metadata:
                print(f"✅ {field}: {metadata[field]}")
            else:
                print(f"❌ 缺失标准字段: {field}")
        
        print("")
        
        # 检查validator特定字段
        if validator_name:
            validator_key = f"{validator_name.lower()}_validation"
            if validator_key in metadata:
                print(f"✅ 找到validator数据: {validator_key}")
                validator_data = metadata[validator_key]
                if isinstance(validator_data, dict):
                    print(f"   子键: {list(validator_data.keys())}")
                    if 'decision' in validator_data:
                        decision = validator_data['decision']
                        if decision in ValidationDecisionContract.ALL_DECISIONS:
                            print(f"   ✅ decision: {decision}")
                        else:
                            print(f"   ❌ 无效decision: {decision}")
                else:
                    print(f"   ❌ validator数据不是字典: {type(validator_data)}")
            else:
                print(f"❌ 缺失validator字段: {validator_key}")
        
        print("")
        print("完整结构:")
        print(json.dumps(metadata, indent=2, ensure_ascii=False, default=str))


# CLI入口
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "report":
            output_file = sys.argv[2] if len(sys.argv) > 2 else None
            report = ContractValidator.generate_contract_report(output_file)
            print(report)
        else:
            print("Usage: python contract_validator.py report [output_file]")
    else:
        # 默认生成报告
        report = ContractValidator.generate_contract_report()
        print(report)