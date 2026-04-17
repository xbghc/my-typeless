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
    } else {
        input.type = 'password';
        icon.textContent = 'visibility';
    }
}

// ── Test Connection (Provider Modal) ──

async function testModalConnection() {
    const btn = document.getElementById('modalTestBtn');
    const type = document.getElementById('modalProviderType').value;
    const apiType = document.getElementById('modalProviderApiType').value;
    const url = document.getElementById('modalProviderUrl').value.trim();
    const key = document.getElementById('modalProviderKey').value.trim();

    if ((!url && apiType !== 'anthropic') || !key) {
        alert('API Key (and Base URL for OpenAI) are required to test connection.');
        return;
    }

    if (modalModels.length === 0) {
        alert('At least one model must be added to test connection.');
        return;
    }

    const model = modalModels[0]; // Test the first model

    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="material-symbols-outlined text-[16px] animate-spin">progress_activity</span> Testing...';

    try {
        let result;
        const payload = { base_url: url, api_key: key, model: model, provider_type: apiType };

        if (type === 'stt') {
            result = await pywebview.api.test_stt_connection(payload);
        } else {
            result = await pywebview.api.test_llm_connection(payload);
        }

        if (result.success) {
            btn.innerHTML = '<span class="material-symbols-outlined text-[16px] text-green-500">check_circle</span> Success';
            setTimeout(() => {
                if (!btn.disabled) return;
                btn.disabled = false;
                btn.innerHTML = originalText;
            }, 2000);
        } else {
            alert('Connection failed: ' + (result.error || 'Unknown'));
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    } catch (e) {
        alert('Connection failed: ' + e);
        btn.disabled = false;
        btn.innerHTML = originalText;
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

    const llmOverride = null; // Will use active backend config implicitly

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


// ── Provider Management ──

function generateId() {
    return Math.random().toString(36).substring(2, 15);
}

function renderProviderDropdown(type) {
    const providers = type === 'stt' ? sttProviders : llmProviders;
    const activeId = type === 'stt' ? activeSttProviderId : activeLlmProviderId;
    const activeModel = type === 'stt' ? activeSttModel : activeLlmModel;

    const providerSelect = document.getElementById(`${type}ActiveProvider`);
    const modelSelect = document.getElementById(`${type}ActiveModel`);

    providerSelect.innerHTML = providers.map(p =>
        `<option value="${escapeHtml(p.id)}" ${p.id === activeId ? 'selected' : ''}>${escapeHtml(p.name)}</option>`
    ).join('');

    if (providers.length === 0) {
        providerSelect.innerHTML = '<option value="">No providers</option>';
        modelSelect.innerHTML = '<option value="">N/A</option>';
        return;
    }

    updateModelDropdown(type, activeId, activeModel);
}

function updateModelDropdown(type, providerId, selectedModel) {
    const providers = type === 'stt' ? sttProviders : llmProviders;
    const provider = providers.find(p => p.id === providerId);
    const modelSelect = document.getElementById(`${type}ActiveModel`);

    if (!provider || !provider.models || provider.models.length === 0) {
        modelSelect.innerHTML = '<option value="">No models</option>';
        return;
    }

    modelSelect.innerHTML = provider.models.map(m =>
        `<option value="${escapeHtml(m)}" ${m === selectedModel ? 'selected' : ''}>${escapeHtml(m)}</option>`
    ).join('');
}

function onSttProviderChange() {
    const id = document.getElementById('sttActiveProvider').value;
    updateModelDropdown('stt', id, null);
    activeSttProviderId = id;
}

function onLlmProviderChange() {
    const id = document.getElementById('llmActiveProvider').value;
    updateModelDropdown('llm', id, null);
    activeLlmProviderId = id;
}

function renderProviderList(type) {
    const providers = type === 'stt' ? sttProviders : llmProviders;
    const list = document.getElementById(`${type}ProviderList`);

    if (providers.length === 0) {
        list.innerHTML = `<tr><td colspan="4" class="px-6 py-8 text-center text-gray-500">No providers configured. Click "New Provider" to add one.</td></tr>`;
        return;
    }

    list.innerHTML = providers.map(p => {
        const maskedKey = p.api_key ? '••••••••' : 'None';
        const modelsHtml = p.models.map(m => `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800 border border-gray-200">${escapeHtml(m)}</span>`).join(' ');

        return `
            <tr class="hover:bg-gray-50 transition-colors group">
                <td class="px-6 py-4 whitespace-nowrap">
                    <div class="font-semibold text-primary">${escapeHtml(p.name)}</div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-gray-500 font-mono text-xs">
                    ${escapeHtml(p.base_url)}
                </td>
                <td class="px-6 py-4">
                    <div class="flex flex-wrap gap-1">
                        ${modelsHtml || '<span class="text-gray-400 text-xs italic">No models</span>'}
                    </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <div class="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button onclick="editProvider('${type}', '${escapeHtml(p.id)}')" class="p-1 text-gray-400 hover:text-primary transition-colors" title="Edit">
                            <span class="material-symbols-outlined text-[18px]">edit</span>
                        </button>
                        <button onclick="deleteProvider('${type}', '${escapeHtml(p.id)}')" class="p-1 text-gray-400 hover:text-red-600 transition-colors" title="Delete">
                            <span class="material-symbols-outlined text-[18px]">delete</span>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

// ── Modal Logic ──

function openProviderModal(type, providerId = null) {
    document.getElementById('modalProviderType').value = type;
    document.getElementById('providerModalTitle').textContent = providerId ? 'Edit Provider' : 'Add Provider';

    const providers = type === 'stt' ? sttProviders : llmProviders;
    let provider = providerId ? providers.find(p => p.id === providerId) : null;

    document.getElementById('modalProviderId').value = providerId || '';
    document.getElementById('modalProviderName').value = provider ? provider.name : '';
    document.getElementById('modalProviderUrl').value = provider ? provider.base_url : '';
    document.getElementById('modalProviderKey').value = provider ? provider.api_key : '';

    const keyInput = document.getElementById('modalProviderKey');
    const icon = keyInput.nextElementSibling.querySelector('.material-symbols-outlined');
    keyInput.type = 'password';
    icon.textContent = 'visibility';

    modalModels = provider ? [...provider.models] : [];
    renderModalModels();

    const modal = document.getElementById('providerModal');
    const content = document.getElementById('providerModalContent');

    modal.classList.remove('hidden');
    // small delay to allow display:block to apply before animation
    setTimeout(() => {
        modal.classList.remove('opacity-0');
        content.classList.remove('scale-95');
    }, 10);
}

function closeProviderModal() {
    const modal = document.getElementById('providerModal');
    const content = document.getElementById('providerModalContent');

    modal.classList.add('opacity-0');
    content.classList.add('scale-95');

    setTimeout(() => {
        modal.classList.add('hidden');
    }, 200);
}

function renderModalModels() {
    const container = document.getElementById('modalModelsContainer');
    container.innerHTML = modalModels.map((m, i) => `
        <div class="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-gray-100 border border-gray-200 text-sm font-medium text-primary">
            ${escapeHtml(m)}
            <button onclick="removeModalModel(${i})" class="text-gray-400 hover:text-red-500 rounded-full flex items-center justify-center p-0.5">
                <span class="material-symbols-outlined text-[14px]">close</span>
            </button>
        </div>
    `).join('');
}

function handleModelInputKeyDown(e) {
    if (e.key === 'Enter') {
        e.preventDefault();
        const input = document.getElementById('modalModelInput');
        const val = input.value.trim();
        if (val && !modalModels.includes(val)) {
            modalModels.push(val);
            renderModalModels();
            input.value = '';
        }
    } else if (e.key === 'Backspace' && document.getElementById('modalModelInput').value === '' && modalModels.length > 0) {
        modalModels.pop();
        renderModalModels();
    }
}

function removeModalModel(index) {
    modalModels.splice(index, 1);
    renderModalModels();
}

async function saveProviderModal() {
    const type = document.getElementById('modalProviderType').value;
    const id = document.getElementById('modalProviderId').value || generateId();
    const name = document.getElementById('modalProviderName').value.trim();
    const url = document.getElementById('modalProviderUrl').value.trim();
    const key = document.getElementById('modalProviderKey').value.trim();

    if (!name || !url) {
        alert('Name and Base URL are required.');
        return;
    }

    const newProvider = {
        id: id,
        name: name,
        base_url: url,
        api_key: key,
        models: [...modalModels]
    };

    const providers = type === 'stt' ? sttProviders : llmProviders;
    const existingIndex = providers.findIndex(p => p.id === id);

    if (existingIndex >= 0) {
        providers[existingIndex] = newProvider;
    } else {
        providers.push(newProvider);
    }

    renderProviderList(type);
    renderProviderDropdown(type);
    closeProviderModal();

    // Auto-save
    await applyConfig();
}

async function deleteProvider(type, id) {
    if (!confirm('Are you sure you want to delete this provider?')) return;

    if (type === 'stt') {
        sttProviders = sttProviders.filter(p => p.id !== id);
        if (activeSttProviderId === id) {
            activeSttProviderId = sttProviders.length > 0 ? sttProviders[0].id : '';
        }
    } else {
        llmProviders = llmProviders.filter(p => p.id !== id);
        if (activeLlmProviderId === id) {
            activeLlmProviderId = llmProviders.length > 0 ? llmProviders[0].id : '';
        }
    }

    renderProviderList(type);
    renderProviderDropdown(type);

    // Auto-save
    await applyConfig();
}

function editProvider(type, id) {
    openProviderModal(type, id);
}
