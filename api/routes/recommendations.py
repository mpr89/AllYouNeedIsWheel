"""
Options Recommendations API routes
"""

from flask import Blueprint, request, jsonify
from api.services.options_service import OptionsService

bp = Blueprint('recommendations', __name__, url_prefix='/api/recommendations')
options_service = OptionsService()

@bp.route('/', methods=['GET'])
def get_recommendations():
    """
    Get recommended options based on the strategy
    """
    try:
        # Parse query parameters
        tickers = request.args.get('tickers', None)
        if tickers:
            tickers = tickers.split(',')
            
        strategy = request.args.get('strategy', 'simple')
        expiration = request.args.get('expiration', None)
        
        # Get recommendations
        results = options_service.get_recommendations(
            tickers=tickers,
            strategy=strategy,
            expiration=expiration
        )
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/strategies', methods=['GET'])
def get_strategies():
    """
    Get available option strategies
    """
    try:
        results = options_service.get_available_strategies()
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500 