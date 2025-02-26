import os, secrets
from flask import Flask, redirect, request, jsonify, session
import requests
from dotenv import load_dotenv

app = Flask(__name__)
load_dotenv()
app.secret_key = secrets.token_hex(16)  # Required to securely store session data

# Configuration: Replace these with your actual TikTok app credentials
CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "your_client_key")
CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "your_client_secret")
# This should match your TikTok app's redirect URI. Ngrok will provide a public URL.
REDIRECT_URI = os.getenv("TIKTOK_REDIRECT_URI")

# TikTok OAuth2 endpoints (subject to change, check TikTok docs for updates)
AUTHORIZATION_BASE_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"

@app.route("/")
def index():
    return '<a href="/login">Login with TikTok</a>'

@app.route("/login")
def login():
    # Generate and store a random state value to prevent CSRF attacks
    state = secrets.token_urlsafe(16)
    session['oauth_state'] = state
    
    params = {
        "client_key": CLIENT_KEY,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "user.info.basic,video.upload,video.publish",
        "state": state
    }
    auth_url = requests.Request('GET', AUTHORIZATION_BASE_URL, params=params).prepare().url
    return redirect(auth_url)

@app.route("/callback")
def auth():
    # Check for errors returned in the callback
    error = request.args.get('error')
    error_description = request.args.get('error_description')
    if error:
        return f"Error encountered: {error_description or error}", 400

    # Validate state parameter to prevent CSRF attacks
    state = request.args.get("state")
    if not state or state != session.get("oauth_state"):
        return "Invalid state parameter.", 400

    code = request.args.get("code")
    print(f"Received authorization code: {code}")
    if not code:
        return "Authorization code not provided.", 400

    # Exchange the authorization code for an access token
    data = {
        "client_key": CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    token_response = requests.post(TOKEN_URL, data=data, headers=headers)
    if token_response.status_code != 200:
        return f"Failed to retrieve token: {token_response.text}", 400

    token_info = token_response.json()
    # Optionally, you can also inspect token_info.get("scopes") if needed
    return jsonify({
        "open_id": token_info.get("open_id"),
        "access_token": token_info.get("access_token"),
        "expires_in": token_info.get("expires_in"),
        "refresh_token": token_info.get("refresh_token"),
        "refresh_expires_in": token_info.get("refresh_expires_in"),
        "scope": token_info.get("scope"),
        "token_type": token_info.get("token_type"),
    })

if __name__ == "__main__":
    app.run(use_reloader=False, debug=True)