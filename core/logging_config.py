"""
Centralized logging configuration module for the Auto-Trader application
"""

import os
import time
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

# Base directory for logs
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')

# Ensure log directories exist
for subdir in ['api', 'tws', 'server', 'general']:
    os.makedirs(os.path.join(LOGS_DIR, subdir), exist_ok=True)

# Log file name format with timestamp
TIMESTAMP = datetime.now().strftime('%Y%m%d_%H%M%S')

def get_log_path(log_type):
    """Get the path for a specific log type with timestamp"""
    return os.path.join(LOGS_DIR, log_type, f"{log_type}_{TIMESTAMP}.log")

def configure_logging(module_name, log_type=None, console_level=logging.INFO, file_level=logging.DEBUG):
    """
    Configure logging for a module
    
    Args:
        module_name (str): Name of the module (used as logger name)
        log_type (str, optional): Type of log ('api', 'tws', 'server', or None for 'general')
        console_level (int, optional): Logging level for console output. Defaults to logging.INFO.
        file_level (int, optional): Logging level for file output. Defaults to logging.DEBUG.
        
    Returns:
        logging.Logger: Configured logger
    """
    # Determine log type directory
    if not log_type:
        log_type = 'general'
    
    # Create logger
    logger = logging.getLogger(module_name)
    logger.setLevel(logging.DEBUG)  # Capture all levels
    
    # Remove existing handlers if any
    if logger.handlers:
        logger.handlers = []
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler - rotating file handler to prevent huge log files
    log_file = get_log_path(log_type)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)
    
    # Log startup information
    logger.info(f"Logging initialized for {module_name} to {log_file}")
    
    return logger

def get_logger(module_name, log_type=None):
    """
    Get a configured logger for a module
    
    Args:
        module_name (str): Name of the module
        log_type (str, optional): Type of log ('api', 'tws', 'server', or None for 'general')
        
    Returns:
        logging.Logger: Configured logger
    """
    return configure_logging(module_name, log_type) 