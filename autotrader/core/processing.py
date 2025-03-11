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
import math
import traceback
import jinja2
from ib_insync import Option

from autotrader.core.utils import get_closest_friday, get_next_monthly_expiration

# Configure logger
logger = logging.getLogger('autotrader.processing')

def format_currency(value):
    """Format a value as currency"""
    if value is None or math.isnan(value):
        return "$0.00"
    return f"${value:.2f}"

def format_percentage(value):
    """Format a value as percentage"""
    if value is None or math.isnan(value):
        return "0.00%"
    return f"{value*100:.2f}%"

class SimpleOptionsStrategy:
    """
    Class to implement simple options strategies based on real market data
    """
    
    def __init__(self, ib_connection, config):
        """
        Initialize the options strategy engine
        
        Args:
            ib_connection: IBConnection instance
            config: Configuration dictionary
        """
        self.ib_connection = ib_connection
        self.config = config
        
    def _adjust_to_standard_strike(self, strike):
        """
        Adjust a strike price to a standard option strike increment
        
        Args:
            strike: Strike price
            
        Returns:
            float: Adjusted strike price
        """
        if strike <= 5:
            # $0.50 increments for stocks under $5
            return round(strike * 2) / 2
        elif strike <= 25:
            # $1.00 increments for stocks under $25
            return round(strike)
        elif strike <= 200:
            # $5.00 increments for stocks under $200
            return round(strike / 5) * 5
        else:
            # $10.00 increments for stocks over $200
            return round(strike / 10) * 10
    
    def process_stock(self, ticker, portfolio=None):
        """
        Process a stock to find option trade recommendations
        
        Args:
            ticker (str): Stock ticker symbol
            portfolio (dict, optional): Portfolio data from IB. Defaults to None.
            
        Returns:
            dict: Dictionary with stock and option data and recommendations
        """
        try:
            # Get the stock price
            stock_price = self.ib_connection.get_stock_price(ticker)
            
            if stock_price is None or math.isnan(stock_price):
                logger.error(f"Could not get price for {ticker}, skipping")
                return None
                
            # Check if we have a position in this stock from the portfolio
            stock_position = None
            position_size = 0
            avg_cost = 0
            market_value = 0
            unrealized_pnl = 0
            
            if portfolio and 'positions' in portfolio:
                try:
                    # Try to find position in the portfolio dictionary format
                    if isinstance(portfolio['positions'], dict) and ticker in portfolio['positions']:
                        position_data = portfolio['positions'][ticker]
                        position_size = position_data.get('shares', 0)
                        avg_cost = position_data.get('avg_cost', 0)
                        market_value = position_data.get('market_value', 0)
                        unrealized_pnl = position_data.get('unrealized_pnl', 0)
                        stock_position = position_data
                    # Try to find position in the older list of positions format
                    elif isinstance(portfolio['positions'], list):
                        for position in portfolio['positions']:
                            if isinstance(position, dict) and 'contract' in position and hasattr(position['contract'], 'symbol'):
                                if position['contract'].symbol == ticker and position['contract'].secType == 'STK':
                                    stock_position = position
                                    position_size = position.get('position', 0)
                                    avg_cost = position.get('averageCost', 0)
                                    market_value = position.get('marketValue', 0)
                                    unrealized_pnl = position.get('unrealizedPNL', 0)
                                    break
                            elif isinstance(position, str) and position == ticker:
                                # Legacy format where positions is a list of ticker strings
                                logger.debug(f"Found position for {ticker} in legacy format")
                                # Don't create mock position data anymore
                                pass
                except Exception as e:
                    logger.warning(f"Error checking portfolio positions: {e}")
                    stock_position = None
            
            # Determine strategy based on position
            strategy = "NEUTRAL"  # Default strategy
            
            if stock_position:
                # Decide strategy based on position
                if position_size > 0:
                    strategy = "BULLISH"  # We own the stock, sell calls
                elif position_size < 0:
                    strategy = "BEARISH"  # We are short the stock, sell puts
            
            # Calculate option strike prices at specified percentages
            put_otm_pct = self.config.get('put_otm_percentage', 20)
            call_otm_pct = self.config.get('call_otm_percentage', 20)
            
            put_strike = round(stock_price * (1 - put_otm_pct/100))
            call_strike = round(stock_price * (1 + call_otm_pct/100))
            
            # Adjust to standard option strike increments
            put_strike = self._adjust_to_standard_strike(put_strike)
            call_strike = self._adjust_to_standard_strike(call_strike)
            
            # Get the expiration date for options (closest Friday by default)
            if self.config.get('use_monthly_options', False):
                expiration = get_next_monthly_expiration()
            else:
                expiration = get_closest_friday().strftime('%Y%m%d')
                
            # Get option prices
            put_contract = Option(ticker, expiration, put_strike, 'P')
            call_contract = Option(ticker, expiration, call_strike, 'C')
            
            put_data = self.ib_connection.get_option_price(put_contract)
            call_data = self.ib_connection.get_option_price(call_contract)
            
            # Calculate potential earnings for options
            put_earnings = None
            call_earnings = None
            
            if put_data and 'bid' in put_data and put_data['bid'] is not None:
                # For cash-secured puts
                max_contracts = math.floor(self.config.get('max_position_value', 20000) / (put_strike * 100))
                premium_per_contract = put_data['bid'] * 100  # Convert to dollar amount
                total_premium = premium_per_contract * max_contracts
                return_on_cash = (total_premium / (put_strike * 100 * max_contracts)) * 100 if max_contracts > 0 else 0
                
                put_earnings = {
                    'strategy': 'Cash-Secured Put',
                    'max_contracts': max_contracts,
                    'premium_per_contract': premium_per_contract,
                    'total_premium': total_premium,
                    'return_on_cash': return_on_cash
                }
            
            if call_data and 'bid' in call_data and call_data['bid'] is not None and position_size > 0:
                # For covered calls (only if we own the stock)
                max_contracts = math.floor(abs(position_size) / 100)  # Each contract covers 100 shares
                premium_per_contract = call_data['bid'] * 100  # Convert to dollar amount
                total_premium = premium_per_contract * max_contracts
                return_on_capital = (total_premium / (stock_price * 100 * max_contracts)) * 100 if max_contracts > 0 else 0
                
                call_earnings = {
                    'strategy': 'Covered Call',
                    'max_contracts': max_contracts,
                    'premium_per_contract': premium_per_contract,
                    'total_premium': total_premium,
                    'return_on_capital': return_on_capital
                }
            
            # Create recommendation based on portfolio position
            recommendation = {}
            
            if strategy == "BULLISH" and position_size > 0:
                # We own the stock, recommend selling calls
                recommendation = {
                    'action': 'SELL',
                    'type': 'CALL',
                    'strike': call_strike,
                    'expiration': expiration,
                    'earnings': call_earnings
                }
            elif strategy == "BEARISH" and position_size < 0:
                # We are short the stock, recommend selling puts
                recommendation = {
                    'action': 'SELL',
                    'type': 'PUT',
                    'strike': put_strike,
                    'expiration': expiration,
                    'earnings': put_earnings
                }
            else:
                # Neutral strategy or no position
                # For simplicity, recommend selling puts as it requires less capital than buying stock
                recommendation = {
                    'action': 'SELL',
                    'type': 'PUT',
                    'strike': put_strike,
                    'expiration': expiration,
                    'earnings': put_earnings
                }
                
                # Also include call option as a bullish alternative
                recommendation['alternative'] = {
                    'action': 'BUY',
                    'type': 'CALL',
                    'strike': call_strike,
                    'expiration': expiration
                }
            
            # Build and return the result
            result = {
                'ticker': ticker,
                'price': stock_price,
                'strategy': strategy,
                'position': {
                    'size': position_size,
                    'avg_cost': avg_cost,
                    'market_value': market_value,
                    'unrealized_pnl': unrealized_pnl
                },
                'options': {
                    'expiration': expiration,
                    'put': {
                        'strike': put_strike,
                        'bid': put_data['bid'] if put_data and 'bid' in put_data else None,
                        'ask': put_data['ask'] if put_data and 'ask' in put_data else None,
                        'last': put_data['last'] if put_data and 'last' in put_data else None
                    },
                    'call': {
                        'strike': call_strike,
                        'bid': call_data['bid'] if call_data and 'bid' in call_data else None,
                        'ask': call_data['ask'] if call_data and 'ask' in call_data else None,
                        'last': call_data['last'] if call_data and 'last' in call_data else None
                    }
                },
                'recommendation': recommendation
            }
            
            return result
        except Exception as e:
            logger.error(f"Error processing {ticker}: {str(e)}")
            logger.error(traceback.format_exc())
            return None
            
    def generate_html_report(self, results, output_file):
        """
        Generate an HTML report for the processed stocks
        
        Args:
            results (list): List of stock data dictionaries
            output_file (str): Output file path
            
        Returns:
            str: Path to the generated report
        """
        try:
            # Get the template directory
            template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'templates')
            
            # Create Jinja2 environment
            env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(template_dir),
                autoescape=jinja2.select_autoescape(['html', 'xml'])
            )
            
            # Add custom filters
            env.filters['format_currency'] = format_currency
            env.filters['format_percentage'] = format_percentage
            
            # Get the template
            template = env.get_template('options_report.html')
            
            # Render the template
            html = template.render(
                stocks=results,
                generation_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                expiration_date=results[0]['options']['expiration'] if results else ''
            )
            
            # Write the HTML to file
            with open(output_file, 'w') as f:
                f.write(html)
            
            return output_file
        except Exception as e:
            logger.error(f"Error generating HTML report: {str(e)}")
            logger.error(traceback.format_exc())
            return None

    def process_stocks_bulk(self, tickers, portfolio=None):
        """
        Process multiple stocks in bulk to find option trade recommendations
        
        Args:
            tickers (list): List of stock ticker symbols
            portfolio (dict, optional): Portfolio data from IB. Defaults to None.
            
        Returns:
            list: List of dictionaries with stock and option data and recommendations
        """
        if not tickers:
            logger.warning("No tickers provided for bulk processing")
            return []
            
        logger.info(f"Processing {len(tickers)} tickers in bulk: {', '.join(tickers)}")
        
        # Get all stock prices in one request
        logger.info("Fetching stock prices for all tickers...")
        stock_prices = self.ib_connection.get_multiple_stock_prices(tickers)
        if not stock_prices:
            logger.error("Failed to get stock prices")
            return []
            
        logger.info(f"Successfully retrieved {len(stock_prices)} stock prices")
        
        # Determine the expiration date for options
        if self.config.get('use_monthly_options', False):
            expiration = get_next_monthly_expiration()
        else:
            expiration = get_closest_friday().strftime('%Y%m%d')
            
        logger.info(f"Using option expiration date: {expiration}")
        
        # Prepare strikes for each ticker
        put_otm_pct = self.config.get('put_otm_percentage', 20)
        call_otm_pct = self.config.get('call_otm_percentage', 20)
        
        strikes_map = {}
        valid_tickers = []
        for ticker, price in stock_prices.items():
            if price is None or math.isnan(price):
                logger.warning(f"Could not get price for {ticker}, skipping")
                continue
                
            # Calculate option strike prices at specified percentages
            put_strike = self._adjust_to_standard_strike(price * (1 - put_otm_pct/100))
            call_strike = self._adjust_to_standard_strike(price * (1 + call_otm_pct/100))
            
            strikes_map[ticker] = [put_strike, call_strike]
            valid_tickers.append(ticker)
        
        logger.info(f"Calculated strike prices for {len(strikes_map)} tickers")
        
        # Get option prices for all tickers and strikes in one batch
        logger.info("Fetching option prices for all tickers and strikes...")
        all_option_data = self.ib_connection.get_multiple_stocks_option_prices(
            valid_tickers, 
            expiration, 
            strikes_map=strikes_map
        )
        
        logger.info(f"Successfully retrieved option data for {len(all_option_data)} tickers")
        
        # Process each ticker with the data we've gathered
        results = []
        for i, ticker in enumerate(valid_tickers):
            logger.info(f"Processing data for {ticker} ({i+1}/{len(valid_tickers)})")
            if ticker not in stock_prices or stock_prices[ticker] is None:
                continue
                
            try:
                stock_price = stock_prices[ticker]
                
                # Get the strikes for this ticker
                if ticker not in strikes_map:
                    continue
                
                put_strike, call_strike = strikes_map[ticker]
                
                # Check if we have a position in this stock from the portfolio
                stock_position = None
                position_size = 0
                avg_cost = 0
                market_value = 0
                unrealized_pnl = 0
                
                if portfolio and 'positions' in portfolio:
                    # Try to find position in the portfolio dictionary format
                    if isinstance(portfolio['positions'], dict) and ticker in portfolio['positions']:
                        position_data = portfolio['positions'][ticker]
                        position_size = position_data.get('shares', 0)
                        avg_cost = position_data.get('avg_cost', 0)
                        market_value = position_data.get('market_value', 0)
                        unrealized_pnl = position_data.get('unrealized_pnl', 0)
                        stock_position = position_data
                    # Try to find position in the older list of positions format
                    elif isinstance(portfolio['positions'], list):
                        for position in portfolio['positions']:
                            if isinstance(position, dict) and 'contract' in position and hasattr(position['contract'], 'symbol'):
                                if position['contract'].symbol == ticker and position['contract'].secType == 'STK':
                                    stock_position = position
                                    position_size = position.get('position', 0)
                                    avg_cost = position.get('averageCost', 0)
                                    market_value = position.get('marketValue', 0)
                                    unrealized_pnl = position.get('unrealizedPNL', 0)
                                    break
                            elif isinstance(position, str) and position == ticker:
                                # Legacy format where positions is a list of ticker strings
                                logger.debug(f"Found position for {ticker} in legacy format")
                                # Don't create mock position data anymore - use real portfolio data
                                pass
                
                # Extract option data for this ticker
                put_data = None
                call_data = None
                
                if ticker in all_option_data:
                    ticker_options = all_option_data[ticker]
                    for option_key, option_data in ticker_options.items():
                        # Option key is a tuple of (strike, right)
                        strike, right = option_key
                        if right == 'P' and abs(strike - put_strike) < 0.01:
                            put_data = option_data
                        elif right == 'C' and abs(strike - call_strike) < 0.01:
                            call_data = option_data
                
                # If options data not found in bulk, try individual requests as fallback
                if put_data is None:
                    put_contract = self.ib_connection.create_option_contract(ticker, expiration, put_strike, 'P')
                    put_data = self.ib_connection.get_option_price(put_contract)
                
                if call_data is None:
                    call_contract = self.ib_connection.create_option_contract(ticker, expiration, call_strike, 'C')
                    call_data = self.ib_connection.get_option_price(call_contract)
                
                # Determine strategy based on position
                strategy = "NEUTRAL"  # Default strategy
                
                if stock_position:
                    # Decide strategy based on position
                    if position_size > 0:
                        strategy = "BULLISH"  # We own the stock, sell calls
                    elif position_size < 0:
                        strategy = "BEARISH"  # We are short the stock, sell puts
                
                # Calculate potential earnings for options
                put_earnings = None
                call_earnings = None
                
                if put_data and 'bid' in put_data and put_data['bid'] is not None:
                    # For cash-secured puts
                    max_contracts = math.floor(self.config.get('max_position_value', 20000) / (put_strike * 100))
                    premium_per_contract = put_data['bid'] * 100  # Convert to dollar amount
                    total_premium = premium_per_contract * max_contracts
                    return_on_cash = (total_premium / (put_strike * 100 * max_contracts)) * 100 if max_contracts > 0 else 0
                    
                    put_earnings = {
                        'strategy': 'Cash-Secured Put',
                        'max_contracts': max_contracts,
                        'premium_per_contract': premium_per_contract,
                        'total_premium': total_premium,
                        'return_on_cash': return_on_cash
                    }
                
                if call_data and 'bid' in call_data and call_data['bid'] is not None and position_size > 0:
                    # For covered calls (only if we own the stock)
                    max_contracts = math.floor(abs(position_size) / 100)  # Each contract covers 100 shares
                    premium_per_contract = call_data['bid'] * 100  # Convert to dollar amount
                    total_premium = premium_per_contract * max_contracts
                    return_on_capital = (total_premium / (stock_price * 100 * max_contracts)) * 100 if max_contracts > 0 else 0
                    
                    call_earnings = {
                        'strategy': 'Covered Call',
                        'max_contracts': max_contracts,
                        'premium_per_contract': premium_per_contract,
                        'total_premium': total_premium,
                        'return_on_capital': return_on_capital
                    }
                
                # Create recommendation based on portfolio position
                recommendation = {}
                
                if strategy == "BULLISH" and position_size > 0:
                    # We own the stock, recommend selling calls
                    recommendation = {
                        'action': 'SELL',
                        'type': 'CALL',
                        'strike': call_strike,
                        'expiration': expiration,
                        'earnings': call_earnings
                    }
                elif strategy == "BEARISH" and position_size < 0:
                    # We are short the stock, recommend selling puts
                    recommendation = {
                        'action': 'SELL',
                        'type': 'PUT',
                        'strike': put_strike,
                        'expiration': expiration,
                        'earnings': put_earnings
                    }
                else:
                    # Neutral strategy or no position
                    # For simplicity, recommend selling puts as it requires less capital than buying stock
                    recommendation = {
                        'action': 'SELL',
                        'type': 'PUT',
                        'strike': put_strike,
                        'expiration': expiration,
                        'earnings': put_earnings
                    }
                    
                    # Also include call option as a bullish alternative
                    recommendation['alternative'] = {
                        'action': 'BUY',
                        'type': 'CALL',
                        'strike': call_strike,
                        'expiration': expiration
                    }
                
                # Build and return the result
                result = {
                    'ticker': ticker,
                    'price': stock_price,
                    'strategy': strategy,
                    'position': {
                        'size': position_size,
                        'avg_cost': avg_cost,
                        'market_value': market_value,
                        'unrealized_pnl': unrealized_pnl
                    },
                    'options': {
                        'expiration': expiration,
                        'put': {
                            'strike': put_strike,
                            'bid': put_data['bid'] if put_data and 'bid' in put_data else None,
                            'ask': put_data['ask'] if put_data and 'ask' in put_data else None,
                            'last': put_data['last'] if put_data and 'last' in put_data else None
                        },
                        'call': {
                            'strike': call_strike,
                            'bid': call_data['bid'] if call_data and 'bid' in call_data else None,
                            'ask': call_data['ask'] if call_data and 'ask' in call_data else None,
                            'last': call_data['last'] if call_data and 'last' in call_data else None
                        }
                    },
                    'recommendation': recommendation
                }
                
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing {ticker} in bulk: {str(e)}")
                logger.error(traceback.format_exc())
        
        return results

def print_stock_summary(stock_data):
    """
    Print a summary of stock data to the console
    
    Args:
        stock_data (dict): Stock data dictionary
    """
    print(f"\n=== {stock_data['ticker']} ===")
    print(f"Current Price: ${stock_data['price']:.2f}")
    
    # Print position info if available
    if stock_data.get('position') and stock_data['position'].get('size') != 0:
        position = stock_data['position']
        print(f"Position: {position['size']} shares @ ${position.get('avg_cost', 0):.2f}")
        print(f"Market Value: ${position.get('market_value', 0):.2f}")
        print(f"Unrealized P&L: ${position.get('unrealized_pnl', 0):.2f}")
    
    # Print option recommendations
    if 'recommendation' in stock_data:
        rec = stock_data['recommendation']
        print("\nRecommendation:")
        
        if rec.get('type') == 'PUT':
            option_data = stock_data['options']['put']
            print(f"{rec.get('action', 'SELL')} PUT @ ${rec.get('strike', 0):.2f} " +
                  f"({(rec.get('strike', 0)/stock_data['price'] - 1)*100:.1f}%)")
        else:
            option_data = stock_data['options']['call']
            print(f"{rec.get('action', 'BUY')} CALL @ ${rec.get('strike', 0):.2f} " +
                  f"({(rec.get('strike', 0)/stock_data['price'] - 1)*100:.1f}%)")
        
        print(f"Bid: ${option_data.get('bid', 0):.2f}, Ask: ${option_data.get('ask', 0):.2f}")
        
        if rec.get('earnings'):
            earnings = rec['earnings']
            print(f"\nEstimated Earnings ({earnings.get('strategy', '')}):")
            print(f"  Contracts: {earnings.get('max_contracts', 0)}")
            print(f"  Premium: ${earnings.get('total_premium', 0):.2f}")
            if 'return_on_cash' in earnings:
                print(f"  Return: {earnings.get('return_on_cash', 0):.2f}%")
            elif 'return_on_capital' in earnings:
                print(f"  Return: {earnings.get('return_on_capital', 0):.2f}%")

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
    Open a file in the default web browser
    
    Args:
        file_path (str): Path to the file to open
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if not os.path.exists(file_path):
            return False
            
        # Convert to file URL
        file_url = f"file://{os.path.abspath(file_path)}"
        webbrowser.open(file_url)
        return True
    except Exception as e:
        logger.error(f"Error opening browser: {str(e)}")
        return False 