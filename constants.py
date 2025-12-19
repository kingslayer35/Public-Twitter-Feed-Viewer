"""
Constants module for X Feed Viewer Extension
Centralizes all magic numbers, strings, and configuration values
"""

# API Response Messages
MSG_SUCCESS_ACCOUNT_ADDED = "Successfully saved session for '{account_name}'."
MSG_ERROR_MISSING_FIELDS = "Account Name, Password, and either Username or Email are required."
MSG_ERROR_INVALID_CREDENTIALS = "Login failed. Please check your credentials."
MSG_ERROR_SESSION_EXPIRED = "Session has expired or is invalid. Please re-add the account."
MSG_ERROR_ACCOUNT_NOT_FOUND = "Session for '{account_name}' not found in database."
MSG_ERROR_EMPTY_SESSION = "Session data is empty or invalid in database."
MSG_ERROR_DATABASE_RETRIEVAL = "Could not retrieve accounts from database."
MSG_ERROR_UNEXPECTED = "An unexpected error occurred."
MSG_ERROR_NO_ACCOUNT_NAME = "Account name not provided."
MSG_ERROR_INVALID_API_KEY = "Invalid or missing API key."
MSG_ERROR_RATE_LIMIT = "Rate limit exceeded. Please try again later."
MSG_ERROR_INVALID_EMAIL = "Invalid email format."
MSG_ERROR_INVALID_ACCOUNT_NAME = "Account name contains invalid characters. Use only letters, numbers, spaces, hyphens, and underscores."
MSG_ERROR_ACCOUNT_NAME_TOO_LONG = "Account name is too long. Maximum {max_length} characters."

# HTTP Status Codes
HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_RATE_LIMIT = 429
HTTP_INTERNAL_ERROR = 500

# Cache Keys
CACHE_PREFIX_FEED = "feed:"
CACHE_PREFIX_ACCOUNT = "account:"

# Firebase Collections
COLLECTION_SESSIONS = "sessions"
COLLECTION_ANALYTICS = "analytics"

# Analytics Event Types
EVENT_ACCOUNT_ADDED = "account_added"
EVENT_FEED_LOADED = "feed_loaded"
EVENT_ACCOUNT_SWITCHED = "account_switched"
EVENT_SESSION_EXPIRED = "session_expired"
EVENT_ERROR_OCCURRED = "error_occurred"

# UI Constants (for JavaScript)
AVATAR_COLORS = [
    'bg-blue-500',
    'bg-green-500',
    'bg-red-500',
    'bg-purple-500',
    'bg-pink-500',
    'bg-indigo-500',
    'bg-teal-500',
    'bg-orange-500',
    'bg-yellow-500',
    'bg-cyan-500'
]

# Tweet Processing
TWITTER_SHORT_URL_PATTERN = r'https://t\.co/[a-zA-Z0-9]+'
URL_PATTERN = r'(https?://[^\s]+)'
MENTION_PATTERN = r'@(\w+)'
HASHTAG_PATTERN = r'#(\w+)'

# Media Types
MEDIA_TYPE_PHOTO = 'photo'
MEDIA_TYPE_VIDEO = 'video'
MEDIA_TYPE_GIF = 'animated_gif'

# API Endpoints
ENDPOINT_GET_ACCOUNTS = '/get-accounts'
ENDPOINT_ADD_ACCOUNT = '/add_account'
ENDPOINT_GET_FEED = '/get_feed'
ENDPOINT_GET_ANALYTICS = '/get_analytics'
ENDPOINT_EXPORT_FEED = '/export_feed'
ENDPOINT_HEALTH = '/health'

# Export Formats
EXPORT_FORMAT_JSON = 'json'
EXPORT_FORMAT_CSV = 'csv'

# Validation Regex
EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
ACCOUNT_NAME_REGEX = r'^[a-zA-Z0-9_\- ]+$'

# Performance Metrics
DEFAULT_REQUEST_TIMEOUT = 30  # seconds
MAX_RETRY_ATTEMPTS = 3
RETRY_BACKOFF_FACTOR = 2  # exponential backoff multiplier

# Stats Formatting Thresholds
STATS_THOUSAND = 1000
STATS_MILLION = 1000000
