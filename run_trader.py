#!/usr/bin/env python
"""
Simple script to read option prices from multiple stocks using Interactive Brokers API.
"""

import sys
import os
import logging
import argparse
from datetime import datetime, timedelta

# Configure logging
# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Set up file handler for all logs
log_file = os.path.join('logs', f'trader_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
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
logger = logging.getLogger('run_trader')
logger.setLevel(logging.DEBUG)  # Capture all logs
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Import the IBConnection class and export functions
from autotrader.core import IBConnection, export_options_data, create_combined_html_report, export_to_csv

# Configuration
DEFAULT_TICKERS = ['NVDA', 'TSLA']  # Default tickers to query
USE_CLOSEST_FRIDAY = True  # Set to False to use monthly expirations instead
USE_SPECIFIC_DATE = False  # Set to True to use the date below
SPECIFIC_EXPIRATION = '20250321'  # Format YYYYMMDD
VERBOSE = True  # Set to True to check available expirations
STRIKE_RANGE = 10  # How far from current price to check (in $)
STRIKE_INTERVAL = 5  # Interval between strikes (in $)
EXPORT_FORMAT = 'all'  # 'csv', 'html', or 'all'
OUTPUT_DIR = 'reports'  # Directory for export files

def get_closest_friday():
    """Get the closest Friday from today"""
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
    """Get the nearest third Friday (monthly expiration)"""
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

def get_expiration_date():
    """Get the expiration date based on configuration"""
    if USE_SPECIFIC_DATE:
        logger.info(f"Using specific expiration date: {SPECIFIC_EXPIRATION}")
        return SPECIFIC_EXPIRATION
    elif USE_CLOSEST_FRIDAY:
        return get_closest_friday()
    else:
        return get_next_monthly_expiration()

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Option Price Reader for Multiple Stocks')
    
    # Add command line options that can override the defaults
    parser.add_argument('--tickers', nargs='+', help='Stock tickers to query (space separated)')
    parser.add_argument('--expiration', help='Specific expiration date (YYYYMMDD format)')
    parser.add_argument('--closest-friday', action='store_true', help='Use closest Friday expiration')
    parser.add_argument('--monthly', action='store_true', help='Use monthly expiration (third Friday)')
    parser.add_argument('--strike-range', type=int, help='How far from current price to check (in $)')
    parser.add_argument('--strike-interval', type=int, help='Interval between strikes (in $)')
    parser.add_argument('--export', choices=['csv', 'html', 'all'], help='Export format')
    parser.add_argument('--output-dir', help='Directory for output files')
    parser.add_argument('--verbose', action='store_true', help='Verbose output mode')
    
    return parser.parse_args()

def process_stock(ib, ticker, expiration):
    """
    Process a single stock ticker to get option data
    
    Args:
        ib: IBConnection instance
        ticker: Stock ticker symbol
        expiration: Option expiration date
        
    Returns:
        dict: Dictionary containing stock price, call options, and put options
    """
    logger.debug(f"Processing {ticker}...")
    
    # Store option data
    call_options = {}
    put_options = {}
    
    # Get stock price
    logger.debug(f"Getting {ticker} stock price...")
    stock_price = ib.get_stock_price(ticker)
    if stock_price is None:
        logger.error(f"Failed to get {ticker} stock price")
        return None
    
    logger.info(f"{ticker} current price: ${stock_price:.2f}")
    
    # Calculate appropriate strikes (around the current price)
    # Round to nearest interval
    current_strike = round(stock_price / STRIKE_INTERVAL) * STRIKE_INTERVAL
    strikes_to_check = []
    
    # Add strikes below current price
    for i in range(1, (STRIKE_RANGE // STRIKE_INTERVAL) + 1):
        strikes_to_check.append(current_strike - (i * STRIKE_INTERVAL))
    
    # Add current strike
    strikes_to_check.append(current_strike)
    
    # Add strikes above current price
    for i in range(1, (STRIKE_RANGE // STRIKE_INTERVAL) + 1):
        strikes_to_check.append(current_strike + (i * STRIKE_INTERVAL))
    
    # Sort strikes
    strikes_to_check.sort()
    
    logger.debug(f"Checking strikes for {ticker}: {strikes_to_check}")
    
    # Get option prices for both calls and puts in one batch
    logger.debug(f"Getting {ticker} option prices (calls and puts)...")
    option_data = ib.get_multiple_option_prices(ticker, expiration, strikes_to_check)
    
    # Process the results
    logger.debug(f"Processing {ticker} call options:")
    for strike in strikes_to_check:
        key = (strike, 'C')
        if key in option_data:
            data = option_data[key]
            bid_str = f"${data['bid']:.2f}" if data['bid'] is not None and data['bid'] > 0 else "N/A"
            ask_str = f"${data['ask']:.2f}" if data['ask'] is not None and data['ask'] > 0 else "N/A"
            last_str = f"${data['last']:.2f}" if data['last'] is not None and data['last'] > 0 else "N/A"
            logger.debug(f"{ticker} {expiration} ${strike} Call: Bid={bid_str}, Ask={ask_str}, Last={last_str}")
            call_options[strike] = {'bid': bid_str, 'ask': ask_str, 'last': last_str}
        else:
            logger.warning(f"Could not get data for {ticker} {expiration} ${strike} Call")
    
    logger.debug(f"Processing {ticker} put options:")
    for strike in strikes_to_check:
        key = (strike, 'P')
        if key in option_data:
            data = option_data[key]
            bid_str = f"${data['bid']:.2f}" if data['bid'] is not None and data['bid'] > 0 else "N/A"
            ask_str = f"${data['ask']:.2f}" if data['ask'] is not None and data['ask'] > 0 else "N/A"
            last_str = f"${data['last']:.2f}" if data['last'] is not None and data['last'] > 0 else "N/A"
            logger.debug(f"{ticker} {expiration} ${strike} Put: Bid={bid_str}, Ask={ask_str}, Last={last_str}")
            put_options[strike] = {'bid': bid_str, 'ask': ask_str, 'last': last_str}
        else:
            logger.warning(f"Could not get data for {ticker} {expiration} ${strike} Put")
    
    return {
        'ticker': ticker,
        'stock_price': stock_price,
        'call_options': call_options,
        'put_options': put_options
    }

def print_stock_summary(stock_data):
    """Print a summary of stock options to the console"""
    ticker = stock_data['ticker']
    stock_price = stock_data['stock_price']
    call_options = stock_data['call_options']
    put_options = stock_data['put_options']
    
    print(f"\n=== {ticker} OPTIONS SUMMARY ===")
    print(f"{ticker} Price: ${stock_price:.2f}")
    
    print("\nCall Options:")
    print(f"{'Strike':<10} {'Bid':<10} {'Ask':<10} {'Last':<10}")
    print("-" * 40)
    for strike in sorted(call_options.keys()):
        opt = call_options[strike]
        print(f"${strike:<9} {opt['bid']:<10} {opt['ask']:<10} {opt['last']:<10}")
    
    print("\nPut Options:")
    print(f"{'Strike':<10} {'Bid':<10} {'Ask':<10} {'Last':<10}")
    print("-" * 40)
    for strike in sorted(put_options.keys()):
        opt = put_options[strike]
        print(f"${strike:<9} {opt['bid']:<10} {opt['ask']:<10} {opt['last']:<10}")

def export_all_stocks_data(stocks_data, expiration, format='all', output_dir='reports'):
    """
    Export data for multiple stocks
    
    Args:
        stocks_data: List of dictionaries containing stock data
        expiration: Option expiration date
        format: Export format ('csv', 'html', or 'all')
        output_dir: Directory to save export files
    
    Returns:
        dict: Paths to exported files
    """
    export_results = {}
    
    # Create timestamp for filenames
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Export individual CSV files
    if format.lower() in ['csv', 'all']:
        for stock_data in stocks_data:
            ticker = stock_data['ticker']
            stock_price = stock_data['stock_price']
            call_options = stock_data['call_options']
            put_options = stock_data['put_options']
            
            # Export individual stock data to CSV
            csv_filename = os.path.join(output_dir, f"{ticker.lower()}_options_data_{timestamp}.csv")
            csv_path = export_to_csv(
                stock_price,
                expiration,
                call_options,
                put_options,
                filename=csv_filename
            )
            
            # Store results
            if 'csv' not in export_results:
                export_results['csv'] = []
            export_results['csv'].append(csv_path)
    
    # Create combined HTML report if HTML format is requested
    if format.lower() in ['html', 'all']:
        from autotrader.core import create_combined_html_report
        combined_html_path = create_combined_html_report(
            stocks_data,
            expiration,
            output_dir=output_dir
        )
        # Add combined report to results
        export_results['html'] = [combined_html_path]
    
    return export_results

def main():
    """
    Main function to get options prices for multiple stocks
    """
    # Parse command line arguments
    args = parse_arguments()
    
    # Override defaults with command line arguments if provided
    global USE_CLOSEST_FRIDAY, USE_SPECIFIC_DATE, SPECIFIC_EXPIRATION
    global VERBOSE, STRIKE_RANGE, STRIKE_INTERVAL, EXPORT_FORMAT, OUTPUT_DIR
    global DEFAULT_TICKERS
    
    # Get tickers to process
    tickers = DEFAULT_TICKERS
    if args.tickers:
        tickers = args.tickers
    
    if args.expiration:
        USE_SPECIFIC_DATE = True
        SPECIFIC_EXPIRATION = args.expiration
        USE_CLOSEST_FRIDAY = False
    elif args.closest_friday:
        USE_CLOSEST_FRIDAY = True
        USE_SPECIFIC_DATE = False
    elif args.monthly:
        USE_CLOSEST_FRIDAY = False
        USE_SPECIFIC_DATE = False
    
    if args.verbose is not None:
        VERBOSE = args.verbose
    if args.strike_range is not None:
        STRIKE_RANGE = args.strike_range
    if args.strike_interval is not None:
        STRIKE_INTERVAL = args.strike_interval
    if args.export is not None:
        EXPORT_FORMAT = args.export
    if args.output_dir is not None:
        OUTPUT_DIR = args.output_dir
    
    logger.info(f"Starting options reader for tickers: {', '.join(tickers)}...")
    
    # Initialize connection to IB
    ib = IBConnection(readonly=True)
    
    # List to store all stock data
    all_stocks_data = []
    
    try:
        # Connect to IB (default port 7497 for paper trading, 7496 for live)
        if not ib.connect():
            logger.error("Failed to connect to IB. Make sure TWS/IB Gateway is running and API connections are enabled.")
            return
        
        logger.info("Successfully connected to IB")
        
        # Get expiration date based on configuration
        expiration = get_expiration_date()
        logger.info(f"Using expiration date: {expiration}")
        
        # Process each ticker
        for ticker in tickers:
            stock_data = process_stock(ib, ticker, expiration)
            if stock_data:
                all_stocks_data.append(stock_data)
                print_stock_summary(stock_data)
        
        # Export all stock data
        if all_stocks_data:
            logger.info(f"Exporting option data in {EXPORT_FORMAT} format to {OUTPUT_DIR} directory...")
            export_results = export_all_stocks_data(
                all_stocks_data,
                expiration,
                format=EXPORT_FORMAT,
                output_dir=OUTPUT_DIR
            )
            
            # Show export results
            for format_type, paths in export_results.items():
                for path in paths:
                    logger.info(f"Exported {format_type.upper()} report: {path}")
                    # Open HTML file in browser if on a desktop
                    if format_type == 'html' and os.name != 'nt':  # Not on Windows
                        try:
                            import webbrowser
                            webbrowser.open('file://' + os.path.abspath(path))
                        except:
                            pass  # Silently fail if browser can't be opened
            
    except Exception as e:
        logger.exception(f"Error: {e}")
    finally:
        # Disconnect
        ib.disconnect()
        logger.info("Disconnected from IB")

if __name__ == "__main__":
    main() 