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

    // Memory insert elements
    const insertMemoryBtn = document.getElementById('insert-memory-btn');
    const memoryContent = document.getElementById('memory-content');
    const memoryTags = document.getElementById('memory-tags');
    const memoryCategory = document.getElementById('memory-category');
    const memoryPinned = document.getElementById('memory-pinned');
    const historyList = document.getElementById('history-list');
    const tagSelect = document.getElementById('tag-select');
    const totalMemoryLabel = document.getElementById('total-memory-label');

    // Load initial state
    loadState();
    loadDocuments();
    loadAgents();
    loadMemoryHistory();
    loadTags();

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

    // Memory insert
    if (insertMemoryBtn) {
        insertMemoryBtn.addEventListener('click', async function() {
            const content = memoryContent.value.trim();
            if (!content) { alert('Enter memory content'); return; }
            const tags = memoryTags.value.trim();
            const category = memoryCategory.value;
            const pinned = memoryPinned.checked;
            try {
                const response = await fetch('/api/memory/insert', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content, tags, category, pinned })
                });
                const data = await response.json();
                if (data.error) {
                    alert(`Error: ${data.error}`);
                } else {
                    memoryContent.value = '';
                    memoryTags.value = '';
                    memoryPinned.checked = false;
                    loadMemoryHistory();
                    loadTags();
                    loadState();
                }
            } catch (error) {
                alert(`Error: ${error.message}`);
            }
        });
    }

    // Tag filter
    if (tagSelect) {
        tagSelect.addEventListener('change', function() {
            loadMemoryHistory(this.value);
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
                loadMemoryHistory(tagSelect?.value);
                loadTags();
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
            if (data.total_memory_counts && totalMemoryLabel) {
                const t = data.total_memory_counts;
                const total = (t.working || 0) + (t.quarantine || 0) + (t.classical || 0);
                totalMemoryLabel.textContent = `(${total} total)`;
            }
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

    async function loadMemoryHistory(tagFilter) {
        if (!historyList) return;
        try {
            let url = '/api/memory/history?limit=50';
            if (tagFilter) url = `/api/audit/memory?all_sessions=true&tags=${encodeURIComponent(tagFilter)}&limit=50`;
            const response = await fetch(url);
            const items = await response.json();

            historyList.innerHTML = '';
            if (items.length === 0) {
                historyList.innerHTML = '<p style="font-size:0.75rem;color:var(--text-muted);padding:0.25rem;">No memory items yet</p>';
                return;
            }

            items.forEach(item => {
                const el = document.createElement('div');
                el.style.cssText = 'padding:0.4rem;margin-bottom:0.35rem;background:var(--bg-tertiary);border-radius:0.25rem;font-size:0.75rem;border-left:3px solid ' +
                    (item.category === 'classical' ? 'var(--accent-success)' : item.category === 'quarantine' ? 'var(--accent-warning)' : 'var(--accent-primary)');

                const content = item.inte?.target || item.inte?.action || 'Memory item';
                const tags = (item.tags || []).map(t => `<span style="background:var(--accent-primary);color:#fff;padding:0 4px;border-radius:3px;font-size:0.65rem;margin-right:2px;">${escapeHtml(t)}</span>`).join('');
                const pin = item.pinned ? '<span title="Pinned" style="cursor:pointer;" data-id="' + item.id + '" class="pin-toggle">&#128204;</span> ' : '';
                const src = item.source === 'user' ? '<span style="color:var(--accent-warning);font-size:0.65rem;">[manual]</span> ' : '';

                el.innerHTML = `${pin}${src}<span style="color:var(--text-primary);">${escapeHtml(content.substring(0, 80))}</span>` +
                    (tags ? `<div style="margin-top:2px;">${tags}</div>` : '') +
                    `<div style="color:var(--text-muted);font-size:0.65rem;margin-top:2px;">${item.category} | ${item.created_at ? item.created_at.substring(0, 16) : ''}</div>`;

                historyList.appendChild(el);
            });

            // Pin toggle clicks
            historyList.querySelectorAll('.pin-toggle').forEach(el => {
                el.addEventListener('click', async function() {
                    const id = this.dataset.id;
                    await fetch(`/api/memory/${id}/pin`, { method: 'POST' });
                    loadMemoryHistory(tagSelect?.value);
                });
            });
        } catch (error) {
            console.error('Failed to load memory history:', error);
        }
    }

    async function loadTags() {
        if (!tagSelect) return;
        try {
            const response = await fetch('/api/memory/tags');
            const tags = await response.json();
            const current = tagSelect.value;
            tagSelect.innerHTML = '<option value="">All tags</option>';
            tags.forEach(tag => {
                const opt = document.createElement('option');
                opt.value = tag;
                opt.textContent = tag;
                tagSelect.appendChild(opt);
            });
            tagSelect.value = current;
        } catch (error) {
            console.error('Failed to load tags:', error);
        }
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
});
