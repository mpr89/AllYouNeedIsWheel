"""
Export module for saving option data in different formats
"""

import os
import csv
import logging
import pandas as pd
from datetime import datetime
from .utils import format_date_string, parse_date_string

logger = logging.getLogger('autotrader.export')

def format_price(price):
    """
    Format price for display
    
    Args:
        price: Price value (float or string)
        
    Returns:
        str: Formatted price string
    """
    if price is None or (isinstance(price, (int, float)) and price <= 0):
        return 'N/A'
    elif isinstance(price, str):
        return price
    else:
        return f"${price:.2f}"

def export_to_csv(stock_price, expiration, call_options, put_options, filename=None, prefix=''):
    """
    Export option data to CSV file
    
    Args:
        stock_price (float): Stock price
        expiration (str): Option expiration date
        call_options (dict): Call option data
        put_options (dict): Put option data
        filename (str): Optional filename, if None a default name is generated
        prefix (str): Optional prefix for the filename (e.g., ticker name)
        
    Returns:
        str: Path to the saved CSV file
    """
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{prefix}options_data_{timestamp}.csv"
    
    # Create the directory if it doesn't exist
    os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
    
    # Prepare data for CSV
    csv_data = []
    
    # Header row
    csv_data.append(['Stock Price', f"${stock_price:.2f}"])
    csv_data.append(['Expiration', expiration])
    csv_data.append([])  # Empty row
    
    # Create headers
    csv_data.append(['Strike', 'Call Bid', 'Call Ask', 'Call Last', '', 'Put Bid', 'Put Ask', 'Put Last'])
    
    # Get all strikes (combine and sort)
    all_strikes = sorted(set(list(call_options.keys()) + list(put_options.keys())))
    
    # Add data rows
    for strike in all_strikes:
        row = [strike]
        
        # Add call data if available
        if strike in call_options:
            row.extend([
                call_options[strike]['bid'],
                call_options[strike]['ask'],
                call_options[strike]['last']
            ])
        else:
            row.extend(['N/A', 'N/A', 'N/A'])
        
        # Add spacer
        row.append('')
        
        # Add put data if available
        if strike in put_options:
            row.extend([
                put_options[strike]['bid'],
                put_options[strike]['ask'],
                put_options[strike]['last']
            ])
        else:
            row.extend(['N/A', 'N/A', 'N/A'])
        
        csv_data.append(row)
    
    # Write to CSV
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerows(csv_data)
    
    logger.info(f"Exported option data to CSV: {filename}")
    return filename

def export_to_html(stock_price, expiration, call_options, put_options, filename=None, prefix='', title=None):
    """
    Export option data to HTML file with nice formatting
    
    Args:
        stock_price (float): Stock price
        expiration (str): Option expiration date
        call_options (dict): Call option data
        put_options (dict): Put option data
        filename (str): Optional filename, if None a default name is generated
        prefix (str): Optional prefix for the filename (e.g., ticker name)
        title (str): Optional title for the HTML page
        
    Returns:
        str: Path to the saved HTML file
    """
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{prefix}options_data_{timestamp}.html"
    
    # Create the directory if it doesn't exist
    os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
    
    # Format expiration date for display
    try:
        # Try to parse the expiration from YYYYMMDD format
        exp_year = expiration[:4]
        exp_month = expiration[4:6]
        exp_day = expiration[6:8]
        formatted_expiration = f"{exp_year}-{exp_month}-{exp_day}"
    except:
        formatted_expiration = expiration
    
    # Default title if none provided
    if title is None:
        if prefix:
            # Extract ticker from prefix (assuming format like "nvda_")
            ticker = prefix.strip('_').upper()
            title = f"{ticker} Options Data"
        else:
            title = "Options Data"
    
    # Create HTML content
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 20px;
                color: #333;
                line-height: 1.6;
            }}
            .container {{
                max-width: 1000px;
                margin: 0 auto;
            }}
            h1, h2 {{
                color: #2c3e50;
            }}
            .summary {{
                background-color: #f8f9fa;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 20px;
                border-left: 5px solid #007bff;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 20px;
            }}
            th, td {{
                padding: 12px 15px;
                text-align: center;
                border-bottom: 1px solid #ddd;
            }}
            th {{
                background-color: #007bff;
                color: white;
                position: sticky;
                top: 0;
            }}
            tr:nth-child(even) {{
                background-color: #f2f2f2;
            }}
            tr:hover {{
                background-color: #e9ecef;
            }}
            .timestamp {{
                font-size: 12px;
                color: #6c757d;
                margin-top: 40px;
                text-align: center;
            }}
            .price-data {{
                font-weight: bold;
                font-size: 18px;
            }}
            .strike-header {{
                background-color: #343a40;
            }}
            .call-section th {{
                background-color: #28a745;
            }}
            .put-section th {{
                background-color: #dc3545;
            }}
            .unavailable {{
                color: #999;
                font-style: italic;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>{title}</h1>
            
            <div class="summary">
                <p><strong>Stock Price:</strong> <span class="price-data">${stock_price:.2f}</span></p>
                <p><strong>Expiration Date:</strong> {formatted_expiration}</p>
            </div>
            
            <h2>Option Prices</h2>
            
            <table>
                <thead>
                    <tr>
                        <th rowspan="2" class="strike-header">Strike</th>
                        <th colspan="3" class="call-section">Call Options</th>
                        <th colspan="3" class="put-section">Put Options</th>
                    </tr>
                    <tr>
                        <th class="call-section">Bid</th>
                        <th class="call-section">Ask</th>
                        <th class="call-section">Last</th>
                        <th class="put-section">Bid</th>
                        <th class="put-section">Ask</th>
                        <th class="put-section">Last</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    # Get all strikes (combine and sort)
    all_strikes = sorted(set(list(call_options.keys()) + list(put_options.keys())))
    
    # Add data rows
    for strike in all_strikes:
        html_content += f"""
                    <tr>
                        <td><strong>${strike}</strong></td>
        """
        
        # Add call data if available
        if strike in call_options:
            call = call_options[strike]
            html_content += f"""
                        <td>{call['bid']}</td>
                        <td>{call['ask']}</td>
                        <td>{call['last']}</td>
            """
        else:
            html_content += """
                        <td class="unavailable">N/A</td>
                        <td class="unavailable">N/A</td>
                        <td class="unavailable">N/A</td>
            """
        
        # Add put data if available
        if strike in put_options:
            put = put_options[strike]
            html_content += f"""
                        <td>{put['bid']}</td>
                        <td>{put['ask']}</td>
                        <td>{put['last']}</td>
            """
        else:
            html_content += """
                        <td class="unavailable">N/A</td>
                        <td class="unavailable">N/A</td>
                        <td class="unavailable">N/A</td>
            """
        
        html_content += """
                    </tr>
        """
    
    # Complete the HTML
    html_content += f"""
                </tbody>
            </table>
            
            <div class="timestamp">
                Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </div>
        </div>
    </body>
    </html>
    """
    
    # Write to file
    with open(filename, 'w') as f:
        f.write(html_content)
    
    logger.info(f"Exported option data to HTML: {filename}")
    return filename

def export_options_data(stock_price, expiration, call_options, put_options, format='all', output_dir='reports', prefix=''):
    """
    Export options data in specified format
    
    Args:
        stock_price (float): Stock price
        expiration (str): Option expiration date
        call_options (dict): Call option data
        put_options (dict): Put option data
        format (str): Export format ('csv', 'html', or 'all')
        output_dir (str): Directory to save export files
        prefix (str): Optional prefix for filenames (e.g., ticker name)
        
    Returns:
        dict: Paths to exported files
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Results dictionary to return file paths
    results = {}
    
    # Generate timestamp for filenames
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Export to CSV if requested
    if format.lower() in ['csv', 'all']:
        csv_filename = os.path.join(output_dir, f"{prefix}options_data_{timestamp}.csv")
        csv_path = export_to_csv(
            stock_price,
            expiration,
            call_options,
            put_options,
            filename=csv_filename
        )
        results['csv'] = csv_path
    
    # Export to HTML if requested
    if format.lower() in ['html', 'all']:
        html_filename = os.path.join(output_dir, f"{prefix}options_data_{timestamp}.html")
        # Get title from prefix if available
        title = None
        if prefix:
            # Extract ticker from prefix (assuming format like "nvda_")
            ticker = prefix.strip('_').upper()
            title = f"{ticker} Options Data"
            
        html_path = export_to_html(
            stock_price,
            expiration,
            call_options,
            put_options,
            filename=html_filename,
            title=title
        )
        results['html'] = html_path
    
    return results

def process_option_data(option_data, field):
    """
    Process option data to get a value for display, using last price as fallback
    
    Args:
        option_data (dict): Option data containing bid, ask, last
        field (str): Field to get ('bid', 'ask')
        
    Returns:
        str: Formatted price string
    """
    # Use the specified field if available
    if field in option_data and not (option_data[field] == 'N/A' or 
                                    (isinstance(option_data[field], str) and option_data[field].startswith('$0')) or
                                    (isinstance(option_data[field], (int, float)) and option_data[field] <= 0)):
        return option_data[field]
    
    # Fall back to last price if main field not available
    if 'last' in option_data and not (option_data['last'] == 'N/A' or 
                                    (isinstance(option_data['last'], str) and option_data['last'].startswith('$0')) or
                                    (isinstance(option_data['last'], (int, float)) and option_data['last'] <= 0)):
        return option_data['last']
    
    # If nothing available
    return 'N/A'

def create_combined_html_report(stocks_data, expiration, output_dir='reports'):
    """
    Create a combined HTML report for multiple stocks
    
    Args:
        stocks_data: List of dictionaries containing stock data
        expiration: Option expiration date
        output_dir: Directory to save the report
        
    Returns:
        str: Path to the HTML report
    """
    # Create timestamp for filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Make sure the output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Create HTML content
    html_content = []
    html_content.append("<html><head>")
    html_content.append("<style>")
    html_content.append("body { font-family: Arial, sans-serif; margin: 20px; }")
    html_content.append("table { border-collapse: collapse; margin: 10px 0; }")
    html_content.append("th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }")
    html_content.append("th { background-color: #f5f5f5; }")
    html_content.append("h1, h2 { color: #333; }")
    html_content.append(".profits { color: green; }")
    html_content.append(".losses { color: red; }")
    html_content.append("</style>")
    html_content.append("</head><body>")
    
    html_content.append("<h1>Options Trading Report</h1>")
    html_content.append(f"<p>Expiration Date: {expiration}</p>")
    html_content.append(f"<p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>")
    
    # Add summary table
    html_content.append("<h2>Summary</h2>")
    html_content.append("<table>")
    html_content.append("<tr><th>Ticker</th><th>Current Price</th><th>Position</th><th>Recommended Put (Sell)</th><th>Recommended Call</th></tr>")
    
    for stock in stocks_data:
        ticker = stock['ticker']
        price = stock['price']
        recommendation = stock.get('recommendation', {})
        position = stock.get('position')
        
        # Format position info
        position_info = "None"
        if position:
            shares = position['shares']
            avg_cost = position['avg_cost']
            position_info = f"{shares:.0f} shares @ ${avg_cost:.2f}"
        
        # Get recommendations
        put_rec = recommendation.get('put', {})
        call_rec = recommendation.get('call', {})
        
        put_info = ""
        if put_rec:
            put_strike = put_rec.get('strike')
            put_info = f"${put_strike:.2f} ({put_rec.get('percent')}%)"
            
        call_info = ""
        if call_rec:
            call_strike = call_rec.get('strike')
            call_action = call_rec.get('action')
            call_info = f"{call_action} ${call_strike:.2f} ({call_rec.get('percent')}%)"
            
        html_content.append(f"<tr>")
        html_content.append(f"<td>{ticker}</td>")
        html_content.append(f"<td>${price:.2f}</td>")
        html_content.append(f"<td>{position_info}</td>")
        html_content.append(f"<td>{put_info}</td>")
        html_content.append(f"<td>{call_info}</td>")
        html_content.append("</tr>")
        
    html_content.append("</table>")
    
    # Add detailed information for each stock
    for stock in stocks_data:
        ticker = stock['ticker']
        price = stock['price']
        options = stock.get('options', {})
        recommendation = stock.get('recommendation', {})
        position = stock.get('position')
        estimated_earnings = stock.get('estimated_earnings', {})
        
        html_content.append(f"<h2>{ticker} (${price:.2f})</h2>")
        
        # Add position information if available
        if position:
            html_content.append("<h3>Current Position</h3>")
            html_content.append("<table>")
            html_content.append("<tr><th>Shares</th><th>Average Cost</th><th>Market Value</th><th>Unrealized P&L</th></tr>")
            
            # Format unrealized PnL with color
            pnl = position['unrealized_pnl']
            pnl_class = "profits" if pnl >= 0 else "losses"
            pnl_sign = "+" if pnl > 0 else ""
            
            html_content.append(f"<tr>")
            html_content.append(f"<td>{position['shares']:.0f}</td>")
            html_content.append(f"<td>${position['avg_cost']:.2f}</td>")
            html_content.append(f"<td>${position['market_value']:.2f}</td>")
            html_content.append(f"<td class='{pnl_class}'>{pnl_sign}${pnl:.2f}</td>")
            html_content.append("</tr>")
            html_content.append("</table>")
        
        if recommendation:
            html_content.append("<h3>Recommended Strategy:</h3>")
            html_content.append("<table>")
            html_content.append("<tr><th>Action</th><th>Type</th><th>Strike</th><th>Change</th><th>Bid</th><th>Ask</th><th>Last</th></tr>")
            
            # Add put recommendation
            put_rec = recommendation.get('put', {})
            if put_rec:
                put_strike = put_rec.get('strike')
                put_action = put_rec.get('action')
                put_key = f"{put_strike}_P"
                put_data = options.get(put_key, {})
                
                bid = format_price(put_data.get('bid'))
                ask = format_price(put_data.get('ask'))
                last = format_price(put_data.get('last'))
                
                html_content.append(f"<tr>")
                html_content.append(f"<td>{put_action}</td>")
                html_content.append(f"<td>PUT</td>")
                html_content.append(f"<td>${put_strike:.2f}</td>")
                html_content.append(f"<td>{put_rec.get('percent')}%</td>")
                html_content.append(f"<td>{bid}</td>")
                html_content.append(f"<td>{ask}</td>")
                html_content.append(f"<td>{last}</td>")
                html_content.append("</tr>")
            
            # Add call recommendation
            call_rec = recommendation.get('call', {})
            if call_rec:
                call_strike = call_rec.get('strike')
                call_action = call_rec.get('action')
                call_key = f"{call_strike}_C"
                call_data = options.get(call_key, {})
                
                bid = format_price(call_data.get('bid'))
                ask = format_price(call_data.get('ask'))
                last = format_price(call_data.get('last'))
                
                html_content.append(f"<tr>")
                html_content.append(f"<td>{call_action}</td>")
                html_content.append(f"<td>CALL</td>")
                html_content.append(f"<td>${call_strike:.2f}</td>")
                html_content.append(f"<td>{call_rec.get('percent')}%</td>")
                html_content.append(f"<td>{bid}</td>")
                html_content.append(f"<td>{ask}</td>")
                html_content.append(f"<td>{last}</td>")
                html_content.append("</tr>")
                
            html_content.append("</table>")
            
        # Add estimated earnings information if available
        if estimated_earnings:
            html_content.append("<h3>Potential Earnings:</h3>")
            
            # Covered Call earnings
            call_earnings = estimated_earnings.get('call')
            if call_earnings:
                html_content.append("<h4>Covered Call Strategy:</h4>")
                html_content.append("<table>")
                html_content.append("<tr><th>Contracts</th><th>Premium per Contract</th><th>Total Premium</th><th>Return on Position</th></tr>")
                
                html_content.append(f"<tr>")
                html_content.append(f"<td>{call_earnings['contracts']}</td>")
                html_content.append(f"<td>${call_earnings['premium_per_contract']:.2f}</td>")
                html_content.append(f"<td>${call_earnings['total_premium']:.2f}</td>")
                html_content.append(f"<td>{call_earnings['premium_percent']:.2f}%</td>")
                html_content.append("</tr>")
                html_content.append("</table>")
            
            # Cash-Secured Put earnings
            put_earnings = estimated_earnings.get('put')
            if put_earnings:
                html_content.append("<h4>Cash-Secured Put Strategy:</h4>")
                html_content.append("<table>")
                html_content.append("<tr><th>Max Contracts</th><th>Premium per Contract</th><th>Total Premium</th><th>Return on Cash</th></tr>")
                
                html_content.append(f"<tr>")
                html_content.append(f"<td>{put_earnings['contracts']}</td>")
                html_content.append(f"<td>${put_earnings['premium_per_contract']:.2f}</td>")
                html_content.append(f"<td>${put_earnings['total_premium']:.2f}</td>")
                html_content.append(f"<td>{put_earnings['premium_percent']:.2f}%</td>")
                html_content.append("</tr>")
                html_content.append("</table>")
    
    html_content.append("</body></html>")
    
    # Write HTML file
    html_path = os.path.join(output_dir, f"options_report_{timestamp}.html")
    with open(html_path, 'w') as f:
        f.write("\n".join(html_content))
    
    return html_path 