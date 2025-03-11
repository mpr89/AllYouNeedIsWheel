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

def rotate_reports(reports_dir='reports', max_reports=5):
    """
    Rotate HTML report files, keeping only the specified number of most recent reports.
    
    Args:
        reports_dir (str): Directory containing HTML report files
        max_reports (int): Maximum number of report files to keep
    """
    # Get all HTML report files in the reports directory
    report_files = glob.glob(os.path.join(reports_dir, 'options_report_*.html'))
    
    # If we don't have too many reports yet, no need to delete any
    if len(report_files) <= max_reports:
        return
    
    # Sort report files by modification time (newest first)
    sorted_reports = sorted(report_files, key=os.path.getmtime, reverse=True)
    
    # Keep only the most recent reports, delete others
    reports_to_delete = sorted_reports[max_reports:]
    for report_file in reports_to_delete:
        try:
            os.remove(report_file)
            print(f"Deleted old report file: {report_file}")
        except Exception as e:
            print(f"Error deleting report file {report_file}: {e}")

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
        datetime.date: Date of the closest Friday
    """
    today = datetime.now().date()
    
    # Get the day of the week (0 is Monday, 4 is Friday)
    weekday = today.weekday()
    
    # Calculate days until Friday
    if weekday < 4:  # Monday to Thursday
        days_to_add = 4 - weekday
    elif weekday == 4:  # Friday
        days_to_add = 0
    else:  # Weekend
        days_to_add = 4 + (7 - weekday)  # Next Friday
    
    closest_friday = today + timedelta(days=days_to_add)
    return closest_friday

def get_next_monthly_expiration():
    """
    Get the next monthly options expiration date (3rd Friday of the month)
    
    Returns:
        str: Next monthly expiration date in YYYYMMDD format
    """
    today = datetime.now().date()
    
    # Start with the current month
    year = today.year
    month = today.month
    
    # Find the first day of the month
    first_day = datetime(year, month, 1).date()
    
    # Find the first Friday of the month
    weekday = first_day.weekday()
    if weekday < 4:  # Monday to Thursday
        days_to_add = 4 - weekday
    else:  # Friday to Sunday
        days_to_add = 4 + (7 - weekday)
    
    first_friday = first_day + timedelta(days=days_to_add)
    
    # The third Friday is 14 days after the first Friday
    third_friday = first_friday + timedelta(days=14)
    
    # If the third Friday is in the past, move to next month
    if third_friday < today:
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
            
        first_day = datetime(year, month, 1).date()
        
        # Find the first Friday of the next month
        weekday = first_day.weekday()
        if weekday < 4:  # Monday to Thursday
            days_to_add = 4 - weekday
        else:  # Friday to Sunday
            days_to_add = 4 + (7 - weekday)
        
        first_friday = first_day + timedelta(days=days_to_add)
        third_friday = first_friday + timedelta(days=14)
    
    # Format as YYYYMMDD
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