// Augment Conversation Manager - Frontend JavaScript
// API base URL - change this for GitHub Pages deployment
const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:5001/api'
    : 'http://localhost:5001/api'; // Change to your deployed API URL

let allConversations = [];
let debugEnabled = false;
let debugLogs = [];

// Utility functions (defined early so debugLog can use them)
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Debug logging
function debugLog(message, type = 'info') {
    const timestamp = new Date().toLocaleTimeString();
    const logEntry = `[${timestamp}] ${message}`;

    // Always log to browser console
    if (type === 'error') {
        console.error(logEntry);
    } else if (type === 'warn') {
        console.warn(logEntry);
    } else {
        console.log(logEntry);
    }

    // Store log for later display
    debugLogs.push({ timestamp, message, type });

    // Add to debug console if it exists and is enabled
    const debugLogsElement = document.getElementById('debugLogs');
    if (debugEnabled && debugLogsElement) {
        const entry = document.createElement('div');
        entry.className = `log-entry ${type}`;
        entry.innerHTML = `<span class="timestamp">${timestamp}</span>${escapeHtml(message)}`;
        debugLogsElement.appendChild(entry);
        debugLogsElement.scrollTop = debugLogsElement.scrollHeight;
    }
}

function toggleDebugConsole() {
    debugEnabled = !debugEnabled;
    const consoleElement = document.getElementById('debugConsole');
    const debugLogsElement = document.getElementById('debugLogs');

    consoleElement.style.display = debugEnabled ? 'block' : 'none';

    // Replay all stored logs when enabling
    if (debugEnabled && debugLogsElement) {
        debugLogsElement.innerHTML = '';
        debugLogs.forEach(log => {
            const entry = document.createElement('div');
            entry.className = `log-entry ${log.type}`;
            entry.innerHTML = `<span class="timestamp">${log.timestamp}</span>${escapeHtml(log.message)}`;
            debugLogsElement.appendChild(entry);
        });
        debugLogsElement.scrollTop = debugLogsElement.scrollHeight;
    }

    debugLog('Debug console ' + (debugEnabled ? 'enabled' : 'disabled'), 'info');
}

// Load statistics
async function loadStats() {
    debugLog('Loading statistics from API...', 'info');
    try {
        const response = await fetch(`${API_BASE}/stats`);
        debugLog(`Stats API response status: ${response.status}`, 'info');
        const data = await response.json();

        if (data.success) {
            const stats = data.stats;
            debugLog(`Stats loaded: ${stats.total_conversations} conversations, ${stats.total_messages} messages`, 'info');
            document.getElementById('stats').innerHTML = `
                <span>📊 ${stats.total_conversations} conversations</span>
                <span>💬 ${stats.total_messages.toLocaleString()} messages</span>
                <span>🔧 ${stats.total_tool_states.toLocaleString()} tool states</span>
                <span>💾 ${stats.total_storage_mb.toFixed(2)} MB</span>
                <span>📦 Cache hit rate: ${((stats.redis_hits / (stats.redis_hits + stats.redis_misses)) * 100).toFixed(1)}%</span>
            `;
        } else {
            debugLog(`Stats API returned error: ${data.error}`, 'error');
        }
    } catch (error) {
        debugLog(`Error loading stats: ${error.message}`, 'error');
        document.getElementById('stats').innerHTML = `
            <span style="color: #ffcdd2;">⚠️ Could not connect to API server. Make sure it's running on http://localhost:5001</span>
        `;
    }
}

// Load conversations
async function loadConversations() {
    debugLog('Loading conversations from API...', 'info');
    try {
        const url = `${API_BASE}/conversations?limit=100`;
        debugLog(`Fetching: ${url}`, 'info');
        const response = await fetch(url);
        debugLog(`Conversations API response status: ${response.status}`, 'info');
        const data = await response.json();
        debugLog(`Conversations API response: ${JSON.stringify(data).substring(0, 200)}...`, 'info');

        if (data.success) {
            allConversations = data.conversations;
            debugLog(`Loaded ${allConversations.length} conversations into allConversations array`, 'info');
            displayConversations(allConversations);
        } else {
            debugLog(`Conversations API returned error: ${data.error}`, 'error');
            showError('Failed to load conversations: ' + data.error);
        }
    } catch (error) {
        debugLog(`Error loading conversations: ${error.message}`, 'error');
        showError('Could not connect to API server. Make sure it\'s running on http://localhost:5001');
    }
}

// Display conversations
function displayConversations(conversations) {
    const list = document.getElementById('conversationsList');
    
    if (conversations.length === 0) {
        list.innerHTML = '<div class="loading">No conversations found. Import some conversations first!</div>';
        return;
    }
    
    list.innerHTML = conversations.map(conv => `
        <div class="conversation-item" onclick="openConversation('${conv.conversation_id}', '${escapeHtml(conv.name)}')">
            <div class="conversation-name">${escapeHtml(conv.name)}</div>
            <div class="conversation-meta">
                <span>💬 ${conv.total_messages} messages</span>
                <span>🔧 ${conv.total_tool_states} tools</span>
                <span>📅 ${formatDate(conv.last_interacted_at)}</span>
                <span>💾 ${conv.file_size_mb.toFixed(2)} MB</span>
            </div>
        </div>
    `).join('');
}

// UX-SEARCH-006: Render UX failure banner
function renderUXBanner(data) {
    const banner = document.getElementById("ux-banner");
    if (!banner) return;

    if (data.ux_status === "degraded") {
        banner.style.display = "block";
        banner.className = "ux-banner degraded";
        banner.innerHTML = `
            ⚠️ Search refinement did not change results.<br/>
            <small>${data.ux_reason || 'Showing best-effort matches.'}</small>
        `;
    } else {
        banner.style.display = "none";
    }
}

// UX-SEARCH-006: Render ranking delta widget
function renderRankingDeltaWidget(data) {
    const widget = document.getElementById("ranking-delta");
    if (!widget) return;

    const metrics = data.ux_metrics;
    if (!metrics || metrics.overlap === null || metrics.overlap === undefined) {
        widget.innerHTML = "";
        return;
    }

    const pct = Math.round(metrics.overlap * 100);
    const top10Changes = metrics.top10_changes || 0;

    let label = "High refinement impact";
    let cls = "good";

    if (pct >= 90 && top10Changes < 3) {
        label = "No refinement impact (BLOCKED)";
        cls = "bad";
    } else if (pct > 70) {
        label = "Low refinement impact";
        cls = "warn";
    }

    widget.className = `ranking-delta ${cls}`;
    widget.innerHTML = `
        🔁 Ranking overlap: ${pct}%<br/>
        📊 Top-10 changes: ${top10Changes}<br/>
        <small>${label}</small>
    `;
}

// UX-SEARCH-007: Render query explanation (stop making users guess)
function renderQueryExplanation(data) {
    const widget = document.getElementById("query-explain");
    if (!widget) return;

    const explain = data.query_explanation;
    if (!explain) {
        widget.innerHTML = "";
        return;
    }

    const stopwordsText = explain.stopwords_removed.length > 0
        ? explain.stopwords_removed.join(", ")
        : "none";

    widget.innerHTML = `
        <strong>🔍 Search interpretation:</strong><br/>
        <small>
        Terms used: <code>${explain.effective_terms.join(", ")}</code><br/>
        Stopwords removed: <code>${stopwordsText}</code><br/>
        Stemming: ${explain.stemming_enabled ? "✓ yes" : "✗ no"} |
        Fuzzy matching: ${explain.fuzzy_matching_enabled ? "✓ yes" : "✗ no"}
        </small>
    `;
}

// MODERN UX: Render "did you mean" suggestion
function renderDidYouMean(data) {
    const widget = document.getElementById("did-you-mean");
    if (!widget) return;

    const didYouMean = data.did_you_mean;
    const searchType = data.search_type;

    if (!didYouMean && searchType !== 'fuzzy') {
        widget.innerHTML = "";
        widget.style.display = "none";
        return;
    }

    let html = '';

    if (didYouMean) {
        html = `
            <div style="background: #fff3cd; padding: 10px 14px; border-radius: 4px; border-left: 4px solid #ffc107;">
                <strong>💡 Did you mean:</strong>
                <a href="#" onclick="document.getElementById('searchInput').value='${escapeHtml(didYouMean)}'; searchConversations('${escapeHtml(didYouMean)}'); return false;"
                   style="color: #0066cc; text-decoration: underline; cursor: pointer;">
                    ${escapeHtml(didYouMean)}
                </a>
            </div>
        `;
    }

    if (searchType === 'fuzzy') {
        html += `
            <div style="background: #e3f2fd; padding: 8px 12px; border-radius: 4px; margin-top: 8px; font-size: 0.85rem;">
                ℹ️ Showing fuzzy matches (approximate results)
            </div>
        `;
    }

    widget.innerHTML = html;
    widget.style.display = html ? "block" : "none";
}

// Search message content using backend API (returns message-level matches with snippets)
async function searchConversations(query) {
    debugLog(`Search query: "${query}"`, 'info');

    if (!query.trim()) {
        debugLog('Empty search query, displaying all conversations', 'info');
        displayConversations(allConversations);
        // Clear UX widgets
        document.getElementById("ux-banner").style.display = "none";
        document.getElementById("ranking-delta").innerHTML = "";
        document.getElementById("did-you-mean").style.display = "none";
        document.getElementById("query-explain").innerHTML = "";
        return;
    }

    try {
        const startTime = performance.now();
        const url = `${API_BASE}/search/messages?q=${encodeURIComponent(query)}&limit=50`;
        debugLog(`Calling backend search endpoint: ${url}`, 'info');

        const response = await fetch(url);
        const data = await response.json();
        const elapsed = (performance.now() - startTime).toFixed(0);

        if (data.success) {
            debugLog(`Search results: ${data.count} message matches in ${elapsed}ms`, 'info');

            // Expose to window for Cypress testing (UX-SEARCH-006)
            window.__LAST_SEARCH_RESULTS__ = data.results;
            window.__LAST_SEARCH_DATA__ = data;

            // UX-SEARCH-007: Always show query explanation
            renderQueryExplanation(data);

            // MODERN UX: Show "did you mean" suggestion
            renderDidYouMean(data);

            // UX-NFC-002: HARD STOP - Block rendering if UX is degraded
            if (data.ux_block) {
                debugLog(`🔒 UX FAILURE BLOCKED: ${data.ux_reason}`, 'error');

                // Show UX failure banner
                renderUXBanner(data);
                renderRankingDeltaWidget(data);

                // Clear results and show block message
                document.getElementById('conversationsList').innerHTML = `
                    <div class="blocked-results">
                        ⚠️ Results blocked due to UX failure.<br/>
                        <small>Try a more specific or different query.</small>
                    </div>
                `;
                return;  // 🔒 HARD STOP - no results rendered
            }

            // UX passed - render normally
            renderUXBanner(data);  // Will hide banner if status is "ok"
            renderRankingDeltaWidget(data);
            renderSearchResults(data.results, query);
        } else {
            debugLog(`Search error: ${data.error}`, 'error');
            showError(`Search failed: ${data.error}`);
        }
    } catch (error) {
        debugLog(`Search fetch error: ${error.message}`, 'error');
        showError(`Search failed: ${error.message}`);
    }
}

// Detect programming language from snippet content
function detectLanguage(snippet) {
    const patterns = {
        python: /\b(def|class|import|from|print|if __name__|self\.)\b/,
        javascript: /\b(function|const|let|var|=>|console\.log|require|import)\b/,
        bash: /\b(echo|cd|ls|grep|awk|sed|export|source)\b|^\$\s/m,
        sql: /\b(SELECT|FROM|WHERE|JOIN|INSERT|UPDATE|DELETE|CREATE TABLE)\b/i,
        json: /^\s*[\{\[]/
    };

    for (const [lang, pattern] of Object.entries(patterns)) {
        if (pattern.test(snippet)) {
            return lang;
        }
    }
    return 'markup'; // default
}

// Render enhanced snippet with syntax highlighting
function renderSnippet(snippet, snippetType) {
    const isCode = snippetType === 'code';
    const containerClass = isCode ? 'snippet-code' : 'snippet-prose';

    if (isCode) {
        const language = detectLanguage(snippet);
        const languageBadge = `<span class="language-badge">${language}</span>`;
        const copyButton = `<button class="copy-button" onclick="copySnippet(this, event)">📋 Copy</button>`;

        // Apply syntax highlighting with Prism
        let highlightedCode = snippet;
        try {
            if (window.Prism && Prism.languages[language]) {
                // Temporarily remove <mark> tags, highlight, then restore them
                const marks = [];
                highlightedCode = snippet.replace(/<mark>(.*?)<\/mark>/g, (match, content) => {
                    marks.push(content);
                    return `__MARK_${marks.length - 1}__`;
                });

                highlightedCode = Prism.highlight(highlightedCode, Prism.languages[language], language);

                // Restore marks
                marks.forEach((content, i) => {
                    highlightedCode = highlightedCode.replace(`__MARK_${i}__`, `<mark>${content}</mark>`);
                });
            }
        } catch (e) {
            console.warn('Syntax highlighting failed:', e);
        }

        return `<div class="${containerClass}">${languageBadge}${copyButton}<pre><code class="language-${language}">${highlightedCode}</code></pre></div>`;
    } else {
        return `<div class="${containerClass}">${snippet}</div>`;
    }
}

// Copy snippet to clipboard
function copySnippet(button, event) {
    event.stopPropagation();
    const codeBlock = button.parentElement.querySelector('code');
    const text = codeBlock ? codeBlock.textContent : '';

    navigator.clipboard.writeText(text).then(() => {
        button.textContent = '✅ Copied!';
        button.classList.add('copied');
        setTimeout(() => {
            button.textContent = '📋 Copy';
            button.classList.remove('copied');
        }, 2000);
    }).catch(err => {
        console.error('Copy failed:', err);
    });
}

// Render message-level search results (grouped by conversation) - ELITE UX
function renderSearchResults(messages, query) {
    const container = document.getElementById('conversationsList');

    if (!container) {
        debugLog('Search container not mounted yet', 'warn');
        return;
    }

    if (messages.length === 0) {
        container.innerHTML = '<div class="no-results">No messages found matching your search</div>';
        return;
    }

    // Group messages by conversation and calculate aggregate metrics
    const grouped = {};
    messages.forEach(msg => {
        if (!grouped[msg.conversation_id]) {
            grouped[msg.conversation_id] = {
                name: msg.conversation_name,
                messages: [],
                maxRank: 0,
                totalRank: 0,
                totalMessages: msg.total_messages || 0,
                lastActivity: msg.last_activity
            };
        }
        grouped[msg.conversation_id].messages.push(msg);
        grouped[msg.conversation_id].maxRank = Math.max(grouped[msg.conversation_id].maxRank, msg.rank);
        grouped[msg.conversation_id].totalRank += msg.rank;
    });

    // Sort conversations by relevance (max rank, then total rank, then match count)
    const sortedConversations = Object.entries(grouped).sort((a, b) => {
        const [, dataA] = a;
        const [, dataB] = b;
        if (dataB.maxRank !== dataA.maxRank) return dataB.maxRank - dataA.maxRank;
        if (dataB.totalRank !== dataA.totalRank) return dataB.totalRank - dataA.totalRank;
        return dataB.messages.length - dataA.messages.length;
    });

    // Simplified: Only show relevance for truly exceptional matches
    // Most apps don't show relevance at all - ordering is the signal
    function getRelevanceLabel(rank, isTopResult, messageCount) {
        // Only show label if it's genuinely exceptional
        if (isTopResult && rank > 0.15) return '🏆 Top match';
        // Otherwise, let position speak for itself
        return null;
    }

    // Highlight search terms in snippet (GitHub/Slack style)
    function highlightSearchTerms(snippet, searchQuery) {
        if (!searchQuery || !snippet) return snippet;

        // Split query into words and highlight each
        const terms = searchQuery.toLowerCase().split(/\s+/).filter(t => t.length > 2);
        let highlighted = snippet;

        terms.forEach(term => {
            const regex = new RegExp(`(${escapeRegex(term)})`, 'gi');
            highlighted = highlighted.replace(regex, '<mark>$1</mark>');
        });

        return highlighted;
    }

    function escapeRegex(str) {
        return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    // Format message with inline metadata (GitHub/Slack style)
    function formatMessage(msg, searchQuery) {
        const roleIcon = msg.role === 'user' ? '👤' : msg.role === 'assistant' ? '🤖' : '💬';
        const roleLabel = msg.role === 'user' ? 'User' : msg.role === 'assistant' ? 'Assistant' : 'System';
        const snippetTypeClass = msg.snippet_type === 'code' ? 'code-snippet' : 'prose-snippet';
        const timestamp = formatTimestamp(msg.timestamp);

        // Backend already provides highlighted snippets with <mark> tags
        // Use enhanced snippet rendering with syntax highlighting
        const renderedSnippet = renderSnippet(msg.snippet, msg.snippet_type);

        // ChatGPT FIX 5: Display match metadata (UX transparency)
        const matchType = msg.match_type || 'exact';
        const confidence = msg.snippet_confidence || 'high';
        const note = msg.snippet_note;

        let confidenceBadge = '';
        if (confidence === 'medium') {
            confidenceBadge = '<span class="confidence-badge medium" title="Fuzzy match">~</span>';
        } else if (confidence === 'low') {
            confidenceBadge = '<span class="confidence-badge low" title="Context excerpt">?</span>';
        }

        let noteHtml = '';
        if (note) {
            noteHtml = `<div class="snippet-note">ℹ️ ${escapeHtml(note)}</div>`;
        }

        return `
            <div class="message-result ${snippetTypeClass}">
                <div class="message-header">
                    <span class="role-icon">${roleIcon}</span>
                    <span class="role-label">${roleLabel}</span>
                    ${confidenceBadge}
                    <span class="timestamp" title="${new Date(msg.timestamp).toLocaleString()}">${timestamp}</span>
                </div>
                ${noteHtml}
                <div class="message-snippet">${renderedSnippet}</div>
            </div>
        `;
    }

    // Simplified: Show only relative time (like Slack, GitHub)
    // Full timestamp on hover via title attribute
    function formatTimestamp(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        let relative = '';
        if (diffMins < 1) relative = 'just now';
        else if (diffMins < 60) relative = `${diffMins}m ago`;
        else if (diffHours < 24) relative = `${diffHours}h ago`;
        else if (diffDays < 7) relative = `${diffDays}d ago`;
        else if (diffDays < 30) relative = `${Math.floor(diffDays / 7)}w ago`;
        else relative = date.toLocaleDateString();

        return `<span class="timestamp" title="${date.toLocaleString()}">${relative}</span>`;
    }

    container.innerHTML = sortedConversations.map(([convId, data], convIdx) => {
        const totalMatches = data.messages.length;
        const visibleCount = 3; // Show top 3 by default
        const hasMore = totalMatches > visibleCount;
        const isTopConversation = convIdx === 0;

        return `
            <div class="search-result-group ${isTopConversation ? 'top-conversation' : ''}" data-conv-id="${convId}">
                <div class="conversation-header" onclick="openConversation('${convId}', '${escapeHtml(data.name).replace(/'/g, "\\'")}')">
                    <div class="header-left">
                        <h3>${escapeHtml(data.name)}</h3>
                    </div>
                    <div class="header-right">
                        <span class="match-count">${totalMatches} ${totalMatches === 1 ? 'match' : 'matches'}</span>
                    </div>
                </div>
                ${data.messages.slice(0, visibleCount).map((msg, idx) => {
                    const isTopResult = idx === 0;
                    const relevanceLabel = getRelevanceLabel(msg.rank, isTopResult, totalMatches);
                    return `
                        <div class="message-match ${isTopResult ? 'top-result' : ''}"
                             data-conv-id="${convId}"
                             data-msg-id="${msg.message_id}"
                             onclick="openConversation('${convId}', '${escapeHtml(data.name).replace(/'/g, "\\'")}')">
                            ${relevanceLabel ? `<div class="relevance-badge">${relevanceLabel}</div>` : ''}
                            ${formatMessage(msg, query)}
                        </div>
                    `;
                }).join('')}
                ${hasMore ? `
                    <div class="show-more" onclick="expandResults('${convId}', event)">
                        <span class="expand-icon">▼</span> ${totalMatches - visibleCount} more
                    </div>
                ` : ''}
                <div class="hidden-matches" id="hidden-${convId}">
                    ${data.messages.slice(visibleCount).map(msg => `
                        <div class="message-match"
                             data-conv-id="${convId}"
                             data-msg-id="${msg.message_id}"
                             onclick="openConversation('${convId}', '${escapeHtml(data.name).replace(/'/g, "\\'")}')">
                            ${formatMessage(msg, query)}
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }).join('');

    // Reset keyboard selection
    window.searchSelectedIndex = -1;
}

// Expand hidden search results
function expandResults(convId, event) {
    event.stopPropagation();
    const hiddenDiv = document.getElementById(`hidden-${convId}`);
    const showMoreBtn = event.target;

    if (hiddenDiv) {
        hiddenDiv.style.display = 'block';
        showMoreBtn.style.display = 'none';
    }
}

// Open conversation modal
async function openConversation(conversationId, name) {
    const modal = document.getElementById('conversationModal');
    const modalTitle = document.getElementById('modalTitle');
    const modalBody = document.getElementById('modalBody');
    
    modalTitle.textContent = name;
    modalBody.innerHTML = '<div class="loading">Loading messages...</div>';
    modal.classList.add('active');
    
    try {
        const response = await fetch(`${API_BASE}/messages/${conversationId}?limit=1000`);
        const data = await response.json();
        
        if (data.success) {
            displayMessages(data.messages);
        } else {
            modalBody.innerHTML = `<div class="error">Failed to load messages: ${data.error}</div>`;
        }
    } catch (error) {
        console.error('Error loading messages:', error);
        modalBody.innerHTML = `<div class="error">Could not load messages: ${error.message}</div>`;
    }
}

// Display messages
function displayMessages(messages) {
    const modalBody = document.getElementById('modalBody');
    
    if (messages.length === 0) {
        modalBody.innerHTML = '<div class="loading">No messages found.</div>';
        return;
    }
    
    modalBody.innerHTML = messages.map(msg => {
        const content = typeof msg.content === 'string' 
            ? msg.content 
            : JSON.stringify(msg.content, null, 2);
        
        return `
            <div class="message ${msg.role}">
                <div class="message-role">${msg.role}</div>
                <div class="message-content">${escapeHtml(content)}</div>
            </div>
        `;
    }).join('');
}

// Close modal
function closeModal() {
    document.getElementById('conversationModal').classList.remove('active');
}

// Utility functions (escapeHtml already defined at top)
function formatDate(dateString) {
    if (!dateString) return 'Unknown';
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

function showError(message) {
    document.getElementById('conversationsList').innerHTML = `
        <div class="error">${escapeHtml(message)}</div>
    `;
}

// Event listeners
// Debounce timer to prevent excessive API calls on every keystroke
let searchDebounceTimer = null;

document.getElementById('searchInput').addEventListener('input', (e) => {
    // Clear previous timer
    if (searchDebounceTimer) {
        clearTimeout(searchDebounceTimer);
    }
    
    // Wait 300ms after user stops typing before searching
    searchDebounceTimer = setTimeout(() => {
        searchConversations(e.target.value);
    }, 300);
});


// Keyboard navigation for search results - ELITE UX
window.searchSelectedIndex = -1;

document.getElementById('searchInput').addEventListener('keydown', (e) => {
    const results = document.querySelectorAll('.message-match:not(.hidden-matches .message-match), .conversation-card');

    if (results.length === 0 && e.key !== 'Escape') return;

    if (e.key === 'ArrowDown') {
        e.preventDefault();
        window.searchSelectedIndex = Math.min(window.searchSelectedIndex + 1, results.length - 1);
        updateSearchSelection(results);
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        window.searchSelectedIndex = Math.max(window.searchSelectedIndex - 1, -1);
        if (window.searchSelectedIndex === -1) {
            // Return focus to search input
            results.forEach(el => el.classList.remove('keyboard-selected'));
        } else {
            updateSearchSelection(results);
        }
    } else if (e.key === 'Enter') {
        e.preventDefault();
        if (window.searchSelectedIndex >= 0 && results[window.searchSelectedIndex]) {
            results[window.searchSelectedIndex].click();
        }
    } else if (e.key === 'Escape') {
        e.preventDefault();
        e.target.value = '';
        searchConversations('');
        window.searchSelectedIndex = -1;
        results.forEach(el => el.classList.remove('keyboard-selected'));
    } else if (e.key === 'Tab') {
        // Tab cycles through visible results
        e.preventDefault();
        if (e.shiftKey) {
            window.searchSelectedIndex = Math.max(window.searchSelectedIndex - 1, 0);
        } else {
            window.searchSelectedIndex = Math.min(window.searchSelectedIndex + 1, results.length - 1);
        }
        updateSearchSelection(results);
    }
});

function updateSearchSelection(results) {
    results.forEach((el, idx) => {
        if (idx === window.searchSelectedIndex) {
            el.classList.add('keyboard-selected');
            el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });

            // Show preview in debug console
            const convId = el.dataset.convId;
            const msgId = el.dataset.msgId;
            debugLog(`Selected: ${el.querySelector('.snippet-text')?.textContent?.substring(0, 50) || 'result'}...`, 'info');
        } else {
            el.classList.remove('keyboard-selected');
        }
    });
}

// Close modal on background click
document.getElementById('conversationModal').addEventListener('click', (e) => {
    if (e.target.id === 'conversationModal') {
        closeModal();
    }
});

// Initialize
loadStats();
loadConversations();

