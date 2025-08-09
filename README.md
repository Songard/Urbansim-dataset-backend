# Google Drive 文件监控器

一个用于监控 Google Drive 文件夹并自动处理上传文件的 Python 应用程序。

## 功能特性

- 实时监控指定的 Google Drive 文件夹
- 自动下载新上传的文件
- 支持多种文件类型（PDF、DOCX、TXT、JPG、PNG）
- 文件大小限制和类型过滤
- 避免重复处理已下载的文件
- 可配置的轮询间隔
- 详细的日志记录

## 安装要求

- Python 3.7+
- Google Drive API 访问权限

## 安装步骤

1. 克隆或下载项目文件
2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

3. 设置 Google Drive API：
   - 访问 [Google Cloud Console](https://console.cloud.google.com/)
   - 创建新项目或选择现有项目
   - 启用 Google Drive API
   - 创建服务账号密钥或 OAuth 2.0 客户端 ID
   - 下载 `credentials.json` 文件到项目根目录

4. 配置环境变量：
   - 复制 `.env.example` 为 `.env`
   - 填写必要的配置信息

## 配置说明

### 环境变量

在 `.env` 文件中配置以下变量：

- `MONITORED_FOLDER_ID`: 要监控的 Google Drive 文件夹 ID
- `POLLING_INTERVAL`: 轮询间隔（秒），默认 60 秒
- `DOWNLOAD_DIRECTORY`: 下载文件保存目录，默认 `./downloads`
- `SUPPORTED_FILE_TYPES`: 支持的文件类型，用逗号分隔
- `MAX_FILE_SIZE_MB`: 最大文件大小（MB），默认 100MB
- `LOG_LEVEL`: 日志级别，默认 INFO

### 获取文件夹 ID

1. 在浏览器中打开目标 Google Drive 文件夹
2. 从 URL 中复制文件夹 ID
   ```
   https://drive.google.com/drive/folders/1ABC123DEF456GHI789JKL
   文件夹 ID: 1ABC123DEF456GHI789JKL
   ```

## 使用方法

1. 确保完成所有配置步骤
2. 运行应用程序：
   ```bash
   python main.py
   ```
3. 首次运行时会打开浏览器进行 Google 账号授权
4. 程序将开始监控指定文件夹并处理新文件

## 文件结构

```
├── main.py              # 主程序文件
├── config.py            # 配置文件
├── requirements.txt     # 依赖列表
├── .env.example         # 环境变量示例
├── .gitignore          # Git 忽略文件
├── README.md           # 项目说明
├── credentials.json    # Google API 凭证（需自行添加）
└── downloads/          # 下载文件目录（自动创建）
```

## 自定义文件处理

可以修改 `main.py` 中的 `process_file` 方法来自定义文件处理逻辑：

```python
def process_file(self, file, file_path):
    # 在这里添加自定义处理逻辑
    pass
```

## 注意事项

- 确保 Google Drive API 配额足够
- 大文件下载可能需要较长时间
- 程序会记录已处理的文件以避免重复处理
- 建议在生产环境中使用服务账号而非个人账号

## 故障排除

1. **认证失败**：检查 `credentials.json` 文件是否正确
2. **文件夹访问被拒绝**：确保账号有访问目标文件夹的权限
3. **下载失败**：检查网络连接和文件权限
4. **配置错误**：验证 `.env` 文件中的所有必需配置项

## 许可证

本项目仅供学习和研究使用。