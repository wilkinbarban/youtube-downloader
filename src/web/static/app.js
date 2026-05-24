// YouTube Downloader Web App Client Logic

let socket = null;
let reconnectTimer = null;
let pollTimer = null;
let isWebSocketConnected = false;
let currentLanguage = 'es';

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
        pauseText.textContent = 'Reanudar Todo';
    } else {
        pauseIcon.className = 'fa-solid fa-pause text-yellow-400';
        pauseText.textContent = 'Pausar Todo';
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
            const statusBadge = isSuccess 
                ? '<span class="px-2 py-0.5 rounded-full bg-emerald-950/40 text-emerald-400 border border-emerald-500/20 font-medium">Completado</span>'
                : entry.status === 'cancelled'
                    ? '<span class="px-2 py-0.5 rounded-full bg-slate-950/40 text-slate-400 border border-slate-500/20 font-medium">Cancelado</span>'
                    : '<span class="px-2 py-0.5 rounded-full bg-rose-950/40 text-rose-400 border border-rose-500/20 font-medium">Fallo</span>';

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
            <td colspan="4" class="p-8 text-center text-slate-500 text-xs">
                El historial de descargas está vacío.
            </td>
        `;
        historyRows.appendChild(emptyRow);
    }
}function createActiveCard(workerId, dl) {
    const card = document.createElement('div');
    const progress = dl.progress || {};
    const percent = parseFloat(progress.percent || 0).toFixed(1);
    
    // Status text mapping
    let statusText = 'Descargando...';
    let leftBorderClass = 'border-l-4 border-l-cyan-500';
    if (progress.status_key === 'status_processing') {
        statusText = 'Procesando formatos y fusionando audio/video...';
        leftBorderClass = 'border-l-4 border-l-fuchsia-500';
    }

    card.className = `glass-card p-5 download-card hover-scale relative overflow-hidden bg-slate-900/40 ${leftBorderClass} animate-slide-in`;
    card.setAttribute('data-worker-id', workerId);

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
                <span id="${workerId}-downloaded">${formatBytes(progress.downloaded)}</span> de <span id="${workerId}-total">${formatBytes(progress.total)}</span>
            </div>
            <div class="text-center">
                <i class="fa-solid fa-gauge-high text-slate-500 mr-1"></i> 
                <span id="${workerId}-speed">${formatSpeed(progress.speed)}</span>
            </div>
            <div class="text-right">
                <i class="fa-solid fa-hourglass-half text-slate-500 mr-1"></i> 
                <span>Restante: <span id="${workerId}-eta">${formatEta(progress.eta)}</span></span>
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
                    <span class="text-slate-500 text-xs mr-1">[En cola #${index}]</span> ${task.title || task.url}
                </h3>
                <p class="text-xs text-slate-500 mt-0.5 flex items-center gap-1.5">
                    <span class="px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 text-[10px] font-bold border border-white/5 uppercase">${task.quality}</span>
                    <span>•</span>
                    <span>Pendiente para descargar</span>
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
    if (!await showConfirm('¿Cancelar Descarga?', '¿Estás seguro de que deseas cancelar esta descarga activa?', 'warning')) return;
    try {
        const response = await fetch(`/api/downloads/${encodeURIComponent(workerId)}/cancel`, { method: 'POST' });
        const res = await response.json();
        if (res.success) {
            showToast('Descarga cancelada.', 'success');
        } else {
            showToast('No se pudo cancelar la descarga.', 'error');
        }
    } catch (err) {
        console.error('Error cancelling worker:', err);
        showToast('Error al intentar cancelar la descarga.', 'error');
    } finally {
        pollState();
    }
}

async function removePendingTask(url) {
    if (!await showConfirm('¿Quitar de la Cola?', '¿Estás seguro de que deseas eliminar esta tarea de la cola de pendientes?', 'warning')) return;
    try {
        const response = await fetch('/api/downloads/remove-pending', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url })
        });
        const res = await response.json();
        if (res.success) {
            showToast('Tarea eliminada de la cola.', 'success');
        } else {
            showToast('No se pudo eliminar la tarea.', 'error');
        }
    } catch (err) {
        console.error('Error removing pending task:', err);
        showToast('Error al intentar eliminar la tarea.', 'error');
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
        document.getElementById('conn-status').className = 'font-medium text-emerald-400';
        document.getElementById('conn-status').textContent = 'Conectado (Real-time)';
        
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
                updateUI(message.data);
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
    document.getElementById('conn-status').className = 'font-medium text-amber-500';
    document.getElementById('conn-status').textContent = 'Fallback (Polling 3s)';

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
    let statusText = 'Descargando...';
    if (progress.status_key === 'status_processing') {
        statusText = 'Procesando formatos y fusionando audio/video...';
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
    btnSubmit.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Encolando...';

    try {
        const response = await fetch('/api/downloads/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, quality })
        });
        
        if (!response.ok) throw new Error('Network response not ok');
        const res = await response.json();

        if (res.success) {
            showToast('Extrayendo videos y añadiendo a la cola en segundo plano...', 'success');
            urlInput.value = '';
            // Fetch logs to show visual progress
            setTimeout(fetchLogs, 1000);
        } else {
            showToast('Error encolando descarga', 'error');
        }
    } catch (err) {
        console.error('Error adding task:', err);
        showToast('Error de red al añadir descarga', 'error');
    } finally {
        btnSubmit.disabled = false;
        btnSubmit.innerHTML = '<i class="fa-solid fa-plus"></i> Iniciar Descarga';
        pollState();
    }
}

async function togglePauseQueue() {
    try {
        const response = await fetch('/api/downloads/pause', { method: 'POST' });
        const res = await response.json();
        if (res.success) {
            showToast(res.paused ? 'Descargas en cola pausadas.' : 'Reanudando descargas en cola.', 'info');
        }
    } catch (err) {
        console.error('Error toggling pause:', err);
        showToast('Error de red al pausar cola', 'error');
    } finally {
        pollState();
    }
}

async function cancelAllDownloads() {
    if (!await showConfirm('¿Cancelar Todo?', '¿Estás seguro de que deseas cancelar todas las descargas activas?', 'error')) return;
    try {
        const response = await fetch('/api/downloads/cancel', { method: 'POST' });
        const res = await response.json();
        if (res.success) {
            showToast('Todas las descargas han sido canceladas.', 'error');
        }
    } catch (err) {
        console.error('Error canceling downloads:', err);
        showToast('Error de red al cancelar descargas', 'error');
    } finally {
        pollState();
    }
}

async function clearHistory() {
    try {
        const response = await fetch('/api/downloads/clear', { method: 'POST' });
        const res = await response.json();
        if (res.success) {
            showToast('Historial limpiado correctamente.', 'success');
        }
    } catch (err) {
        console.error('Error clearing history:', err);
        showToast('Error de red al limpiar historial', 'error');
    } finally {
        pollState();
    }
}

async function clearQueue() {
    if (!await showConfirm('¿Limpiar Lista?', '¿Cancelar todas las descargas activas y vaciar la cola de pendientes?', 'error')) return;
    try {
        const response = await fetch('/api/downloads/clear-queue', { method: 'POST' });
        const res = await response.json();
        if (res.success) {
            showToast('Cola de descargas limpiada.', 'success');
        }
    } catch (err) {
        console.error('Error clearing queue:', err);
        showToast('Error al limpiar la cola', 'error');
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
    
    folderList.innerHTML = '<div class="col-span-2 text-center text-slate-500 text-xs py-12"><i class="fa-solid fa-spinner fa-spin mr-1 text-violet-400"></i> Cargando directorios...</div>';
    
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
            folderList.innerHTML = '<div class="col-span-2 text-center text-slate-500 text-xs py-12">Esta carpeta está vacía o no tiene subdirectorios.</div>';
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
        folderList.innerHTML = `<div class="col-span-2 text-center text-rose-400 text-xs py-12"><i class="fa-solid fa-triangle-exclamation mr-1"></i> ${err.message || 'Error al cargar carpeta'}</div>`;
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
                showToast('Ya estás en la raíz del disco.', 'info');
            }
        }
    } catch (err) {
        console.error('Error navigating up:', err);
    }
}

function confirmFolderSelection() {
    if (browserSelectedPath) {
        document.getElementById('setting-folder').value = browserSelectedPath;
        showToast('Carpeta seleccionada: ' + browserSelectedPath, 'success');
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
        showToast('El nombre de la carpeta no puede estar vacío.', 'error');
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
            showToast('Carpeta creada con éxito.', 'success');
            closeNewFolderPrompt();
            loadFileSystemPath(parentPath); // refresh folder list
        } else {
            showToast(res.detail || 'Error al crear carpeta.', 'error');
        }
    } catch (err) {
        console.error('Error creating folder:', err);
        showToast('Error al crear carpeta.', 'error');
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
        
        if (status.cookies_txt) {
            statusSpan.innerText = '🟢 Activo (cookies.txt)';
            statusSpan.className = 'text-xs text-emerald-400 font-semibold';
        } else if (status.cookies_json) {
            statusSpan.innerText = '🟡 Pendiente (cookies.json)';
            statusSpan.className = 'text-xs text-amber-400 font-semibold';
        } else {
            statusSpan.innerText = '🔴 Sin archivo';
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
            showToast(res.error || 'Error al subir archivo de cookies.', 'error');
        }
        updateCookiesStatus();
        fetchLogs();
    } catch (err) {
        console.error('Error uploading cookie file:', err);
        showToast('Error al subir archivo de cookies.', 'error');
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
            showToast('Configuración guardada.', 'success');
            loadSettings();
        }
    } catch (err) {
        console.error('Error saving config:', err);
        showToast('Error guardando configuración', 'error');
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
        terminal.innerText = 'Error al actualizar los logs del sistema.';
    }
}

// Initialize Page
window.addEventListener('DOMContentLoaded', () => {
    loadSettings();
    pollState();
    connectWebSocket();
    updateCookiesStatus();
    
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
