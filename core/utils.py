"""
Utility functions for the autotrader package
"""

import os
import glob
import logging
from datetime import datetime, timedelta
import math

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
    
    # Set ib_insync loggers to WARNING level to reduce noise
    logging.getLogger('ib_insync').setLevel(logging.WARNING)
    logging.getLogger('ib_insync.wrapper').setLevel(logging.WARNING)
    logging.getLogger('ib_insync.client').setLevel(logging.WARNING)
    logging.getLogger('ib_insync.ticker').setLevel(logging.WARNING)
    
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

def format_currency(value):
    """Format a value as currency"""
    if value is None or isinstance(value, float) and math.isnan(value):
        return "$0.00"
    return f"${value:.2f}"

def format_percentage(value):
    """Format a value as percentage"""
    if value is None or isinstance(value, float) and math.isnan(value):
        return "0.00%"
    return f"{value:.2f}%"

def print_stock_summary(stock_data):
    """
    Print a summary of stock data with position and option recommendations
    
    Args:
        stock_data (dict): Stock data including price, position, and options
    """
    ticker = stock_data.get('ticker', 'UNKNOWN')
    price = stock_data.get('price', 0)
    position = stock_data.get('position', {})
    
    position_size = position.get('size', 0)
    avg_cost = position.get('avg_cost', 0)
    market_value = position.get('market_value', 0)
    unrealized_pnl = position.get('unrealized_pnl', 0)
    
    options = stock_data.get('options', {})
    recommendation = stock_data.get('recommendation', {})
    
    print(f"\n==== {ticker} Summary ====")
    print(f"Current Price: {format_currency(price)}")
    
    if position_size != 0:
        print(f"\nPosition:")
        print(f"  Size: {position_size} shares")
        print(f"  Average Cost: {format_currency(avg_cost)}")
        print(f"  Market Value: {format_currency(market_value)}")
        print(f"  Unrealized P&L: {format_currency(unrealized_pnl)}")
    else:
        print("\nNo current position")
    
    if options:
        print("\nOption Contracts:")
        expiration = options.get('expiration', 'Unknown')
        print(f"  Expiration: {expiration}")
        
        put = options.get('put', {})
        if put:
            print(f"\n  Put @ {put.get('strike', 0)}:")
            print(f"    Bid: {format_currency(put.get('bid', 0))}")
            print(f"    Ask: {format_currency(put.get('ask', 0))}")
            print(f"    Last: {format_currency(put.get('last', 0))}")
        
        call = options.get('call', {})
        if call:
            print(f"\n  Call @ {call.get('strike', 0)}:")
            print(f"    Bid: {format_currency(call.get('bid', 0))}")
            print(f"    Ask: {format_currency(call.get('ask', 0))}")
            print(f"    Last: {format_currency(call.get('last', 0))}")
    
    if recommendation:
        print("\nRecommendation:")
        action = recommendation.get('action', 'UNKNOWN')
        option_type = recommendation.get('type', 'UNKNOWN')
        strike = recommendation.get('strike', 0)
        exp = recommendation.get('expiration', 'UNKNOWN')
        
        print(f"  {action} {option_type} @ {strike} expiring {exp}")
        
        earnings = recommendation.get('earnings', {})
        if earnings:
            print("\nPotential Earnings:")
            strategy = earnings.get('strategy', 'UNKNOWN')
            max_contracts = earnings.get('max_contracts', 0)
            premium = earnings.get('premium_per_contract', 0)
            total = earnings.get('total_premium', 0)
            
            print(f"  Strategy: {strategy}")
            print(f"  Max Contracts: {max_contracts}")
            print(f"  Premium per Contract: {format_currency(premium)}")
            print(f"  Total Premium: {format_currency(total)}")
            
            if 'return_on_capital' in earnings:
                print(f"  Return on Capital: {format_percentage(earnings.get('return_on_capital', 0))}")
            if 'return_on_cash' in earnings:
                print(f"  Return on Cash: {format_percentage(earnings.get('return_on_cash', 0))}")

def get_strikes_around_price(price, interval, num_strikes):
    """
    Get a list of strike prices around a given price
    
    Args:
        price (float): Current price
        interval (float): Strike price interval
        num_strikes (int): Number of strikes to return (in each direction)
        
    Returns:
        list: List of strike prices
    """
    # Round price to nearest interval
    base_strike = round(price / interval) * interval
    
    # Generate strikes above and below
    strikes = []
    for i in range(-num_strikes, num_strikes + 1):
        strike = base_strike + (i * interval)
        if strike > 0:
            strikes.append(strike)
            
    return strikes 