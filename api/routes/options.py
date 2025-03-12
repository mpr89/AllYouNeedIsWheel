"""
Options API routes
"""

from flask import Blueprint, request, jsonify
from api.services.options_service import OptionsService

bp = Blueprint('options', __name__, url_prefix='/api/options')
options_service = OptionsService()

@bp.route('/', methods=['GET'])
def get_options():
    """
    Get options data for a specific ticker
    """
    try:
        ticker = request.args.get('ticker')
        if not ticker:
            return jsonify({'error': 'Ticker symbol is required'}), 400
            
        expiration = request.args.get('expiration')
        
        results = options_service.get_options_data(
            ticker, 
            expiration=expiration
        )
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
@bp.route('/chain', methods=['GET'])
def get_option_chain():
    """
    Get the full options chain for a ticker
    """
    try:
        ticker = request.args.get('ticker')
        if not ticker:
            return jsonify({'error': 'Ticker symbol is required'}), 400
            
        expiration = request.args.get('expiration')
        
        results = options_service.get_option_chain(ticker, expiration=expiration)
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
@bp.route('/expirations', methods=['GET'])
def get_expirations():
    """
    Get available option expiration dates for a ticker
    """
    try:
        ticker = request.args.get('ticker')
        if not ticker:
            return jsonify({'error': 'Ticker symbol is required'}), 400
            
        results = options_service.get_expirations(ticker)
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/delta-targeted', methods=['GET'])
def get_delta_targeted_options():
    """
    Get options with delta around 0.1 for each ticker in the portfolio
    """
    try:
        # Parse query parameters
        tickers = request.args.get('tickers', None)
        if tickers:
            tickers = tickers.split(',')
            
        target_delta = request.args.get('delta', 0.1, type=float)
        delta_range = request.args.get('range', 0.05, type=float)
        expiration = request.args.get('expiration')
        monthly = request.args.get('monthly', False, type=bool)
        
        # Get delta-targeted options
        results = options_service.get_delta_targeted_options(
            tickers=tickers,
            target_delta=target_delta,
            delta_range=delta_range,
            expiration=expiration,
            monthly=monthly
        )
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500 