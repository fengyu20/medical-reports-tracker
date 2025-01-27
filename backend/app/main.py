import logging
from flask import Flask
from flask_cors import CORS
from datetime import timedelta
import os
from dotenv import load_dotenv

def create_app():
    app = Flask(__name__)
    
    # Load environment variables early
    load_dotenv()
    
    # Session configuration
    app.config.update(
        SECRET_KEY=os.getenv('FLASK_SECRET_KEY', os.urandom(24).hex()),
        SESSION_COOKIE_SECURE=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=1)
    )
    
    # Configure Logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # CORS configuration
    CORS(app, 
        resources={
            r"/clinical-data/*": {
                "origins": "http://localhost:3030",
                "supports_credentials": True
            },
            r"/auth/*": {
                "origins": "http://localhost:3030",
                "supports_credentials": True
            }
        },
        allow_headers=["Content-Type", "Authorization", "Cache-Control"],
        methods=["GET", "POST", "PUT", "OPTIONS", "DELETE"],
        expose_headers=["Content-Type", "Authorization"],
        max_age=3600
    )
        # Register blueprints
    from app.auth import cognito_service
    from app.clinical_data.routes import clinical_data_bp
    
    cognito_service.init_app(app)
    app.register_blueprint(cognito_service.auth_bp, url_prefix='/auth')
    app.register_blueprint(clinical_data_bp, url_prefix='/clinical-data')
    
    return app
