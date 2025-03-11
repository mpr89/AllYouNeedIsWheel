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
DEFAULT_TICKERS = ['NVDA', 'TSLA', 'AAPL']  # Default tickers to query
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

def process_stock(ib_connection, ticker, expiration_date, interval, num_strikes, stock_price=None):
    """
    Process a single stock to get option prices
    
    Args:
        ib_connection: IBConnection instance
        ticker: Stock ticker symbol
        expiration_date: Option expiration date (YYYYMMDD format)
        interval: Strike price interval
        num_strikes: Number of strikes to check around current price
        stock_price: Current stock price (optional, will be fetched if not provided)
        
    Returns:
        dict: Dictionary containing stock price, call options, and put options
    """
    logger.debug(f"Processing {ticker}...")
    
    # Store option data
    call_options = {}
    put_options = {}
    
    # Get stock price if not provided
    if stock_price is None:
        logger.debug(f"Getting {ticker} stock price...")
        stock_price = ib_connection.get_stock_price(ticker)
        if stock_price is None:
            logger.error(f"Failed to get {ticker} stock price")
            return None
    
    logger.info(f"{ticker} current price: ${stock_price}")
    
    # Calculate appropriate strikes (around the current price)
    current_strike = round(stock_price / interval) * interval
    strikes = []
    
    # Add strikes below and above current price
    for i in range(-num_strikes, num_strikes + 1):
        strike = current_strike + (i * interval)
        strikes.append(strike)
    
    logger.debug(f"Strikes for {ticker}: {strikes}")
    logger.info(f"Getting option prices for {ticker}...")
    
    # Get option data using the correct method name
    option_data = ib_connection.get_multiple_option_prices(ticker, expiration_date, strikes)
    
    # Process call options
    for strike in strikes:
        key = (strike, 'C')
        if key in option_data:
            data = option_data[key]
            bid = data.get('bid', None)
            ask = data.get('ask', None)
            last = data.get('last', None)
            
            bid_str = f"${bid:.2f}" if bid is not None and bid > 0 else "N/A"
            ask_str = f"${ask:.2f}" if ask is not None and ask > 0 else "N/A"
            last_str = f"${last:.2f}" if last is not None and last > 0 else "N/A"
            
            logger.debug(f"{ticker} {expiration_date} ${strike} Call: Bid={bid_str}, Ask={ask_str}, Last={last_str}")
            call_options[strike] = {'bid': bid_str, 'ask': ask_str, 'last': last_str}
    
    # Process put options
    for strike in strikes:
        key = (strike, 'P')
        if key in option_data:
            data = option_data[key]
            bid = data.get('bid', None)
            ask = data.get('ask', None)
            last = data.get('last', None)
            
            bid_str = f"${bid:.2f}" if bid is not None and bid > 0 else "N/A"
            ask_str = f"${ask:.2f}" if ask is not None and ask > 0 else "N/A"
            last_str = f"${last:.2f}" if last is not None and last > 0 else "N/A"
            
            logger.debug(f"{ticker} {expiration_date} ${strike} Put: Bid={bid_str}, Ask={ask_str}, Last={last_str}")
            put_options[strike] = {'bid': bid_str, 'ask': ask_str, 'last': last_str}
    
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
    # Setup argument parser
    parser = argparse.ArgumentParser(description="Run the stock option trader.")
    parser.add_argument("--tickers", help="Comma-separated list of stock tickers to process", default="NVDA,TSLA")
    parser.add_argument("--port", type=int, help="TWS port", default=7497)
    parser.add_argument("--host", help="TWS host", default="127.0.0.1")
    parser.add_argument("--interval", type=int, help="Strike price interval", default=5)
    parser.add_argument("--num_strikes", type=int, help="Number of strikes around current price", default=2)
    # Changed to a date in the current year (2025) for better option data availability
    parser.add_argument("--expiration_date", help="Expiration date in format YYYYMMDD", default="20250321")
    parser.add_argument("--output_dir", help="Directory for output files", default="reports")
    parser.add_argument("--export_format", help="Export format: csv, html, or all", default="html")
    args = parser.parse_args()
    
    # Parse tickers list
    tickers = [ticker.strip() for ticker in args.tickers.split(',')]
    
    logger.info(f"Starting options reader for tickers: {', '.join(tickers)}...")
    
    # Initialize connection to IB
    ib = IBConnection(readonly=True, host=args.host, port=args.port)
    
    # List to store all stock data
    all_stocks_data = []
    
    try:
        # Connect to IB
        if not ib.connect():
            logger.error("Failed to connect to IB. Make sure TWS/IB Gateway is running and API connections are enabled.")
            return
        
        logger.info("Successfully connected to IB")
        
        # Process each ticker
        valid_tickers = []
        stock_prices = {}
        
        # Get stock prices for all tickers first
        for ticker in tickers:
            logger.debug(f"Getting {ticker} stock price...")
            stock_price = ib.get_stock_price(ticker)
            if stock_price is None:
                logger.error(f"Failed to get {ticker} stock price, skipping...")
                continue
                
            logger.info(f"{ticker} current price: ${stock_price}")
            stock_prices[ticker] = stock_price
            valid_tickers.append(ticker)
        
        # Find closest Friday to the target date (default to closest Friday from today)
        if args.expiration_date:
            target_date = datetime.strptime(args.expiration_date, "%Y%m%d").date()
        else:
            target_date = datetime.now().date()
        
        # Find the closest Friday to the target date
        days_to_friday = (4 - target_date.weekday()) % 7
        closest_friday = target_date + timedelta(days=days_to_friday)
        
        formatted_date = target_date.strftime("%Y%m%d")
        if days_to_friday > 0:
            logger.info(f"Using closest Friday: {closest_friday}")
            logger.info(f"User-specified expiration date: {formatted_date}")
        
        # Process each ticker
        for ticker in valid_tickers:
            stock_data = process_stock(
                ib, 
                ticker, 
                formatted_date, 
                args.interval, 
                args.num_strikes, 
                stock_prices[ticker]
            )
            
            if stock_data:
                all_stocks_data.append(stock_data)
                print_stock_summary(stock_data)
        
        # Export data if we have results
        if all_stocks_data:
            logger.info("Generating consolidated HTML report...")
            # Create output directory if it doesn't exist
            os.makedirs(args.output_dir, exist_ok=True)
            
            # Create a consolidated HTML report
            report_path = create_combined_html_report(
                all_stocks_data,
                formatted_date,
                output_dir=args.output_dir
            )
            
            logger.info(f"Exported consolidated HTML report: {report_path}")
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        # Disconnect from IB
        ib.disconnect()
        logger.info("Disconnected from IB")

if __name__ == "__main__":
    main() 