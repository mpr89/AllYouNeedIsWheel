"""
Auto-Trader API
Flask application initialization and configuration.
"""

from flask import Flask
from flask_cors import CORS

def create_app(config=None):
    """
    Create and configure the Flask application.
    
    Args:
        config (dict, optional): Configuration dictionary
        
    Returns:
        Flask: Configured Flask application
    """
    app = Flask(__name__, 
                static_folder='../frontend/static',
                template_folder='../frontend/templates')
    
    # Enable CORS
    CORS(app)
    
    # Default configuration
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE='sqlite:///:memory:',
    )
    
    # Override with passed config
    if config:
        app.config.update(config)
    
    # Register blueprints
    from api.routes import portfolio, options, recommendations
    app.register_blueprint(portfolio.bp)
    app.register_blueprint(options.bp)
    app.register_blueprint(recommendations.bp)
    
    @app.route('/health')
    def health_check():
        return {'status': 'healthy'}
        
    return app 