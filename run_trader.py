#!/usr/bin/env python3
import os
import sys
import argparse
import time
import logging
import datetime
from pathlib import Path
import pandas as pd
import numpy as np
import traceback

# Add the root directory to Python path
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.append(root_dir)

# Configure logging - set ib_insync to WARNING level to reduce noise
logging.getLogger('ib_insync').setLevel(logging.WARNING)
logging.getLogger('ib_insync.wrapper').setLevel(logging.WARNING)
logging.getLogger('ib_insync.client').setLevel(logging.WARNING)
logging.getLogger('ib_insync.ticker').setLevel(logging.WARNING)

# Import from modules
from core.connection import IBConnection, Option, suppress_ib_logs
from core.processing import SimpleOptionsStrategy, print_stock_summary, format_currency, format_percentage
from core.utils import get_closest_friday, get_next_monthly_expiration, setup_logging, rotate_reports
from config import Config

# Suppress ib_insync logs globally
suppress_ib_logs()

# Default configuration
DEFAULT_CONFIG = {
    'host': '127.0.0.1',
    'port': 7497,
    'client_id': 1,
    'readonly': True,
    'default_interval': 15,
    'default_strikes': 10,
    'log_level': 'INFO',
    'report_dir': 'reports',
}

def main():
    parser = argparse.ArgumentParser(description='AutoTrader - Automated Options Trading Helper')
    parser.add_argument('--config', type=str, help='Path to configuration file')
    parser.add_argument('--tickers', type=str, help='Optional: Comma-separated stock tickers to analyze. If not provided, tickers will be derived from portfolio positions.')
    parser.add_argument('--interval', type=int, help='Strike price interval')
    parser.add_argument('--monthly', action='store_true', help='Use monthly options expiration')
    parser.add_argument('--strikes', type=int, help='Number of strikes to analyze')
    args = parser.parse_args()
    
    # Load configuration
    config = Config(args.config)
    
    # Set up logging
    log_level = config.get('log_level', DEFAULT_CONFIG['log_level'])
    log_dir = config.get('log_dir', 'logs')
    logger = setup_logging(level=log_level, log_dir=log_dir)
    
    # Prepare report directory
    reports_dir = config.get('report_dir', DEFAULT_CONFIG['report_dir'])
    os.makedirs(reports_dir, exist_ok=True)
    
    # Rotate old log files and reports
    rotate_reports(reports_dir)
    
    # Get tickers to analyze
    tickers = []
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(',')]
    # We'll set tickers from portfolio later if none provided
        
    # Determine expiration date
    use_monthly = args.monthly or config.get('use_monthly_options', False)
    if use_monthly:
        expiration_date = get_next_monthly_expiration()
    else:
        expiration_date = get_closest_friday().strftime('%Y%m%d')
        
    # Get interval and number of strikes
    interval = args.interval or config.get('default_interval', 5)
    num_strikes = args.strikes or config.get('default_strikes', 10)
    
    # Initialize connection to IB
    try:
        ib_connection = IBConnection(
            host=config.get('host', '127.0.0.1'),
            port=config.get('port', 7497),
            client_id=config.get('client_id', 1),
            readonly=config.get('readonly', True)
        )
        
        logger.debug(f"Connecting to IB at {config.get('host')}:{config.get('port')}")
        connected = ib_connection.connect()
        
        if not connected:
            logger.error("Failed to connect to Interactive Brokers. Check connection settings.")
            return 1
            
        # Initialize options strategy engine
        strategy = SimpleOptionsStrategy(ib_connection, config.to_dict())
        
        # Check if we were able to connect to IB and get portfolio info
        if ib_connection.is_connected():
            logger.info("Successfully connected to Interactive Brokers")
            portfolio = ib_connection.get_portfolio()
            if portfolio:
                logger.info(f"Retrieved portfolio information for account {portfolio.get('account_id', 'Unknown')}")
                logger.debug(f"Available cash: ${portfolio.get('available_cash', 0):.2f}")
                logger.debug(f"Net liquidation value: ${portfolio.get('account_value', 0):.2f}")
                
                # Print portfolio summary
                print("\n=== PORTFOLIO SUMMARY ===")
                print(f"Account: {portfolio.get('account_id', 'Unknown')}")
                print(f"Available Cash: ${portfolio.get('available_cash', 0):.2f}")
                print(f"Net Liquidation Value: ${portfolio.get('account_value', 0):.2f}")
                
                # Check if we have positions
                if portfolio.get('positions'):
                    positions = portfolio['positions']
                    print("\nPositions:")
                    
                    # Handle both dictionary and list format for positions
                    if isinstance(positions, dict):
                        for symbol, position in positions.items():
                            shares = position.get('shares', 0)
                            avg_cost = position.get('avg_cost', 0)
                            market_value = position.get('market_value', 0)
                            unrealized_pnl = position.get('unrealized_pnl', 0)
                            print(f"  {symbol}: {shares} shares @ ${avg_cost:.2f}, Market Value: ${market_value:.2f}, PnL: ${unrealized_pnl:.2f}")
                    else:
                        # Handle list format (older format)
                        for position in positions:
                            if hasattr(position, 'contract') and hasattr(position, 'position'):
                                symbol = position.contract.symbol
                                shares = position.position
                                avg_cost = position.averageCost if hasattr(position, 'averageCost') else 0
                                print(f"  {symbol}: {shares} shares @ ${avg_cost:.2f}")
                            elif isinstance(position, str):
                                print(f"  {position}: (position details not available)")
                
                # Try to derive tickers from portfolio positions if none specified
                if not tickers:
                    portfolio_tickers = []
                    if isinstance(portfolio.get('positions'), dict):
                        portfolio_tickers = list(portfolio['positions'].keys())
                    elif isinstance(portfolio.get('positions'), list):
                        for position in portfolio['positions']:
                            if hasattr(position, 'contract') and hasattr(position.contract, 'symbol'):
                                portfolio_tickers.append(position.contract.symbol)
                            elif isinstance(position, str):
                                portfolio_tickers.append(position)
                    
                    if portfolio_tickers:
                        tickers = portfolio_tickers
                        logger.info(f"Using tickers from portfolio: {', '.join(tickers)}")
            else:
                logger.warning("Could not retrieve portfolio data. Proceeding with market analysis only.")
        
        # If still no tickers, show error and exit
        if not tickers:
            logger.error("No tickers specified and no positions found in portfolio. Use --tickers=SYMBOL1,SYMBOL2")
            return 1
        
        logger.info(f"Processing tickers in bulk: {', '.join(tickers)}")
        
        # Process all tickers in bulk
        all_results = strategy.process_stocks_bulk(tickers, portfolio)
        
        # Display results for each ticker
        for result in all_results:
            ticker = result['ticker']
            
            # Print summary to console
            print(f"\n=== {ticker} OPTIONS SUMMARY ===")
            print(f"{ticker} Price: ${result['price']:.2f}")
            
            # Print position details if available
            if result['position']['size'] != 0:
                print("\nCURRENT POSITION:")
                print(f"  Shares: {result['position']['size']}")
                print(f"  Average Cost: ${result['position']['avg_cost']:.2f}")
                print(f"  Market Value: ${result['position']['market_value']:.2f}")
                print(f"  Unrealized P&L: ${result['position']['unrealized_pnl']:.2f}")
            
            # Print recommendation
            print("\nRECOMMENDED STRATEGY:")
            rec = result['recommendation']
            option_type = rec['type']
            strike = rec['strike']
            expiration = rec['expiration']
            action = rec['action']
            
            option_data = result['options']['put'] if option_type == 'PUT' else result['options']['call']
            
            print(f"{action} {option_type}  @ Strike ${strike:.2f} " + 
                  (f"({(strike/result['price'] - 1)*100:.0f}%)" if option_type == 'CALL' else f"({(strike/result['price'] - 1)*100:.0f}%)"))
            
            # Handle None values in option data
            bid = option_data.get('bid', 0) or 0
            ask = option_data.get('ask', 0) or 0
            last = option_data.get('last', 0) or 0
            print(f"  Bid: ${bid:.2f}, Ask: ${ask:.2f}, Last: ${last:.2f}")
            
            # Print alternative recommendation if available
            if 'alternative' in rec:
                print("\nALTERNATIVE STRATEGY:")
                alt = rec['alternative']
                alt_type = alt['type']
                alt_strike = alt['strike']
                alt_action = alt['action']
                
                alt_option_data = result['options']['put'] if alt_type == 'PUT' else result['options']['call']
                
                print(f"{alt_action} {alt_type}  @ Strike ${alt_strike:.2f} " + 
                      (f"({(alt_strike/result['price'] - 1)*100:.0f}%)" if alt_type == 'CALL' else f"({(alt_strike/result['price'] - 1)*100:.0f}%)"))
                
                # Handle None values in option data
                alt_bid = alt_option_data.get('bid', 0) or 0
                alt_ask = alt_option_data.get('ask', 0) or 0
                alt_last = alt_option_data.get('last', 0) or 0
                print(f"  Bid: ${alt_bid:.2f}, Ask: ${alt_ask:.2f}, Last: ${alt_last:.2f}")
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        logger.error(traceback.format_exc())
        return 1
    finally:
        if 'ib_connection' in locals() and ib_connection.is_connected():
            ib_connection.disconnect()
            
    return 0

if __name__ == "__main__":
    sys.exit(main()) 