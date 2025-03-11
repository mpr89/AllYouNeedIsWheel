"""
Export module for saving option data in different formats
"""

import os
import csv
import logging
import pandas as pd
from datetime import datetime

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

def create_combined_html_report(stocks_data, expiration, output_dir='reports'):
    """
    Create a combined HTML report for multiple stocks
    
    Args:
        stocks_data (list): List of dictionaries containing stock data
        expiration (str): Option expiration date
        output_dir (str): Directory to save export files
        
    Returns:
        str: Path to the saved HTML file
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate timestamp for filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Define filename
    filename = os.path.join(output_dir, f"combined_options_data_{timestamp}.html")
    
    # Format expiration date for display
    try:
        # Try to parse the expiration from YYYYMMDD format
        exp_year = expiration[:4]
        exp_month = expiration[4:6]
        exp_day = expiration[6:8]
        formatted_expiration = f"{exp_year}-{exp_month}-{exp_day}"
    except:
        formatted_expiration = expiration
    
    # Create HTML header
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Combined Options Data</title>
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
            h1, h2, h3 {{
                color: #2c3e50;
            }}
            .summary {{
                background-color: #f8f9fa;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 20px;
                border-left: 5px solid #007bff;
            }}
            .stock-section {{
                margin-bottom: 40px;
                border-bottom: 1px solid #ddd;
                padding-bottom: 20px;
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
            .nav {{
                display: flex;
                gap: 10px;
                margin-bottom: 20px;
                background-color: #f8f9fa;
                padding: 10px;
                border-radius: 5px;
                position: sticky;
                top: 0;
                z-index: 100;
            }}
            .nav a {{
                text-decoration: none;
                color: #007bff;
                font-weight: bold;
                padding: 5px 10px;
                border-radius: 3px;
            }}
            .nav a:hover {{
                background-color: #007bff;
                color: white;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Combined Options Data</h1>
            
            <div class="summary">
                <p><strong>Expiration Date:</strong> {formatted_expiration}</p>
                <p><strong>Stocks Analyzed:</strong> {', '.join(stock['ticker'] for stock in stocks_data)}</p>
            </div>
            
            <div class="nav">
                <a href="#top">Top</a>
    """
    
    # Add navigation links for each stock
    for stock in stocks_data:
        ticker = stock['ticker']
        html_content += f'<a href="#{ticker.lower()}">{ticker}</a>'
    
    html_content += """
            </div>
    """
    
    # Add sections for each stock
    for stock in stocks_data:
        ticker = stock['ticker']
        stock_price = stock['stock_price']
        call_options = stock['call_options']
        put_options = stock['put_options']
        
        html_content += f"""
            <div id="{ticker.lower()}" class="stock-section">
                <h2>{ticker} Options</h2>
                
                <div class="summary">
                    <p><strong>Stock Price:</strong> <span class="price-data">${stock_price:.2f}</span></p>
                </div>
                
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
        
        # Get all strikes for this stock
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
        
        html_content += """
                    </tbody>
                </table>
            </div>
        """
    
    # Complete the HTML
    html_content += f"""
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
    
    return filename 