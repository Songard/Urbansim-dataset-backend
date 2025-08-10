# 文件结构和命名规范检查实现完成

## 功能概述

已成功实现文件结构和命名规范检查功能，包括：

1. **文件命名格式验证**：识别Indoor/I和Outdoor/O开头的文件
2. **文件大小合理性检查**：验证解压后文件大小是否在1GB-3GB范围内
3. **Google Sheets集成**：添加场景类型和大小状态字段
4. **完整系统集成**：新功能已集成到现有文件处理流程中

## 实现详情

### 1. 命名格式验证（utils/validators.py）

#### `validate_scene_naming(file_name: str)`
- **功能**：验证文件命名格式并确定场景类型
- **支持格式**：
  - **Indoor类型**：`Indoor*`, `indoor*`, `INDOOR*`, `I*`, `i*`
  - **Outdoor类型**：`Outdoor*`, `outdoor*`, `OUTDOOR*`, `O*`, `o*`
- **返回值**：
  ```python
  {
      'is_valid_format': bool,  # 命名格式是否正确
      'scene_type': str,        # 'indoor', 'outdoor', 'unknown'
      'detected_prefix': str,   # 检测到的前缀
      'error_message': str      # 错误信息（如果有）
  }
  ```

### 2. 文件大小验证（utils/validators.py）

#### `validate_extracted_file_size(total_size_bytes: int)`
- **功能**：验证解压后文件大小合理性
- **合理范围**：1GB ≤ 文件大小 ≤ 3GB
- **状态分类**：
  - `optimal`：1GB-3GB，最佳范围
  - `warning_small`：0.8GB-1GB，警告但可接受
  - `warning_large`：3GB-3.5GB，警告但可接受
  - `error_too_small`：<0.5GB，异常小
  - `error_too_large`：>6GB，异常大
- **返回值**：
  ```python
  {
      'is_valid_size': bool,     # 大小是否合理
      'size_status': str,        # 状态分类
      'size_mb': float,          # 大小（MB）
      'size_gb': float,          # 大小（GB）
      'error_message': str       # 错误信息（如果有）
  }
  ```

### 3. Google Sheets集成（sheets/sheets_writer.py）

#### 新增字段
- **Scene Type**：场景类型（indoor/outdoor/unknown）
- **Size Status**：大小状态（optimal/warning_small/warning_large/error_too_small/error_too_large）

#### 表头更新
```python
self.headers = [
    'File ID', 'File Name', 'Upload Time', 'File Size', 'File Type',
    'Extract Status', 'File Count', 'Process Time', 'Validation Score', 
    'Start Time', 'Duration', 'Location', 'Scene Type', 'Size Status', 
    'Error Message', 'Notes'
]
```

### 4. 压缩文件处理集成（processors/archive_handler.py）

#### 验证流程集成
1. **文件命名验证**：基于压缩文件名进行场景类型判断（警告级别）
2. **文件大小验证**：基于解压后总文件大小进行合理性检查
3. **综合验证结果**：数据格式 AND 文件大小（场景命名为警告级别，不影响整体结果）
4. **详细日志记录**：所有验证步骤都有相应的日志输出

#### 新增返回字段
```python
result = {
    'is_valid': bool,           # 综合验证结果
    'format': str,              # 压缩格式
    'file_count': int,          # 文件数量
    'total_size': int,          # 解压后总大小
    'file_list': list,          # 文件列表
    'error': str,               # 错误信息
    'data_validation': dict,    # 数据格式验证结果
    'scene_validation': dict,   # 场景命名验证结果
    'size_validation': dict     # 文件大小验证结果
}
```

## 测试验证

### 单元测试（test_naming_validation.py）
- ✅ 场景命名验证：21/21 测试通过
- ✅ 文件大小验证：10/10 测试通过

### 集成测试（integration_test.py）
- ✅ 压缩文件验证完整流程
- ✅ 验证结果正确传递到记录数据
- ✅ Google Sheets字段正确设置

### 功能演示（demo_validation.py）
- ✅ 场景命名格式演示
- ✅ 文件大小验证演示
- ✅ 详细功能说明

## 使用示例

### 基本使用
```python
from utils.validators import validate_scene_naming, validate_extracted_file_size

# 场景命名验证
result = validate_scene_naming("Indoor_scene_001.zip")
print(f"场景类型: {result['scene_type']}")  # indoor

# 文件大小验证 
size_result = validate_extracted_file_size(2 * 1024**3)  # 2GB
print(f"大小状态: {size_result['size_status']}")  # optimal
```

### 集成使用
```python
from processors.archive_handler import ArchiveHandler

handler = ArchiveHandler()
info = handler.get_archive_info("Indoor_test.zip")

print(f"场景类型: {info['scene_type']}")      # indoor
print(f"大小状态: {info['size_status']}")     # optimal
print(f"验证结果: {info['validation_result']['is_valid']}")  # True/False
```

## 日志输出示例

```
[INFO] 场景命名验证结果: indoor - 
[INFO] 文件大小验证结果: 1.953GB - optimal - 
[INFO] 场景命名验证通过: 类型为 indoor
[INFO] 文件大小验证通过: 1.953GB (optimal)
[WARNING] 场景命名警告: 场景类型未知: 建议以Indoor/I或Outdoor/O开头以便自动识别
[WARNING] 文件大小验证警告: 文件过小: 0.49GB (期望 ≥ 1.0GB)
```

## 实现特点

1. **完全向后兼容**：不影响现有功能
2. **智能分级验证**：场景命名为警告级别，文件大小为错误级别
3. **综合验证**：多维度验证确保数据质量
4. **详细反馈**：提供具体的错误信息和建议
5. **灵活处理**：支持任意命名的文件，但推荐规范命名
6. **完整日志**：便于问题追踪和分析
7. **异常处理**：健壮的错误处理机制

## 文件清单

- ✅ `utils/validators.py` - 新增验证函数
- ✅ `processors/archive_handler.py` - 集成验证逻辑
- ✅ `sheets/sheets_writer.py` - 扩展表格字段
- ✅ `test_naming_validation.py` - 单元测试
- ✅ `integration_test.py` - 集成测试
- ✅ `demo_validation.py` - 功能演示
- ✅ `NAMING_VALIDATION_IMPLEMENTATION.md` - 本文档

## 总结

文件结构和命名规范检查功能已成功实现并完全集成到现有系统中。该功能能够：

1. **自动识别**文件的场景类型（indoor/outdoor）
2. **智能检查**解压后文件大小的合理性
3. **实时标记**异常大小的文件
4. **完整记录**所有验证结果到Google Sheets
5. **提供详细**的验证日志和错误信息

新功能现在是文件处理流程的一个组成部分，会自动对所有处理的文件进行验证，确保数据质量和规范性。

## 重要更新（v1.1）

**场景命名验证级别调整**：
- ✅ **Unknown场景类型现在是警告级别，不是错误**
- ✅ 系统支持处理任意命名的文件，不会因为命名不规范而拒绝处理
- ✅ 推荐使用规范命名（Indoor/I或Outdoor/O开头）以便自动识别和分类
- ✅ 验证结果：数据格式 AND 文件大小（场景命名仅作为分类参考）

这使得系统更加灵活，能够处理各种命名格式的文件，同时仍然提供命名规范的建议。