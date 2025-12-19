"""
X Feed Viewer - Flask Backend API
Professional-grade REST API for Chrome extension to view X/Twitter feeds

Author: Your Name
Version: 2.0.0
"""

import os
import json
import logging
import traceback
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

from flask import Flask, jsonify, request
from flask_cors import CORS
from twikit import Client
from twikit.errors import Unauthorized, TooManyRequests
import asyncio
from firebase_admin import credentials, firestore
import firebase_admin

# Local imports
from config import get_config
from constants import *
from utils import (
    validate_email,
    validate_account_name,
    validate_password,
    validate_username,
    sanitize_html,
    sanitize_account_name,
    require_api_key,
    check_rate_limit,
    format_tweet_stats,
    format_timestamp,
    SimpleCache,
    create_error_response,
    create_success_response
)

# ============= APPLICATION SETUP =============

app = Flask(__name__)
config = get_config()
app.config.from_object(config)

# CORS configuration with specific origins
CORS(app, resources={
    r"/*": {
        "origins": config.ALLOWED_ORIGINS,
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "X-API-Key"]
    }
})

# Logging configuration
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT,
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============= FIREBASE INITIALIZATION =============

try:
    cred = credentials.Certificate(config.FIREBASE_CREDENTIALS_PATH)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    logger.info("✓ Firebase initialized successfully")
except FileNotFoundError:
    logger.error(f"Firebase credentials file not found: {config.FIREBASE_CREDENTIALS_PATH}")
    logger.error("Please create a .env file and set FIREBASE_CREDENTIALS_PATH")
    raise SystemExit("Firebase initialization failed: Credentials file not found")
except Exception as e:
    logger.error(f"Error initializing Firebase: {traceback.format_exc()}")
    raise SystemExit(f"Firebase initialization failed: {str(e)}")

# ============= CACHE INITIALIZATION =============

feed_cache = SimpleCache(default_ttl=config.CACHE_TIMEOUT_SECONDS)
logger.info("✓ Cache initialized")

# ============= ANALYTICS FUNCTIONS =============

def log_analytics_event(event_type: str, data: Dict[str, Any]) -> None:
    """
    Log analytics event to Firebase

    Args:
        event_type: Type of event (e.g., 'account_added', 'feed_loaded')
        data: Event data dictionary
    """
    try:
        event_data = {
            'event_type': event_type,
            'timestamp': datetime.now().isoformat(),
            **data
        }
        db.collection(COLLECTION_ANALYTICS).add(event_data)
        logger.debug(f"Analytics logged: {event_type}")
    except Exception as e:
        # Don't fail the request if analytics fails
        logger.warning(f"Failed to log analytics: {str(e)}")


# ============= HEALTH CHECK ENDPOINT =============

@app.route(ENDPOINT_HEALTH, methods=['GET'])
def health_check():
    """
    Health check endpoint for monitoring

    Returns:
        JSON response with service status
    """
    try:
        # Check Firebase connection
        db.collection('sessions').limit(1).get()

        return jsonify({
            "status": "healthy",
            "service": "X Feed Viewer API",
            "version": "2.0.0",
            "timestamp": datetime.now().isoformat()
        }), HTTP_OK
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), HTTP_INTERNAL_ERROR


# ============= GET ACCOUNTS ENDPOINT =============

@app.route(ENDPOINT_GET_ACCOUNTS, methods=['GET'])
def get_accounts():
    """
    Retrieve list of all saved account names from Firebase

    Returns:
        JSON array of account names

    Example:
        GET /get-accounts
        Response: ["Account1", "Account2", "Account3"]
    """
    try:
        # Check rate limit
        client_ip = request.remote_addr
        if not check_rate_limit(client_ip, config.RATE_LIMIT_PER_MINUTE, 60):
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return create_error_response(MSG_ERROR_RATE_LIMIT, HTTP_RATE_LIMIT)

        # Get all document IDs from the 'sessions' collection
        docs = db.collection(COLLECTION_SESSIONS).stream()
        accounts = [doc.id for doc in docs]

        logger.info(f"Retrieved {len(accounts)} accounts")
        return jsonify(accounts), HTTP_OK

    except Exception as e:
        logger.error(f"Error retrieving accounts: {traceback.format_exc()}")
        return create_error_response(
            MSG_ERROR_DATABASE_RETRIEVAL,
            HTTP_INTERNAL_ERROR,
            str(e) if config.DEBUG else None
        )


# ============= ADD ACCOUNT ENDPOINT =============

@app.route(ENDPOINT_ADD_ACCOUNT, methods=['POST'])
def add_account():
    """
    Authenticate user with X/Twitter and save session to Firebase

    Request Body:
        {
            "account_name": "Friendly Name",
            "username": "twitter_username",
            "email": "user@example.com",
            "password": "password123"
        }

    Returns:
        JSON response with success/error message

    Example:
        POST /add_account
        Body: {"account_name": "MyAccount", "email": "test@test.com", "password": "pass123"}
        Response: {"success": true, "message": "Successfully saved session for 'MyAccount'."}
    """
    try:
        data = request.get_json()
        if not data:
            return create_error_response("Request body is required", HTTP_BAD_REQUEST)

        # Extract and validate inputs
        account_name = data.get('account_name', '').strip()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')

        # Validate required fields
        if not account_name or not password or (not username and not email):
            return create_error_response(MSG_ERROR_MISSING_FIELDS, HTTP_BAD_REQUEST)

        # Validate account name
        is_valid_name, name_error = validate_account_name(account_name)
        if not is_valid_name:
            return create_error_response(name_error, HTTP_BAD_REQUEST)

        # Sanitize account name
        account_name = sanitize_account_name(account_name)

        # Validate email if provided
        if email and not validate_email(email):
            return create_error_response(MSG_ERROR_INVALID_EMAIL, HTTP_BAD_REQUEST)

        # Validate username if provided
        if username and not validate_username(username):
            return create_error_response(
                "Invalid username format. Twitter usernames are 1-15 characters (alphanumeric and underscore).",
                HTTP_BAD_REQUEST
            )

        # Validate password
        is_valid_pass, pass_error = validate_password(password)
        if not is_valid_pass:
            return create_error_response(pass_error, HTTP_BAD_REQUEST)

        # Check rate limit
        if not check_rate_limit(f"add_account:{account_name}", 3, 300):
            return create_error_response(
                "Too many login attempts. Please wait 5 minutes.",
                HTTP_RATE_LIMIT
            )

        logger.info(f"Attempting login for account: {account_name}")

        # Perform async login
        async def login_and_get_cookies():
            """Async function to authenticate with X/Twitter"""
            client = Client(config.DEFAULT_LOCALE)
            await client.login(
                auth_info_1=username if username else email,
                auth_info_2=email if email else username,
                password=password
            )
            return client.get_cookies()

        # Execute async login
        cookies = asyncio.run(login_and_get_cookies())

        # Save cookies to Firebase
        doc_ref = db.collection(COLLECTION_SESSIONS).document(account_name)
        doc_ref.set({
            **cookies,
            'created_at': datetime.now().isoformat(),
            'last_used': datetime.now().isoformat()
        })

        # Log analytics
        log_analytics_event(EVENT_ACCOUNT_ADDED, {
            'account_name': account_name,
            'has_username': bool(username),
            'has_email': bool(email)
        })

        logger.info(f"✓ Successfully saved session for {account_name}")
        return jsonify(create_success_response(
            MSG_SUCCESS_ACCOUNT_ADDED.format(account_name=account_name)
        )), HTTP_OK

    except Unauthorized:
        logger.warning(f"Login failed (Unauthorized) for account: {account_name}")
        log_analytics_event(EVENT_ERROR_OCCURRED, {
            'error_type': 'unauthorized',
            'account_name': account_name
        })
        return create_error_response(MSG_ERROR_INVALID_CREDENTIALS, HTTP_UNAUTHORIZED)

    except TooManyRequests:
        logger.warning(f"Twitter rate limit hit for account: {account_name}")
        return create_error_response(
            "Twitter rate limit exceeded. Please wait a few minutes and try again.",
            HTTP_RATE_LIMIT
        )

    except Exception as e:
        logger.error(f"Unexpected error during login for {account_name}:\n{traceback.format_exc()}")
        log_analytics_event(EVENT_ERROR_OCCURRED, {
            'error_type': 'unexpected',
            'account_name': account_name,
            'error': str(e)
        })
        return create_error_response(
            MSG_ERROR_UNEXPECTED + " during login.",
            HTTP_INTERNAL_ERROR,
            str(e) if config.DEBUG else None
        )


# ============= GET FEED ENDPOINT =============

@app.route(ENDPOINT_GET_FEED, methods=['POST'])
def get_feed():
    """
    Fetch X/Twitter timeline for a saved account

    Request Body:
        {
            "account_name": "Account Name",
            "count": 100  # Optional, defaults to config value
        }

    Returns:
        JSON array of formatted tweets with media, stats, and user info

    Example:
        POST /get_feed
        Body: {"account_name": "MyAccount", "count": 50}
        Response: [{tweet1}, {tweet2}, ...]
    """
    try:
        data = request.get_json()
        if not data:
            return create_error_response("Request body is required", HTTP_BAD_REQUEST)

        account_name = data.get('account_name', '').strip()
        tweet_count = data.get('count', config.MAX_TWEETS_PER_REQUEST)

        if not account_name:
            return create_error_response(MSG_ERROR_NO_ACCOUNT_NAME, HTTP_BAD_REQUEST)

        # Validate account name
        is_valid, error = validate_account_name(account_name)
        if not is_valid:
            return create_error_response(error, HTTP_BAD_REQUEST)

        account_name = sanitize_account_name(account_name)

        # Validate tweet count
        if not isinstance(tweet_count, int) or tweet_count < 1 or tweet_count > config.MAX_TWEETS_PER_REQUEST:
            return create_error_response(
                f"Tweet count must be between 1 and {config.MAX_TWEETS_PER_REQUEST}",
                HTTP_BAD_REQUEST
            )

        # Check cache first
        cache_key = f"{CACHE_PREFIX_FEED}{account_name}:{tweet_count}"
        cached_feed = feed_cache.get(cache_key)
        if cached_feed:
            logger.info(f"✓ Returning cached feed for {account_name} ({len(cached_feed)} tweets)")
            return jsonify(cached_feed), HTTP_OK

        # Check rate limit
        if not check_rate_limit(f"get_feed:{account_name}", config.RATE_LIMIT_PER_MINUTE, 60):
            return create_error_response(MSG_ERROR_RATE_LIMIT, HTTP_RATE_LIMIT)

        # Retrieve session from Firebase
        doc_ref = db.collection(COLLECTION_SESSIONS).document(account_name)
        doc = doc_ref.get()

        if not doc.exists:
            logger.warning(f"Session not found for: {account_name}")
            return create_error_response(
                MSG_ERROR_ACCOUNT_NOT_FOUND.format(account_name=account_name),
                HTTP_NOT_FOUND
            )

        session_data = doc.to_dict()
        if not session_data:
            return create_error_response(MSG_ERROR_EMPTY_SESSION, HTTP_BAD_REQUEST)

        # Remove metadata fields, keep only cookies
        cookies = {k: v for k, v in session_data.items() if k not in ['created_at', 'last_used']}

        logger.info(f"Fetching timeline for {account_name} ({tweet_count} tweets)")

        # Async function to fetch timeline
        async def get_timeline_async(loaded_cookies: Dict[str, str], count: int) -> List[Any]:
            """Fetch timeline using stored session cookies"""
            client = Client(config.DEFAULT_LOCALE)
            client.set_cookies(loaded_cookies)
            return await client.get_timeline(count=count)

        # Fetch timeline
        start_time = datetime.now()
        timeline = asyncio.run(get_timeline_async(cookies, tweet_count))
        fetch_duration = (datetime.now() - start_time).total_seconds()

        # Format tweets
        formatted_tweets = format_tweets(timeline)

        # Update last_used timestamp
        doc_ref.update({'last_used': datetime.now().isoformat()})

        # Cache the feed
        feed_cache.set(cache_key, formatted_tweets)

        # Log analytics
        log_analytics_event(EVENT_FEED_LOADED, {
            'account_name': account_name,
            'tweet_count': len(formatted_tweets),
            'fetch_duration_seconds': fetch_duration,
            'from_cache': False
        })

        logger.info(f"✓ Successfully fetched {len(formatted_tweets)} tweets for {account_name} in {fetch_duration:.2f}s")
        return jsonify(formatted_tweets), HTTP_OK

    except Unauthorized:
        logger.warning(f"Session expired for {account_name}, deleting from Firebase")

        # Delete expired session
        try:
            db.collection(COLLECTION_SESSIONS).document(account_name).delete()
            feed_cache.delete(f"{CACHE_PREFIX_FEED}{account_name}")
        except Exception as del_error:
            logger.error(f"Failed to delete expired session: {str(del_error)}")

        log_analytics_event(EVENT_SESSION_EXPIRED, {'account_name': account_name})

        return create_error_response(MSG_ERROR_SESSION_EXPIRED, HTTP_UNAUTHORIZED)

    except TooManyRequests:
        logger.warning(f"Twitter rate limit hit for {account_name}")
        return create_error_response(
            "Twitter rate limit exceeded. Please wait a few minutes.",
            HTTP_RATE_LIMIT
        )

    except Exception as e:
        logger.error(f"Error fetching feed for {account_name}:\n{traceback.format_exc()}")
        log_analytics_event(EVENT_ERROR_OCCURRED, {
            'error_type': 'feed_fetch',
            'account_name': account_name,
            'error': str(e)
        })
        return create_error_response(
            MSG_ERROR_UNEXPECTED + " while processing the feed.",
            HTTP_INTERNAL_ERROR,
            str(e) if config.DEBUG else None
        )


# ============= HELPER FUNCTION: FORMAT TWEETS =============

def format_tweets(timeline: List[Any]) -> List[Dict[str, Any]]:
    """
    Format raw tweets into structured JSON

    Args:
        timeline: List of tweet objects from Twikit

    Returns:
        List of formatted tweet dictionaries
    """
    formatted_tweets = []

    for tweet in timeline:
        try:
            # Process media
            media_list = process_media(tweet)

            # Process user info
            user_info = process_user(tweet)

            # Sanitize tweet text
            tweet_text = sanitize_html(getattr(tweet, 'text', ''))

            formatted_tweets.append({
                "id": tweet.id,
                "text": tweet_text,
                "created_at": getattr(tweet, 'created_at', None),
                "user": user_info,
                "stats": {
                    "likes": getattr(tweet, 'favorite_count', 0),
                    "retweets": getattr(tweet, 'retweet_count', 0),
                    "replies": getattr(tweet, 'reply_count', 0),
                    "views": getattr(tweet, 'view_count', 0)
                },
                "media": media_list,
                "is_retweet": hasattr(tweet, 'retweeted_tweet'),
                "is_reply": bool(getattr(tweet, 'in_reply_to_status_id', None))
            })

        except Exception as e:
            logger.warning(f"Failed to format tweet {getattr(tweet, 'id', 'unknown')}: {str(e)}")
            continue

    return formatted_tweets


def process_media(tweet: Any) -> List[Dict[str, Any]]:
    """
    Extract and process media from tweet

    Args:
        tweet: Tweet object

    Returns:
        List of media dictionaries
    """
    media_list = []

    if not hasattr(tweet, 'media') or not tweet.media:
        return media_list

    for media_item in tweet.media:
        try:
            media_type = getattr(media_item, 'type', None)
            media_info = {'type': media_type}

            if media_type == MEDIA_TYPE_PHOTO:
                url = getattr(media_item, 'media_url', None)

            elif media_type in [MEDIA_TYPE_VIDEO, MEDIA_TYPE_GIF]:
                if hasattr(media_item, 'video_info'):
                    variants = media_item.video_info.get('variants', [])
                    # Find highest bitrate video
                    video_variants = [v for v in variants if v.get('bitrate') is not None]
                    if video_variants:
                        best_variant = max(video_variants, key=lambda v: v.get('bitrate', 0))
                        url = best_variant.get('url')
                    else:
                        url = None
                else:
                    url = None
            else:
                url = None

            if url:
                media_info['url'] = url
                media_list.append(media_info)

        except Exception as e:
            logger.warning(f"Failed to process media item: {str(e)}")
            continue

    return media_list


def process_user(tweet: Any) -> Dict[str, Any]:
    """
    Extract and sanitize user information from tweet

    Args:
        tweet: Tweet object

    Returns:
        User information dictionary
    """
    default_user = {
        "name": "Unknown User",
        "screen_name": "unknown",
        "profile_image_url_https": "",
        "is_verified": False,
        "is_blue_verified": False,
        "followers_count": 0
    }

    if not hasattr(tweet, 'user'):
        return default_user

    user_data = tweet.user

    return {
        "name": sanitize_html(getattr(user_data, 'name', 'Unknown User')),
        "screen_name": getattr(user_data, 'screen_name', 'unknown'),
        "profile_image_url_https": getattr(user_data, 'profile_image_url', ''),
        "is_verified": getattr(user_data, 'verified', False),
        "is_blue_verified": getattr(user_data, 'is_blue_verified', False),
        "followers_count": getattr(user_data, 'followers_count', 0)
    }


# ============= EXPORT FEED ENDPOINT =============

@app.route(ENDPOINT_EXPORT_FEED, methods=['POST'])
def export_feed():
    """
    Export feed data in specified format (JSON or CSV)

    Request Body:
        {
            "account_name": "Account Name",
            "format": "json" | "csv",
            "count": 100
        }

    Returns:
        Downloadable file in specified format
    """
    try:
        data = request.get_json()
        account_name = data.get('account_name', '').strip()
        export_format = data.get('format', 'json').lower()
        tweet_count = data.get('count', config.MAX_TWEETS_PER_REQUEST)

        if export_format not in [EXPORT_FORMAT_JSON, EXPORT_FORMAT_CSV]:
            return create_error_response(
                f"Invalid format. Must be '{EXPORT_FORMAT_JSON}' or '{EXPORT_FORMAT_CSV}'",
                HTTP_BAD_REQUEST
            )

        # Reuse get_feed logic (could be refactored into shared function)
        # For now, return JSON format
        # TODO: Implement CSV export using pandas or csv module

        logger.info(f"Export requested for {account_name} in {export_format} format")
        return jsonify({
            "message": "Export functionality coming soon",
            "format": export_format,
            "account_name": account_name
        }), HTTP_OK

    except Exception as e:
        logger.error(f"Export error: {traceback.format_exc()}")
        return create_error_response(MSG_ERROR_UNEXPECTED, HTTP_INTERNAL_ERROR)


# ============= ANALYTICS ENDPOINT =============

@app.route(ENDPOINT_GET_ANALYTICS, methods=['GET'])
def get_analytics():
    """
    Retrieve analytics data (for admin/dashboard use)

    Returns:
        JSON with analytics summary
    """
    try:
        # Get analytics events from Firebase
        events = db.collection(COLLECTION_ANALYTICS).limit(100).stream()
        analytics_data = [event.to_dict() for event in events]

        # Calculate summary statistics
        summary = {
            'total_events': len(analytics_data),
            'accounts_added': sum(1 for e in analytics_data if e.get('event_type') == EVENT_ACCOUNT_ADDED),
            'feeds_loaded': sum(1 for e in analytics_data if e.get('event_type') == EVENT_FEED_LOADED),
            'errors': sum(1 for e in analytics_data if e.get('event_type') == EVENT_ERROR_OCCURRED)
        }

        return jsonify({
            'summary': summary,
            'recent_events': analytics_data[:20]  # Last 20 events
        }), HTTP_OK

    except Exception as e:
        logger.error(f"Analytics retrieval error: {traceback.format_exc()}")
        return create_error_response(MSG_ERROR_UNEXPECTED, HTTP_INTERNAL_ERROR)


# ============= ERROR HANDLERS =============

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({"error": "Internal server error"}), 500


# ============= APPLICATION ENTRY POINT =============

if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("🚀 X Feed Viewer API v2.0.0 Starting...")
    logger.info(f"Environment: {config.FLASK_ENV}")
    logger.info(f"Debug Mode: {config.DEBUG}")
    logger.info(f"Host: {config.HOST}:{config.PORT}")
    logger.info(f"Max Tweets Per Request: {config.MAX_TWEETS_PER_REQUEST}")
    logger.info(f"Cache Timeout: {config.CACHE_TIMEOUT_SECONDS}s")
    logger.info("=" * 60)

    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG
    )
