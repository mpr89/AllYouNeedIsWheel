"""
Auto-Trader Web Application
Main entry point for the web application
"""

import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
from api import create_app
from core.logging_config import get_logger

# Configure logging
logger = get_logger('autotrader.app', 'api')

# Create Flask application
app = create_app()

# Web routes
@app.route('/')
def index():
    """
    Render the dashboard page
    """
    logger.info("Rendering dashboard page")
    return render_template('dashboard.html')

@app.route('/portfolio')
def portfolio():
    """
    Render the portfolio page
    """
    logger.info("Rendering portfolio page")
    return render_template('portfolio.html')

@app.route('/options')
def options():
    """
    Render the options analysis page
    """
    # Get ticker from query params
    ticker = request.args.get('ticker', None)
    logger.info(f"Rendering options page with ticker: {ticker}")
    return render_template('options.html', ticker=ticker)

@app.route('/recommendations')
def recommendations():
    """
    Render the recommendations page
    """
    logger.info("Rendering recommendations page")
    return render_template('recommendations.html')

@app.errorhandler(404)
def page_not_found(e):
    """
    Handle 404 errors
    """
    logger.warning(f"404 error: {request.path}")
    return render_template('error.html', error_code=404, message="Page not found"), 404

@app.errorhandler(500)
def server_error(e):
    """
    Handle 500 errors
    """
    logger.error(f"500 error: {str(e)}")
    return render_template('error.html', error_code=500, message="Server error"), 500

if __name__ == '__main__':
    # Get port from environment variable or use default
    port = int(os.environ.get('PORT', 5000))
    
    # Run the application
    logger.info(f"Starting Flask development server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True) 