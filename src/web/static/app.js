// YouTube Downloader Web App Client Logic

let socket = null;
let reconnectTimer = null;
let pollTimer = null;
let isWebSocketConnected = false;
let currentLanguage = 'es';
let translations = {};

function getTranslation(key, fallback = '') {
    if (translations[currentLanguage] && translations[currentLanguage][key]) {
        return translations[currentLanguage][key];
    }
    return fallback;
}

async function applyTranslations(lang) {
    if (!lang) return;
    try {
        let trans = translations[lang];
        if (!trans) {
            const response = await fetch(`/api/i18n/${lang}`);
            if (!response.ok) throw new Error('Failed to load translations');
            trans = await response.json();
            translations[lang] = trans;
        }
        currentLanguage = lang;
        
        // Update document title
        const webManagerLabel = trans['btn_web_manager'] || 'Web Manager';
        document.title = `YouTube Downloader - ${webManagerLabel}`;
        
        // Apply translations to all elements with data-i18n attribute
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            const val = trans[key];
            if (val) {
                if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                    el.placeholder = val;
                } else {
                    el.textContent = val;
                }
            }
        });

        // Update connection status label
        const connStatusEl = document.getElementById('conn-status');
        if (connStatusEl) {
            if (isWebSocketConnected) {
                connStatusEl.textContent = trans['web_status_conn_ws'] || 'Conectado (Real-time)';
            } else {
                connStatusEl.textContent = trans['web_status_conn_polling'] || 'Fallback (Polling 3s)';
            }
        }
        
        // Update pause/resume button text if it exists
        const pauseText = document.getElementById('pause-text');
        if (pauseText) {
            const isPaused = pauseText.getAttribute('data-paused') === 'true';
            if (isPaused) {
                pauseText.textContent = trans['btn_resume_all'] || 'Reanudar Todo';
            } else {
                pauseText.textContent = trans['btn_pause_all'] || 'Pausar Todo';
            }
        }
        
        // Refresh active/pending queues and history table in the new language
        pollState();
    } catch (err) {
        console.error('Error applying translations:', err);
    }
}

// UI Update Throttling to prevent rendering storms under batch enqueuing/completion
let pendingUIState = null;
let updateUITimeout = null;

function throttleUpdateUI(state) {
    pendingUIState = state;
    if (!updateUITimeout) {
        updateUITimeout = setTimeout(() => {
            if (pendingUIState) {
                updateUI(pendingUIState);
                pendingUIState = null;
            }
            updateUITimeout = null;
        }, 150);
    }
}

// Toast Notification System
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    const toastIcon = document.getElementById('toast-icon');
    const toastIconBg = document.getElementById('toast-icon-bg');
    const toastMessage = document.getElementById('toast-message');

    toastMessage.textContent = message;

    // Reset styles
    toastIconBg.className = 'w-8 h-8 rounded-lg flex items-center justify-center text-white';
    
    if (type === 'success') {
        toastIconBg.classList.add('bg-emerald-500');
        toastIcon.className = 'fa-solid fa-circle-check';
    } else if (type === 'error') {
        toastIconBg.classList.add('bg-rose-500');
        toastIcon.className = 'fa-solid fa-circle-xmark';
    } else {
        toastIconBg.classList.add('bg-violet-500');
        toastIcon.className = 'fa-solid fa-circle-info';
    }

    toast.classList.remove('translate-y-12', 'opacity-0');
    toast.classList.add('translate-y-0', 'opacity-100');

    setTimeout(() => {
        toast.classList.remove('translate-y-0', 'opacity-100');
        toast.classList.add('translate-y-12', 'opacity-0');
    }, 4000);
}

// Format utilities
function formatBytes(bytes) {
    if (!bytes || isNaN(bytes)) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatSpeed(bytesPerSec) {
    if (!bytesPerSec || isNaN(bytesPerSec)) return '0 KB/s';
    return formatBytes(bytesPerSec) + '/s';
}

function formatEta(seconds) {
    if (!seconds || isNaN(seconds)) return '--:--';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// UI State Updater
function updateUI(state) {
    // Stats Update
    const activeCount = Object.keys(state.active_downloads).length;
    const pendingCount = state.pending_downloads.length;
    document.getElementById('stat-active').textContent = activeCount;
    document.getElementById('stat-pending').textContent = pendingCount;

    // Pause/Resume Button state
    const isPaused = state.paused;
    const pauseIcon = document.getElementById('pause-icon');
    const pauseText = document.getElementById('pause-text');
    if (isPaused) {
        pauseIcon.className = 'fa-solid fa-play text-emerald-400';
        pauseText.textContent = getTranslation('btn_resume_all', 'Reanudar Todo');
        pauseText.setAttribute('data-paused', 'true');
    } else {
        pauseIcon.className = 'fa-solid fa-pause text-yellow-400';
        pauseText.textContent = getTranslation('btn_pause_all', 'Pausar Todo');
        pauseText.setAttribute('data-paused', 'false');
    }

    // Queue Rendering
    const downloadsContainer = document.getElementById('downloads-container');
    
    // Clear dynamic cards
    const cardSelector = downloadsContainer.querySelectorAll('.download-card');
    cardSelector.forEach(el => el.remove());

    const hasTasks = activeCount > 0 || pendingCount > 0;
    const emptyQueueState = document.getElementById('empty-queue-state');

    if (hasTasks) {
        emptyQueueState.classList.add('hidden');
        
        // Active Downloads
        Object.entries(state.active_downloads).forEach(([workerId, dl]) => {
            const card = createActiveCard(workerId, dl);
            downloadsContainer.appendChild(card);
        });

        // Pending Downloads
        state.pending_downloads.forEach((task, idx) => {
            const card = createPendingCard(task, idx + 1);
            downloadsContainer.appendChild(card);
        });
    } else {
        emptyQueueState.classList.remove('hidden');
    }

    // History Table Rendering
    const historyRows = document.getElementById('history-rows');
    historyRows.innerHTML = '';

    if (state.download_history && state.download_history.length > 0) {
        // Render in reverse to show latest first
        [...state.download_history].reverse().forEach(entry => {
            const row = document.createElement('tr');
            row.className = 'hover:bg-slate-900/40 transition-colors text-xs text-slate-300';
            
            const isSuccess = entry.status === 'success';
            const statusLabel = isSuccess 
                ? getTranslation('status_success', 'Completado')
                : entry.status === 'cancelled'
                    ? getTranslation('status_cancelled', 'Cancelado')
                    : getTranslation('status_error', 'Fallo');
            
            const badgeClass = isSuccess 
                ? 'bg-emerald-950/40 text-emerald-400 border border-emerald-500/20'
                : entry.status === 'cancelled'
                    ? 'bg-slate-950/40 text-slate-400 border border-slate-500/20'
                    : 'bg-rose-950/40 text-rose-400 border border-rose-500/20';

            const statusBadge = `<span class="px-2 py-0.5 rounded-full ${badgeClass} font-medium">${statusLabel}</span>`;

            const name = entry.title || 'Video';
            const errDetails = entry.error ? `<span class="block text-[10px] text-rose-400/80 mt-0.5">${entry.error}</span>` : '';

            row.innerHTML = `
                <td class="p-4 font-medium text-white max-w-xs md:max-w-md truncate">
                    ${name}
                    ${errDetails}
                </td>
                <td class="p-4">${entry.quality || 'N/A'}</td>
                <td class="p-4 text-slate-500">${entry.date || ''}</td>
                <td class="p-4">${statusBadge}</td>
            `;
            historyRows.appendChild(row);
        });
    } else {
        const emptyRow = document.createElement('tr');
        emptyRow.innerHTML = `
            <td colspan="4" class="p-8 text-center text-slate-500 text-xs" data-i18n="web_empty_history">
                ${getTranslation('web_empty_history', 'El historial de descargas está vacío.')}
            </td>
        `;
        historyRows.appendChild(emptyRow);
    }
}function createActiveCard(workerId, dl) {
    const card = document.createElement('div');
    const progress = dl.progress || {};
    const percent = parseFloat(progress.percent || 0).toFixed(1);
    
    // Status text mapping
    let statusText = getTranslation('status_downloading', 'Descargando...');
    let leftBorderClass = 'border-l-4 border-l-cyan-500';
    if (progress.status_key === 'status_processing') {
        statusText = getTranslation('status_processing', 'Procesando formatos y fusionando audio/video...');
        leftBorderClass = 'border-l-4 border-l-fuchsia-500';
    } else if (progress.status_key === 'status_retrying') {
        statusText = getTranslation('status_retrying', 'Reintentando...');
        leftBorderClass = 'border-l-4 border-l-amber-500';
    }

    card.className = `glass-card p-5 download-card hover-scale relative overflow-hidden bg-slate-900/40 ${leftBorderClass} animate-slide-in`;
    card.setAttribute('data-worker-id', workerId);

    const wordOf = currentLanguage === 'en' ? 'of' : 'de';

    card.innerHTML = `
        <div class="flex items-start justify-between gap-4 mb-3">
            <div class="flex-1 min-w-0">
                <h3 class="text-sm font-semibold text-white truncate font-outfit" title="${dl.title || dl.url}">
                    ${dl.title || dl.url}
                </h3>
                <p class="text-xs text-slate-400 flex items-center gap-1.5 mt-1">
                    <span class="px-1.5 py-0.5 rounded bg-violet-600/20 text-violet-400 text-[10px] font-bold border border-violet-500/10 uppercase">${dl.quality}</span>
                    <span>•</span>
                    <span id="${workerId}-status" class="text-slate-400">${statusText}</span>
                </p>
            </div>
            <div class="flex items-center gap-3">
                <span id="${workerId}-percent" class="text-sm font-bold font-outfit text-violet-400">${percent}%</span>
                <button onclick="cancelActiveWorker('${workerId}')" 
                        class="text-slate-400 hover:text-rose-400 transition-all p-1 hover:scale-110 active:scale-95" 
                        title="Cancelar descarga">
                    <i class="fa-solid fa-xmark text-sm"></i>
                </button>
            </div>
        </div>

        <!-- Progress Bar -->
        <div class="w-full h-2 bg-slate-950/40 rounded-full overflow-hidden mb-3">
            <div id="${workerId}-bar" class="h-full progress-fill" style="width: ${percent}%"></div>
        </div>

        <!-- Stats Grid -->
        <div id="${workerId}-stats" class="grid grid-cols-3 gap-2 text-xs text-slate-400 font-medium">
            <div>
                <i class="fa-solid fa-download text-slate-500 mr-1"></i> 
                <span id="${workerId}-downloaded">${formatBytes(progress.downloaded)}</span> ${wordOf} <span id="${workerId}-total">${formatBytes(progress.total)}</span>
            </div>
            <div class="text-center">
                <i class="fa-solid fa-gauge-high text-slate-500 mr-1"></i> 
                <span id="${workerId}-speed">${formatSpeed(progress.speed)}</span>
            </div>
            <div class="text-right">
                <i class="fa-solid fa-hourglass-half text-slate-500 mr-1"></i> 
                <span>${getTranslation('downloads_eta', 'Restante')}: <span id="${workerId}-eta">${formatEta(progress.eta)}</span></span>
            </div>
        </div>
    `;
    return card;
}

function createPendingCard(task, index) {
    const card = document.createElement('div');
    card.className = 'glass-card p-4 download-card border-l-4 border-l-purple-500/40 bg-slate-950/10 animate-slide-in';

    card.innerHTML = `
        <div class="flex items-center justify-between gap-4">
            <div class="flex-1 min-w-0">
                <h3 class="text-sm font-semibold text-slate-300 truncate font-outfit">
                    <span class="text-slate-500 text-xs mr-1">[${getTranslation('status_pending', 'En cola')} #${index}]</span> ${task.title || task.url}
                </h3>
                <p class="text-xs text-slate-500 mt-0.5 flex items-center gap-1.5">
                    <span class="px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 text-[10px] font-bold border border-white/5 uppercase">${task.quality}</span>
                    <span>•</span>
                    <span>${getTranslation('status_pending', 'Pendiente para descargar')}</span>
                </p>
            </div>
            <div class="flex items-center gap-2">
                <button onclick="removePendingTask('${task.url}')" 
                        class="text-slate-500 hover:text-rose-400 transition-all p-1 hover:scale-110 active:scale-95" 
                        title="Eliminar de la cola">
                    <i class="fa-solid fa-trash-can text-sm"></i>
                </button>
                <i class="fa-solid fa-clock text-slate-600 text-lg animate-pulse"></i>
            </div>
        </div>
    `;
    return card;
}

async function cancelActiveWorker(workerId) {
    const confirmTitle = getTranslation('web_confirm_title', 'Confirmar Acción');
    const confirmMsg = getTranslation('web_confirm_cancel', '¿Cancelar esta descarga?');
    if (!await showConfirm(confirmTitle, confirmMsg, 'warning')) return;
    try {
        const response = await fetch(`/api/downloads/${encodeURIComponent(workerId)}/cancel`, { method: 'POST' });
        const res = await response.json();
        if (res.success) {
            let msg = 'Descarga cancelada.';
            if (currentLanguage === 'en') msg = 'Download cancelled.';
            else if (currentLanguage === 'pt') msg = 'Download cancelado.';
            showToast(msg, 'success');
        } else {
            let msg = 'No se pudo cancelar la descarga.';
            if (currentLanguage === 'en') msg = 'Could not cancel download.';
            else if (currentLanguage === 'pt') msg = 'Não foi possível cancelar o download.';
            showToast(msg, 'error');
        }
    } catch (err) {
        console.error('Error cancelling worker:', err);
        let msg = 'Error al intentar cancelar la descarga.';
        if (currentLanguage === 'en') msg = 'Error trying to cancel download.';
        else if (currentLanguage === 'pt') msg = 'Erro ao tentar cancelar o download.';
        showToast(msg, 'error');
    } finally {
        pollState();
    }
}

async function removePendingTask(url) {
    const confirmTitle = getTranslation('web_confirm_title', 'Confirmar Acción');
    const confirmMsg = getTranslation('web_confirm_remove', '¿Eliminar este video de la cola?');
    if (!await showConfirm(confirmTitle, confirmMsg, 'warning')) return;
    try {
        const response = await fetch('/api/downloads/remove-pending', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url })
        });
        const res = await response.json();
        if (res.success) {
            let msg = 'Tarea eliminada de la cola.';
            if (currentLanguage === 'en') msg = 'Task removed from queue.';
            else if (currentLanguage === 'pt') msg = 'Tarefa removida da fila.';
            showToast(msg, 'success');
        } else {
            let msg = 'No se pudo eliminar la tarea.';
            if (currentLanguage === 'en') msg = 'Could not remove task.';
            else if (currentLanguage === 'pt') msg = 'Não foi possível remover a tarefa.';
            showToast(msg, 'error');
        }
    } catch (err) {
        console.error('Error removing pending task:', err);
        let msg = 'Error al intentar eliminar la tarea.';
        if (currentLanguage === 'en') msg = 'Error trying to remove task.';
        else if (currentLanguage === 'pt') msg = 'Erro ao tentar remover a tarefa.';
        showToast(msg, 'error');
    } finally {
        pollState();
    }
}

// WebSocket connection lifecycle
function connectWebSocket() {
    if (socket) {
        socket.close();
    }

    const loc = window.location;
    const protocol = loc.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${loc.host}/api/ws`;

    console.log(`Connecting to WebSocket at ${wsUrl}`);
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        console.log('WebSocket connection established.');
        isWebSocketConnected = true;
        const connEl = document.getElementById('conn-status');
        if (connEl) {
            connEl.className = 'font-medium text-emerald-400';
            connEl.textContent = getTranslation('web_status_conn_ws', 'Conectado (Real-time)');
        }
        
        // Stop REST polling if active
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
        
        if (reconnectTimer) {
            clearTimeout(reconnectTimer);
            reconnectTimer = null;
        }
    };

    socket.onmessage = (event) => {
        try {
            const message = JSON.parse(event.data);
            
            if (message.event === 'state_changed') {
                throttleUpdateUI(message.data);
            } else if (message.event === 'progress') {
                updateTaskProgress(message.data.worker_id, message.data.progress);
            }
        } catch (err) {
            console.error('Error parsing WS message:', err);
        }
    };

    socket.onclose = () => {
        console.warn('WebSocket connection closed. Switching to polling fallback.');
        handleConnectionDrop();
    };

    socket.onerror = (err) => {
        console.error('WebSocket encountered an error:', err);
        socket.close();
    };
}

function handleConnectionDrop() {
    isWebSocketConnected = false;
    const connEl = document.getElementById('conn-status');
    if (connEl) {
        connEl.className = 'font-medium text-amber-500';
        connEl.textContent = getTranslation('web_status_conn_polling', 'Fallback (Polling 3s)');
    }

    // Start Polling Fallback
    if (!pollTimer) {
        pollTimer = setInterval(pollState, 3000);
    }

    // Schedule Reconnection
    if (!reconnectTimer) {
        reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            connectWebSocket();
        }, 5000);
    }
}

// Real-time progress updater for active downloads (avoids full list redrawing)
function updateTaskProgress(workerId, progress) {
    const bar = document.getElementById(`${workerId}-bar`);
    if (!bar) {
        // Card might not exist in the DOM yet, ignore this tick
        return;
    }
    const percentEl = document.getElementById(`${workerId}-percent`);
    const statusEl = document.getElementById(`${workerId}-status`);
    const downloadedEl = document.getElementById(`${workerId}-downloaded`);
    const totalEl = document.getElementById(`${workerId}-total`);
    const speedEl = document.getElementById(`${workerId}-speed`);
    const etaEl = document.getElementById(`${workerId}-eta`);

    const percent = parseFloat(progress.percent || 0).toFixed(1);
    bar.style.width = `${percent}%`;
    percentEl.textContent = `${percent}%`;

    // Status text mapping
    let statusText = getTranslation('status_downloading', 'Descargando...');
    if (progress.status_key === 'status_processing') {
        statusText = getTranslation('status_processing', 'Procesando formatos y fusionando audio/video...');
    } else if (progress.status_key === 'status_retrying') {
        statusText = getTranslation('status_retrying', 'Reintentando...');
    }
    statusEl.textContent = statusText;

    if (downloadedEl) downloadedEl.textContent = formatBytes(progress.downloaded);
    if (totalEl) totalEl.textContent = formatBytes(progress.total);
    if (speedEl) speedEl.textContent = formatSpeed(progress.speed);
    if (etaEl) etaEl.textContent = formatEta(progress.eta);
}

// REST Fallback polling
async function pollState() {
    try {
        const response = await fetch('/api/downloads/status');
        if (!response.ok) throw new Error('API Response Error');
        const state = await response.json();
        updateUI(state);
    } catch (err) {
        console.error('Error polling state:', err);
    }
}

// API command handlers
async function handleAddTask() {
    const urlInput = document.getElementById('task-url');
    const qualitySelect = document.getElementById('task-quality');
    const btnSubmit = document.getElementById('btn-submit');

    const url = urlInput.value.trim();
    const quality = qualitySelect.value;

    if (!url) return;

    // Visual loading
    btnSubmit.disabled = true;
    let submitText = 'Encolando...';
    if (currentLanguage === 'en') submitText = 'Queueing...';
    else if (currentLanguage === 'pt') submitText = 'Enfileirando...';
    btnSubmit.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> ${submitText}`;

    try {
        const response = await fetch('/api/downloads/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, quality })
        });
        
        if (!response.ok) throw new Error('Network response not ok');
        const res = await response.json();

        if (res.success) {
            showToast(getTranslation('web_toast_add_success', 'URL agregada a la cola.'), 'success');
            urlInput.value = '';
            // Fetch logs to show visual progress
            setTimeout(fetchLogs, 1000);
        } else {
            let msg = 'Error encolando descarga';
            if (currentLanguage === 'en') msg = 'Error queueing download';
            else if (currentLanguage === 'pt') msg = 'Erro ao enfileirar o download';
            showToast(msg, 'error');
        }
    } catch (err) {
        console.error('Error adding task:', err);
        let msg = 'Error de red al añadir descarga';
        if (currentLanguage === 'en') msg = 'Network error while adding download';
        else if (currentLanguage === 'pt') msg = 'Erro de rede ao adicionar download';
        showToast(msg, 'error');
    } finally {
        btnSubmit.disabled = false;
        btnSubmit.innerHTML = `<i class="fa-solid fa-plus"></i> ${getTranslation('web_start_download', 'Iniciar Descarga')}`;
        pollState();
    }
}

async function togglePauseQueue() {
    try {
        const response = await fetch('/api/downloads/pause', { method: 'POST' });
        const res = await response.json();
        if (res.success) {
            let msg = '';
            if (res.paused) {
                if (currentLanguage === 'en') msg = 'Queued downloads paused.';
                else if (currentLanguage === 'pt') msg = 'Downloads na fila pausados.';
                else msg = 'Descargas en cola pausadas.';
            } else {
                if (currentLanguage === 'en') msg = 'Resuming queued downloads.';
                else if (currentLanguage === 'pt') msg = 'Retomando downloads na fila.';
                else msg = 'Reanudando descargas en cola.';
            }
            showToast(msg, 'info');
        }
    } catch (err) {
        console.error('Error toggling pause:', err);
        let msg = 'Error de red al pausar cola';
        if (currentLanguage === 'en') msg = 'Network error while pausing queue';
        else if (currentLanguage === 'pt') msg = 'Erro de rede ao pausar fila';
        showToast(msg, 'error');
    } finally {
        pollState();
    }
}

async function cancelAllDownloads() {
    const confirmTitle = getTranslation('web_confirm_title', 'Confirmar Acción');
    const confirmMsg = getTranslation('web_confirm_clear_queue', '¿Cancelar todas las descargas activas?');
    if (!await showConfirm(confirmTitle, confirmMsg, 'error')) return;
    try {
        const response = await fetch('/api/downloads/cancel', { method: 'POST' });
        const res = await response.json();
        if (res.success) {
            let msg = 'Todas las descargas han sido canceladas.';
            if (currentLanguage === 'en') msg = 'All downloads have been cancelled.';
            else if (currentLanguage === 'pt') msg = 'Todos os downloads foram cancelados.';
            showToast(msg, 'error');
        }
    } catch (err) {
        console.error('Error canceling downloads:', err);
        let msg = 'Error de red al cancelar descargas';
        if (currentLanguage === 'en') msg = 'Network error while cancelling downloads';
        else if (currentLanguage === 'pt') msg = 'Erro de rede ao cancelar downloads';
        showToast(msg, 'error');
    } finally {
        pollState();
    }
}

async function clearHistory() {
    const confirmTitle = getTranslation('web_confirm_title', 'Confirmar Acción');
    const confirmMsg = getTranslation('web_confirm_clear_history', '¿Limpiar el historial de descargas completadas?');
    if (!await showConfirm(confirmTitle, confirmMsg, 'warning')) return;
    try {
        const response = await fetch('/api/downloads/clear', { method: 'POST' });
        const res = await response.json();
        if (res.success) {
            let msg = 'Historial limpiado correctamente.';
            if (currentLanguage === 'en') msg = 'History cleared successfully.';
            else if (currentLanguage === 'pt') msg = 'Histórico limpo com sucesso.';
            showToast(msg, 'success');
        }
    } catch (err) {
        console.error('Error clearing history:', err);
        let msg = 'Error de red al limpiar historial';
        if (currentLanguage === 'en') msg = 'Network error while clearing history';
        else if (currentLanguage === 'pt') msg = 'Erro de rede ao limpar histórico';
        showToast(msg, 'error');
    } finally {
        pollState();
    }
}

async function clearQueue() {
    const confirmTitle = getTranslation('web_confirm_title', 'Confirmar Acción');
    const confirmMsg = getTranslation('web_confirm_clear_queue', '¿Cancelar todas las descargas activas y vaciar la cola de pendientes?');
    if (!await showConfirm(confirmTitle, confirmMsg, 'error')) return;
    try {
        const response = await fetch('/api/downloads/clear-queue', { method: 'POST' });
        const res = await response.json();
        if (res.success) {
            showToast(getTranslation('clear_queue_done', 'Cola de descargas limpiada.'), 'success');
        }
    } catch (err) {
        console.error('Error clearing queue:', err);
        let msg = 'Error al limpiar la cola';
        if (currentLanguage === 'en') msg = 'Error while clearing queue';
        else if (currentLanguage === 'pt') msg = 'Erro ao limpar a fila';
        showToast(msg, 'error');
    } finally {
        pollState();
    }
}

// ==========================================
// Web Integrated Folder Browser Logic
// ==========================================

let browserSelectedPath = '';

async function browseFolderWeb() {
    openFolderBrowser();
}

function openFolderBrowser() {
    const modal = document.getElementById('folder-browser-modal');
    modal.classList.add('modal-active');
    
    // Get the current path from settings input
    let currentPath = document.getElementById('setting-folder').value.trim();
    loadFileSystemPath(currentPath);
}

function closeFolderBrowser() {
    const modal = document.getElementById('folder-browser-modal');
    modal.classList.remove('modal-active');
}

async function loadFileSystemPath(path) {
    const folderList = document.getElementById('browser-folder-list');
    const pathInput = document.getElementById('browser-current-path');
    const driveContainer = document.getElementById('browser-drive-container');
    const driveSelect = document.getElementById('browser-drive-select');
    
    let loadingText = 'Cargando directorios...';
    if (currentLanguage === 'en') loadingText = 'Loading directories...';
    else if (currentLanguage === 'pt') loadingText = 'Carregando diretórios...';
    folderList.innerHTML = `<div class="col-span-2 text-center text-slate-500 text-xs py-12"><i class="fa-solid fa-spinner fa-spin mr-1 text-violet-400"></i> ${loadingText}</div>`;
    
    try {
        let url = '/api/filesystem/browse';
        if (path) {
            url += `?path=${encodeURIComponent(path)}`;
        }
        
        const response = await fetch(url);
        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || 'Error al leer directorios');
        }
        
        const data = await response.json();
        
        browserSelectedPath = data.current_path;
        pathInput.value = data.current_path;
        
        // Render drives if available (Windows)
        if (data.drives && data.drives.length > 0) {
            driveContainer.classList.remove('hidden');
            driveSelect.innerHTML = '';
            data.drives.forEach(drive => {
                const opt = document.createElement('option');
                opt.value = drive;
                opt.textContent = drive;
                if (data.current_path.toUpperCase().startsWith(drive.toUpperCase())) {
                    opt.selected = true;
                }
                driveSelect.appendChild(opt);
            });
        } else {
            driveContainer.classList.add('hidden');
        }
        
        // Render folder contents
        folderList.innerHTML = '';
        if (data.directories.length === 0) {
            let emptyText = 'Esta carpeta está vacía o no tiene subdirectorios.';
            if (currentLanguage === 'en') emptyText = 'This folder is empty or has no subdirectories.';
            else if (currentLanguage === 'pt') emptyText = 'Esta pasta está vazia ou não possui subdiretórios.';
            folderList.innerHTML = `<div class="col-span-2 text-center text-slate-500 text-xs py-12">${emptyText}</div>`;
        } else {
            data.directories.forEach(dir => {
                const item = document.createElement('div');
                item.className = 'folder-item-card p-3 flex items-center gap-3';
                item.setAttribute('data-path', dir.path);
                
                // Double click to enter folder
                item.addEventListener('dblclick', () => {
                    loadFileSystemPath(dir.path);
                });
                
                // Single click to highlight/select path
                item.addEventListener('click', () => {
                    // Remove highlight from others
                    folderList.querySelectorAll('.folder-item-card').forEach(el => {
                        el.classList.remove('border-violet-500/50', 'bg-violet-600/5');
                    });
                    item.classList.add('border-violet-500/50', 'bg-violet-600/5');
                    browserSelectedPath = dir.path;
                    pathInput.value = dir.path;
                });
                
                item.innerHTML = `
                    <div class="w-8 h-8 rounded-lg bg-violet-600/10 border border-violet-500/10 flex items-center justify-center text-violet-400">
                        <i class="fa-solid fa-folder text-sm"></i>
                    </div>
                    <span class="text-xs font-semibold text-slate-200 truncate flex-1">${dir.name}</span>
                `;
                folderList.appendChild(item);
            });
        }
    } catch (err) {
        console.error('Error browsing filesystem:', err);
        let errorText = err.message || 'Error al cargar carpeta';
        folderList.innerHTML = `<div class="col-span-2 text-center text-rose-400 text-xs py-12"><i class="fa-solid fa-triangle-exclamation mr-1"></i> ${errorText}</div>`;
    }
}

// Enter folder directly when pressing enter in the path bar
setTimeout(() => {
    const pathInput = document.getElementById('browser-current-path');
    if (pathInput) {
        pathInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                loadFileSystemPath(e.target.value.trim());
            }
        });
    }
}, 500);

function handleDriveChange() {
    const driveSelect = document.getElementById('browser-drive-select');
    loadFileSystemPath(driveSelect.value);
}

async function navigateFolderUp() {
    const pathInput = document.getElementById('browser-current-path');
    try {
        const response = await fetch(`/api/filesystem/browse?path=${encodeURIComponent(pathInput.value)}`);
        if (response.ok) {
            const data = await response.json();
            if (data.parent_path) {
                loadFileSystemPath(data.parent_path);
            } else {
                let msg = 'Ya estás en la raíz del disco.';
                if (currentLanguage === 'en') msg = 'You are already at the root directory.';
                else if (currentLanguage === 'pt') msg = 'Você já está na raiz do disco.';
                showToast(msg, 'info');
            }
        }
    } catch (err) {
        console.error('Error navigating up:', err);
    }
}

function confirmFolderSelection() {
    if (browserSelectedPath) {
        document.getElementById('setting-folder').value = browserSelectedPath;
        let msg = 'Carpeta seleccionada: ';
        if (currentLanguage === 'en') msg = 'Selected folder: ';
        else if (currentLanguage === 'pt') msg = 'Pasta selecionada: ';
        showToast(msg + browserSelectedPath, 'success');
        closeFolderBrowser();
    }
}

// New folder modals
function openNewFolderPrompt() {
    document.getElementById('new-folder-modal').classList.add('modal-active');
    document.getElementById('new-folder-name').value = '';
    document.getElementById('new-folder-name').focus();
}

function closeNewFolderPrompt() {
    document.getElementById('new-folder-modal').classList.remove('modal-active');
}

async function submitNewFolder() {
    const nameInput = document.getElementById('new-folder-name');
    const folderName = nameInput.value.trim();
    if (!folderName) {
        let msg = 'El nombre de la carpeta no puede estar vacío.';
        if (currentLanguage === 'en') msg = 'Folder name cannot be empty.';
        else if (currentLanguage === 'pt') msg = 'O nome da pasta não pode estar vazio.';
        showToast(msg, 'error');
        return;
    }
    
    const parentPath = document.getElementById('browser-current-path').value.trim();
    try {
        const response = await fetch('/api/filesystem/create-folder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ parent_path: parentPath, folder_name: folderName })
        });
        
        const res = await response.json();
        if (response.ok && res.success) {
            let msg = 'Carpeta creada con éxito.';
            if (currentLanguage === 'en') msg = 'Folder created successfully.';
            else if (currentLanguage === 'pt') msg = 'Pasta criada com sucesso.';
            showToast(msg, 'success');
            closeNewFolderPrompt();
            loadFileSystemPath(parentPath); // refresh folder list
        } else {
            showToast(res.detail || 'Error al crear carpeta.', 'error');
        }
    } catch (err) {
        console.error('Error creating folder:', err);
        let msg = 'Error al crear carpeta.';
        if (currentLanguage === 'en') msg = 'Error creating folder.';
        else if (currentLanguage === 'pt') msg = 'Erro ao criar pasta.';
        showToast(msg, 'error');
    }
}

// Settings handlers
async function updateCookiesStatus() {
    const statusSpan = document.getElementById('cookie-file-status');
    if (!statusSpan) return;
    try {
        const response = await fetch('/api/config/cookies/status');
        if (!response.ok) return;
        const status = await response.json();
        
        let activeLabel = 'Activo';
        let pendingLabel = 'Pendiente';
        let noFileLabel = 'Sin archivo';
        
        if (currentLanguage === 'en') {
            activeLabel = 'Active';
            pendingLabel = 'Pending';
            noFileLabel = 'No file';
        } else if (currentLanguage === 'pt') {
            activeLabel = 'Ativo';
            pendingLabel = 'Pendente';
            noFileLabel = 'Sem arquivo';
        }

        if (status.cookies_txt) {
            statusSpan.innerText = `🟢 ${activeLabel} (cookies.txt)`;
            statusSpan.className = 'text-xs text-emerald-400 font-semibold';
        } else if (status.cookies_json) {
            statusSpan.innerText = `🟡 ${pendingLabel} (cookies.json)`;
            statusSpan.className = 'text-xs text-amber-400 font-semibold';
        } else {
            statusSpan.innerText = `🔴 ${noFileLabel}`;
            statusSpan.className = 'text-xs text-rose-400 font-semibold';
        }
    } catch (err) {
        console.error('Error fetching cookie status:', err);
    }
}

async function uploadCookieFile() {
    const fileInput = document.getElementById('cookie-file-input');
    if (!fileInput.files.length) return;
    
    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch('/api/config/cookies', {
            method: 'POST',
            body: formData
        });
        const res = await response.json();
        
        if (response.ok && res.success) {
            showToast(res.message, 'success');
        } else {
            let msg = 'Error al subir archivo de cookies.';
            if (currentLanguage === 'en') msg = 'Error uploading cookies file.';
            else if (currentLanguage === 'pt') msg = 'Erro ao carregar arquivo de cookies.';
            showToast(res.error || msg, 'error');
        }
        updateCookiesStatus();
        fetchLogs();
    } catch (err) {
        console.error('Error uploading cookie file:', err);
        let msg = 'Error al subir archivo de cookies.';
        if (currentLanguage === 'en') msg = 'Error uploading cookies file.';
        else if (currentLanguage === 'pt') msg = 'Erro ao carregar arquivo de cookies.';
        showToast(msg, 'error');
    } finally {
        fileInput.value = ''; // Reset input
    }
}

async function loadSettings() {
    try {
        const response = await fetch('/api/config');
        if (!response.ok) return;
        const config = await response.json();
        
        document.getElementById('setting-folder').value = config.download_folder || '';
        document.getElementById('setting-mix-limit').value = config.mix_max_videos || 100;
        document.getElementById('setting-lang').value = config.language || 'es';
        document.getElementById('setting-cookies').value = config.cookies_browser || 'none';
        
        currentLanguage = config.language || 'es';
        applyTranslations(currentLanguage);
        updateCookiesStatus();
    } catch (err) {
        console.error('Error loading config:', err);
    }
}

async function saveSettings() {
    const downloadFolder = document.getElementById('setting-folder').value.trim();
    const mixLimit = parseInt(document.getElementById('setting-mix-limit').value) || 100;
    const lang = document.getElementById('setting-lang').value;
    const cookiesBrowser = document.getElementById('setting-cookies').value;

    const payload = {
        download_folder: downloadFolder,
        mix_max_videos: mixLimit,
        language: lang,
        cookies_browser: cookiesBrowser
    };

    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        if (res.success) {
            const statusLabel = document.getElementById('settings-save-status');
            statusLabel.className = 'text-xs text-emerald-400 opacity-100 transition-opacity duration-300';
            setTimeout(() => {
                statusLabel.className = 'text-xs text-emerald-400 opacity-0 transition-opacity duration-300';
            }, 2000);
            showToast(getTranslation('web_toast_save_success', 'Configuración guardada.'), 'success');
            loadSettings();
        }
    } catch (err) {
        console.error('Error saving config:', err);
        showToast(getTranslation('web_toast_save_error', 'Error guardando configuración'), 'error');
    }
}

// Custom Confirmation Modal Logic
let confirmPromiseResolve = null;

function showConfirm(title, message, iconType = 'warning') {
    const modal = document.getElementById('confirm-modal');
    const titleEl = document.getElementById('confirm-modal-title');
    const messageEl = document.getElementById('confirm-modal-message');
    const iconEl = document.getElementById('confirm-modal-icon');
    const iconBg = document.getElementById('confirm-modal-icon-bg');
    
    titleEl.textContent = title;
    messageEl.textContent = message;
    
    // Icon and colors
    iconBg.className = 'w-10 h-10 rounded-xl flex items-center justify-center shrink-0 border';
    if (iconType === 'error') {
        iconBg.classList.add('bg-rose-500/20', 'border-rose-500/30', 'text-rose-400');
        iconEl.className = 'fa-solid fa-ban text-lg';
    } else if (iconType === 'info') {
        iconBg.classList.add('bg-blue-500/20', 'border-blue-500/30', 'text-blue-400');
        iconEl.className = 'fa-solid fa-circle-info text-lg';
    } else { // warning
        iconBg.classList.add('bg-amber-500/20', 'border-amber-500/30', 'text-amber-400');
        iconEl.className = 'fa-solid fa-triangle-exclamation text-lg';
    }
    
    modal.classList.add('modal-active');
    
    return new Promise((resolve) => {
        confirmPromiseResolve = resolve;
    });
}

function handleConfirmResult(value) {
    const modal = document.getElementById('confirm-modal');
    modal.classList.remove('modal-active');
    if (confirmPromiseResolve) {
        confirmPromiseResolve(value);
        confirmPromiseResolve = null;
    }
}

function closeConfirmModal() {
    handleConfirmResult(false);
}

// Fetch logs and output to terminal log box
async function fetchLogs() {
    const terminal = document.getElementById('terminal-logs');
    try {
        const response = await fetch('/api/logs');
        if (!response.ok) return;
        const data = await response.json();
        
        // Strip out ansi color codes or formatting if any, parse linebreaks
        const formattedLogs = data.logs.replace(/[\u001b\u009b][[()#;?]*(?:[0-9]{1,4}(?:;[0-9]{0,4})*)?[0-9A-ORZcf-nqry=><]/g, '');
        terminal.innerText = formattedLogs;
        
        // Scroll terminal to bottom
        terminal.scrollTop = terminal.scrollHeight;
    } catch (err) {
        let msg = 'Error al actualizar los logs del sistema.';
        if (currentLanguage === 'en') msg = 'Error refreshing system logs.';
        else if (currentLanguage === 'pt') msg = 'Erro ao atualizar os logs do sistema.';
        terminal.innerText = msg;
    }
}

// Initialize Page
window.addEventListener('DOMContentLoaded', () => {
    loadSettings();
    pollState();
    connectWebSocket();
    updateCookiesStatus();
    
    // Setup language dropdown event listener for live translation
    const langSelect = document.getElementById('setting-lang');
    if (langSelect) {
        langSelect.addEventListener('change', (e) => {
            applyTranslations(e.target.value);
        });
    }
    
    // Setup confirm modal action listener
    const btnConfirmOk = document.getElementById('btn-confirm-ok');
    if (btnConfirmOk) {
        btnConfirmOk.addEventListener('click', () => handleConfirmResult(true));
    }
    
    // Setup Drag & Drop Cookie Upload Zone
    const dropZone = document.getElementById('cookie-drop-zone');
    if (dropZone) {
        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.add('dragover');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.remove('dragover');
            }, false);
        });

        dropZone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files && files.length > 0) {
                const fileInput = document.getElementById('cookie-file-input');
                fileInput.files = files; // Assign files to input
                uploadCookieFile(); // Trigger upload
            }
        }, false);
    }
    
    // Fetch logs every 5 seconds
    fetchLogs();
    setInterval(fetchLogs, 5000);
});
