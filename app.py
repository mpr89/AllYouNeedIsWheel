"""
Auto-Trader Web Application
Main entry point for the web application
"""

import os
import logging
from flask import Flask, render_template, request, redirect, url_for, jsonify
from api import create_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create Flask application
app = create_app()

# Web routes
@app.route('/')
def index():
    """
    Render the dashboard page
    """
    return render_template('dashboard.html')

@app.route('/portfolio')
def portfolio():
    """
    Render the portfolio page
    """
    return render_template('portfolio.html')

@app.route('/options')
def options():
    """
    Render the options analysis page
    """
    # Get ticker from query params
    ticker = request.args.get('ticker', None)
    return render_template('options.html', ticker=ticker)

@app.route('/recommendations')
def recommendations():
    """
    Render the recommendations page
    """
    return render_template('recommendations.html')

@app.errorhandler(404)
def page_not_found(e):
    """
    Handle 404 errors
    """
    return render_template('error.html', error_code=404, message="Page not found"), 404

@app.errorhandler(500)
def server_error(e):
    """
    Handle 500 errors
    """
    return render_template('error.html', error_code=500, message="Server error"), 500

if __name__ == '__main__':
    # Get port from environment variable or use default
    port = int(os.environ.get('PORT', 5000))
    
    # Run the application
    app.run(host='0.0.0.0', port=port, debug=True) 