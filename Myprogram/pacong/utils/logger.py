"""
日志配置模块
"""
import logging
import sys
from logging.handlers import RotatingFileHandler

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LOG_CONFIG


def setup_logger(name: str = 'crawler') -> logging.Logger:
    """
    配置并返回日志记录器
    同时输出到控制台和文件
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOG_CONFIG['level']))
    formatter = logging.Formatter(LOG_CONFIG['format'])

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器（滚动日志）
    file_handler = RotatingFileHandler(
        LOG_CONFIG['file'],
        maxBytes=LOG_CONFIG['max_bytes'],
        backupCount=LOG_CONFIG['backup_count'],
        encoding='utf-8',
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def get_logger(module_name: str) -> logging.Logger:
    """获取子模块日志记录器"""
    return logging.getLogger(f'crawler.{module_name}')
