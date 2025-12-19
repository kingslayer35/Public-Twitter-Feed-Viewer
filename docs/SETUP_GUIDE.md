# 🚀 X Feed Viewer - Complete Setup Guide

This guide will help you set up and run the X Feed Viewer extension professionally.

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Initial Setup](#initial-setup)
3. [Configuration](#configuration)
4. [Running the Application](#running-the-application)
5. [Using Docker](#using-docker)
6. [Development Workflow](#development-workflow)
7. [Testing](#testing)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

- **Python 3.8+** ([Download](https://www.python.org/downloads/))
- **Google Chrome** (Latest version)
- **Firebase Account** ([Create free account](https://firebase.google.com/))
- **Git** (For version control)

### Optional (Recommended)

- **Docker** (For containerized deployment)
- **VS Code** (With Python extension)

---

## Initial Setup

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/x-feed-viewer.git
cd x-feed-viewer
```

### 2. Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Configuration

### 1. Firebase Setup

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Create a new project or select existing
3. Go to **Project Settings** → **Service Accounts**
4. Click **Generate New Private Key**
5. Save the JSON file as `serviceAccountKey.json` in the project root

### 2. Enable Firestore Database

1. In Firebase Console, go to **Firestore Database**
2. Click **Create Database**
3. Choose **Start in production mode**
4. Select a location

### 3. Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` and configure:

```env
# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=False
FLASK_HOST=127.0.0.1
FLASK_PORT=5000

# Security
SECRET_KEY=your-super-secret-key-change-this-in-production
API_KEY=your-api-key-for-extension

# Firebase
FIREBASE_CREDENTIALS_PATH=serviceAccountKey.json

# Application Settings
MAX_TWEETS_PER_REQUEST=200
CACHE_TIMEOUT_SECONDS=300
RATE_LIMIT_PER_MINUTE=10

# CORS Configuration
ALLOWED_ORIGINS=http://127.0.0.1:5000,chrome-extension://*

# Logging
LOG_LEVEL=INFO
LOG_FILE=app.log
```

**IMPORTANT:** Generate secure random keys:

```python
# Run in Python console
import secrets
print(f"SECRET_KEY={secrets.token_hex(32)}")
print(f"API_KEY={secrets.token_hex(16)}")
```

---

## Running the Application

### Method 1: Local Python Server (Development)

1. **Start the Backend:**

```bash
python app.py
```

You should see:

```
🚀 X Feed Viewer API v2.0.0 Starting...
Environment: development
Debug Mode: False
Host: 127.0.0.1:5000
```

2. **Load Chrome Extension:**

- Open Chrome and go to `chrome://extensions/`
- Enable **Developer mode** (top right toggle)
- Click **Load unpacked**
- Select the project directory
- The extension icon will appear in your toolbar

3. **Test the Extension:**

- Click the extension icon
- Add a new account with your X credentials
- Navigate to `x.com` or `twitter.com`
- Click "View Feed" for any saved account

### Method 2: Using Docker (Production)

1. **Build and Run:**

```bash
docker-compose up --build
```

Or manually:

```bash
docker build -t x-feed-viewer .
docker run -p 5000:5000 --env-file .env x-feed-viewer
```

2. **Stop the Container:**

```bash
docker-compose down
```

---

## Development Workflow

### Project Structure

```
x-feed-viewer/
├── app.py                 # Main Flask application
├── config.py             # Configuration management
├── constants.py          # Centralized constants
├── utils.py              # Utility functions
├── test_app.py           # Test suite
├── popup.js              # Extension frontend
├── popup.html            # Extension UI
├── manifest.json         # Chrome extension config
├── requirements.txt      # Python dependencies
├── Dockerfile            # Docker image definition
├── docker-compose.yml    # Docker orchestration
├── .env                  # Environment variables (gitignored)
├── .env.example          # Example environment file
└── .gitignore            # Git ignore rules
```

### Code Style

We use industry-standard Python conventions:

- **PEP 8** for Python code style
- **JSDoc** comments for JavaScript functions
- **Type hints** for Python functions
- **Descriptive variable names**

### Pre-commit Checks (Optional)

Install pre-commit hooks:

```bash
pip install black flake8 pylint
```

Format code before committing:

```bash
black app.py utils.py config.py
flake8 app.py utils.py
```

---

## Testing

### Run Unit Tests

```bash
# Basic test run
pytest test_app.py -v

# With coverage report
pytest test_app.py -v --cov=app --cov=utils --cov-report=html

# View coverage report
# Open htmlcov/index.html in your browser
```

### Manual Testing Checklist

- [ ] Backend starts without errors
- [ ] `/health` endpoint returns 200 OK
- [ ] Extension loads in Chrome
- [ ] Can add new account successfully
- [ ] Saved accounts appear in list
- [ ] Feed loads correctly on x.com
- [ ] Media (images/videos) displays properly
- [ ] Error messages are user-friendly
- [ ] Cache reduces load times on repeat views

---

## Troubleshooting

### Common Issues

#### 1. "Firebase initialization failed"

**Problem:** Missing or invalid `serviceAccountKey.json`

**Solution:**
- Ensure file exists in project root
- Verify it's valid JSON
- Check `.env` has correct `FIREBASE_CREDENTIALS_PATH`

#### 2. "Could not connect to backend server"

**Problem:** Flask server not running or wrong port

**Solution:**
- Run `python app.py` to start server
- Check console for port number (default 5000)
- Ensure firewall allows localhost:5000

#### 3. "Session has expired"

**Problem:** X/Twitter session cookies invalidated

**Solution:**
- Re-add the account through extension popup
- Check if account has 2FA enabled (may require app password)

#### 4. "Rate limit exceeded"

**Problem:** Too many requests to X API

**Solution:**
- Wait 5-10 minutes before retrying
- Reduce `MAX_TWEETS_PER_REQUEST` in `.env`
- Implement longer cache timeouts

#### 5. Extension not appearing in Chrome

**Problem:** Manifest version mismatch or loading error

**Solution:**
- Check Chrome console for errors (`chrome://extensions/`)
- Ensure all files are in correct directory
- Reload extension after code changes

#### 6. "ModuleNotFoundError" when running app

**Problem:** Missing dependencies

**Solution:**
```bash
pip install --upgrade -r requirements.txt
```

### Debug Mode

Enable detailed logging:

1. Edit `.env`:
```env
LOG_LEVEL=DEBUG
```

2. Check `app.log` for detailed traces

3. View browser console (F12) for frontend errors

### Performance Issues

If feeds load slowly:

1. **Increase cache timeout:**
```env
CACHE_TIMEOUT_SECONDS=600
```

2. **Reduce tweets per request:**
```env
MAX_TWEETS_PER_REQUEST=50
```

3. **Check Firebase connection:**
- Ensure you're on stable internet
- Firebase location should be geographically close

---

## Security Best Practices

### Production Checklist

- [ ] Change `SECRET_KEY` and `API_KEY` to strong random values
- [ ] Set `FLASK_DEBUG=False` in production
- [ ] Use HTTPS for backend (not localhost)
- [ ] Implement API key authentication for all endpoints
- [ ] Regularly rotate Firebase service account keys
- [ ] Monitor `app.log` for suspicious activity
- [ ] Set up automated backups for Firebase data

### Never Commit

- `serviceAccountKey.json` (Firebase credentials)
- `.env` file (secrets)
- `app.log` (may contain sensitive data)
- `__pycache__/` directories

These are already in `.gitignore`.

---

## Next Steps

After successful setup:

1. **Test all features thoroughly**
2. **Customize UI colors** (edit `tailwind.config.js`)
3. **Add more accounts** for competitor tracking
4. **Review analytics** (`/get_analytics` endpoint)
5. **Deploy to production** (see Deployment Guide)

---

## Support

If you encounter issues not covered here:

1. Check the main [README.md](README.md)
2. Review [GitHub Issues](https://github.com/yourusername/x-feed-viewer/issues)
3. Consult [X/Twitter API documentation](https://developer.twitter.com/en/docs)

---

**Made with ❤️ for the X community**
