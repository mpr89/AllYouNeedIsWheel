"""
Stock data processing functions
"""

import os
import logging
from datetime import datetime
from .export import export_to_csv, create_combined_html_report
import pandas as pd
import numpy as np
import webbrowser

# Configure logger
logger = logging.getLogger('autotrader.processing')

def process_stock(ib_connection, ticker, expiration_date, interval, num_strikes, stock_price=None):
    """
    Process a single stock to get option prices
    
    Args:
        ib_connection: IBConnection instance
        ticker: Stock ticker symbol
        expiration_date: Option expiration date in YYYYMMDD format
        interval: Strike price interval
        num_strikes: Number of strikes to fetch on each side of current price
        stock_price: Current stock price (if None, it will be fetched)
        
    Returns:
        dict: Dictionary with stock data including current price and option chains
    """
    logger = logging.getLogger(__name__)
    
    # Get current stock price if not provided
    if stock_price is None:
        stock_price = ib_connection.get_stock_price(ticker)
        
    if stock_price is None:
        logger.error(f"Could not get current price for {ticker}")
        return None
        
    logger.info(f"Current price for {ticker}: ${stock_price:.2f}")
    
    # Calculate recommended strike prices (20% below and 20% above)
    put_strike = round(stock_price * 0.8 / interval) * interval
    call_strike = round(stock_price * 1.2 / interval) * interval
    
    # Get option prices for put and call
    logger.info(f"Fetching recommended options for {ticker} at expiration {expiration_date}")
    logger.info(f"Recommended PUT (sell): Strike ${put_strike:.2f} (-20%)")
    logger.info(f"Recommended CALL (buy): Strike ${call_strike:.2f} (+20%)")
    
    # Get option prices
    options_data = {}
    
    # Get put option data
    put_contract = ib_connection.create_option_contract(ticker, expiration_date, put_strike, 'P')
    put_data = ib_connection.get_option_price(put_contract)
    if put_data:
        options_data[f"{put_strike}_P"] = put_data
    
    # Get call option data
    call_contract = ib_connection.create_option_contract(ticker, expiration_date, call_strike, 'C')
    call_data = ib_connection.get_option_price(call_contract)
    if call_data:
        options_data[f"{call_strike}_C"] = call_data
    
    # Return stock data
    return {
        'ticker': ticker,
        'price': stock_price,
        'options': options_data,
        'recommendation': {
            'put': {
                'strike': put_strike,
                'action': 'SELL',
                'percent': -20
            },
            'call': {
                'strike': call_strike,
                'action': 'BUY',
                'percent': 20
            }
        }
    }

def print_stock_summary(stock_data):
    """
    Print a summary of stock options data to the console
    
    Args:
        stock_data (dict): Stock data dictionary
    """
    if not stock_data:
        print("No data available")
        return
        
    ticker = stock_data['ticker']
    price = stock_data['price']
    options = stock_data.get('options', {})
    recommendation = stock_data.get('recommendation', {})
    
    print(f"\n=== {ticker} OPTIONS SUMMARY ===")
    print(f"{ticker} Price: ${price:.2f}")
    
    if recommendation:
        print("\nRECOMMENDED STRATEGY:")
        
        put_rec = recommendation.get('put', {})
        if put_rec:
            put_strike = put_rec.get('strike')
            put_key = f"{put_strike}_P"
            put_data = options.get(put_key, {})
            
            bid = put_data.get('bid', 'N/A')
            ask = put_data.get('ask', 'N/A')
            last = put_data.get('last', 'N/A')
            
            if isinstance(bid, (int, float)) and bid > 0:
                bid = f"${bid:.2f}"
            if isinstance(ask, (int, float)) and ask > 0:
                ask = f"${ask:.2f}"
            if isinstance(last, (int, float)) and last > 0:
                last = f"${last:.2f}"
                
            print(f"SELL PUT  @ Strike ${put_strike:.2f} ({put_rec.get('percent')}%)")
            print(f"  Bid: {bid}, Ask: {ask}, Last: {last}")
        
        call_rec = recommendation.get('call', {})
        if call_rec:
            call_strike = call_rec.get('strike')
            call_key = f"{call_strike}_C"
            call_data = options.get(call_key, {})
            
            bid = call_data.get('bid', 'N/A')
            ask = call_data.get('ask', 'N/A')
            last = call_data.get('last', 'N/A')
            
            if isinstance(bid, (int, float)) and bid > 0:
                bid = f"${bid:.2f}"
            if isinstance(ask, (int, float)) and ask > 0:
                ask = f"${ask:.2f}"
            if isinstance(last, (int, float)) and last > 0:
                last = f"${last:.2f}"
                
            print(f"BUY CALL  @ Strike ${call_strike:.2f} ({call_rec.get('percent')}%)")
            print(f"  Bid: {bid}, Ask: {ask}, Last: {last}")

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

def open_in_browser(file_path):
    """
    Opens the given file path in the default web browser.
    
    Args:
        file_path (str): Path to the file to open in browser
        
    Returns:
        bool: True if successful, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    if not os.path.exists(file_path):
        logger.error(f"Cannot open in browser: File not found: {file_path}")
        return False
    
    try:
        url = 'file://' + os.path.abspath(file_path)
        logger.info(f"Opening in browser: {url}")
        webbrowser.open(url)
        return True
    except Exception as e:
        logger.error(f"Failed to open browser: {e}")
        return False 