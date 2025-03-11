#!/usr/bin/env python
"""
Simple script to read option prices from multiple stocks using Interactive Brokers API.
"""

import os
import argparse
from datetime import datetime, timedelta

# Import the autotrader core modules
from autotrader.core import (
    IBConnection,
    setup_logging,
    process_stock,
    print_stock_summary,
    export_all_stocks_data,
    create_combined_html_report,
    open_in_browser
)

# Set up logging
logger = setup_logging(logs_dir='logs', log_prefix='trader')

def main():
    """
    Main function to get options prices for multiple stocks
    """
    # Setup argument parser
    parser = argparse.ArgumentParser(description="Run the stock option trader.")
    parser.add_argument("--tickers", help="Comma-separated list of stock tickers to process", default="NVDA,TSLA,AAPL")
    parser.add_argument("--port", type=int, help="TWS port", default=7497)
    parser.add_argument("--host", help="TWS host", default="127.0.0.1")
    parser.add_argument("--interval", type=int, help="Strike price interval", default=5)
    parser.add_argument("--num_strikes", type=int, help="Number of strikes around current price", default=2)
    parser.add_argument("--expiration_date", help="Expiration date in format YYYYMMDD", default="20250321")
    parser.add_argument("--output_dir", help="Directory for output files", default="reports")
    parser.add_argument("--export_format", help="Export format: csv, html, or all", default="html")
    parser.add_argument("--no_browser", action="store_true", help="Don't open report in browser")
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
        
        # Get stock prices for all tickers in a batch
        logger.info(f"Getting stock prices for all tickers in batch: {', '.join(tickers)}")
        stock_prices = ib.get_multiple_stock_prices(tickers)
        
        # Filter valid tickers that have prices
        valid_tickers = []
        for ticker, price in stock_prices.items():
            if price is not None:
                logger.info(f"{ticker} current price: ${price}")
                valid_tickers.append(ticker)
            else:
                logger.error(f"Failed to get {ticker} stock price, skipping...")
        
        # Use the expiration date specified
        expiration_date = args.expiration_date
        
        # Process each ticker
        for ticker in valid_tickers:
            stock_data = process_stock(
                ib, 
                ticker, 
                expiration_date, 
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
                expiration_date,
                output_dir=args.output_dir
            )
            
            logger.info(f"Exported consolidated HTML report: {report_path}")
            
            # Open the report in a browser if not disabled
            if not args.no_browser:
                open_in_browser(report_path)
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