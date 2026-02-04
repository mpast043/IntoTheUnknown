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

    // Tier selector elements
    const tierButtons = document.querySelectorAll('.tier-btn');
    const tierDescription = document.getElementById('tier-description');

    // Agent selector elements
    const agentSelect = document.getElementById('agent-select');
    const newAgentBtn = document.getElementById('new-agent-btn');
    const newAgentForm = document.getElementById('new-agent-form');
    const newAgentId = document.getElementById('new-agent-id');
    const agentIsolated = document.getElementById('agent-isolated');
    const createAgentBtn = document.getElementById('create-agent-btn');
    const cancelAgentBtn = document.getElementById('cancel-agent-btn');
    const memoryPoolEl = document.getElementById('memory-pool');

    let currentAgentId = agentSelect ? agentSelect.value : 'default';

    // Load initial state
    loadState();
    loadDocuments();
    loadAgents();

    // Tier button clicks
    tierButtons.forEach(btn => {
        btn.addEventListener('click', async function() {
            const newTier = parseInt(this.dataset.tier);
            await setTier(newTier);
        });
    });

    // Agent selector events
    if (agentSelect) {
        agentSelect.addEventListener('change', async function() {
            await switchAgent(this.value);
        });
    }

    if (newAgentBtn) {
        newAgentBtn.addEventListener('click', function() {
            newAgentForm.style.display = newAgentForm.style.display === 'none' ? 'block' : 'none';
        });
    }

    if (cancelAgentBtn) {
        cancelAgentBtn.addEventListener('click', function() {
            newAgentForm.style.display = 'none';
            newAgentId.value = '';
            agentIsolated.checked = false;
        });
    }

    if (createAgentBtn) {
        createAgentBtn.addEventListener('click', async function() {
            const id = newAgentId.value.trim();
            if (!id) {
                alert('Please enter an agent ID');
                return;
            }
            await createAgent(id, agentIsolated.checked);
        });
    }

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
                body: JSON.stringify({ message, agent_id: currentAgentId })
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

        // Update tier buttons
        tierButtons.forEach(btn => {
            btn.classList.toggle('active', parseInt(btn.dataset.tier) === tier);
        });

        // Update header badge
        const headerBadge = document.querySelector('.header .tier-badge');
        if (headerBadge) {
            headerBadge.textContent = `Tier ${tier}`;
            headerBadge.className = `tier-badge tier-${tier}`;
        }

        // Update tier description
        if (tierDescription) {
            const descriptions = {
                1: 'Non-committing: Memory cannot promote to classical.',
                2: 'Verified commit: Can promote to classical with accuracy token.',
                3: 'Persistent: High-confidence verified state.'
            };
            tierDescription.textContent = descriptions[tier] || '';
        }
    }

    async function setTier(newTier) {
        try {
            const response = await fetch('/api/tier', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tier: newTier })
            });

            const data = await response.json();

            if (data.error) {
                alert(`Error changing tier: ${data.error}`);
            } else {
                updateTier(data.new_tier);
                // Add system message about tier change
                const welcomeMsg = chatMessages.querySelector('.welcome-message');
                if (welcomeMsg) welcomeMsg.remove();
                appendMessage('assistant', `Tier changed to ${data.new_tier}. ${data.message}`);
            }
        } catch (error) {
            alert(`Error changing tier: ${error.message}`);
        }
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

    async function loadAgents() {
        try {
            const response = await fetch('/api/agents');
            const agents = await response.json();

            if (agentSelect) {
                const currentVal = agentSelect.value;
                agentSelect.innerHTML = '';
                agents.forEach(agent => {
                    const opt = document.createElement('option');
                    opt.value = agent.id;
                    opt.textContent = agent.id + (agent.memory_pool.startsWith('isolated:') ? ' (isolated)' : '');
                    agentSelect.appendChild(opt);
                });
                agentSelect.value = currentVal || agents[0]?.id || 'default';
                currentAgentId = agentSelect.value;
            }
        } catch (error) {
            console.error('Failed to load agents:', error);
        }
    }

    async function switchAgent(agentId) {
        try {
            const response = await fetch(`/api/agents/${agentId}/switch`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            const data = await response.json();

            if (data.error) {
                alert(`Error switching agent: ${data.error}`);
            } else {
                currentAgentId = data.agent_id;
                if (memoryPoolEl) {
                    memoryPoolEl.textContent = data.memory_pool;
                }
                loadState();
            }
        } catch (error) {
            alert(`Error switching agent: ${error.message}`);
        }
    }

    async function createAgent(agentId, isolated) {
        try {
            const response = await fetch('/api/agents', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: agentId, isolated })
            });

            const data = await response.json();

            if (data.error) {
                alert(`Error creating agent: ${data.error}`);
            } else {
                newAgentForm.style.display = 'none';
                newAgentId.value = '';
                agentIsolated.checked = false;
                await loadAgents();
                await switchAgent(data.agent_id);
            }
        } catch (error) {
            alert(`Error creating agent: ${error.message}`);
        }
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
});
