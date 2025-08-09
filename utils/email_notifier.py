import os
import smtplib
import ssl
from datetime import datetime

# 修复可能的email模块导入问题
try:
    from email.mime.text import MimeText
    from email.mime.multipart import MimeMultipart
    from email.mime.base import MimeBase
    from email import encoders
except ImportError as e:
    print(f"邮件模块导入失败: {e}")
    print("请确保你在正确的conda环境中运行: conda activate drive-monitor")
    raise ImportError("邮件功能不可用，请检查Python环境") from e
from typing import List, Optional, Dict, Any
from pathlib import Path

from config import Config
from utils.logger import get_logger

logger = get_logger(__name__)

class EmailNotifier:
    """
    邮件通知器
    
    功能:
    - 发送文件处理成功/失败通知
    - 发送系统状态报告
    - 发送错误警报
    - 支持HTML和纯文本邮件
    - 支持邮件附件
    """
    
    def __init__(self):
        self.smtp_server = Config.SMTP_SERVER
        self.smtp_port = Config.SMTP_PORT
        self.smtp_username = Config.SMTP_USERNAME
        self.smtp_password = Config.SMTP_PASSWORD
        self.sender_email = Config.SENDER_EMAIL
        self.sender_name = Config.SENDER_NAME
        self.recipient_emails = Config.RECIPIENT_EMAILS
        self.use_tls = Config.SMTP_USE_TLS
        self.use_ssl = Config.SMTP_USE_SSL
        
        logger.info(f"EmailNotifier initialized - Server: {self.smtp_server}:{self.smtp_port}")
    
    def send_email(self, subject: str, body: str, recipients: List[str] = None, 
                  html_body: str = None, attachments: List[str] = None) -> bool:
        """
        发送邮件
        
        Args:
            subject (str): 邮件主题
            body (str): 邮件正文（纯文本）
            recipients (List[str]): 收件人列表，默认使用配置中的收件人
            html_body (str): HTML格式邮件正文（可选）
            attachments (List[str]): 附件文件路径列表（可选）
            
        Returns:
            bool: 发送是否成功
        """
        if not Config.EMAIL_NOTIFICATIONS_ENABLED:
            logger.debug("邮件通知已禁用，跳过发送")
            return True
        
        try:
            # 使用默认收件人列表
            if recipients is None:
                recipients = self.recipient_emails
            
            if not recipients:
                logger.warning("没有配置收件人，无法发送邮件")
                return False
            
            # 创建邮件消息
            message = MimeMultipart('alternative')
            message['Subject'] = f"[Google Drive Monitor] {subject}"
            message['From'] = f"{self.sender_name} <{self.sender_email}>"
            message['To'] = ', '.join(recipients)
            
            # 添加纯文本内容
            text_part = MimeText(body, 'plain', 'utf-8')
            message.attach(text_part)
            
            # 添加HTML内容（如果提供）
            if html_body:
                html_part = MimeText(html_body, 'html', 'utf-8')
                message.attach(html_part)
            
            # 添加附件（如果有）
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        self._add_attachment(message, file_path)
                    else:
                        logger.warning(f"附件文件不存在，跳过: {file_path}")
            
            # 发送邮件
            return self._send_message(message, recipients)
            
        except Exception as e:
            logger.error(f"发送邮件异常: {e}")
            return False
    
    def _add_attachment(self, message: MimeMultipart, file_path: str):
        """添加附件到邮件"""
        try:
            with open(file_path, 'rb') as attachment:
                part = MimeBase('application', 'octet-stream')
                part.set_payload(attachment.read())
            
            encoders.encode_base64(part)
            filename = os.path.basename(file_path)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= "{filename}"'
            )
            message.attach(part)
            logger.debug(f"添加附件: {filename}")
            
        except Exception as e:
            logger.error(f"添加附件失败 {file_path}: {e}")
    
    def _send_message(self, message: MimeMultipart, recipients: List[str]) -> bool:
        """发送邮件消息"""
        try:
            # 创建SMTP连接
            if self.use_ssl:
                # 使用SSL连接
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=context)
            else:
                # 使用普通连接或STARTTLS
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                if self.use_tls:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
            
            # 登录
            if self.smtp_username and self.smtp_password:
                server.login(self.smtp_username, self.smtp_password)
            
            # 发送邮件
            text = message.as_string()
            server.sendmail(self.sender_email, recipients, text)
            server.quit()
            
            logger.info(f"邮件发送成功 -> {', '.join(recipients)}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP认证失败: {e}")
            return False
        except smtplib.SMTPConnectError as e:
            logger.error(f"SMTP连接失败: {e}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP异常: {e}")
            return False
        except Exception as e:
            logger.error(f"发送邮件异常: {e}")
            return False
    
    def notify_file_processed(self, file_info: Dict[str, Any], success: bool, 
                            error_message: str = None) -> bool:
        """
        发送文件处理通知
        
        Args:
            file_info (Dict): 文件信息
            success (bool): 处理是否成功
            error_message (str): 错误信息（如果处理失败）
            
        Returns:
            bool: 发送是否成功
        """
        try:
            file_name = file_info.get('name', '未知文件')
            file_size_mb = file_info.get('size', 0) / (1024 * 1024)
            file_id = file_info.get('id', '未知ID')
            
            if success:
                subject = f"文件处理成功 - {file_name}"
                status_text = "✅ 处理成功"
                status_color = "#28a745"
            else:
                subject = f"文件处理失败 - {file_name}"
                status_text = "❌ 处理失败"
                status_color = "#dc3545"
            
            # 纯文本邮件内容
            body = f"""Google Drive 文件监控系统通知

文件处理状态: {status_text}

文件信息:
- 文件名: {file_name}
- 文件ID: {file_id}
- 文件大小: {file_size_mb:.2f} MB
- 处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

"""
            
            if success:
                body += f"""处理结果:
- 下载状态: 成功
- 解压状态: {file_info.get('extract_status', '不适用')}
- 文件数量: {file_info.get('file_count', '不适用')}
- 已记录到Google Sheets
"""
            else:
                body += f"""错误信息:
{error_message or '未知错误'}
"""
            
            body += f"""
系统信息:
- 监控文件夹ID: {Config.DRIVE_FOLDER_ID}
- 处理服务器: {os.getenv('COMPUTERNAME', 'Unknown')}

---
此邮件由Google Drive监控系统自动发送
"""
            
            # HTML邮件内容
            html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Google Drive 监控通知</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: {status_color};">Google Drive 文件监控系统</h2>
        
        <div style="background: #f8f9fa; padding: 15px; border-left: 4px solid {status_color}; margin: 20px 0;">
            <h3 style="margin: 0; color: {status_color};">{status_text}</h3>
        </div>
        
        <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: bold;">文件名</td>
                <td style="padding: 8px; border-bottom: 1px solid #ddd;">{file_name}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: bold;">文件大小</td>
                <td style="padding: 8px; border-bottom: 1px solid #ddd;">{file_size_mb:.2f} MB</td>
            </tr>
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: bold;">处理时间</td>
                <td style="padding: 8px; border-bottom: 1px solid #ddd;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td>
            </tr>
"""
            
            if success:
                html_body += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: bold;">解压状态</td>
                <td style="padding: 8px; border-bottom: 1px solid #ddd;">{file_info.get('extract_status', '不适用')}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: bold;">文件数量</td>
                <td style="padding: 8px; border-bottom: 1px solid #ddd;">{file_info.get('file_count', '不适用')}</td>
            </tr>
"""
            else:
                html_body += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: bold;">错误信息</td>
                <td style="padding: 8px; border-bottom: 1px solid #ddd; color: #dc3545;">{error_message or '未知错误'}</td>
            </tr>
"""
            
            html_body += """
        </table>
        
        <div style="margin: 30px 0; padding: 15px; background: #e9ecef; border-radius: 5px;">
            <small style="color: #6c757d;">
                此邮件由Google Drive监控系统自动发送<br>
                如需帮助，请联系系统管理员
            </small>
        </div>
    </div>
</body>
</html>
"""
            
            return self.send_email(subject, body, html_body=html_body)
            
        except Exception as e:
            logger.error(f"发送文件处理通知异常: {e}")
            return False
    
    def notify_system_status(self, stats: Dict[str, Any]) -> bool:
        """
        发送系统状态报告
        
        Args:
            stats (Dict): 系统统计信息
            
        Returns:
            bool: 发送是否成功
        """
        try:
            uptime_hours = stats.get('uptime_seconds', 0) / 3600
            
            subject = f"系统状态报告 - {datetime.now().strftime('%Y-%m-%d')}"
            
            body = f"""Google Drive 监控系统状态报告

运行时间: {uptime_hours:.1f} 小时
处理文件总数: {stats.get('total_files_processed', 0)}
本次会话处理: {stats.get('files_processed_session', 0)}
处理失败: {stats.get('files_failed_session', 0)}
成功率: {stats.get('success_rate', 0):.1f}%

最后处理时间: {stats.get('last_processed', '无')}
数据文件大小: {stats.get('data_file_size', 0)} bytes

系统运行正常。

---
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            return self.send_email(subject, body)
            
        except Exception as e:
            logger.error(f"发送系统状态通知异常: {e}")
            return False
    
    def notify_error(self, error_type: str, error_message: str, context: Dict = None) -> bool:
        """
        发送错误警报
        
        Args:
            error_type (str): 错误类型
            error_message (str): 错误信息
            context (Dict): 错误上下文信息
            
        Returns:
            bool: 发送是否成功
        """
        try:
            subject = f"系统错误警报 - {error_type}"
            
            body = f"""Google Drive 监控系统错误警报

错误类型: {error_type}
错误时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

错误信息:
{error_message}

"""
            
            if context:
                body += "上下文信息:\n"
                for key, value in context.items():
                    body += f"- {key}: {value}\n"
            
            body += """
请及时检查系统状态。

---
此为自动警报邮件
"""
            
            return self.send_email(subject, body)
            
        except Exception as e:
            logger.error(f"发送错误警报异常: {e}")
            return False
    
    def test_connection(self) -> bool:
        """
        测试邮件连接
        
        Returns:
            bool: 连接是否成功
        """
        try:
            test_subject = "邮件系统测试"
            test_body = f"""这是一封测试邮件，用于验证Google Drive监控系统的邮件通知功能。

测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
系统配置:
- SMTP服务器: {self.smtp_server}:{self.smtp_port}
- 发送者: {self.sender_email}
- 收件人: {', '.join(self.recipient_emails)}

如果您收到此邮件，说明邮件通知功能工作正常。

---
Google Drive 监控系统
"""
            
            success = self.send_email(test_subject, test_body)
            if success:
                logger.info("邮件连接测试成功")
            else:
                logger.error("邮件连接测试失败")
            
            return success
            
        except Exception as e:
            logger.error(f"邮件连接测试异常: {e}")
            return False