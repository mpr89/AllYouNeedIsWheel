"""
Core package for the auto-trader
"""

from .connection import IBConnection
from .export import export_options_data, export_to_csv, export_to_html, create_combined_html_report
from .utils import (
    rotate_logs, 
    setup_logging, 
    get_closest_friday, 
    get_next_monthly_expiration,
    parse_date_string,
    format_date_string
)
from .processing import (
    process_stock,
    print_stock_summary,
    export_all_stocks_data,
    get_strikes_around_price
)

__all__ = [
    # Connection
    'IBConnection',
    
    # Export
    'export_options_data', 
    'export_to_csv', 
    'export_to_html', 
    'create_combined_html_report',
    
    # Utils
    'rotate_logs',
    'setup_logging',
    'get_closest_friday',
    'get_next_monthly_expiration',
    'parse_date_string',
    'format_date_string',
    
    # Processing
    'process_stock',
    'print_stock_summary',
    'export_all_stocks_data',
    'get_strikes_around_price'
] 