"""
Options Recommendations API routes
"""

from flask import Blueprint, request, jsonify
from api.services.options_service import OptionsService

bp = Blueprint('recommendations', __name__, url_prefix='/api/recommendations')
