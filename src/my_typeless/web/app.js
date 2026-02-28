/* ── My Typeless Settings - Frontend Logic ── */

let currentConfig = {};
let currentHotkey = 'right alt';
let glossaryTerms = [];

// ── Initialization ──

window.addEventListener('pywebviewready', async () => {
    try {
        const [config, version] = await Promise.all([
            pywebview.api.get_config(),
            pywebview.api.get_version(),
        ]);
        currentConfig = config;
        currentHotkey = config.hotkey || 'right alt';
        document.getElementById('versionLabel').textContent = `v${version}`;
        populateForms(config);
    } catch (e) {
        console.error('Init failed:', e);
    }
});

function populateForms(config) {
    // General
    document.getElementById('hotkeyBtn').textContent = config.hotkey;
    document.getElementById('autostartToggle').checked = config.start_with_windows;

    // STT
    document.getElementById('sttUrl').value = config.stt?.base_url || '';
    document.getElementById('sttKey').value = config.stt?.api_key || '';
    document.getElementById('sttModel').value = config.stt?.model || '';

    // LLM
    document.getElementById('llmUrl').value = config.llm?.base_url || '';
    document.getElementById('llmKey').value = config.llm?.api_key || '';
    document.getElementById('llmModel').value = config.llm?.model || '';
    document.getElementById('llmPrompt').value = config.llm?.prompt || '';

    // Glossary
    glossaryTerms = [...(config.glossary || [])];
    renderGlossary();

    // Update status badges
    updateStatusBadge('sttStatusBadge', !!config.stt?.api_key);
    updateStatusBadge('llmStatusBadge', !!config.llm?.api_key);
}

function updateStatusBadge(id, active) {
    const badge = document.getElementById(id);
    if (active) {
        badge.textContent = 'ACTIVE';
        badge.className = 'px-2.5 py-1 bg-primary text-white text-[10px] font-bold rounded tracking-widest';
    } else {
        badge.textContent = 'INACTIVE';
        badge.className = 'px-2.5 py-1 bg-border-gray rounded-full text-[10px] font-bold text-primary tracking-wider';
    }
}

// ── Navigation ──

document.getElementById('navList').addEventListener('click', (e) => {
    const item = e.target.closest('.nav-item');
    if (!item) return;
    switchPage(item.dataset.page);
});

function switchPage(pageName) {
    document.querySelectorAll('.nav-item').forEach(el => {
        el.classList.remove('nav-item-active');
        el.classList.add('text-text-muted');
    });
    const activeNav = document.querySelector(`.nav-item[data-page="${pageName}"]`);
    if (activeNav) {
        activeNav.classList.add('nav-item-active');
        activeNav.classList.remove('text-text-muted');
    }

    document.querySelectorAll('.page').forEach(el => el.classList.remove('active'));
    const page = document.getElementById(`page-${pageName}`);
    if (page) page.classList.add('active');

    if (pageName === 'history') loadHistory();
}

// ── Config Save / Cancel ──

async function saveConfig() {
    const data = collectFormData();
    try {
        const result = await pywebview.api.save_config(data);
        if (result.success) {
            await pywebview.api.close_window();
        } else {
            alert('Save failed: ' + (result.error || 'Unknown error'));
        }
    } catch (e) {
        alert('Save failed: ' + e);
    }
}

function cancelSettings() {
    pywebview.api.close_window();
}

function collectFormData() {
    return {
        hotkey: currentHotkey,
        start_with_windows: document.getElementById('autostartToggle').checked,
        stt: {
            base_url: document.getElementById('sttUrl').value.trim(),
            api_key: document.getElementById('sttKey').value.trim(),
            model: document.getElementById('sttModel').value.trim(),
            language: currentConfig.stt?.language || '',
        },
        llm: {
            base_url: document.getElementById('llmUrl').value.trim(),
            api_key: document.getElementById('llmKey').value.trim(),
            model: document.getElementById('llmModel').value.trim(),
            prompt: document.getElementById('llmPrompt').value.trim(),
        },
        glossary: [...glossaryTerms],
    };
}

// ── Hotkey Capture ──

function startHotkeyCapture() {
    const btn = document.getElementById('hotkeyBtn');
    btn.textContent = 'Press a key...';
    btn.classList.add('listening');
    pywebview.api.start_hotkey_capture();
}

function onHotkeyCaptured(key) {
    const btn = document.getElementById('hotkeyBtn');
    btn.classList.remove('listening');
    if (key) {
        currentHotkey = key;
        btn.textContent = key;
    } else {
        btn.textContent = currentHotkey;
    }
}

// ── Password Visibility Toggle ──

function togglePasswordVisibility(btn) {
    const input = btn.closest('.relative').querySelector('input');
    const icon = btn.querySelector('.material-symbols-outlined');
    if (input.type === 'password') {
        input.type = 'text';
        icon.textContent = 'visibility_off';
        btn.setAttribute('aria-label', 'Hide password');
        btn.setAttribute('title', 'Hide password');
    } else {
        input.type = 'password';
        icon.textContent = 'visibility';
        btn.setAttribute('aria-label', 'Show password');
        btn.setAttribute('title', 'Show password');
    }
}

// ── Test Connection ──

async function testSttConnection() {
    const badge = document.getElementById('sttStatusBadge');
    badge.textContent = 'TESTING...';
    badge.className = 'px-2.5 py-1 bg-gray-300 text-primary text-[10px] font-bold rounded tracking-widest';
    try {
        const result = await pywebview.api.test_stt_connection({
            base_url: document.getElementById('sttUrl').value.trim(),
            api_key: document.getElementById('sttKey').value.trim(),
            model: document.getElementById('sttModel').value.trim(),
        });
        updateStatusBadge('sttStatusBadge', result.success);
        if (!result.success) alert('STT Connection failed: ' + (result.error || 'Unknown'));
    } catch (e) {
        updateStatusBadge('sttStatusBadge', false);
        alert('STT Connection failed: ' + e);
    }
}

async function testLlmConnection() {
    const badge = document.getElementById('llmStatusBadge');
    badge.textContent = 'TESTING...';
    badge.className = 'px-2.5 py-1 bg-gray-300 text-primary text-[10px] font-bold rounded tracking-widest';
    try {
        const result = await pywebview.api.test_llm_connection({
            base_url: document.getElementById('llmUrl').value.trim(),
            api_key: document.getElementById('llmKey').value.trim(),
            model: document.getElementById('llmModel').value.trim(),
        });
        updateStatusBadge('llmStatusBadge', result.success);
        if (!result.success) alert('LLM Connection failed: ' + (result.error || 'Unknown'));
    } catch (e) {
        updateStatusBadge('llmStatusBadge', false);
        alert('LLM Connection failed: ' + e);
    }
}

// ── Glossary ──

function renderGlossary() {
    const list = document.getElementById('glossaryList');
    if (glossaryTerms.length === 0) {
        list.innerHTML = '<p class="text-center text-text-muted text-sm py-8">No terms added yet.</p>';
    } else {
        list.innerHTML = glossaryTerms.map((term, i) => `
            <div class="flex items-center px-4 py-3 border-b border-border-gray group hover:bg-neutral-50 transition-colors" data-index="${i}" onclick="toggleGlossarySelect(this)">
                <input type="checkbox" class="rounded border-border-gray text-primary focus:ring-0 cursor-pointer size-4" onclick="event.stopPropagation(); toggleGlossarySelect(this.parentElement)"/>
                <span class="ml-4 text-sm font-medium text-primary">${escapeHtml(term)}</span>
            </div>
        `).join('');
    }
    document.getElementById('glossaryCount').textContent = `${glossaryTerms.length} term(s)`;
}

function addGlossaryTerm() {
    const input = document.getElementById('glossaryInput');
    const term = input.value.trim();
    if (!term || glossaryTerms.includes(term)) {
        input.value = '';
        return;
    }
    glossaryTerms.push(term);
    input.value = '';
    renderGlossary();
}

function toggleGlossarySelect(el) {
    const checkbox = el.querySelector('input[type="checkbox"]');
    if (checkbox && document.activeElement !== checkbox) {
        checkbox.checked = !checkbox.checked;
    }
    el.classList.toggle('bg-neutral-50', checkbox?.checked);
}

function deleteSelectedTerms() {
    const items = document.querySelectorAll('#glossaryList > div');
    const toRemove = new Set();
    items.forEach(item => {
        const cb = item.querySelector('input[type="checkbox"]');
        if (cb?.checked) toRemove.add(parseInt(item.dataset.index));
    });
    if (toRemove.size === 0) return;
    glossaryTerms = glossaryTerms.filter((_, i) => !toRemove.has(i));
    renderGlossary();
}

// ── Playground ──

async function runTest() {
    const raw = document.getElementById('testInput').value.trim();
    const statusDot = document.getElementById('testStatusDot');
    const statusText = document.getElementById('testStatus');
    const runBtn = document.getElementById('testRunBtn');
    const output = document.getElementById('testOutput');

    if (!raw) {
        statusDot.className = 'w-2 h-2 rounded-full bg-red-400';
        statusText.textContent = 'Enter text first';
        return;
    }

    const llmOverride = {
        base_url: document.getElementById('llmUrl').value.trim(),
        api_key: document.getElementById('llmKey').value.trim(),
        model: document.getElementById('llmModel').value.trim(),
        prompt: document.getElementById('llmPrompt').value.trim(),
    };

    runBtn.disabled = true;
    runBtn.innerHTML = '<span class="material-symbols-outlined text-[16px] animate-spin">progress_activity</span> Running...';
    output.value = '';
    statusDot.className = 'w-2 h-2 rounded-full bg-primary';
    statusText.textContent = 'Calling LLM...';

    try {
        const result = await pywebview.api.run_test(raw, llmOverride);
        if (result.success) {
            output.value = result.result || '';
            statusDot.className = 'w-2 h-2 rounded-full bg-green-500';
            statusText.textContent = 'Done';
        } else {
            statusDot.className = 'w-2 h-2 rounded-full bg-red-400';
            statusText.textContent = `Error: ${result.error}`;
        }
    } catch (e) {
        statusDot.className = 'w-2 h-2 rounded-full bg-red-400';
        statusText.textContent = `Error: ${e}`;
    } finally {
        runBtn.disabled = false;
        runBtn.innerHTML = '<span class="material-symbols-outlined text-[16px]">play_arrow</span> Run';
    }
}

function copyTestOutput() {
    const text = document.getElementById('testOutput').value;
    if (text) navigator.clipboard.writeText(text);
}

// ── History (scrolling pagination) ──

let historyOffset = 0;
let historyLoading = false;
let historyHasMore = true;

function renderHistoryEntry(e) {
    return `
        <div class="border border-gray-200 rounded-lg overflow-hidden bg-white flex flex-col">
            <div class="px-4 py-2 bg-gray-50 border-b border-gray-200 flex justify-between items-center">
                <span class="text-[10px] font-medium text-gray-500 uppercase tracking-tight">${escapeHtml(e.timestamp)}</span>
            </div>
            <div class="grid grid-cols-2 min-h-[80px]">
                <div class="p-4 border-r border-gray-100">
                    <label class="block text-[10px] font-bold text-gray-400 uppercase mb-2">Input</label>
                    <p class="text-sm text-gray-600 leading-relaxed">${escapeHtml(e.raw_input)}</p>
                </div>
                <div class="p-4">
                    <label class="block text-[10px] font-bold text-gray-400 uppercase mb-2">Output</label>
                    <p class="text-sm text-primary font-medium leading-relaxed">${escapeHtml(e.refined_output)}</p>
                </div>
            </div>
        </div>`;
}

async function loadHistory() {
    historyOffset = 0;
    historyHasMore = true;
    historyLoading = false;
    document.getElementById('historyList').innerHTML = '';
    await loadMoreHistory();
}

async function loadMoreHistory() {
    if (historyLoading || !historyHasMore) return;
    historyLoading = true;
    const list = document.getElementById('historyList');
    try {
        const data = await pywebview.api.get_history(historyOffset, 20);
        const entries = data.entries || [];
        historyHasMore = data.has_more;
        if (data.next_offset != null) historyOffset = data.next_offset;

        if (entries.length === 0 && historyOffset === 0) {
            list.innerHTML = '<p class="text-center text-text-muted text-sm py-8">No history entries yet.</p>';
        } else {
            list.insertAdjacentHTML('beforeend', entries.map(renderHistoryEntry).join(''));
        }
    } catch (e) {
        if (historyOffset === 0) {
            list.innerHTML = `<p class="text-center text-text-muted text-sm py-8">Failed to load history: ${e}</p>`;
        }
    } finally {
        historyLoading = false;
    }
}

// Scroll listener for infinite loading
document.getElementById('historyList').addEventListener('scroll', () => {
    const el = document.getElementById('historyList');
    if (el.scrollHeight - el.scrollTop - el.clientHeight < 200) {
        loadMoreHistory();
    }
});

async function clearAllHistory() {
    if (!confirm('Clear all history entries?')) return;
    try {
        await pywebview.api.clear_history();
        historyOffset = 0;
        historyHasMore = true;
        historyLoading = false;
        document.getElementById('historyList').innerHTML =
            '<p class="text-center text-text-muted text-sm py-8">No history entries yet.</p>';
    } catch (e) {
        alert('Failed: ' + e);
    }
}

// ── Utilities ──

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
