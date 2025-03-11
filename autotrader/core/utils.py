"""
Utility functions for the autotrader package
"""

import os
import glob
import logging
from datetime import datetime, timedelta

# Configure logger
logger = logging.getLogger('autotrader.utils')

def rotate_logs(logs_dir='logs', max_logs=5):
    """
    Rotate log files, keeping only the specified number of most recent logs.
    
    Args:
        logs_dir (str): Directory containing log files
        max_logs (int): Maximum number of log files to keep
    """
    # Get all log files in the logs directory
    log_files = glob.glob(os.path.join(logs_dir, 'trader_*.log'))
    
    # If we don't have too many logs yet, no need to delete any
    if len(log_files) <= max_logs:
        return
    
    # Sort log files by modification time (newest first)
    sorted_logs = sorted(log_files, key=os.path.getmtime, reverse=True)
    
    # Keep only the most recent logs, delete others
    logs_to_delete = sorted_logs[max_logs:]
    for log_file in logs_to_delete:
        try:
            os.remove(log_file)
            print(f"Deleted old log file: {log_file}")
        except Exception as e:
            print(f"Error deleting log file {log_file}: {e}")

def setup_logging(logs_dir='logs', log_prefix='trader', log_level=logging.DEBUG):
    """
    Set up logging configuration
    
    Args:
        logs_dir (str): Directory to store log files
        log_prefix (str): Prefix for log filenames
        log_level (int): Logging level
        
    Returns:
        logger: Configured logger instance
    """
    # Create logs directory if it doesn't exist
    os.makedirs(logs_dir, exist_ok=True)
    
    # Rotate logs on startup
    rotate_logs(logs_dir=logs_dir, max_logs=5)
    
    # Set up file handler for all logs
    log_file = os.path.join(logs_dir, f"{log_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)  # Capture all logs in file
    
    # Set up console handler for important messages only
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)  # Only show warnings and errors in console
    
    # Create formatters
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    
    # Set formatters
    file_handler.setFormatter(file_formatter)
    console_handler.setFormatter(console_formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Return a logger for the calling module
    return logging.getLogger('autotrader')

def get_closest_friday():
    """
    Get the closest Friday from today
    
    Returns:
        str: Date string in format YYYYMMDD
    """
    today = datetime.now()
    # Find days until Friday (weekday 4)
    days_until_friday = (4 - today.weekday()) % 7
    
    # If today is Friday, use next Friday
    if days_until_friday == 0:
        days_until_friday = 7
    
    closest_friday = today + timedelta(days=days_until_friday)
    logger.info(f"Using closest Friday: {closest_friday.strftime('%Y-%m-%d')}")
    return closest_friday.strftime('%Y%m%d')

def get_next_monthly_expiration():
    """
    Get the nearest third Friday (monthly expiration)
    
    Returns:
        str: Date string in format YYYYMMDD
    """
    today = datetime.now()
    
    # Find the next third Friday of the month
    # First, find the first day of the current month
    first_day = datetime(today.year, today.month, 1)
    
    # Find the first Friday
    days_until_friday = (4 - first_day.weekday()) % 7
    first_friday = first_day + timedelta(days=days_until_friday)
    
    # Third Friday is 14 days after the first Friday
    third_friday = first_friday + timedelta(days=14)
    
    # If we've passed the third Friday of this month, go to next month
    if today > third_friday:
        if today.month == 12:
            next_month = datetime(today.year + 1, 1, 1)
        else:
            next_month = datetime(today.year, today.month + 1, 1)
        
        days_until_friday = (4 - next_month.weekday()) % 7
        first_friday = next_month + timedelta(days=days_until_friday)
        third_friday = first_friday + timedelta(days=14)
    
    logger.info(f"Using next monthly expiration: {third_friday.strftime('%Y-%m-%d')}")
    return third_friday.strftime('%Y%m%d')

def parse_date_string(date_str):
    """
    Parse a date string in YYYYMMDD format
    
    Args:
        date_str (str): Date string in YYYYMMDD format
        
    Returns:
        datetime: Datetime object
    """
    return datetime.strptime(date_str, "%Y%m%d")

def format_date_string(date_obj):
    """
    Format a datetime object as YYYYMMDD
    
    Args:
        date_obj (datetime): Datetime object
        
    Returns:
        str: Date string in YYYYMMDD format
    """
    return date_obj.strftime("%Y%m%d") 