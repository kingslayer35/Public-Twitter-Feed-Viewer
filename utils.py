"""
Utility functions for X Feed Viewer Extension
Includes validation, sanitization, and helper functions
"""

import re
import html
import hashlib
import secrets
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
import logging

from constants import (
    EMAIL_REGEX,
    ACCOUNT_NAME_REGEX,
    HTTP_BAD_REQUEST,
    HTTP_UNAUTHORIZED,
    MSG_ERROR_INVALID_EMAIL,
    MSG_ERROR_INVALID_ACCOUNT_NAME,
    MSG_ERROR_ACCOUNT_NAME_TOO_LONG,
    MSG_ERROR_INVALID_API_KEY
)
from config import Config

logger = logging.getLogger(__name__)


# ============= VALIDATION FUNCTIONS =============

def validate_email(email: str) -> bool:
    """
    Validate email format using regex

    Args:
        email: Email address to validate

    Returns:
        True if valid, False otherwise
    """
    if not email:
        return False
    return bool(re.match(EMAIL_REGEX, email.strip()))


def validate_account_name(account_name: str) -> tuple[bool, Optional[str]]:
    """
    Validate account name format and length

    Args:
        account_name: Account name to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not account_name:
        return False, "Account name is required."

    account_name = account_name.strip()

    if len(account_name) > Config.MAX_ACCOUNT_NAME_LENGTH:
        return False, MSG_ERROR_ACCOUNT_NAME_TOO_LONG.format(
            max_length=Config.MAX_ACCOUNT_NAME_LENGTH
        )

    if not re.match(ACCOUNT_NAME_REGEX, account_name):
        return False, MSG_ERROR_INVALID_ACCOUNT_NAME

    return True, None


def validate_password(password: str) -> tuple[bool, Optional[str]]:
    """
    Validate password strength

    Args:
        password: Password to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not password:
        return False, "Password is required."

    if len(password) < Config.MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {Config.MIN_PASSWORD_LENGTH} characters."

    return True, None


def validate_username(username: str) -> bool:
    """
    Validate Twitter/X username format

    Args:
        username: Username to validate

    Returns:
        True if valid, False otherwise
    """
    if not username:
        return False

    # Remove @ if present
    username = username.strip().lstrip('@')

    # Twitter usernames: 1-15 chars, alphanumeric and underscore
    pattern = r'^[a-zA-Z0-9_]{1,15}$'
    return bool(re.match(pattern, username))


# ============= SANITIZATION FUNCTIONS =============

def sanitize_html(text: str) -> str:
    """
    Sanitize HTML to prevent XSS attacks

    Args:
        text: Text to sanitize

    Returns:
        Sanitized text
    """
    if not text:
        return ""
    return html.escape(text)


def sanitize_account_name(account_name: str) -> str:
    """
    Sanitize account name by removing invalid characters

    Args:
        account_name: Account name to sanitize

    Returns:
        Sanitized account name
    """
    if not account_name:
        return ""

    # Remove any characters not in allowed pattern
    sanitized = re.sub(r'[^a-zA-Z0-9_\- ]', '', account_name.strip())
    return sanitized[:Config.MAX_ACCOUNT_NAME_LENGTH]


# ============= AUTHENTICATION FUNCTIONS =============

def generate_api_key() -> str:
    """
    Generate a secure API key

    Returns:
        32-character hexadecimal API key
    """
    return secrets.token_hex(16)


def hash_api_key(api_key: str) -> str:
    """
    Hash API key using SHA-256

    Args:
        api_key: API key to hash

    Returns:
        Hashed API key
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def require_api_key(f):
    """
    Decorator to require API key authentication for endpoints

    Usage:
        @app.route('/protected')
        @require_api_key
        def protected_route():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get API key from request header
        api_key = request.headers.get('X-API-Key')

        if not api_key:
            logger.warning("Request missing API key")
            return jsonify({"error": MSG_ERROR_INVALID_API_KEY}), HTTP_UNAUTHORIZED

        # Validate API key
        if api_key != Config.API_KEY:
            logger.warning(f"Invalid API key attempted: {api_key[:8]}...")
            return jsonify({"error": MSG_ERROR_INVALID_API_KEY}), HTTP_UNAUTHORIZED

        return f(*args, **kwargs)

    return decorated_function


# ============= RATE LIMITING =============

# Simple in-memory rate limiting (for production, use Redis)
_rate_limit_store: Dict[str, List[datetime]] = {}


def check_rate_limit(identifier: str, max_requests: int, window_seconds: int) -> bool:
    """
    Check if request is within rate limit

    Args:
        identifier: Unique identifier (e.g., IP address, account name)
        max_requests: Maximum number of requests allowed
        window_seconds: Time window in seconds

    Returns:
        True if within limit, False otherwise
    """
    now = datetime.now()
    cutoff = now - timedelta(seconds=window_seconds)

    # Initialize if not exists
    if identifier not in _rate_limit_store:
        _rate_limit_store[identifier] = []

    # Clean old entries
    _rate_limit_store[identifier] = [
        timestamp for timestamp in _rate_limit_store[identifier]
        if timestamp > cutoff
    ]

    # Check limit
    if len(_rate_limit_store[identifier]) >= max_requests:
        return False

    # Add current request
    _rate_limit_store[identifier].append(now)
    return True


# ============= DATA FORMATTING =============

def format_tweet_stats(count: int) -> str:
    """
    Format large numbers with K/M suffixes

    Args:
        count: Number to format

    Returns:
        Formatted string (e.g., "1.2K", "3.4M")
    """
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}".rstrip('0').rstrip('.') + 'M'
    elif count >= 1_000:
        return f"{count / 1_000:.1f}".rstrip('0').rstrip('.') + 'K'
    else:
        return str(count)


def format_timestamp(timestamp: str) -> str:
    """
    Format timestamp to relative time (e.g., "2 hours ago")

    Args:
        timestamp: ISO format timestamp

    Returns:
        Human-readable relative time
    """
    try:
        tweet_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        now = datetime.now(tweet_time.tzinfo)
        delta = now - tweet_time

        if delta.days > 365:
            return f"{delta.days // 365}y ago"
        elif delta.days > 30:
            return f"{delta.days // 30}mo ago"
        elif delta.days > 0:
            return f"{delta.days}d ago"
        elif delta.seconds > 3600:
            return f"{delta.seconds // 3600}h ago"
        elif delta.seconds > 60:
            return f"{delta.seconds // 60}m ago"
        else:
            return "just now"
    except Exception:
        return timestamp


# ============= CACHE HELPERS =============

class SimpleCache:
    """Simple in-memory cache with TTL"""

    def __init__(self, default_ttl: int = 300):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        if key not in self.cache:
            return None

        entry = self.cache[key]
        if datetime.now() > entry['expires']:
            del self.cache[key]
            return None

        return entry['value']

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with TTL"""
        ttl = ttl or self.default_ttl
        self.cache[key] = {
            'value': value,
            'expires': datetime.now() + timedelta(seconds=ttl)
        }

    def delete(self, key: str) -> None:
        """Delete key from cache"""
        if key in self.cache:
            del self.cache[key]

    def clear(self) -> None:
        """Clear all cache entries"""
        self.cache.clear()

    def cleanup(self) -> int:
        """Remove expired entries and return count removed"""
        now = datetime.now()
        expired = [k for k, v in self.cache.items() if now > v['expires']]
        for key in expired:
            del self.cache[key]
        return len(expired)


# ============= ERROR HANDLING =============

def create_error_response(
    error_message: str,
    status_code: int = HTTP_BAD_REQUEST,
    details: Optional[str] = None
) -> tuple[Dict[str, Any], int]:
    """
    Create standardized error response

    Args:
        error_message: Main error message
        status_code: HTTP status code
        details: Optional additional details

    Returns:
        Tuple of (response_dict, status_code)
    """
    response = {"error": error_message}
    if details:
        response["details"] = details
    return response, status_code


def create_success_response(
    message: str,
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create standardized success response

    Args:
        message: Success message
        data: Optional data payload

    Returns:
        Response dictionary
    """
    response = {"success": True, "message": message}
    if data:
        response["data"] = data
    return response
