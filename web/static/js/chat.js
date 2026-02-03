// IntoTheUnknown - Chat Interface JavaScript

document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chat-form');
    const messageInput = document.getElementById('message-input');
    const chatMessages = document.getElementById('chat-messages');
    const sendBtn = document.getElementById('send-btn');
    const fileInput = document.getElementById('file-input');
    const documentList = document.getElementById('document-list');
    const decisionPanel = document.getElementById('decision-panel');
    const decisionContent = document.getElementById('decision-content');

    // Memory count elements
    const workingCount = document.getElementById('working-count');
    const quarantineCount = document.getElementById('quarantine-count');
    const classicalCount = document.getElementById('classical-count');
    const currentTier = document.getElementById('current-tier');

    let isLoading = false;

    // Load initial state
    loadState();
    loadDocuments();

    // Chat form submission
    chatForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        const message = messageInput.value.trim();
        if (!message || isLoading) return;

        // Clear welcome message if present
        const welcomeMsg = chatMessages.querySelector('.welcome-message');
        if (welcomeMsg) welcomeMsg.remove();

        // Add user message
        appendMessage('user', message);
        messageInput.value = '';

        // Show loading state
        setLoading(true);

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message })
            });

            const data = await response.json();

            if (data.error) {
                appendMessage('assistant', `Error: ${data.error}`, true);
            } else {
                appendMessage('assistant', data.response);
                updateDecision(data.decision);
                updateMemoryCounts(data.memory_counts);
                updateTier(data.tier);
            }
        } catch (error) {
            appendMessage('assistant', `Error: ${error.message}`, true);
        } finally {
            setLoading(false);
        }
    });

    // Ctrl+Enter to send
    messageInput.addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.key === 'Enter') {
            chatForm.dispatchEvent(new Event('submit'));
        }
    });

    // File upload
    fileInput.addEventListener('change', async function(e) {
        const file = e.target.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.error) {
                alert(`Upload error: ${data.error}`);
            } else {
                loadDocuments();
            }
        } catch (error) {
            alert(`Upload error: ${error.message}`);
        }

        // Reset input
        fileInput.value = '';
    });

    function appendMessage(role, content, isError = false) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role}`;
        if (isError) msgDiv.classList.add('error');

        const time = new Date().toLocaleTimeString();

        msgDiv.innerHTML = `
            <div class="message-header">
                <span class="message-role">${role === 'user' ? 'You' : 'Agent'}</span>
                <span class="message-time">${time}</span>
            </div>
            <div class="message-content">${escapeHtml(content)}</div>
        `;

        chatMessages.appendChild(msgDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function updateDecision(decision) {
        if (!decision || Object.keys(decision).length === 0) {
            decisionPanel.style.display = 'none';
            return;
        }

        decisionPanel.style.display = 'block';
        decisionContent.textContent = JSON.stringify(decision, null, 2);
    }

    function updateMemoryCounts(counts) {
        if (!counts) return;
        workingCount.textContent = counts.working || 0;
        quarantineCount.textContent = counts.quarantine || 0;
        classicalCount.textContent = counts.classical || 0;
    }

    function updateTier(tier) {
        if (!tier) return;
        currentTier.textContent = tier;
        currentTier.className = `value tier-badge tier-${tier}`;
    }

    function setLoading(loading) {
        isLoading = loading;
        sendBtn.disabled = loading;
        sendBtn.textContent = loading ? 'Sending...' : 'Send';
    }

    async function loadState() {
        try {
            const response = await fetch('/api/state');
            const data = await response.json();
            updateMemoryCounts(data.memory_counts);
            updateTier(data.tier);
        } catch (error) {
            console.error('Failed to load state:', error);
        }
    }

    async function loadDocuments() {
        try {
            const response = await fetch('/documents');
            const docs = await response.json();

            documentList.innerHTML = '';

            if (docs.length === 0) {
                documentList.innerHTML = '<p class="upload-hint">No documents uploaded</p>';
                return;
            }

            docs.forEach(doc => {
                const docDiv = document.createElement('div');
                docDiv.className = 'document-item';
                docDiv.innerHTML = `
                    <span class="doc-name" title="${escapeHtml(doc.filename)}">${escapeHtml(doc.filename)}</span>
                    <span class="doc-status">${doc.processed ? '✓' : '○'}</span>
                `;
                documentList.appendChild(docDiv);
            });
        } catch (error) {
            console.error('Failed to load documents:', error);
        }
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
});
