"""
验证系统数据契约定义

这个模块定义了整个验证系统的数据格式契约，确保所有组件使用相同的数据结构。

数据流向：
ValidationResult → archive_handler → main.py → sheets_writer

重要规则：
1. 所有validator必须遵循STANDARD_METADATA_FORMAT
2. 所有sheets字段必须在SHEETS_RECORD_CONTRACT中定义
3. 修改任何契约前必须更新所有相关组件
"""

from typing import Dict, Any, Optional, List, Union, TypedDict
from datetime import datetime


class ValidationMetricsContract(TypedDict, total=False):
    """
    验证指标的标准格式
    
    所有validator生成的metrics都应该遵循这个格式
    """
    # 数值类型指标 - 使用float类型，sheets显示时会格式化
    score: float                    # 验证得分 0.0-100.0
    confidence: Optional[float]     # 置信度 0.0-1.0
    
    # 计数类型指标
    total_items: Optional[int]      # 总项目数
    valid_items: Optional[int]      # 有效项目数
    error_items: Optional[int]      # 错误项目数
    
    # 百分比指标 - 存储为0.0-100.0的float值
    success_rate: Optional[float]   # 成功率百分比
    coverage: Optional[float]       # 覆盖率百分比
    
    # 密度/频率指标 - 用于transient detection等
    density: Optional[float]        # 密度值
    frequency: Optional[float]      # 频率值


class ValidationDecisionContract:
    """
    验证决策的标准值
    
    所有validator的decision字段必须使用这些值之一
    """
    PASS = "PASS"                   # 验证通过
    FAIL = "FAIL"                   # 验证失败
    NEED_REVIEW = "NEED_REVIEW"     # 需要人工审查
    ERROR = "ERROR"                 # 验证过程出错
    SKIP = "SKIP"                   # 跳过验证
    
    # 所有可能的决策值
    ALL_DECISIONS = [PASS, FAIL, NEED_REVIEW, ERROR, SKIP]


class ValidatorDataContract(TypedDict, total=False):
    """
    单个validator结果的标准格式
    
    所有validator在metadata中存储的数据都应该遵循这个格式：
    metadata[validator_name] = ValidatorDataContract
    """
    # 核心验证结果
    decision: str                           # 必须是ValidationDecisionContract中的值
    confidence: Optional[float]             # 决策置信度 0.0-1.0
    timestamp: str                          # ISO格式时间戳
    
    # 详细指标
    metrics: Optional[ValidationMetricsContract]  # 详细数值指标
    
    # 问题和建议
    problems_found: List[str]               # 发现的问题列表
    suggestions: Optional[List[str]]        # 改进建议
    
    # 处理信息
    processing_time_ms: Optional[float]     # 处理时间（毫秒）
    items_processed: Optional[int]          # 处理的项目数
    
    # 特定于validator的额外数据
    details: Optional[Dict[str, Any]]       # validator特有的详细信息


# 标准的metadata格式 - 这是所有ValidationResult.metadata必须遵循的格式
STANDARD_METADATA_FORMAT = {
    # 基础信息（由validation manager添加）
    "manager_version": "str - 验证管理器版本",
    "selected_validator": "str - 使用的验证器名称",
    "auto_selected": "bool - 是否自动选择验证器",
    
    # 提取的元数据信息（从数据包中解析）
    "extracted_metadata": {
        "start_time": "str - 开始时间",
        "duration": "str - 持续时间",
        "location": {
            "latitude": "str - 纬度",
            "longitude": "str - 经度"
        },
        "parsed_successfully": "bool - 是否解析成功",
        "duration_status": "str - 持续时间状态（optimal/warning_long/error等）",
        "duration_seconds": "int - 持续时间（秒）"
    },
    
    # ===== VALIDATOR结果区域 =====
    # 每个validator都应该在这里添加自己的结果，格式为：
    # "validator_name_validation": ValidatorDataContract
    
    # MetaCam基础格式验证结果
    "metacam_validation": "ValidatorDataContract - MetaCam格式验证结果",
    
    # 移动障碍物检测结果
    "transient_validation": {
        "transient_detection": "ValidatorDataContract - transient检测的核心结果",
        "camera_info": "Dict - 相机信息",
        "detection_results": "Dict - 按相机分组的检测结果", 
        "processing_details": "Dict - 处理详情",
        "statistics": "Dict - 统计信息"
    },
    
    # PCD点云验证结果
    "pcd_validation": "ValidatorDataContract - PCD点云验证结果",
    
    # 场景验证结果
    "scene_validation": "ValidatorDataContract - 场景验证结果",
    
    # 文件大小验证结果
    "size_validation": "ValidatorDataContract - 文件大小验证结果",
    
    # 流水线验证组合结果（用于多validator组合）
    "validation_pipeline": {
        "base_validation": {
            "score": "float - 基础验证得分",
            "is_valid": "bool - 基础验证是否通过",
            "summary": "str - 基础验证摘要",
            "errors": "int - 错误数量",
            "warnings": "int - 警告数量"
        },
        "transient_validation": {
            "score": "float - 移动障碍物检测得分",
            "is_valid": "bool - 移动障碍物检测是否通过",
            "summary": "str - 移动障碍物检测摘要",
            "errors": "int - 错误数量",
            "warnings": "int - 警告数量"
        },
        "combined_score": "float - 组合得分",
        "weights": {
            "base": "float - 基础验证权重",
            "transient": "float - 移动障碍物检测权重"
        }
    }
}


class SheetsRecordContract(TypedDict, total=False):
    """
    Google Sheets记录的标准格式
    
    这定义了main.py传递给sheets_writer的record结构
    """
    # ===== 基础文件信息 =====
    file_id: str                    # Google Drive文件ID
    file_name: str                  # 文件名
    upload_time: str                # 上传时间
    file_size: int                  # 文件大小（字节）
    file_type: str                  # MIME类型
    
    # ===== 处理信息 =====
    extract_status: str             # 解压状态
    file_count: Union[str, int]     # 文件数量
    process_time: datetime          # 处理时间
    
    # ===== 验证结果 =====
    validation_score: str           # 验证得分（格式化后的字符串）
    validation_result: Union[Dict, Any]  # 完整的验证结果对象
    
    # ===== 元数据信息 =====
    start_time: str                 # 记录开始时间
    duration: str                   # 持续时间
    location: str                   # 地理位置
    
    # ===== 场景信息 =====
    scene_type: str                 # 场景类型（outdoor/indoor/unknown等）
    size_status: str                # 大小状态
    pcd_scale: str                  # PCD尺度信息
    
    # ===== TRANSIENT检测信息 =====
    # 注意：这些字段名与sheets header中的字段对应
    transient_decision: str         # 移动障碍物检测决策 -> "Transient Detection"列
    wdd: str                       # 加权检测密度 -> "WDD"列
    wpo: str                       # 加权人员占用率 -> "WPO"列  
    sai: str                       # 场景活动指数 -> "SAI"列
    
    # ===== 状态信息（用于格式化）=====
    size_status_level: str          # 大小状态级别（用于颜色编码）
    pcd_scale_status: str          # PCD尺度状态（用于颜色编码）
    
    # ===== 其他信息 =====
    error_message: str             # 错误信息
    notes: str                     # 备注信息


# Google Sheets列定义 - 必须与sheets_writer.py中的headers保持一致
SHEETS_COLUMNS_CONTRACT = [
    # 索引:  列名                           对应SheetsRecord字段         数据类型     说明
    #  0     'File ID'                     file_id                     str         Google Drive文件ID
    #  1     'File Name'                   file_name                   str         文件名
    #  2     'Upload Time'                 upload_time                 str         上传时间
    #  3     'File Size'                   file_size -> 格式化          str         文件大小（MB格式）
    #  4     'File Type'                   file_type                   str         MIME类型
    #  5     'Extract Status'              extract_status              str         解压状态
    #  6     'File Count'                  file_count                  str/int     文件数量
    #  7     'Process Time'                process_time -> 格式化       str         处理时间
    #  8     'Validation Score'            validation_score            str         验证得分
    #  9     'Start Time'                  start_time                  str         开始时间
    # 10     'Duration'                    duration                    str         持续时间
    # 11     'Location'                    location                    str         地理位置
    # 12     'Scene Type'                  scene_type                  str         场景类型
    # 13     'Size Status'                 size_status                 str         大小状态
    # 14     'PCD Scale'                   pcd_scale                   str         PCD尺度
    # 15     'Transient Detection'         transient_decision          str         移动障碍物检测决策
    # 16     'Weighted Detection Density'  wdd                         str         加权检测密度 (WDD)
    # 17     'Weighted Person Occupancy'   wpo                         str         加权人员占用率 (WPO)
    # 18     'Scene Activity Index'        sai                         str         场景活动指数 (SAI)
    # 19     'Error Message'               error_message               str         错误信息
    # 20     'Notes'                       notes                       str         备注信息
]


def validate_metadata_contract(metadata: Dict[str, Any], validator_name: str) -> List[str]:
    """
    验证metadata是否符合契约要求
    
    Args:
        metadata: 要验证的metadata字典
        validator_name: 验证器名称
        
    Returns:
        违反契约的问题列表，空列表表示符合契约
    """
    issues = []
    
    if not isinstance(metadata, dict):
        issues.append(f"Metadata must be a dictionary, got {type(metadata)}")
        return issues
    
    # 检查必需的顶级字段
    required_top_level = ["manager_version", "selected_validator", "auto_selected"]
    for field in required_top_level:
        if field not in metadata:
            issues.append(f"Missing required top-level field: {field}")
    
    # 检查validator特定的字段
    validator_key = f"{validator_name}_validation"
    if validator_key not in metadata:
        issues.append(f"Missing validator result: {validator_key}")
    else:
        validator_data = metadata[validator_key]
        if not isinstance(validator_data, dict):
            issues.append(f"Validator data must be a dictionary: {validator_key}")
        else:
            # 检查核心字段
            if "decision" not in validator_data:
                issues.append(f"Missing decision in {validator_key}")
            elif validator_data["decision"] not in ValidationDecisionContract.ALL_DECISIONS:
                issues.append(f"Invalid decision value in {validator_key}: {validator_data['decision']}")
    
    return issues


def validate_sheets_record_contract(record: Dict[str, Any]) -> List[str]:
    """
    验证sheets record是否符合契约要求
    
    Args:
        record: 要验证的record字典
        
    Returns:
        违反契约的问题列表，空列表表示符合契约
    """
    issues = []
    
    if not isinstance(record, dict):
        issues.append(f"Record must be a dictionary, got {type(record)}")
        return issues
    
    # 检查必需字段
    required_fields = ["file_id", "file_name"]
    for field in required_fields:
        if field not in record:
            issues.append(f"Missing required field: {field}")
    
    # 检查transient字段的完整性
    transient_fields = ["transient_decision", "wdd", "wpo", "sai"]
    transient_present = [field for field in transient_fields if field in record and record[field] not in ['', 'N/A', None]]
    
    # 如果有部分transient字段，应该全部都有
    if transient_present and len(transient_present) != len(transient_fields):
        issues.append(f"Incomplete transient data: have {transient_present}, missing {set(transient_fields) - set(transient_present)}")
    
    return issues