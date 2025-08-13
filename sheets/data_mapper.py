"""
数据映射器 - 统一处理ValidationResult到Sheets的数据转换

这个模块负责：
1. 定义标准的数据契约
2. 统一处理各种ValidationResult格式
3. 提供一致的sheets数据格式
4. 减少数据传递错误
"""

from typing import Dict, Any, Optional, Union
from datetime import datetime
from validation.base import ValidationResult


class SheetsDataMapper:
    """将ValidationResult统一映射为Sheets记录格式"""
    
    # 定义标准的sheets字段映射
    SHEETS_FIELDS = {
        # 基础字段
        'file_id': str,
        'file_name': str,
        'upload_time': str,
        'file_size': int,
        'file_type': str,
        'extract_status': str,
        'file_count': str,
        'process_time': datetime,
        
        # 验证字段
        'validation_score': str,
        'start_time': str,
        'duration': str,
        'location': str,
        
        # 场景字段
        'scene_type': str,
        'size_status': str,
        'pcd_scale': str,
        
        # Transient检测字段
        'transient_decision': str,
        'wdd': str,
        'wpo': str,
        'sai': str,
        
        # 其他字段
        'error_message': str,
        'notes': str
    }
    
    @classmethod
    def map_validation_result(cls, validation_result: Union[ValidationResult, Dict], 
                            base_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        将ValidationResult映射为标准的sheets记录
        
        Args:
            validation_result: ValidationResult对象或字典
            base_record: 基础记录信息（文件信息等）
            
        Returns:
            标准化的sheets记录
        """
        # 复制基础记录
        sheets_record = base_record.copy()
        
        if not validation_result:
            return cls._fill_default_values(sheets_record)
        
        # 提取基础验证信息
        sheets_record.update(cls._extract_basic_validation(validation_result))
        
        # 提取场景信息
        sheets_record.update(cls._extract_scene_info(validation_result))
        
        # 提取transient检测信息
        sheets_record.update(cls._extract_transient_info(validation_result))
        
        # 提取元数据信息
        sheets_record.update(cls._extract_metadata_info(validation_result))
        
        return sheets_record
    
    @classmethod
    def _extract_basic_validation(cls, validation_result: Union[ValidationResult, Dict]) -> Dict[str, Any]:
        """提取基础验证信息"""
        if isinstance(validation_result, dict):
            return {
                'validation_score': f"{validation_result.get('score', 0):.1f}/100",
            }
        else:
            return {
                'validation_score': f"{getattr(validation_result, 'score', 0):.1f}/100",
            }
    
    @classmethod
    def _extract_scene_info(cls, validation_result: Union[ValidationResult, Dict]) -> Dict[str, Any]:
        """提取场景相关信息 - 需要根据实际archive_handler实现调整"""
        # 这里需要根据实际的validation_result结构来提取
        # 目前由main.py处理，暂时返回空
        return {}
    
    @classmethod
    def _extract_transient_info(cls, validation_result: Union[ValidationResult, Dict]) -> Dict[str, Any]:
        """提取transient检测信息"""
        transient_info = {
            'transient_decision': 'N/A',
            'wdd': 'N/A',
            'wpo': 'N/A',
            'sai': 'N/A'
        }
        
        try:
            # 获取metadata
            if isinstance(validation_result, dict):
                metadata = validation_result.get('metadata', {})
            else:
                metadata = getattr(validation_result, 'metadata', {})
            
            if not metadata:
                return transient_info
            
            # 遵循正确的数据路径：metadata -> transient_validation -> transient_detection
            transient_validation = metadata.get('transient_validation', {})
            transient_detection = transient_validation.get('transient_detection', {})
            
            if transient_detection:
                transient_info['transient_decision'] = transient_detection.get('decision', 'N/A')
                
                metrics = transient_detection.get('metrics', {})
                if metrics:
                    wdd = metrics.get('WDD')
                    wpo = metrics.get('WPO')
                    sai = metrics.get('SAI')
                    
                    transient_info['wdd'] = f"{wdd:.3f}" if wdd is not None else 'N/A'
                    transient_info['wpo'] = f"{wpo:.1f}%" if wpo is not None else 'N/A'
                    transient_info['sai'] = f"{sai:.1f}%" if sai is not None else 'N/A'
        
        except Exception as e:
            print(f"Warning: Failed to extract transient info: {e}")
        
        return transient_info
    
    @classmethod
    def _extract_metadata_info(cls, validation_result: Union[ValidationResult, Dict]) -> Dict[str, Any]:
        """提取metadata中的其他信息（如时间、位置等）"""
        metadata_info = {
            'start_time': '',
            'duration': '',
            'location': ''
        }
        
        try:
            # 获取metadata
            if isinstance(validation_result, dict):
                metadata = validation_result.get('metadata', {})
            else:
                metadata = getattr(validation_result, 'metadata', {})
            
            if not metadata:
                return metadata_info
            
            # 提取时间和位置信息
            extracted_metadata = metadata.get('extracted_metadata', {})
            if extracted_metadata:
                metadata_info['start_time'] = extracted_metadata.get('start_time', '')
                metadata_info['duration'] = extracted_metadata.get('duration', '')
                
                location = extracted_metadata.get('location', {})
                if location:
                    lat = location.get('latitude', '')
                    lon = location.get('longitude', '')
                    if lat and lon:
                        metadata_info['location'] = f"{lat}, {lon}"
        
        except Exception as e:
            print(f"Warning: Failed to extract metadata info: {e}")
        
        return metadata_info
    
    @classmethod
    def _fill_default_values(cls, sheets_record: Dict[str, Any]) -> Dict[str, Any]:
        """为缺失的validation_result填充默认值"""
        defaults = {
            'validation_score': 'N/A (未验证)',
            'start_time': '',
            'duration': '',
            'location': '',
            'scene_type': 'unknown',
            'size_status': 'unknown',
            'pcd_scale': 'unknown',
            'transient_decision': 'N/A',
            'wdd': 'N/A',
            'wpo': 'N/A',
            'sai': 'N/A'
        }
        
        sheets_record.update(defaults)
        return sheets_record
    
    @classmethod
    def validate_record(cls, record: Dict[str, Any]) -> bool:
        """验证record是否包含所有必需字段"""
        required_fields = ['file_id', 'file_name']
        return all(field in record for field in required_fields)