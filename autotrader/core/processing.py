"""
Stock data processing functions
"""

import os
import logging
from datetime import datetime
from .export import export_to_csv, create_combined_html_report

# Configure logger
logger = logging.getLogger('autotrader.processing')

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
    
    # Get option data
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
    """
    Print a summary of stock options to the console
    
    Args:
        stock_data (dict): Dictionary containing stock price, call options, and put options
    """
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
    
    # Make sure the output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
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
        combined_html_path = create_combined_html_report(
            stocks_data,
            expiration,
            output_dir=output_dir
        )
        # Add combined report to results
        export_results['html'] = [combined_html_path]
    
    return export_results

def get_strikes_around_price(price, interval, num_strikes):
    """
    Get a list of strike prices around a given price
    
    Args:
        price (float): Current price
        interval (float): Interval between strikes
        num_strikes (int): Number of strikes to include on each side
        
    Returns:
        list: List of strike prices
    """
    current_strike = round(price / interval) * interval
    strikes = []
    
    # Add strikes below and above current price
    for i in range(-num_strikes, num_strikes + 1):
        strike = current_strike + (i * interval)
        strikes.append(strike)
    
    return strikes 