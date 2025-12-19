/**
 * X Feed Viewer - Chrome Extension Frontend
 * Handles UI interactions and backend communication
 *
 * Version: 2.0.0
 */

// ============= CONFIGURATION =============

const CONFIG = {
    API_BASE_URL: 'http://127.0.0.1:5000',
    MAX_ACCOUNT_NAME_LENGTH: 50,
    AVATAR_COLORS: [
        'bg-blue-500', 'bg-green-500', 'bg-red-500', 'bg-purple-500',
        'bg-pink-500', 'bg-indigo-500', 'bg-teal-500', 'bg-orange-500',
        'bg-yellow-500', 'bg-cyan-500'
    ],
    REQUEST_TIMEOUT: 30000 // 30 seconds
};

// ============= INITIALIZATION =============

document.addEventListener('DOMContentLoaded', () => {
    loadSavedAccounts();
    document.getElementById('add-account-form').addEventListener('submit', handleAddAccount);
});

// ============= ACCOUNT LOADING =============

/**
 * Load and display all saved accounts from backend
 */
async function loadSavedAccounts() {
    const listDiv = document.getElementById('saved-accounts-list');

    try {
        const response = await fetchWithTimeout(`${CONFIG.API_BASE_URL}/get-accounts`, {
            method: 'GET'
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const accounts = await response.json();
        renderAccountsList(listDiv, accounts);

    } catch (error) {
        console.error('Failed to load accounts:', error);
        listDiv.innerHTML = createErrorElement(
            'Error: Could not connect to backend server. Is it running?'
        ).outerHTML;
    }
}

/**
 * Render accounts list in the UI
 * @param {HTMLElement} container - Container element
 * @param {Array<string>} accounts - Array of account names
 */
function renderAccountsList(container, accounts) {
    // Clear existing content
    container.innerHTML = '';

    if (!accounts || accounts.length === 0) {
        const emptyMessage = document.createElement('p');
        emptyMessage.className = 'text-x-text-secondary p-3';
        emptyMessage.textContent = 'No saved accounts found.';
        container.appendChild(emptyMessage);
        return;
    }

    accounts.forEach((name, index) => {
        const accountElement = createAccountElement(name, index);
        container.appendChild(accountElement);
    });
}

/**
 * Create account element with avatar and view button
 * @param {string} name - Account name
 * @param {number} index - Account index for color rotation
 * @returns {HTMLElement} Account container element
 */
function createAccountElement(name, index) {
    const entryContainer = document.createElement('div');
    entryContainer.className = 'w-full';

    const accountRow = document.createElement('div');
    accountRow.className = 'flex w-full items-center p-2 transition-colors hover:bg-white/10';

    // Create avatar
    const avatar = createAvatar(name, index);

    // Create name span
    const nameSpan = document.createElement('span');
    nameSpan.className = 'ml-3 flex-grow text-base font-bold';
    nameSpan.textContent = sanitizeText(name); // Sanitize for XSS protection

    // Create view button
    const viewButton = document.createElement('button');
    viewButton.textContent = 'View Feed';
    viewButton.className = 'flex-shrink-0 rounded-full bg-x-text-primary px-4 py-1.5 text-sm font-bold text-x-bg transition-colors hover:bg-opacity-90';
    viewButton.onclick = () => loadFeedFor(name);

    // Create status div
    const statusDiv = document.createElement('div');
    statusDiv.id = `status-${sanitizeId(name)}`;
    statusDiv.className = 'hidden p-3';

    // Assemble elements
    accountRow.appendChild(avatar);
    accountRow.appendChild(nameSpan);
    accountRow.appendChild(viewButton);

    entryContainer.appendChild(accountRow);
    entryContainer.appendChild(statusDiv);

    return entryContainer;
}

/**
 * Create avatar element with first letter and color
 * @param {string} name - Account name
 * @param {number} index - Index for color selection
 * @returns {HTMLElement} Avatar element
 */
function createAvatar(name, index) {
    const avatar = document.createElement('div');
    const color = CONFIG.AVATAR_COLORS[index % CONFIG.AVATAR_COLORS.length];
    avatar.className = `flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-lg font-bold text-white ${color}`;
    avatar.textContent = (name.charAt(0) || '?').toUpperCase();
    return avatar;
}

// ============= FEED LOADING =============

/**
 * Load feed for specified account
 * @param {string} accountName - Name of account to load feed for
 */
async function loadFeedFor(accountName) {
    const statusDiv = document.getElementById(`status-${sanitizeId(accountName)}`);
    updateIndividualStatus(statusDiv, 'Loading feed...', 'loading');

    try {
        const response = await fetchWithTimeout(`${CONFIG.API_BASE_URL}/get_feed`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ account_name: accountName })
        });

        const result = await response.json();

        if (!response.ok) {
            throw result;
        }

        updateIndividualStatus(statusDiv, 'Feed loaded. Injecting...', 'success');

        // Inject feed into active tab
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

        if (!tab || !tab.id) {
            throw new Error('No active tab found');
        }

        // Check if we're on X/Twitter
        if (!tab.url || !tab.url.includes('x.com') && !tab.url.includes('twitter.com')) {
            updateIndividualStatus(
                statusDiv,
                'Please navigate to x.com or twitter.com to view the feed.',
                'error'
            );
            return;
        }

        chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: displayFeedInPage,
            args: [result, accountName]
        });

        // Update success message after a delay
        setTimeout(() => {
            updateIndividualStatus(statusDiv, `✓ ${result.length} tweets loaded successfully`, 'success');
        }, 1000);

    } catch (error) {
        console.error('Feed loading error:', error);

        const errorMessage = error && error.error
            ? `<b>Error:</b> ${escapeHtml(error.error)}`
            : '<b>Network Error:</b> Could not load feed.';

        updateIndividualStatus(statusDiv, errorMessage, 'error');
    }
}

// ============= ACCOUNT ADDITION =============

/**
 * Handle account addition form submission
 * @param {Event} event - Form submit event
 */
async function handleAddAccount(event) {
    event.preventDefault();
    updateLoginStatus('Logging in...', 'loading');

    // Get form data
    const formData = {
        account_name: document.getElementById('account_name').value.trim(),
        username: document.getElementById('username').value.trim(),
        email: document.getElementById('email').value.trim(),
        password: document.getElementById('password').value
    };

    // Client-side validation
    const validationError = validateFormData(formData);
    if (validationError) {
        updateLoginStatus(`<b>Input Error:</b> ${escapeHtml(validationError)}`, 'error');
        return;
    }

    try {
        const response = await fetchWithTimeout(`${CONFIG.API_BASE_URL}/add_account`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        const result = await response.json();

        if (!response.ok) {
            throw result;
        }

        updateLoginStatus(escapeHtml(result.message), 'success');
        document.getElementById('add-account-form').reset();

        // Reload accounts list
        setTimeout(() => {
            loadSavedAccounts();
        }, 500);

    } catch (error) {
        console.error('Account addition error:', error);

        const errorMessage = error && error.error
            ? `<b>Server Error:</b> ${escapeHtml(error.error)}`
            : '<b>Network Error:</b> Could not reach server.';

        updateLoginStatus(errorMessage, 'error');
    }
}

/**
 * Validate form data before submission
 * @param {Object} data - Form data object
 * @returns {string|null} Error message or null if valid
 */
function validateFormData(data) {
    if (!data.account_name || data.account_name.length === 0) {
        return 'Account name is required.';
    }

    if (data.account_name.length > CONFIG.MAX_ACCOUNT_NAME_LENGTH) {
        return `Account name must be less than ${CONFIG.MAX_ACCOUNT_NAME_LENGTH} characters.';
    }

    if (!data.password || data.password.length < 8) {
        return 'Password must be at least 8 characters.';
    }

    if (!data.username && !data.email) {
        return 'Either username or email is required.';
    }

    if (data.email && !isValidEmail(data.email)) {
        return 'Please enter a valid email address.';
    }

    return null;
}

/**
 * Check if email format is valid
 * @param {string} email - Email to validate
 * @returns {boolean} True if valid
 */
function isValidEmail(email) {
    const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    return emailRegex.test(email);
}

// ============= STATUS UPDATE FUNCTIONS =============

/**
 * Update individual account status display
 * @param {HTMLElement} element - Status element
 * @param {string} message - Message to display (can contain HTML)
 * @param {string} type - Type: 'success', 'error', or 'loading'
 */
function updateIndividualStatus(element, message, type) {
    if (!element) return;

    element.innerHTML = message; // Safe because we control the message source
    element.className = 'rounded-md border p-3 text-sm';

    // Show the element
    element.classList.remove('hidden');

    switch (type) {
        case 'success':
            element.classList.add('bg-green-900/50', 'border-green-700', 'text-green-300');
            break;
        case 'error':
            element.classList.add('bg-red-900/50', 'border-red-700', 'text-red-300');
            break;
        case 'loading':
            element.classList.add('bg-yellow-900/50', 'border-yellow-700', 'text-yellow-300');
            break;
    }
}

/**
 * Update login form status display
 * @param {string} message - Message to display
 * @param {string} type - Type: 'success', 'error', or 'loading'
 */
function updateLoginStatus(message, type) {
    const statusDiv = document.getElementById('login-status');
    statusDiv.innerHTML = message;
    statusDiv.className = 'rounded-md border p-3 text-sm';

    // Show the element
    statusDiv.classList.remove('hidden');

    switch (type) {
        case 'success':
            statusDiv.classList.add('bg-green-900/50', 'border-green-700', 'text-green-300');
            break;
        case 'error':
            statusDiv.classList.add('bg-red-900/50', 'border-red-700', 'text-red-300');
            break;
        case 'loading':
            statusDiv.classList.add('bg-yellow-900/50', 'border-yellow-700', 'text-yellow-300');
            break;
    }
}

// ============= FEED DISPLAY (CONTENT SCRIPT) =============

/**
 * Display feed in the current page (injected as content script)
 * SECURITY: Uses DOM manipulation instead of innerHTML to prevent XSS
 *
 * @param {Array} tweets - Array of tweet objects
 * @param {string} accountName - Account name for display
 */
function displayFeedInPage(tweets, accountName) {
    const primaryColumn = document.querySelector('div[data-testid="primaryColumn"]');

    if (!primaryColumn) {
        alert('Could not find the primary column to inject content. Please make sure you\'re on x.com or twitter.com.');
        return;
    }

    // Remove old container if exists
    const oldContainer = document.getElementById('custom-feed-container');
    if (oldContainer) oldContainer.remove();

    // Create new feed container
    const feedContainer = document.createElement('div');
    feedContainer.id = 'custom-feed-container';

    // Create header
    const header = createFeedHeader(accountName);
    feedContainer.appendChild(header);

    // Create tweets
    tweets.forEach(tweet => {
        try {
            const tweetElement = createTweetElement(tweet);
            feedContainer.appendChild(tweetElement);
        } catch (error) {
            console.warn('Failed to render tweet:', tweet.id, error);
        }
    });

    // Inject at top of primary column
    primaryColumn.prepend(feedContainer);
}

/**
 * Create feed header element
 * @param {string} accountName - Account name
 * @returns {HTMLElement} Header element
 */
function createFeedHeader(accountName) {
    const header = document.createElement('h2');
    header.style.cssText = 'padding: 1rem; margin:0; text-align: center; color: #e7e9ea; border-bottom: 1px solid #38444d; border-top: 1px solid #38444d; font-weight: bold;';
    header.textContent = `Displaying Custom Feed for "${accountName}"`;
    return header;
}

/**
 * Create tweet element (SECURITY: Uses DOM methods, not innerHTML)
 * @param {Object} tweet - Tweet data object
 * @returns {HTMLElement} Tweet article element
 */
function createTweetElement(tweet) {
    const article = document.createElement('article');
    article.style.cssText = 'border-bottom: 1px solid #38444d; padding: 1rem; display: flex; flex-direction: column;';

    // Create header row with avatar and user info
    const headerRow = document.createElement('div');
    headerRow.style.cssText = 'display: flex; align-items: flex-start;';

    // Profile image
    const profileImg = document.createElement('img');
    profileImg.src = tweet.user.profile_image_url_https || '';
    profileImg.style.cssText = 'width: 48px; height: 48px; border-radius: 50%; flex-shrink: 0;';
    profileImg.onerror = function() { this.style.display = 'none'; };

    // User info container
    const userInfoDiv = document.createElement('div');
    userInfoDiv.style.cssText = 'margin-left: 12px; line-height: 1.4; width: 100%;';

    // User name row
    const userNameRow = document.createElement('div');
    userNameRow.style.cssText = 'display: flex; align-items: center; flex-wrap: wrap;';

    const nameSpan = document.createElement('span');
    nameSpan.style.cssText = 'font-weight: bold; margin: 0; color: #e7e9ea;';
    nameSpan.textContent = tweet.user.name;
    userNameRow.appendChild(nameSpan);

    // Verified badge
    if (tweet.user.is_verified || tweet.user.is_blue_verified) {
        const badge = createVerifiedBadge();
        userNameRow.appendChild(badge);
    }

    // Screen name
    const screenNameSpan = document.createElement('span');
    screenNameSpan.style.cssText = 'font-weight: normal; color: #71767b; margin-left: 5px;';
    screenNameSpan.textContent = `@${tweet.user.screen_name}`;
    userNameRow.appendChild(screenNameSpan);

    userInfoDiv.appendChild(userNameRow);

    // Tweet text
    const textDiv = document.createElement('div');
    textDiv.style.cssText = 'margin: 5px 0 0 0; white-space: pre-wrap; word-wrap: break-word; color: #e7e9ea; font-size: 15px;';
    textDiv.appendChild(formatTweetText(tweet.text));
    userInfoDiv.appendChild(textDiv);

    headerRow.appendChild(profileImg);
    headerRow.appendChild(userInfoDiv);
    article.appendChild(headerRow);

    // Media
    if (tweet.media && tweet.media.length > 0) {
        const mediaContainer = createMediaContainer(tweet.media);
        article.appendChild(mediaContainer);
    }

    // Stats row
    const statsRow = createStatsRow(tweet);
    article.appendChild(statsRow);

    return article;
}

/**
 * Create verified badge SVG
 * @returns {HTMLElement} Badge element
 */
function createVerifiedBadge() {
    const badge = document.createElement('span');
    badge.style.cssText = 'margin-left: 4px; vertical-align: text-bottom; display: inline-flex; align-items: center; justify-content: center; width: 20px; height: 20px; background-color: #1d9bf0; border-radius: 50%;';
    badge.innerHTML = '<svg viewBox="0 0 24 24" style="height: 14px; fill: white;"><g><path d="M9.98 15.36l-3.888-3.635 1.332-1.26 2.556 2.373 5.448-5.18 1.332 1.26-6.78 6.44z"></path></g></svg>';
    return badge;
}

/**
 * Format tweet text with linkify (SECURITY: Uses Text Nodes)
 * @param {string} text - Tweet text
 * @returns {DocumentFragment} Formatted text fragment
 */
function formatTweetText(text) {
    const fragment = document.createDocumentFragment();

    // Remove t.co URLs
    text = text.replace(/https:\/\/t\.co\/[a-zA-Z0-9]+/g, '');

    // Split by URLs and create text nodes and links
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const parts = text.split(urlRegex);

    parts.forEach(part => {
        if (part.match(urlRegex)) {
            // Create link
            const link = document.createElement('a');
            link.href = part;
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            link.style.color = '#1d9bf0';
            link.textContent = part;
            fragment.appendChild(link);
        } else {
            // Create text node (safe from XSS)
            fragment.appendChild(document.createTextNode(part));
        }
    });

    return fragment;
}

/**
 * Create media container with images/videos
 * @param {Array} mediaList - Array of media objects
 * @returns {HTMLElement} Media container
 */
function createMediaContainer(mediaList) {
    const container = document.createElement('div');
    container.style.cssText = 'margin-top: 12px;';

    const mediaStyle = 'width: 100%; max-height: 500px; object-fit: cover; border-radius: 16px; margin-top: 12px; border: 1px solid #38444d;';

    mediaList.forEach(media => {
        if (media.type === 'photo') {
            const img = document.createElement('img');
            img.src = media.url;
            img.style.cssText = mediaStyle;
            img.onerror = function() { this.style.display = 'none'; };
            container.appendChild(img);

        } else if (media.type === 'video') {
            const video = document.createElement('video');
            video.src = media.url;
            video.controls = true;
            video.style.cssText = mediaStyle;
            container.appendChild(video);

        } else if (media.type === 'animated_gif') {
            const video = document.createElement('video');
            video.src = media.url;
            video.autoplay = true;
            video.loop = true;
            video.muted = true;
            video.playsInline = true;
            video.style.cssText = mediaStyle;
            container.appendChild(video);
        }
    });

    return container;
}

/**
 * Create stats row with engagement metrics
 * @param {Object} tweet - Tweet object
 * @returns {HTMLElement} Stats row element
 */
function createStatsRow(tweet) {
    const statsRow = document.createElement('div');
    statsRow.style.cssText = 'display: flex; justify-content: space-between; align-items:center; color: #71767b; margin-top: 12px; font-size: 13px;';

    const statsLeft = document.createElement('div');

    const likesSpan = document.createElement('span');
    likesSpan.textContent = `❤️ ${formatStats(tweet.stats.likes)}`;
    statsLeft.appendChild(likesSpan);

    const retweetsSpan = document.createElement('span');
    retweetsSpan.style.marginLeft = '1rem';
    retweetsSpan.textContent = `🔁 ${formatStats(tweet.stats.retweets)}`;
    statsLeft.appendChild(retweetsSpan);

    const viewsSpan = document.createElement('span');
    viewsSpan.style.marginLeft = '1rem';
    viewsSpan.textContent = `👁️ ${formatStats(tweet.stats.views)}`;
    statsLeft.appendChild(viewsSpan);

    const timestamp = document.createElement('span');
    timestamp.textContent = new Date(tweet.created_at).toLocaleString();
    timestamp.style.color = '#71767b';

    statsRow.appendChild(statsLeft);
    statsRow.appendChild(timestamp);

    return statsRow;
}

/**
 * Format large numbers with K/M suffixes
 * @param {number} num - Number to format
 * @returns {string} Formatted string
 */
function formatStats(num) {
    if (!num) return '0';
    if (num >= 1000000) return (num / 1000000).toFixed(1).replace(/\.0$/, '') + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1).replace(/\.0$/, '') + 'K';
    return num.toString();
}

// ============= UTILITY FUNCTIONS =============

/**
 * Fetch with timeout wrapper
 * @param {string} url - URL to fetch
 * @param {Object} options - Fetch options
 * @param {number} timeout - Timeout in milliseconds
 * @returns {Promise<Response>} Fetch response
 */
async function fetchWithTimeout(url, options = {}, timeout = CONFIG.REQUEST_TIMEOUT) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
        const response = await fetch(url, {
            ...options,
            signal: controller.signal
        });
        clearTimeout(timeoutId);
        return response;
    } catch (error) {
        clearTimeout(timeoutId);
        if (error.name === 'AbortError') {
            throw new Error('Request timeout');
        }
        throw error;
    }
}

/**
 * Escape HTML to prevent XSS
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Sanitize text for safe display
 * @param {string} text - Text to sanitize
 * @returns {string} Sanitized text
 */
function sanitizeText(text) {
    return text.replace(/[<>\"']/g, char => {
        const entities = { '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
        return entities[char] || char;
    });
}

/**
 * Sanitize ID for use in DOM queries
 * @param {string} id - ID to sanitize
 * @returns {string} Sanitized ID
 */
function sanitizeId(id) {
    return id.replace(/[^a-zA-Z0-9_-]/g, '_');
}

/**
 * Create error message element
 * @param {string} message - Error message
 * @returns {HTMLElement} Error element
 */
function createErrorElement(message) {
    const p = document.createElement('p');
    p.className = 'text-red-500 p-3';
    p.textContent = message;
    return p;
}
