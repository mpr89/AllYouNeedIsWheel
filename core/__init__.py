"""
AutoTrader Core Module
"""

# Import tools and utilities
from .utils import (
    setup_logging, 
    rotate_logs, 
    rotate_reports, 
    get_closest_friday, 
    get_next_monthly_expiration
)

# Import connection classes
from .connection import IBConnection, Option

# Import processing classes
from .processing import (
    SimpleOptionsStrategy,
    print_stock_summary,
    format_currency,
    format_percentage
)

__all__ = [
    # Connection
    'IBConnection',
    
    # Utils
    'rotate_logs',
    'rotate_reports',
    'setup_logging',
    'get_closest_friday',
    'get_next_monthly_expiration',
    
    # Processing
    'print_stock_summary',
    'SimpleOptionsStrategy',
    'format_currency',
    'format_percentage'
] 