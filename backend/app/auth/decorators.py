from functools import wraps
from flask import session, jsonify, request
import logging

logger = logging.getLogger(__name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Allow OPTIONS requests to pass through
        if request.method == 'OPTIONS':
            return f(*args, **kwargs)
            
        if 'user' not in session:
            logger.warning("Unauthorized access attempt - no user in session")
            return jsonify({"error": "Authentication required"}), 401
            
        # Check if session is expired
        if 'session_expiry' in session:
            import time
            if time.time() > session['session_expiry']:
                logger.warning("Unauthorized access attempt - session expired")
                session.clear()
                return jsonify({"error": "Session expired"}), 401
                
        return f(*args, **kwargs)
    return decorated_function 