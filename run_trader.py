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
    rotate_logs,
    rotate_reports,
    process_stock,
    print_stock_summary,
    export_all_stocks_data,
    create_combined_html_report,
    open_in_browser,
    get_next_monthly_expiration
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
    parser.add_argument("--interval", type=float, help="Strike price interval", default=5.0)
    parser.add_argument("--num_strikes", type=int, help="Number of strikes to fetch around current price", default=5)
    parser.add_argument("--days", type=int, help="Days to expiration (defaults to closest Friday)", default=None)
    parser.add_argument("--ib_host", help="IB TWS/Gateway host", default="127.0.0.1")
    parser.add_argument("--ib_port", type=int, help="IB TWS/Gateway port", default=7497)
    parser.add_argument("--output_dir", help="Directory to save output files", default="reports")
    parser.add_argument("--no_browser", action="store_true", help="Disable automatic opening of report in browser")
    
    args = parser.parse_args()
    
    # Split tickers
    tickers = [t.strip() for t in args.tickers.split(',')]
    
    # Create IB connection
    ib = IBConnection(host=args.ib_host, port=args.ib_port, readonly=True)
    
    try:
        # Connect to IB
        if not ib.connect():
            logger.error("Failed to connect to IB")
            return
        
        # Get current date and target expiration date
        today = datetime.now().date()
        
        # Determine expiration date
        if args.days:
            # Use specified days to expiration
            expiration_date = (today + timedelta(days=args.days)).strftime('%Y%m%d')
        else:
            # Use the closest monthly expiration date
            expiration_date = get_next_monthly_expiration()
            
        logger.info(f"Using expiration date: {expiration_date}")
        
        # Fetch portfolio data
        portfolio = ib.get_portfolio()
        if portfolio is None:
            logger.warning("Could not retrieve portfolio data")
            portfolio = {
                'account_value': 0,
                'available_cash': 0,
                'positions': {}
            }
            
        # Get stock prices for all tickers at once
        stock_prices = ib.get_multiple_stock_prices(tickers)
        
        # Process each stock
        all_stocks_data = []
        for ticker in tickers:
            if ticker not in stock_prices or stock_prices[ticker] is None:
                logger.warning(f"Could not get price for {ticker}, skipping")
                continue
                
            stock_data = process_stock(
                ib, 
                ticker, 
                expiration_date, 
                args.interval, 
                args.num_strikes, 
                stock_prices[ticker],
                portfolio
            )
            
            if stock_data:
                all_stocks_data.append(stock_data)
                print_stock_summary(stock_data)
        
        # Export data if we have results
        if all_stocks_data:
            # Create output directory if it doesn't exist
            os.makedirs(args.output_dir, exist_ok=True)
            
            # Rotate reports to keep only the most recent ones
            rotate_reports(reports_dir=args.output_dir, max_reports=5)
            
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

if __name__ == "__main__":
    main() 