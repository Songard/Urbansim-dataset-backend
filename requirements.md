# Google Drive 自动监控系统 - 功能需求文档

## 项目概述
开发一个Python应用程序，自动监控Google Drive指定文件夹中的新文件上传，下载并验证文件格式，将处理结果记录到Google Sheets中，实现资产上传的自动化登记。

## 核心配置信息
```
Google Drive 文件夹 ID: 1NXEAm1QWAKpyZLYWHYzBNdt3kZlMV3hK
Google Sheets ID: 1l26xiptV_rYxy0YKMJXhBHUeDyRS24HfrZTopWNmFiw
认证文件: service-account.json
```

## 详细功能需求

### 1. 项目结构要求
```
google-drive-monitor/
├── service-account.json      # Google服务账号密钥文件
├── .env                       # 环境变量配置
├── .env.example              # 环境变量示例
├── requirements.txt          # Python依赖包
├── config.py                 # 配置管理模块
├── main.py                   # 主程序入口
├── monitor/                  # 监控模块目录
│   ├── __init__.py
│   ├── drive_monitor.py     # Drive监控核心
│   └── file_tracker.py      # 文件追踪管理
├── processors/               # 处理器模块目录
│   ├── __init__.py
│   ├── file_downloader.py   # 文件下载器
│   └── archive_handler.py   # 压缩文件处理器
├── sheets/                   # Sheets操作模块
│   ├── __init__.py
│   └── sheets_writer.py     # Sheets写入器
├── utils/                    # 工具模块
│   ├── __init__.py
│   ├── logger.py            # 日志管理
│   └── validators.py        # 验证器
├── tests/                    # 测试脚本
│   ├── test_connection.py   # 连接测试
│   └── test_full_flow.py    # 完整流程测试
├── logs/                     # 日志文件目录
├── downloads/                # 临时下载目录
├── processed/                # 已处理文件目录
├── data/                     # 数据存储目录
│   └── processed_files.json # 已处理文件记录
├── scripts/                  # 部署脚本
│   ├── run_windows.bat      # Windows运行脚本
│   ├── deploy_linux.sh      # Linux部署脚本
│   └── drive-monitor.service # Systemd服务配置
└── README.md                 # 项目说明文档
```

### 2. 核心功能模块

#### 2.1 Google Drive 监控模块 (drive_monitor.py)
**功能描述：**
- 使用Google Drive API v3连接到指定文件夹
- 每30秒轮询检查新文件（可配置）
- 识别新上传的文件（通过比对processed_files.json）
- 获取文件元数据：名称、大小、创建时间、修改时间、MIME类型
- 支持文件过滤：按文件类型、大小限制
- 实现增量检查，避免重复处理

**具体实现要求：**
```python
class DriveMonitor:
    def __init__(self, folder_id, credentials):
        """初始化监控器"""
        
    def get_new_files(self):
        """获取新文件列表"""
        
    def mark_as_processed(self, file_id):
        """标记文件为已处理"""
        
    def start_monitoring(self, callback):
        """开始监控循环"""
```

#### 2.2 文件下载器 (file_downloader.py)
**功能描述：**
- 支持断点续传
- 显示下载进度
- 自动重试机制（最多3次）
- 下载到指定的临时目录
- 验证下载完整性（比对文件大小）
- 支持并发下载（可配置最大并发数）

**错误处理：**
- 网络超时：自动重试
- 磁盘空间不足：记录错误并跳过
- 权限问题：记录并通知

#### 2.3 压缩文件处理器 (archive_handler.py)
**功能描述：**
- 支持格式：.zip, .rar, .7z, .tar, .tar.gz, .tar.bz2
- 自动检测压缩格式
- 解压到临时目录进行验证
- 验证解压是否成功（检查文件完整性）
- 获取压缩包内文件列表
- 处理密码保护的压缩文件（配置默认密码列表）

**验证规则：**
```python
def validate_archive(file_path):
    """
    验证压缩文件
    返回: {
        'is_valid': bool,
        'format': str,
        'file_count': int,
        'total_size': int,
        'file_list': list,
        'error': str or None
    }
    """
```

#### 2.4 Google Sheets 写入器 (sheets_writer.py)
**功能描述：**
- 自动创建表头（如果不存在）
- 追加新记录到下一个空行
- 支持批量写入
- 自动格式化（日期、数字、文本）
- 错误重试机制

**表格结构：**
| 列名 | 数据类型 | 说明 |
|------|---------|------|
| 文件ID | 文本 | Google Drive文件ID |
| 文件名 | 文本 | 原始文件名 |
| 上传时间 | 日期时间 | Drive中的创建时间 |
| 文件大小 | 数字 | 以MB为单位 |
| 文件类型 | 文本 | MIME类型或扩展名 |
| 解压状态 | 文本 | 成功/失败/不适用 |
| 文件数量 | 数字 | 压缩包内文件数 |
| 处理时间 | 日期时间 | 系统处理时间 |
| 错误信息 | 文本 | 如有错误记录详情 |
| 备注 | 文本 | 其他信息 |

#### 2.5 文件追踪管理 (file_tracker.py)
**功能描述：**
- 使用JSON文件持久化已处理文件列表
- 支持并发访问（文件锁）
- 定期清理过期记录（可配置保留天数）
- 提供查询接口

**数据结构：**
```json
{
  "processed_files": [
    {
      "file_id": "1abc...",
      "file_name": "example.zip",
      "processed_time": "2024-01-20 10:30:00",
      "status": "success",
      "sheets_row": 15
    }
  ],
  "last_check_time": "2024-01-20 10:30:00",
  "total_processed": 150
}
```

### 3. 配置管理 (config.py)
**环境变量配置：**
```python
# Google API配置
DRIVE_FOLDER_ID = "1NXEAm1QWAKpyZLYWHYzBNdt3kZlMV3hK"
SPREADSHEET_ID = "1l26xiptV_rYxy0YKMJXhBHUeDyRS24HfrZTopWNmFiw"
SERVICE_ACCOUNT_FILE = "service-account.json"

# 监控配置
CHECK_INTERVAL = 30  # 秒
ENABLE_MONITORING = True
MAX_CONCURRENT_DOWNLOADS = 3

# 文件处理配置
DOWNLOAD_PATH = "./downloads"
PROCESSED_PATH = "./processed"
MAX_FILE_SIZE_MB = 500
ALLOWED_EXTENSIONS = ['.zip', '.rar', '.7z', '.tar', '.gz']
DEFAULT_PASSWORDS = ['123456', 'password']  # 尝试的默认密码

# 日志配置
LOG_LEVEL = "INFO"
LOG_FILE = "logs/monitor.log"
LOG_MAX_SIZE = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5

# 重试配置
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY = 5  # 秒

# Sheets配置
SHEET_NAME = "Sheet1"
BATCH_WRITE_SIZE = 10  # 批量写入大小

# 清理配置
KEEP_PROCESSED_DAYS = 30  # 保留已处理记录天数
CLEAN_TEMP_FILES = True
```

### 4. 日志管理 (logger.py)
**日志要求：**
- 分级日志：DEBUG, INFO, WARNING, ERROR, CRITICAL
- 同时输出到控制台和文件
- 日志轮转（按大小或日期）
- 结构化日志格式
- 支持彩色控制台输出（Windows/Linux兼容）

**日志格式：**
```
[2024-01-20 10:30:45] [INFO] [drive_monitor] 发现新文件: example.zip (15.3 MB)
[2024-01-20 10:30:46] [INFO] [downloader] 开始下载: example.zip
[2024-01-20 10:31:02] [SUCCESS] [processor] 文件解压成功: 包含 25 个文件
[2024-01-20 10:31:03] [INFO] [sheets] 已写入Sheets第 156 行
```

### 5. 主程序 (main.py)
**功能流程：**
```python
def main():
    """
    主程序流程：
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
```

**命令行参数：**
```bash
python main.py [选项]
  --debug              启用调试模式
  --once              运行一次后退出
  --interval <秒>     设置检查间隔
  --dry-run           模拟运行，不实际下载处理
  --config <文件>     指定配置文件
```

### 6. 错误处理策略

#### 6.1 网络错误
- API调用失败：指数退避重试
- 下载中断：断点续传
- 认证过期：自动刷新

#### 6.2 文件处理错误
- 压缩文件损坏：记录到Sheets，标记为失败
- 磁盘空间不足：发送警告，暂停下载
- 权限错误：记录日志，跳过文件

#### 6.3 系统错误
- 程序崩溃：自动重启（通过systemd或批处理）
- 内存不足：限制并发处理数
- 日志过大：自动轮转

### 7. 测试脚本

#### 7.1 连接测试 (test_connection.py)
```python
"""
测试项目：
1. Service Account认证
2. Drive API连接和权限
3. Sheets API连接和写入权限
4. 网络连接
5. 本地目录权限
"""
```

#### 7.2 完整流程测试 (test_full_flow.py)
```python
"""
端到端测试：
1. 上传测试文件到Drive
2. 等待监控器检测
3. 验证下载
4. 验证解压
5. 验证Sheets记录
6. 清理测试数据
"""
```

### 8. 部署脚本

#### 8.1 Windows批处理 (run_windows.bat)
```batch
@echo off
REM 检查Python
REM 创建虚拟环境
REM 安装依赖
REM 运行程序
REM 错误处理
```

#### 8.2 Linux部署 (deploy_linux.sh)
```bash
#!/bin/bash
# 系统依赖检查
# Python环境设置
# 服务配置
# 权限设置
# 启动服务
```

#### 8.3 Systemd服务 (drive-monitor.service)
```ini
[Unit]
Description=Google Drive Monitor Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/drive-monitor
ExecStart=/opt/drive-monitor/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 9. 性能要求
- 内存使用：< 200MB
- CPU使用：< 5%（空闲时）
- 响应时间：新文件检测 < 1分钟
- 并发处理：支持3个文件同时下载
- 日志大小：自动控制在50MB以内

### 10. 安全要求
- Service Account密钥加密存储
- 敏感信息不记录到日志
- 下载文件病毒扫描（可选）
- 访问控制和权限最小化
- 定期清理临时文件

## 使用此文档作为Claude Code输入

将此文档保存为 `requirements.md`，然后使用以下命令：

```bash
# 一次性生成完整项目
claude "根据requirements.md文档，创建完整的Google Drive监控系统项目代码"

# 或分模块开发
claude "根据requirements.md中的2.1节，实现Google Drive监控模块"
claude "根据requirements.md中的2.3节，实现压缩文件处理器"
```

## 开发优先级
1. **P0 - 核心功能**（必须实现）
   - Drive连接和文件检测
   - 文件下载
   - Sheets写入
   - 基础日志

2. **P1 - 重要功能**（应该实现）
   - 压缩文件验证
   - 错误重试
   - 已处理文件追踪
   - 配置管理

3. **P2 - 优化功能**（建议实现）
   - 并发下载
   - 断点续传
   - 日志轮转
   - 性能优化

4. **P3 - 额外功能**（可选实现）
   - Web界面
   - 邮件通知
   - 统计报表
   - 病毒扫描