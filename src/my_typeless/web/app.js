/* ── My Typeless Settings - Frontend Logic ── */

let currentConfig = {};
let currentHotkey = 'right alt';
let glossaryTerms = [];
let sttProviders = [];
let llmProviders = [];
let activeSttProviderId = '';
let activeSttModel = '';
let activeLlmProviderId = '';
let activeLlmModel = '';
let modalModels = [];

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
    setText('hotkeyBtn', config.hotkey || currentHotkey);
    setChecked('autostartToggle', !!config.start_with_windows);

    // STT
    sttProviders = normalizeProviders(config.stt?.providers);
    activeSttProviderId = resolveActiveProviderId(sttProviders, config.stt?.active_provider_id);
    activeSttModel = resolveActiveModel(sttProviders, activeSttProviderId, config.stt?.active_model);
    renderProviderList('stt');
    renderProviderDropdown('stt');

    // LLM
    llmProviders = normalizeProviders(config.llm?.providers);
    activeLlmProviderId = resolveActiveProviderId(llmProviders, config.llm?.active_provider_id);
    activeLlmModel = resolveActiveModel(llmProviders, activeLlmProviderId, config.llm?.active_model);
    const activeLlmProvider = findProvider(llmProviders, activeLlmProviderId);
    setValue('llmUrl', activeLlmProvider?.base_url || '');
    setValue('llmKey', activeLlmProvider?.api_key || '');
    setValue('llmModel', activeLlmModel || '');
    setValue('llmPrompt', config.llm?.prompt || '');
    renderProviderList('llm');
    renderProviderDropdown('llm');

    // Glossary
    glossaryTerms = [...(config.glossary || [])];
    renderGlossary();

    // Update status badges
    updateStatusBadge('sttStatusBadge', !!findProvider(sttProviders, activeSttProviderId)?.api_key);
    updateStatusBadge('llmStatusBadge', !!activeLlmProvider?.api_key);
}

function updateStatusBadge(id, active) {
    const badge = document.getElementById(id);
    if (!badge) return;
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
    const sttProviderId = getValue('sttActiveProvider') || activeSttProviderId;
    const sttModel = getValue('sttActiveModel') || activeSttModel;
    activeSttProviderId = resolveActiveProviderId(sttProviders, sttProviderId);
    activeSttModel = sttModel || resolveActiveModel(sttProviders, activeSttProviderId, '');

    const llmProvider = findProvider(llmProviders, activeLlmProviderId);
    const llmUrl = getValue('llmUrl').trim();
    const llmKey = getValue('llmKey').trim();
    const llmModel = getValue('llmModel').trim();
    if (llmProvider) {
        llmProvider.base_url = llmUrl;
        llmProvider.api_key = llmKey;
        if (llmModel) {
            llmProvider.models = [llmModel, ...(llmProvider.models || []).filter(m => m !== llmModel)];
        }
        activeLlmModel = llmModel || resolveActiveModel(llmProviders, activeLlmProviderId, activeLlmModel);
    }

    return {
        hotkey: currentHotkey,
        start_with_windows: !!document.getElementById('autostartToggle')?.checked,
        stt: {
            providers: sttProviders,
            active_provider_id: activeSttProviderId,
            active_model: activeSttModel,
            language: currentConfig.stt?.language || '',
        },
        llm: {
            providers: llmProviders,
            active_provider_id: activeLlmProviderId,
            active_model: activeLlmModel,
            prompt: getValue('llmPrompt').trim(),
        },
        glossary: [...glossaryTerms],
    };
}

async function applyConfig() {
    const result = await pywebview.api.save_config(collectFormData());
    if (!result.success) {
        alert('Save failed: ' + (result.error || 'Unknown error'));
    }
    return result;
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

    btn.disabled = true;
    setButtonContent(btn, 'progress_activity', 'Testing...', 'text-[16px] animate-spin');

    try {
        let result;
        const payload = { base_url: url, api_key: key, model: model, provider_type: apiType };

        if (type === 'stt') {
            result = await pywebview.api.test_stt_connection(payload);
        } else {
            result = await pywebview.api.test_llm_connection(payload);
        }

        if (result.success) {
            setButtonContent(btn, 'check_circle', 'Success', 'text-[16px] text-green-500');
            setTimeout(() => {
                if (!btn.disabled) return;
                btn.disabled = false;
                setModalTestButtonDefault(btn);
            }, 2000);
        } else {
            alert('Connection failed: ' + (result.error || 'Unknown'));
            btn.disabled = false;
            setModalTestButtonDefault(btn);
        }
    } catch (e) {
        alert('Connection failed: ' + e);
        btn.disabled = false;
        setModalTestButtonDefault(btn);
    }
}


// ── Glossary ──

function renderGlossary() {
    const list = document.getElementById('glossaryList');
    list.replaceChildren();

    if (glossaryTerms.length === 0) {
        list.appendChild(createStatusMessage('No terms added yet.'));
    } else {
        const fragment = document.createDocumentFragment();
        glossaryTerms.forEach((term, i) => {
            const item = document.createElement('div');
            item.className = 'flex items-center px-4 py-3 border-b border-border-gray group hover:bg-neutral-50 transition-colors';
            item.dataset.index = String(i);
            item.addEventListener('click', () => toggleGlossarySelect(item));

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'rounded border-border-gray text-primary focus:ring-0 cursor-pointer size-4';
            checkbox.addEventListener('click', (event) => {
                event.stopPropagation();
                item.classList.toggle('bg-neutral-50', checkbox.checked);
            });

            const text = document.createElement('span');
            text.className = 'ml-4 text-sm font-medium text-primary';
            text.textContent = safeText(term);

            item.append(checkbox, text);
            fragment.appendChild(item);
        });
        list.appendChild(fragment);
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
    if (!checkbox) return;
    checkbox.checked = !checkbox.checked;
    el.classList.toggle('bg-neutral-50', checkbox.checked);
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
    setButtonContent(runBtn, 'progress_activity', 'Running...', 'text-[16px] animate-spin');
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
        setButtonContent(runBtn, 'play_arrow', 'Run');
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
    const card = document.createElement('div');
    card.className = 'border border-gray-200 rounded-lg overflow-hidden bg-white flex flex-col';

    const header = document.createElement('div');
    header.className = 'px-4 py-2 bg-gray-50 border-b border-gray-200 flex justify-between items-center';
    const timestamp = document.createElement('span');
    timestamp.className = 'text-[10px] font-medium text-gray-500 uppercase tracking-tight';
    timestamp.textContent = safeText(e.timestamp);
    header.appendChild(timestamp);

    const content = document.createElement('div');
    content.className = 'grid grid-cols-2 min-h-[80px]';

    const inputColumn = document.createElement('div');
    inputColumn.className = 'p-4 border-r border-gray-100';
    const inputLabel = document.createElement('label');
    inputLabel.className = 'block text-[10px] font-bold text-gray-400 uppercase mb-2';
    inputLabel.textContent = 'Input';
    const inputText = document.createElement('p');
    inputText.className = 'text-sm text-gray-600 leading-relaxed';
    inputText.textContent = safeText(e.raw_input);
    inputColumn.append(inputLabel, inputText);

    const outputColumn = document.createElement('div');
    outputColumn.className = 'p-4';
    const outputLabel = document.createElement('label');
    outputLabel.className = 'block text-[10px] font-bold text-gray-400 uppercase mb-2';
    outputLabel.textContent = 'Output';
    const outputText = document.createElement('p');
    outputText.className = 'text-sm text-primary font-medium leading-relaxed';
    outputText.textContent = safeText(e.refined_output);
    outputColumn.append(outputLabel, outputText);

    content.append(inputColumn, outputColumn);
    card.append(header, content);
    return card;
}

async function loadHistory() {
    historyOffset = 0;
    historyHasMore = true;
    historyLoading = false;
    document.getElementById('historyList').replaceChildren();
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
            list.replaceChildren(createStatusMessage('No history entries yet.'));
        } else {
            const fragment = document.createDocumentFragment();
            entries.forEach((entry) => {
                fragment.appendChild(renderHistoryEntry(entry));
            });
            list.appendChild(fragment);
        }
    } catch (e) {
        if (historyOffset === 0) {
            list.replaceChildren(createStatusMessage(`Failed to load history: ${e}`));
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
        document.getElementById('historyList').replaceChildren(createStatusMessage('No history entries yet.'));
    } catch (e) {
        alert('Failed: ' + e);
    }
}

// ── Utilities ──

function getValue(id) {
    return document.getElementById(id)?.value || '';
}

function setValue(id, value) {
    const el = document.getElementById(id);
    if (el) el.value = value || '';
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value || '';
}

function setChecked(id, value) {
    const el = document.getElementById(id);
    if (el) el.checked = !!value;
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function setButtonContent(button, iconName, label, iconClass = 'text-[16px]') {
    const icon = document.createElement('span');
    icon.className = `material-symbols-outlined ${iconClass}`;
    icon.textContent = iconName;
    const text = document.createElement('span');
    text.textContent = label;
    button.replaceChildren(icon, text);
}

function setModalTestButtonDefault(button) {
    setButtonContent(button, 'link', 'Test Connection');
}

function safeText(value) {
    return value == null ? '' : String(value);
}

function createStatusMessage(text) {
    const message = document.createElement('p');
    message.className = 'text-center text-text-muted text-sm py-8';
    message.textContent = text;
    return message;
}

function createOption(value, label, selected = false) {
    const option = document.createElement('option');
    option.value = safeText(value);
    option.textContent = safeText(label);
    option.selected = selected;
    return option;
}

function createIcon(name, className = '') {
    const icon = document.createElement('span');
    icon.className = `material-symbols-outlined ${className}`.trim();
    icon.textContent = name;
    return icon;
}

function normalizeProviders(providers) {
    if (!Array.isArray(providers)) return [];

    return providers.map((p, index) => ({
        id: p.id || `provider-${index + 1}`,
        name: p.name || p.id || `Provider ${index + 1}`,
        base_url: p.base_url || '',
        api_key: p.api_key || '',
        models: Array.isArray(p.models) ? p.models.filter(Boolean) : [],
        provider_type: p.provider_type || 'openai',
    }));
}

function findProvider(providers, providerId) {
    return providers.find(p => p.id === providerId) || providers[0] || null;
}

function resolveActiveProviderId(providers, configuredId) {
    if (!providers.length) return '';
    if (configuredId && providers.some(p => p.id === configuredId)) return configuredId;
    return providers[0].id;
}

function resolveActiveModel(providers, providerId, configuredModel) {
    const provider = findProvider(providers, providerId);
    if (!provider || !provider.models?.length) return '';
    if (configuredModel && provider.models.includes(configuredModel)) return configuredModel;
    return provider.models[0];
}


// ── Provider Management ──

function generateId() {
    return Math.random().toString(36).substring(2, 15);
}

function renderProviderDropdown(type) {
    const providers = type === 'stt' ? sttProviders : llmProviders;

    const providerSelect = document.getElementById(`${type}ActiveProvider`);
    const modelSelect = document.getElementById(`${type}ActiveModel`);
    if (!providerSelect || !modelSelect) return;

    let activeId = type === 'stt' ? activeSttProviderId : activeLlmProviderId;
    let activeModel = type === 'stt' ? activeSttModel : activeLlmModel;

    activeId = resolveActiveProviderId(providers, activeId);
    activeModel = resolveActiveModel(providers, activeId, activeModel);

    if (providers.length === 0) {
        providerSelect.replaceChildren(createOption('', 'No providers'));
        modelSelect.replaceChildren(createOption('', 'N/A'));
        activeId = '';
        activeModel = '';
    } else {
        providerSelect.replaceChildren(
            ...providers.map((p) => createOption(p.id, p.name, p.id === activeId))
        );
        providerSelect.value = activeId;
        updateModelDropdown(type, activeId, activeModel);
    }

    if (type === 'stt') {
        activeSttProviderId = activeId;
        activeSttModel = activeModel;
    } else {
        activeLlmProviderId = activeId;
        activeLlmModel = activeModel;
    }

}

function updateModelDropdown(type, providerId, selectedModel) {
    const providers = type === 'stt' ? sttProviders : llmProviders;
    const provider = providers.find(p => p.id === providerId);
    const modelSelect = document.getElementById(`${type}ActiveModel`);
    if (!modelSelect) return;
    const models = Array.isArray(provider?.models) ? provider.models : [];

    if (models.length === 0) {
        modelSelect.replaceChildren(createOption('', 'No models'));
        if (type === 'stt') activeSttModel = '';
        else activeLlmModel = '';
        return;
    }

    const activeModel = models.includes(selectedModel) ? selectedModel : models[0];
    modelSelect.replaceChildren(
        ...models.map((m) => createOption(m, m, m === activeModel))
    );
    modelSelect.value = activeModel;

    if (type === 'stt') activeSttModel = activeModel;
    else activeLlmModel = activeModel;
}

function onSttProviderChange() {
    const select = document.getElementById('sttActiveProvider');
    if (!select) return;
    const id = select.value;
    activeSttProviderId = id;
    updateModelDropdown('stt', id, null);
}

function onLlmProviderChange() {
    const select = document.getElementById('llmActiveProvider');
    if (!select) return;
    const id = select.value;
    activeLlmProviderId = id;
    updateModelDropdown('llm', id, null);
}

function renderProviderList(type) {
    const providers = type === 'stt' ? sttProviders : llmProviders;
    const list = document.getElementById(`${type}ProviderList`);
    if (!list) return;
    list.replaceChildren();

    if (providers.length === 0) {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = 4;
        cell.className = 'px-6 py-8 text-center text-gray-500';
        cell.textContent = 'No providers configured. Click "New Provider" to add one.';
        row.appendChild(cell);
        list.appendChild(row);
        return;
    }

    const fragment = document.createDocumentFragment();
    providers.forEach((p) => {
        const row = document.createElement('tr');
        row.className = 'hover:bg-gray-50 transition-colors group';

        const nameCell = document.createElement('td');
        nameCell.className = 'px-6 py-4 whitespace-nowrap';
        const name = document.createElement('div');
        name.className = 'font-semibold text-primary';
        name.textContent = safeText(p.name);
        nameCell.appendChild(name);

        const urlCell = document.createElement('td');
        urlCell.className = 'px-6 py-4 whitespace-nowrap text-gray-500 font-mono text-xs';
        urlCell.textContent = safeText(p.base_url);

        const modelsCell = document.createElement('td');
        modelsCell.className = 'px-6 py-4';
        const modelsWrapper = document.createElement('div');
        modelsWrapper.className = 'flex flex-wrap gap-1';
        const models = Array.isArray(p.models) ? p.models : [];
        if (models.length === 0) {
            const empty = document.createElement('span');
            empty.className = 'text-gray-400 text-xs italic';
            empty.textContent = 'No models';
            modelsWrapper.appendChild(empty);
        } else {
            models.forEach((model) => {
                const modelTag = document.createElement('span');
                modelTag.className = 'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800 border border-gray-200';
                modelTag.textContent = safeText(model);
                modelsWrapper.appendChild(modelTag);
            });
        }
        modelsCell.appendChild(modelsWrapper);

        const actionsCell = document.createElement('td');
        actionsCell.className = 'px-6 py-4 whitespace-nowrap text-right text-sm font-medium';
        const actions = document.createElement('div');
        actions.className = 'flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity';

        const editButton = document.createElement('button');
        editButton.type = 'button';
        editButton.className = 'p-1 text-gray-400 hover:text-primary transition-colors';
        editButton.title = 'Edit';
        editButton.addEventListener('click', () => editProvider(type, p.id));
        editButton.appendChild(createIcon('edit', 'text-[18px]'));

        const deleteButton = document.createElement('button');
        deleteButton.type = 'button';
        deleteButton.className = 'p-1 text-gray-400 hover:text-red-600 transition-colors';
        deleteButton.title = 'Delete';
        deleteButton.addEventListener('click', () => deleteProvider(type, p.id));
        deleteButton.appendChild(createIcon('delete', 'text-[18px]'));

        actions.append(editButton, deleteButton);
        actionsCell.appendChild(actions);
        row.append(nameCell, urlCell, modelsCell, actionsCell);
        fragment.appendChild(row);
    });
    list.appendChild(fragment);
}

// ── Modal Logic ──

function openProviderModal(type, providerId = null) {
    document.getElementById('modalProviderType').value = type;
    document.getElementById('providerModalTitle').textContent = providerId ? 'Edit Provider' : 'Add Provider';

    const providers = type === 'stt' ? sttProviders : llmProviders;
    let provider = providerId ? providers.find(p => p.id === providerId) : null;

    document.getElementById('modalProviderId').value = providerId || '';
    document.getElementById('modalProviderApiType').value = provider?.provider_type || 'openai';
    document.getElementById('modalProviderName').value = provider ? safeText(provider.name) : '';
    document.getElementById('modalProviderUrl').value = provider ? safeText(provider.base_url) : '';
    document.getElementById('modalProviderKey').value = provider ? safeText(provider.api_key) : '';

    const keyInput = document.getElementById('modalProviderKey');
    const icon = keyInput.nextElementSibling.querySelector('.material-symbols-outlined');
    keyInput.type = 'password';
    icon.textContent = 'visibility';

    modalModels = provider && Array.isArray(provider.models) ? [...provider.models] : [];
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
    container.replaceChildren();

    const fragment = document.createDocumentFragment();
    modalModels.forEach((m, i) => {
        const tag = document.createElement('div');
        tag.className = 'inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-gray-100 border border-gray-200 text-sm font-medium text-primary';

        const label = document.createElement('span');
        label.textContent = safeText(m);

        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'text-gray-400 hover:text-red-500 rounded-full flex items-center justify-center p-0.5';
        button.addEventListener('click', () => removeModalModel(i));
        button.appendChild(createIcon('close', 'text-[14px]'));

        tag.append(label, button);
        fragment.appendChild(tag);
    });
    container.appendChild(fragment);
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
    const providerType = document.getElementById('modalProviderApiType').value || 'openai';
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
        models: [...modalModels],
        provider_type: providerType,
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
