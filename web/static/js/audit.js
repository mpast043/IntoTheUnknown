// IntoTheUnknown - Audit Dashboard JavaScript

document.addEventListener('DOMContentLoaded', function() {
    const sessionFilter = document.getElementById('session-filter');
    const eventFilter = document.getElementById('event-filter');
    const memoryCategoryFilter = document.getElementById('memory-category-filter');
    const refreshBtn = document.getElementById('refresh-btn');
    const prevPageBtn = document.getElementById('prev-page');
    const nextPageBtn = document.getElementById('next-page');
    const pageInfo = document.getElementById('page-info');

    // Stats elements
    const totalEvents = document.getElementById('total-events');
    const totalSessions = document.getElementById('total-sessions');
    const controllerSteps = document.getElementById('controller-steps');
    const voidCommands = document.getElementById('void-commands');

    // Content elements
    const auditLogBody = document.getElementById('audit-log-body');
    const memoryItems = document.getElementById('memory-items');
    const sessionsBody = document.getElementById('sessions-body');

    // Memory reconciliation elements
    const selectAllCheckbox = document.getElementById('select-all-memory');
    const deleteSelectedBtn = document.getElementById('delete-selected-btn');
    const clearCategoryBtn = document.getElementById('clear-category-btn');
    const selectedCount = document.getElementById('selected-count');

    let currentPage = 0;
    const pageSize = 20;
    let selectedMemoryIds = new Set();

    // Initial load
    loadSessions();
    loadAuditLog();
    loadStats();
    loadMemoryItems();

    // Event listeners
    refreshBtn.addEventListener('click', refreshAll);
    sessionFilter.addEventListener('change', refreshAll);
    eventFilter.addEventListener('change', () => { currentPage = 0; loadAuditLog(); });
    memoryCategoryFilter.addEventListener('change', () => {
        selectedMemoryIds.clear();
        updateSelectedCount();
        loadMemoryItems();
    });

    prevPageBtn.addEventListener('click', () => {
        if (currentPage > 0) {
            currentPage--;
            loadAuditLog();
        }
    });

    nextPageBtn.addEventListener('click', () => {
        currentPage++;
        loadAuditLog();
    });

    // Memory reconciliation listeners
    selectAllCheckbox.addEventListener('change', function() {
        const checkboxes = memoryItems.querySelectorAll('.memory-checkbox');
        checkboxes.forEach(cb => {
            cb.checked = this.checked;
            if (this.checked) {
                selectedMemoryIds.add(cb.dataset.id);
            } else {
                selectedMemoryIds.delete(cb.dataset.id);
            }
        });
        updateSelectedCount();
    });

    deleteSelectedBtn.addEventListener('click', async function() {
        if (selectedMemoryIds.size === 0) return;

        if (!confirm(`Delete ${selectedMemoryIds.size} selected memory items? This action is logged but cannot be undone.`)) {
            return;
        }

        try {
            const response = await fetch('/api/memory/bulk-delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ item_ids: Array.from(selectedMemoryIds) })
            });

            const data = await response.json();

            if (data.success) {
                alert(`Successfully deleted ${data.deleted_count} items.`);
                selectedMemoryIds.clear();
                selectAllCheckbox.checked = false;
                updateSelectedCount();
                loadMemoryItems();
                loadAuditLog();
                loadStats();
            } else {
                alert(`Error: ${data.error}`);
            }
        } catch (error) {
            alert(`Error deleting items: ${error.message}`);
        }
    });

    clearCategoryBtn.addEventListener('click', async function() {
        const category = memoryCategoryFilter.value;
        if (!category) {
            alert('Please select a category to clear.');
            return;
        }

        const sessionId = sessionFilter.value;
        const scope = sessionId ? 'this session' : 'ALL sessions';

        if (!confirm(`Clear ALL ${category} memory items from ${scope}? This action is logged but cannot be undone.`)) {
            return;
        }

        try {
            const body = { category };
            if (sessionId) body.session_id = sessionId;

            const response = await fetch('/api/memory/clear-category', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            const data = await response.json();

            if (data.success) {
                alert(`Successfully cleared ${data.deleted_count} ${category} items.`);
                selectedMemoryIds.clear();
                selectAllCheckbox.checked = false;
                updateSelectedCount();
                loadMemoryItems();
                loadAuditLog();
                loadStats();
            } else {
                alert(`Error: ${data.error}`);
            }
        } catch (error) {
            alert(`Error clearing category: ${error.message}`);
        }
    });

    function updateSelectedCount() {
        selectedCount.textContent = `${selectedMemoryIds.size} selected`;
        deleteSelectedBtn.disabled = selectedMemoryIds.size === 0;
    }

    function refreshAll() {
        currentPage = 0;
        selectedMemoryIds.clear();
        selectAllCheckbox.checked = false;
        updateSelectedCount();
        loadAuditLog();
        loadStats();
        loadMemoryItems();
        loadSessions();
    }

    async function loadSessions() {
        try {
            const response = await fetch('/api/audit/sessions');
            const sessions = await response.json();

            // Update filter dropdown
            const currentValue = sessionFilter.value;
            sessionFilter.innerHTML = '<option value="">All Sessions</option>';
            sessions.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.id;
                opt.textContent = `${s.id.substring(0, 8)}... (Tier ${s.tier})`;
                sessionFilter.appendChild(opt);
            });
            sessionFilter.value = currentValue;

            // Update sessions table
            sessionsBody.innerHTML = '';
            totalSessions.textContent = sessions.length;

            sessions.forEach(s => {
                const tr = document.createElement('tr');
                const status = s.terminated ?
                    `<span style="color: var(--accent-danger)">Terminated</span>` :
                    (s.ended_at ? '<span style="color: var(--text-muted)">Ended</span>' :
                    '<span style="color: var(--accent-success)">Active</span>');

                tr.innerHTML = `
                    <td>${s.id.substring(0, 8)}...</td>
                    <td>${formatTime(s.started_at)}</td>
                    <td>${s.ended_at ? formatTime(s.ended_at) : '-'}</td>
                    <td><span class="tier-badge tier-${s.tier}">${s.tier}</span></td>
                    <td>${status}</td>
                `;
                sessionsBody.appendChild(tr);
            });
        } catch (error) {
            console.error('Failed to load sessions:', error);
        }
    }

    async function loadAuditLog() {
        const sessionId = sessionFilter.value;
        const eventType = eventFilter.value;

        try {
            let url = `/api/audit/logs?limit=${pageSize}&offset=${currentPage * pageSize}`;
            if (sessionId) url += `&session_id=${sessionId}`;
            if (eventType) url += `&event_type=${eventType}`;

            const response = await fetch(url);
            const logs = await response.json();

            auditLogBody.innerHTML = '';

            if (logs.length === 0) {
                auditLogBody.innerHTML = `<tr><td colspan="4" class="loading">No events found</td></tr>`;
                prevPageBtn.disabled = true;
                nextPageBtn.disabled = true;
                return;
            }

            logs.forEach(log => {
                const tr = document.createElement('tr');
                const details = formatDetails(log.details);

                tr.innerHTML = `
                    <td>${formatTime(log.timestamp)}</td>
                    <td><span class="event-type event-type-${log.event_type}">${log.event_type}</span></td>
                    <td>${log.session_id ? log.session_id.substring(0, 8) + '...' : '-'}</td>
                    <td title="${escapeHtml(JSON.stringify(log.details))}">${escapeHtml(details)}</td>
                `;
                auditLogBody.appendChild(tr);
            });

            // Update pagination
            prevPageBtn.disabled = currentPage === 0;
            nextPageBtn.disabled = logs.length < pageSize;
            pageInfo.textContent = `Page ${currentPage + 1}`;

        } catch (error) {
            console.error('Failed to load audit log:', error);
            auditLogBody.innerHTML = `<tr><td colspan="4" class="loading">Error loading logs</td></tr>`;
        }
    }

    async function loadStats() {
        const sessionId = sessionFilter.value;

        try {
            let url = '/api/audit/stats';
            if (sessionId) url += `?session_id=${sessionId}`;

            const response = await fetch(url);
            const stats = await response.json();

            totalEvents.textContent = stats.total_events || 0;
            controllerSteps.textContent = stats.by_event_type?.controller_step || 0;
            voidCommands.textContent = stats.by_event_type?.void_command || 0;

        } catch (error) {
            console.error('Failed to load stats:', error);
        }
    }

    async function loadMemoryItems() {
        const sessionId = sessionFilter.value;
        const category = memoryCategoryFilter.value;

        try {
            let url = '/api/audit/memory?limit=50';
            if (sessionId) url += `&session_id=${sessionId}`;
            if (category) url += `&category=${category}`;

            const response = await fetch(url);
            const items = await response.json();

            memoryItems.innerHTML = '';

            if (items.length === 0) {
                memoryItems.innerHTML = '<p class="no-items">No memory items found</p>';
                return;
            }

            items.forEach(item => {
                const div = document.createElement('div');
                div.className = `memory-item ${item.category}`;
                div.dataset.id = item.id;

                const isSelected = selectedMemoryIds.has(item.id);
                const obsPreview = JSON.stringify(item.obs, null, 2).substring(0, 150);
                const intePreview = item.inte?.target || '';

                div.innerHTML = `
                    <div class="memory-item-header">
                        <label class="memory-select">
                            <input type="checkbox" class="memory-checkbox" data-id="${item.id}" ${isSelected ? 'checked' : ''}>
                        </label>
                        <span class="memory-category">${item.category}</span>
                        <span class="memory-time">${formatTime(item.created_at)}</span>
                        <button class="btn-icon delete-single" data-id="${item.id}" title="Delete this item">×</button>
                    </div>
                    <div class="memory-item-content">
                        ${intePreview ? `<div class="memory-target">${escapeHtml(intePreview.substring(0, 100))}</div>` : ''}
                        <div class="memory-obs">${escapeHtml(obsPreview)}...</div>
                    </div>
                `;

                // Add event listeners
                const checkbox = div.querySelector('.memory-checkbox');
                checkbox.addEventListener('change', function() {
                    if (this.checked) {
                        selectedMemoryIds.add(item.id);
                    } else {
                        selectedMemoryIds.delete(item.id);
                    }
                    updateSelectedCount();
                });

                const deleteBtn = div.querySelector('.delete-single');
                deleteBtn.addEventListener('click', async function(e) {
                    e.stopPropagation();
                    if (!confirm('Delete this memory item?')) return;

                    try {
                        const response = await fetch(`/api/memory/${item.id}`, {
                            method: 'DELETE'
                        });
                        const data = await response.json();

                        if (data.success) {
                            selectedMemoryIds.delete(item.id);
                            updateSelectedCount();
                            loadMemoryItems();
                            loadAuditLog();
                        } else {
                            alert(`Error: ${data.error}`);
                        }
                    } catch (error) {
                        alert(`Error: ${error.message}`);
                    }
                });

                memoryItems.appendChild(div);
            });

        } catch (error) {
            console.error('Failed to load memory items:', error);
            memoryItems.innerHTML = '<p class="loading">Error loading memory items</p>';
        }
    }

    function formatTime(isoString) {
        if (!isoString) return '-';
        const date = new Date(isoString);
        return date.toLocaleString();
    }

    function formatDetails(details) {
        if (!details) return '-';

        // Show key info based on what's available
        const parts = [];

        if (details.tier !== undefined) parts.push(`tier=${details.tier}`);
        if (details.old_tier !== undefined && details.new_tier !== undefined) {
            parts.push(`${details.old_tier} → ${details.new_tier}`);
        }
        if (details.user_input) parts.push(`input="${details.user_input.substring(0, 30)}..."`);
        if (details.reason) parts.push(`reason="${details.reason}"`);
        if (details.filename) parts.push(`file="${details.filename}"`);
        if (details.deleted_count !== undefined) parts.push(`deleted=${details.deleted_count}`);
        if (details.category) parts.push(`category=${details.category}`);
        if (details.decision?.stopgates?.length) parts.push(`stopgates=${details.decision.stopgates.length}`);

        return parts.length > 0 ? parts.join(', ') : JSON.stringify(details).substring(0, 50) + '...';
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
});
