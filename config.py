"""
Configuration module for X Feed Viewer Extension
Centralizes all application settings and environment variables
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
basedir = Path(__file__).parent
load_dotenv(basedir / '.env')


class Config:
    """Base configuration class with default values"""

    # Flask Settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    HOST = os.getenv('FLASK_HOST', '127.0.0.1')
    PORT = int(os.getenv('FLASK_PORT', '5000'))

    # Security Settings
    API_KEY = os.getenv('API_KEY', 'default-api-key-insecure')
    ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', 'http://127.0.0.1:5000').split(',')

    # Firebase Settings
    FIREBASE_CREDENTIALS_PATH = os.getenv('FIREBASE_CREDENTIALS_PATH', 'serviceAccountKey.json')

    # Application Settings
    MAX_TWEETS_PER_REQUEST = int(os.getenv('MAX_TWEETS_PER_REQUEST', '200'))
    CACHE_TIMEOUT_SECONDS = int(os.getenv('CACHE_TIMEOUT_SECONDS', '300'))
    RATE_LIMIT_PER_MINUTE = int(os.getenv('RATE_LIMIT_PER_MINUTE', '10'))

    # Logging Settings
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'app.log')
    LOG_FORMAT = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'

    # Twitter/X Settings
    DEFAULT_LOCALE = 'en-US'
    SESSION_COLLECTION = 'sessions'
    ANALYTICS_COLLECTION = 'analytics'

    # Validation Settings
    MIN_PASSWORD_LENGTH = 8
    MAX_ACCOUNT_NAME_LENGTH = 50
    ALLOWED_ACCOUNT_NAME_PATTERN = r'^[a-zA-Z0-9_\- ]+$'

    # Performance Settings
    MAX_CACHE_SIZE = 100  # Maximum number of cached feeds


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    FLASK_ENV = 'production'


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    FLASK_ENV = 'development'


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config():
    """Get configuration based on environment"""
    env = os.getenv('FLASK_ENV', 'development')
    return config.get(env, config['default'])
