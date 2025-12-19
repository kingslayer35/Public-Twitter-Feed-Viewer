"""
Unit Tests for X Feed Viewer API
Comprehensive test suite for backend endpoints and utilities

Run with: pytest test_app.py -v --cov=app --cov-report=html
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Import modules to test
from utils import (
    validate_email,
    validate_account_name,
    validate_password,
    validate_username,
    sanitize_html,
    sanitize_account_name,
    format_tweet_stats,
    SimpleCache
)
from constants import *


# ============= UTILITY FUNCTION TESTS =============

class TestValidationFunctions:
    """Test validation utility functions"""

    def test_validate_email_valid(self):
        """Test valid email formats"""
        assert validate_email("test@example.com") == True
        assert validate_email("user.name+tag@example.co.uk") == True
        assert validate_email("test123@test-domain.com") == True

    def test_validate_email_invalid(self):
        """Test invalid email formats"""
        assert validate_email("invalid") == False
        assert validate_email("@example.com") == False
        assert validate_email("test@") == False
        assert validate_email("") == False
        assert validate_email(None) == False

    def test_validate_account_name_valid(self):
        """Test valid account names"""
        is_valid, error = validate_account_name("Test Account")
        assert is_valid == True
        assert error is None

        is_valid, error = validate_account_name("Account_123")
        assert is_valid == True

    def test_validate_account_name_invalid(self):
        """Test invalid account names"""
        # Empty name
        is_valid, error = validate_account_name("")
        assert is_valid == False
        assert "required" in error

        # Too long
        long_name = "a" * 100
        is_valid, error = validate_account_name(long_name)
        assert is_valid == False
        assert "too long" in error.lower()

        # Invalid characters
        is_valid, error = validate_account_name("test@#$%")
        assert is_valid == False

    def test_validate_password_valid(self):
        """Test valid passwords"""
        is_valid, error = validate_password("password123")
        assert is_valid == True
        assert error is None

        is_valid, error = validate_password("verylongpassword")
        assert is_valid == True

    def test_validate_password_invalid(self):
        """Test invalid passwords"""
        # Too short
        is_valid, error = validate_password("short")
        assert is_valid == False
        assert "at least" in error

        # Empty
        is_valid, error = validate_password("")
        assert is_valid == False

    def test_validate_username_valid(self):
        """Test valid Twitter usernames"""
        assert validate_username("testuser") == True
        assert validate_username("@testuser") == True  # Should handle @
        assert validate_username("test_user_123") == True

    def test_validate_username_invalid(self):
        """Test invalid Twitter usernames"""
        assert validate_username("") == False
        assert validate_username("toolongusernametoolongusername") == False
        assert validate_username("test@user") == False


class TestSanitizationFunctions:
    """Test sanitization utility functions"""

    def test_sanitize_html(self):
        """Test HTML escaping"""
        assert sanitize_html("<script>alert('xss')</script>") == "&lt;script&gt;alert('xss')&lt;/script&gt;"
        assert sanitize_html("Normal text") == "Normal text"
        assert sanitize_html("<b>Bold</b>") == "&lt;b&gt;Bold&lt;/b&gt;"
        assert sanitize_html("") == ""

    def test_sanitize_account_name(self):
        """Test account name sanitization"""
        assert sanitize_account_name("Test Account") == "Test Account"
        assert sanitize_account_name("Test@#$%Account") == "TestAccount"

        # Should truncate to max length
        long_name = "a" * 100
        result = sanitize_account_name(long_name)
        assert len(result) <= 50


class TestFormattingFunctions:
    """Test data formatting functions"""

    def test_format_tweet_stats(self):
        """Test number formatting with K/M suffixes"""
        assert format_tweet_stats(500) == "500"
        assert format_tweet_stats(1500) == "1.5K"
        assert format_tweet_stats(1000) == "1K"
        assert format_tweet_stats(1000000) == "1M"
        assert format_tweet_stats(1500000) == "1.5M"
        assert format_tweet_stats(0) == "0"


class TestSimpleCache:
    """Test SimpleCache class"""

    def test_cache_set_get(self):
        """Test basic cache set and get"""
        cache = SimpleCache(default_ttl=60)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_cache_expiration(self):
        """Test cache expiration"""
        cache = SimpleCache(default_ttl=1)  # 1 second TTL
        cache.set("key1", "value1", ttl=0)  # Immediate expiration

        import time
        time.sleep(0.1)
        assert cache.get("key1") is None

    def test_cache_delete(self):
        """Test cache deletion"""
        cache = SimpleCache()
        cache.set("key1", "value1")
        cache.delete("key1")
        assert cache.get("key1") is None

    def test_cache_clear(self):
        """Test cache clear"""
        cache = SimpleCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None


# ============= API ENDPOINT TESTS =============

@pytest.fixture
def app():
    """Create test Flask app"""
    # Mock Firebase to avoid requiring credentials
    with patch('app.firebase_admin.initialize_app'):
        with patch('app.firestore.client'):
            from app import app as flask_app
            flask_app.config['TESTING'] = True
            yield flask_app


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


class TestHealthEndpoint:
    """Test health check endpoint"""

    def test_health_check_success(self, client):
        """Test successful health check"""
        with patch('app.db.collection') as mock_collection:
            mock_collection.return_value.limit.return_value.get.return_value = []

            response = client.get('/health')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['status'] == 'healthy'
            assert 'version' in data


class TestGetAccountsEndpoint:
    """Test GET /get-accounts endpoint"""

    def test_get_accounts_empty(self, client):
        """Test retrieving empty account list"""
        with patch('app.db.collection') as mock_collection:
            mock_collection.return_value.stream.return_value = []

            response = client.get('/get-accounts')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data == []

    def test_get_accounts_with_data(self, client):
        """Test retrieving account list with data"""
        # Mock Firebase documents
        mock_doc1 = Mock()
        mock_doc1.id = "Account1"
        mock_doc2 = Mock()
        mock_doc2.id = "Account2"

        with patch('app.db.collection') as mock_collection:
            mock_collection.return_value.stream.return_value = [mock_doc1, mock_doc2]

            response = client.get('/get-accounts')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert len(data) == 2
            assert "Account1" in data
            assert "Account2" in data


class TestAddAccountEndpoint:
    """Test POST /add_account endpoint"""

    def test_add_account_missing_fields(self, client):
        """Test account addition with missing fields"""
        response = client.post(
            '/add_account',
            data=json.dumps({}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_add_account_invalid_email(self, client):
        """Test account addition with invalid email"""
        response = client.post(
            '/add_account',
            data=json.dumps({
                'account_name': 'Test',
                'email': 'invalid-email',
                'password': 'password123'
            }),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'email' in data['error'].lower()


class TestGetFeedEndpoint:
    """Test POST /get_feed endpoint"""

    def test_get_feed_missing_account_name(self, client):
        """Test feed retrieval without account name"""
        response = client.post(
            '/get_feed',
            data=json.dumps({}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_get_feed_account_not_found(self, client):
        """Test feed retrieval for non-existent account"""
        with patch('app.db.collection') as mock_collection:
            mock_doc = Mock()
            mock_doc.exists = False
            mock_collection.return_value.document.return_value.get.return_value = mock_doc

            response = client.post(
                '/get_feed',
                data=json.dumps({'account_name': 'NonExistent'}),
                content_type='application/json'
            )
            assert response.status_code == 404
            data = json.loads(response.data)
            assert 'error' in data


# ============= INTEGRATION TESTS =============

class TestRateLimiting:
    """Test rate limiting functionality"""

    def test_rate_limit_enforcement(self):
        """Test that rate limiting works"""
        from utils import check_rate_limit

        # Should allow first 3 requests
        assert check_rate_limit("test_user", 3, 60) == True
        assert check_rate_limit("test_user", 3, 60) == True
        assert check_rate_limit("test_user", 3, 60) == True

        # 4th request should be blocked
        assert check_rate_limit("test_user", 3, 60) == False


# ============= CONSTANTS TESTS =============

class TestConstants:
    """Test that all constants are properly defined"""

    def test_http_status_codes(self):
        """Test HTTP status code constants"""
        assert HTTP_OK == 200
        assert HTTP_BAD_REQUEST == 400
        assert HTTP_UNAUTHORIZED == 401
        assert HTTP_NOT_FOUND == 404
        assert HTTP_INTERNAL_ERROR == 500

    def test_endpoint_constants(self):
        """Test endpoint path constants"""
        assert ENDPOINT_GET_ACCOUNTS == '/get-accounts'
        assert ENDPOINT_ADD_ACCOUNT == '/add_account'
        assert ENDPOINT_GET_FEED == '/get_feed'
        assert ENDPOINT_HEALTH == '/health'


# ============= PYTEST CONFIGURATION =============

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=app', '--cov=utils', '--cov-report=html'])
