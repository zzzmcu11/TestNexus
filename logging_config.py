import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

def setup_logging():
    """
    配置日志系统，同时输出到控制台和按日期滚动的文件
    """
    # 确保logs目录存在
    os.makedirs('logs', exist_ok=True)
    
    # 获取当天日期
    today = datetime.now().strftime('%Y%m%d')
    log_filename = f'logs/ai-testcase-{today}.log'
    
    # 创建根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # 移除现有的处理器，避免重复
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    
    # 创建文件处理器（按日期滚动，最大10MB，保留5个备份）
    file_handler = RotatingFileHandler(
        log_filename,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    
    # 添加处理器到根日志记录器
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # 设置特定模块的日志级别
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    
    return root_logger

def get_logger(name):
    """
    获取指定名称的日志记录器
    """
    return logging.getLogger(name)
