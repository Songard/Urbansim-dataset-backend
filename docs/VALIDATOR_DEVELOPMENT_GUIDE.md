# Validator开发指南

本指南帮助开发者安全地添加新的验证器，避免数据传递错误和sheets更新问题。

## 常见错误分析

### 1. 数据传递链断裂
**问题**：ValidationResult → archive_handler → main.py → sheets_writer 的数据传递链条脆弱
**原因**：每一层都有自己的数据格式转换，缺乏统一标准

### 2. 数据路径错误  
**问题**：sheets_writer在错误的metadata路径中查找数据
**原因**：缺乏明确的数据结构文档

### 3. 字段映射不一致
**问题**：ValidationResult中的字段名与sheets中的字段名不匹配
**原因**：缺乏统一的字段映射规范

## 安全开发流程

### Step 1: 设计Validator
```python
class NewValidator(BaseValidator):
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.validator_type = "NewValidator"
    
    def validate(self, target_path: str, validation_level: ValidationLevel) -> ValidationResult:
        # 实现验证逻辑
        # 重要：确保metadata结构遵循标准格式
        metadata = {
            'new_validation': {  # 使用描述性的顶级键
                'specific_data': {   # 具体的数据结构
                    'decision': 'PASS/FAIL/NEED_REVIEW',
                    'metrics': {
                        'metric1': 0.5,
                        'metric2': 10.2
                    },
                    'details': {...}
                }
            },
            'other_standard_fields': {...}
        }
        
        return ValidationResult(
            is_valid=True,
            validation_level=validation_level,
            score=85.0,
            errors=[],
            warnings=[],
            metadata=metadata,  # 确保metadata完整
            # ... 其他字段
        )
```

### Step 2: 更新数据映射器
在 `sheets/data_mapper.py` 中添加提取逻辑：

```python
@classmethod
def _extract_new_validation_info(cls, validation_result):
    """提取新验证器的信息"""
    new_info = {
        'new_metric1': 'N/A',
        'new_metric2': 'N/A'
    }
    
    try:
        metadata = cls._get_metadata(validation_result)
        if not metadata:
            return new_info
        
        # 遵循标准路径：metadata -> new_validation -> specific_data
        new_validation = metadata.get('new_validation', {})
        specific_data = new_validation.get('specific_data', {})
        
        if specific_data:
            metrics = specific_data.get('metrics', {})
            new_info['new_metric1'] = f"{metrics.get('metric1', 0):.2f}"
            new_info['new_metric2'] = f"{metrics.get('metric2', 0):.1f}"
    
    except Exception as e:
        print(f"Warning: Failed to extract new validation info: {e}")
    
    return new_info

# 在 map_validation_result 中调用
@classmethod
def map_validation_result(cls, validation_result, base_record):
    sheets_record = base_record.copy()
    
    if not validation_result:
        return cls._fill_default_values(sheets_record)
    
    # 现有的提取方法
    sheets_record.update(cls._extract_basic_validation(validation_result))
    sheets_record.update(cls._extract_transient_info(validation_result))
    
    # 添加新的提取方法
    sheets_record.update(cls._extract_new_validation_info(validation_result))
    
    return sheets_record
```

### Step 3: 更新Sheets Header
在 `sheets/sheets_writer.py` 中：

```python
def __init__(self):
    # 更新headers（注意：WDD/WPO/SAI已改为全称）
    self.headers = [
        # ... 现有headers
        'Weighted Detection Density', 'Weighted Person Occupancy', 'Scene Activity Index',
        'New Metric 1', 'New Metric 2',  # 添加新字段
        'Error Message', 'Notes'
    ]
    
    # 更新字段映射
    self.field_mapping = {
        # ... 现有映射
        'wdd': 16,          # Weighted Detection Density
        'wpo': 17,          # Weighted Person Occupancy  
        'sai': 18,          # Scene Activity Index
        'new_metric1': 19,  # 新字段索引
        'new_metric2': 20,  # 新字段索引
        'error_message': 21,  # 更新后续索引
        'notes': 22
    }
```

### Step 4: 更新Archive Handler (如果需要)
如果新的validator需要在archive validation中使用：

```python
# 确保metadata被保存
result['data_validation'] = {
    'is_valid': validation_result.is_valid,
    'score': validation_result.score,
    'errors': validation_result.errors,
    'warnings': validation_result.warnings,
    'summary': validation_result.summary,
    'validator_type': validation_result.validator_type,
    'metadata': validation_result.metadata  # 重要：保存完整的metadata
}
```

### Step 5: 测试检查清单

- [ ] ValidationResult.metadata结构正确
- [ ] 数据映射器能正确提取数据  
- [ ] Sheets字段映射正确
- [ ] 新headers与field_mapping一致
- [ ] 测试各种ValidationResult格式（字典/对象）
- [ ] 测试缺失数据的fallback处理

## 最佳实践

### 1. 使用统一的数据路径约定
```python
metadata = {
    'validator_name': {           # 使用validator名称作为顶级键
        'primary_result': {       # 主要结果
            'decision': str,
            'metrics': dict,
            'details': dict
        },
        'secondary_data': {...}   # 次要数据
    }
}
```

### 2. 总是提供fallback值
```python
# 好的做法
new_metric = metrics.get('new_metric', 0) if metrics else 0

# 坏的做法  
new_metric = metrics['new_metric']  # 可能KeyError
```

### 3. 使用类型提示
```python
def extract_metrics(validation_result: Union[ValidationResult, Dict]) -> Dict[str, str]:
    """明确参数和返回值类型"""
    pass
```

### 4. 添加调试日志
```python
logger.debug(f"Extracting data from path: metadata.{validator_name}.{data_key}")
logger.debug(f"Extracted metrics: {metrics}")
```

### 5. 单元测试
为每个新的数据提取方法编写测试：

```python
def test_extract_new_validation_info():
    # 测试正常情况
    validation_result = create_mock_validation_result()
    info = SheetsDataMapper._extract_new_validation_info(validation_result)
    assert info['new_metric1'] != 'N/A'
    
    # 测试异常情况
    info = SheetsDataMapper._extract_new_validation_info(None)
    assert info['new_metric1'] == 'N/A'
```

## 调试工具

### 启用详细日志
```python
# 在main.py中添加
logger.setLevel('DEBUG')
```

### 数据结构检查工具
```python
def debug_validation_structure(validation_result):
    """调试ValidationResult的结构"""
    if isinstance(validation_result, dict):
        print("Dict keys:", list(validation_result.keys()))
        metadata = validation_result.get('metadata', {})
    else:
        print("Object attributes:", dir(validation_result))
        metadata = getattr(validation_result, 'metadata', {})
    
    if metadata:
        print("Metadata keys:", list(metadata.keys()))
        for key, value in metadata.items():
            print(f"  {key}: {type(value)}")
```

## 错误预防检查清单

在添加新validator前，请检查：

- [ ] 我是否理解了完整的数据传递链条？
- [ ] 我是否在所有必要的地方添加了新字段？
- [ ] 我是否测试了数据缺失的情况？
- [ ] 我是否更新了相关的文档？
- [ ] 我是否添加了适当的错误处理？
- [ ] 我是否与现有的字段命名保持一致？

遵循这个指南可以大大减少添加新validator时的错误概率。