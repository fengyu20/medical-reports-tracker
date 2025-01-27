from flask import Blueprint, redirect, session, jsonify, url_for, request, make_response
from authlib.integrations.flask_client import OAuth
import os
from dotenv import load_dotenv
import time
import logging
import secrets

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)
oauth = OAuth()

def init_app(app):
    oauth.init_app(app)
    
    # Load environment variables
    load_dotenv()
    
    client_id = os.getenv('CLIENT_ID')
    client_secret = os.getenv('CLIENT_SECRET')
    cognito_idp_domain = os.getenv('COGNITO_IDP_DOMAIN')
    user_pool_id = os.getenv('USER_POOL_ID')

    
    if not all([client_id, client_secret, cognito_idp_domain, user_pool_id]):
        logger.error("Missing required environment variables")
        raise ValueError("Missing required environment variables")

    server_metadata_url = f"https://{cognito_idp_domain}/{user_pool_id}/.well-known/openid-configuration"
    logger.info(f"Using server metadata URL: {server_metadata_url}")

    oauth.register(
        name='cognito',
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url=server_metadata_url,
        client_kwargs={
            'scope': 'openid email profile',
            'response_type': 'code'
        }
    )
    
    logger.info("OAuth client registration complete")

@auth_bp.route('/login')
def login():
    try:
        redirect_uri = url_for('auth.authorize', _external=True)
        logger.info(f"Redirect URI: {redirect_uri}")
        
        # Generate and store state and nonce
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        
        # Store both state and nonce in session
        session['oauth_state'] = state
        session['oauth_nonce'] = nonce
        
        logger.info(f"Generated state: {state}")
        logger.info(f"Generated nonce: {nonce}")
        
        return oauth.cognito.authorize_redirect(
            redirect_uri,
            state=state,
            nonce=nonce
        )
    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        return redirect('http://localhost:3030/signin?error=login_failed')

@auth_bp.route('/authorize')
def authorize():
    try:
        logger.info("Authorization callback received")
        
        # Retrieve stored nonce from session
        nonce = session.get('oauth_nonce')
        if not nonce:
            logger.error("No nonce found in session")
            raise ValueError("Missing nonce")
            
        token = oauth.cognito.authorize_access_token()
        logger.info("Successfully obtained access token")
        
        # Pass the nonce to parse_id_token
        userinfo = oauth.cognito.parse_id_token(token, nonce=nonce)
        logger.info(f"User info: {userinfo}")
        
        # Store in session
        session.clear()  
        session.permanent = True
        session['user'] = {
            'user_id': userinfo.get('sub'),
            'email': userinfo.get('email'),
            'name': userinfo.get('name', userinfo.get('email'))
        }
        session['access_token'] = token.get('access_token')
        session['id_token'] = token.get('id_token')
        session['session_expiry'] = time.time() + 3600  
        session.modified = True
        
        logger.info("Session data stored successfully")
        return redirect('http://localhost:3030/home')
        
    except Exception as e:
        logger.error(f"Authorization error: {str(e)}", exc_info=True)
        return redirect('http://localhost:3030/signin?error=auth_failed')

@auth_bp.route('/check-session')
def check_session():
    logger.info(f"Session check requested. Current session: {dict(session)}")
    
    if 'user' not in session:
        logger.warning("No user in session")
        return jsonify({"authenticated": False}), 401
        
    if 'session_expiry' in session and time.time() > session['session_expiry']:
        logger.warning("Session expired")
        session.clear()
        return jsonify({"authenticated": False, "reason": "expired"}), 401
        
    return jsonify({
        "authenticated": True,
        "user": session['user']
    })

@auth_bp.route('/logout', methods=['GET'])
def logout():
    logger.info("Logout requested")
    session.clear()

    # Fetch environment variables
    client_id = os.getenv('CLIENT_ID')
    logout_url = os.getenv('COGNITO_LOGOUT_URL')
    redirect_url = os.getenv('COGNITO_REDIRECT_URL')

    # Validate environment variables
    if not all([client_id, logout_url, redirect_url]):
        logger.error("Missing required environment variables")
        return jsonify({"error": "Missing required environment variables"}), 500

    # Construct the Cognito logout URL
    final_logout_url = f"{logout_url}?client_id={client_id}&logout_uri={redirect_url}"
    
    logger.info(f"Redirecting to Cognito logout URL: {final_logout_url}")
    
    response = make_response(redirect(final_logout_url))
    response.set_cookie('session', '', expires=0)  # Clear session cookie
    return response