"""
Options API routes
"""

from flask import Blueprint, request, jsonify
from api.services.options_service import OptionsService

bp = Blueprint('options', __name__, url_prefix='/api/options')
options_service = OptionsService()

@bp.route('/<ticker>', methods=['GET'])
def get_options_data(ticker):
    """
    Get options data for a specific ticker
    
    Args:
        ticker (str): Stock ticker symbol
    """
    try:
        # Parse query parameters
        expiration = request.args.get('expiration', None)
        strikes = request.args.get('strikes', 10, type=int)
        interval = request.args.get('interval', 5, type=int)
        monthly = request.args.get('monthly', False, type=bool)
        
        # Get options data
        results = options_service.get_options_data(
            ticker, 
            expiration=expiration,
            strikes=strikes,
            interval=interval,
            monthly=monthly
        )
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<ticker>/chain', methods=['GET'])
def get_option_chain(ticker):
    """
    Get the full option chain for a specific ticker
    
    Args:
        ticker (str): Stock ticker symbol
    """
    try:
        # Parse query parameters
        expiration = request.args.get('expiration', None)
        
        # Get option chain
        results = options_service.get_option_chain(ticker, expiration=expiration)
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/expirations', methods=['GET'])
def get_expirations():
    """
    Get available option expiration dates
    """
    try:
        # Parse query parameters
        ticker = request.args.get('ticker', None)
        
        # Get expirations
        results = options_service.get_expirations(ticker)
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500 