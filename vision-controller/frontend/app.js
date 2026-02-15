// Vision Controller Frontend App
// Handles camera, gesture overlay, and config UI

let gestureConfig = {};
let currentGesture = null;
let currentConfidence = 0;
let wsClient = null;
let captureInterval = null;
let gestureHistory = [];
const MAX_HISTORY_ENTRIES = 20;
let historyRenderTimeout = null;
let pendingGestureUpdate = null;
let gestureUpdateRafScheduled = false;
const BACKEND_HTTP_URL = 'http://127.0.0.1:9000';
const BACKEND_WS_URL = 'ws://127.0.0.1:9000/ws/gestures';

// Initialize app
async function init() {
    console.log('Vision Controller initializing...');
    
    // Load gesture config
    await loadGestureConfig();
    
    // Load gesture history from localStorage
    loadGestureHistory();
    
    // Initialize camera
    initCamera();
    
    // Check backend connection
    checkBackendStatus();
    setInterval(checkBackendStatus, 5000);
}

// Load gesture configuration
async function loadGestureConfig() {
    try {
        // In production, this would fetch from backend
        // For now, load from local config
        const response = await fetch('../config/gestures.json');
        if (response.ok) {
            gestureConfig = await response.json();
            renderGestureConfig();
            console.log('Gesture config loaded:', Object.keys(gestureConfig).length, 'gestures');
        }
    } catch (error) {
        console.error('Failed to load gesture config:', error);
        // Use default config
        gestureConfig = {
            peace: { action: 'applescript', description: 'Default action' },
            thumbs_up: { action: 'openclaw_rpc', description: 'Default action' },
            fist: { action: 'keyboard', description: 'Default action' },
            point: { action: 'applescript', description: 'Default action' },
            stop: { action: 'keyboard', description: 'Default action' }
        };
        renderGestureConfig();
    }
}

// Render gesture configuration list
function renderGestureConfig() {
    const listEl = document.getElementById('gesture-config-list');
    listEl.innerHTML = '';
    
    for (const [gesture, config] of Object.entries(gestureConfig)) {
        const item = document.createElement('div');
        item.className = 'gesture-config-item';
        item.innerHTML = `
            <div class="gesture-header">
                <span class="gesture-name">${gesture}</span>
                <button class="edit-btn" onclick="openEditModal('${gesture}')">Edit</button>
            </div>
            <div class="gesture-action">${config.description || 'No description'}</div>
        `;
        listEl.appendChild(item);
    }
}

// Initialize camera
async function initCamera() {
    const video = document.getElementById('camera');
    const statusEl = document.getElementById('camera-status');
    
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ 
            video: { width: 640, height: 480 } 
        });
        video.srcObject = stream;
        
        statusEl.className = 'status-pill connected';
        statusEl.querySelector('span:last-child').textContent = 'Active';
        
        console.log('Camera initialized');
        
        // Initialize overlay canvas
        initOverlay();
    } catch (error) {
        console.error('Camera error:', error);
        statusEl.className = 'status-pill disconnected';
        statusEl.querySelector('span:last-child').textContent = 'Failed';
    }
}

// Initialize gesture overlay
function initOverlay() {
    const canvas = document.getElementById('gesture-overlay');
    const video = document.getElementById('camera');
    canvas.width = video.clientWidth;
    canvas.height = video.clientHeight;
    
    // Initialize WebSocket connection
    initWebSocket();
    
    // Start frame capture at 10 FPS
    startFrameCapture();
}

// Initialize WebSocket connection to backend
function initWebSocket() {
    wsClient = new GestureWebSocketClient(BACKEND_WS_URL);
    
    wsClient.onConnected = () => {
        console.log('WebSocket connected to backend');
        const statusEl = document.getElementById('backend-status');
        statusEl.className = 'status-pill connected';
        statusEl.querySelector('span:last-child').textContent = 'Connected';
    };
    
    wsClient.onDisconnected = () => {
        console.log('WebSocket disconnected');
        const statusEl = document.getElementById('backend-status');
        statusEl.className = 'status-pill disconnected';
        statusEl.querySelector('span:last-child').textContent = 'Disconnected';
    };
    
    wsClient.onGestureUpdate = (data) => {
        const seq = data.sequence || 0;
        if (seq > 0) {
            if (seq < lastRenderedSequence) {
                return;
            }
            lastRenderedSequence = seq;
            if (seq > lastProcessedSequence) {
                lastProcessedSequence = seq;
            }
        }

        pendingGestureUpdate = {
            gesture: data.gesture,
            confidence: data.confidence,
            hand: data.hand || data.handedness || 'unknown',
            processingTime: data.processing_time_ms || data.processing_time || 0
        };

        // Collapse many inbound socket updates into one DOM update/frame.
        if (!gestureUpdateRafScheduled) {
            gestureUpdateRafScheduled = true;
            requestAnimationFrame(() => {
                if (pendingGestureUpdate) {
                    updateGestureDisplay(
                        pendingGestureUpdate.gesture,
                        pendingGestureUpdate.confidence,
                        pendingGestureUpdate.hand,
                        pendingGestureUpdate.processingTime
                    );
                }
                pendingGestureUpdate = null;
                gestureUpdateRafScheduled = false;
            });
        }
    };

    wsClient.onFrameAck = (data) => {
        const seq = data.sequence || 0;
        if (seq > lastProcessedSequence) {
            lastProcessedSequence = seq;
        }
    };
    
    wsClient.onError = (error) => {
        console.error('WebSocket error:', error);
    };
    
    wsClient.connect();
}

// Start capturing and sending frames - FLUSH STALE RESULTS
let frameSequence = 0;
let lastProcessedSequence = 0;
let lastRenderedSequence = 0;
const MAX_IN_FLIGHT_FRAMES = 2;

function startFrameCapture() {
    const video = document.getElementById('camera');
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    
    // Set canvas size smaller for faster processing
    canvas.width = 320;
    canvas.height = 240;
    
    let lastFrameTime = 0;
    const minFrameInterval = 50; // 20 FPS
    let frameCount = 0;
    let fpsStartTime = Date.now();
    
    function captureFrame(timestamp) {
        const now = performance.now();
        
        // Send frames continuously, let sequence numbers handle ordering
        if (now - lastFrameTime >= minFrameInterval) {
            if (video.readyState === video.HAVE_ENOUGH_DATA && wsClient && wsClient.ws && wsClient.ws.readyState === WebSocket.OPEN) {
                const inFlightFrames = frameSequence - lastProcessedSequence;
                if (inFlightFrames > MAX_IN_FLIGHT_FRAMES) {
                    captureInterval = requestAnimationFrame(captureFrame);
                    return;
                }

                // Draw video frame to canvas (downscaled for speed)
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                
                // Convert to base64 JPEG (quality 0.5 for better recognition)
                const base64Data = canvas.toDataURL('image/jpeg', 0.5);
                
                // Send with sequence number
                frameSequence++;
                wsClient.sendFrame(base64Data, frameSequence);
                
                lastFrameTime = now;
                frameCount++;
                
                // Log FPS every 2 seconds
                const elapsed = Date.now() - fpsStartTime;
                if (elapsed >= 2000) {
                    const actualFPS = Math.round((frameCount / elapsed) * 1000);
                    console.log(`[Capture] FPS: ${actualFPS} | Sent: ${frameSequence} | Processed: ${lastProcessedSequence}`);
                    frameCount = 0;
                    fpsStartTime = Date.now();
                }
            }
        }
        
        // Continue animation loop
        captureInterval = requestAnimationFrame(captureFrame);
    }
    
    // Start the animation loop
    captureInterval = requestAnimationFrame(captureFrame);
    console.log('[Capture] Frame capture started with SEQUENCE-BASED queue flushing');
}

// Stop frame capture (cleanup)
function stopFrameCapture() {
    if (captureInterval) {
        cancelAnimationFrame(captureInterval);
        captureInterval = null;
        console.log('Frame capture stopped');
    }
}

// Update gesture overlay display - RELIABLE, IMMEDIATE
function updateGestureDisplay(gesture, confidence, hand = 'unknown', processingTime = 0) {
    // Get DOM elements directly each time (avoid stale references)
    const overlayEl = document.getElementById('overlay-display');
    const textEl = document.getElementById('gesture-text');
    const barEl = document.getElementById('confidence-bar');
    
    if (!overlayEl || !textEl || !barEl) {
        console.error('[UI] DOM elements not found!');
        return;
    }
    
    currentGesture = gesture;
    currentConfidence = confidence;
    
    // Update for valid gestures
    if (gesture && gesture !== 'unknown' && confidence > 0) {
        const confidencePct = Math.round(confidence * 100);
        overlayEl.style.display = 'block';
        overlayEl.style.opacity = '1';
        textEl.textContent = `${gesture} (${confidencePct}%) - ${hand} hand`;
        barEl.style.width = `${confidencePct}%`;
        barEl.style.transition = 'width 0.1s';
        
        // Update class based on confidence
        let className = 'overlay-text ';
        if (confidence >= 0.8) {
            className += 'high-confidence';
        } else if (confidence >= 0.6) {
            className += 'medium-confidence';
        } else {
            className += 'low-confidence';
        }
        overlayEl.className = className;

        // Add to history
        addToHistory(gesture, confidence, hand, processingTime);
    } else {
        // No valid gesture
        overlayEl.style.display = 'block';
        overlayEl.style.opacity = '0.3';
        textEl.textContent = 'No gesture detected';
        barEl.style.width = '0%';
        overlayEl.className = 'overlay-text';
    }
}

// Check backend connection status
async function checkBackendStatus() {
    const statusEl = document.getElementById('backend-status');
    
    try {
        const response = await fetch(`${BACKEND_HTTP_URL}/health`, { method: 'GET' });
        if (response.ok) {
            statusEl.className = 'status-pill connected';
            statusEl.querySelector('span:last-child').textContent = 'Connected';
        } else {
            throw new Error('Backend not healthy');
        }
    } catch (error) {
        statusEl.className = 'status-pill disconnected';
        statusEl.querySelector('span:last-child').textContent = 'Disconnected';
    }
}

// Open edit modal
function openEditModal(gesture) {
    const modal = document.getElementById('edit-modal');
    const config = gestureConfig[gesture];
    
    document.getElementById('edit-gesture').value = gesture;
    document.getElementById('edit-action-type').value = config.action;
    document.getElementById('edit-description').value = config.description || '';
    
    // Format config as JSON (exclude action and description)
    const configCopy = { ...config };
    delete configCopy.action;
    delete configCopy.description;
    document.getElementById('edit-action-config').value = JSON.stringify(configCopy, null, 2);
    
    modal.classList.add('active');
}

// Close edit modal
function closeEditModal() {
    const modal = document.getElementById('edit-modal');
    modal.classList.remove('active');
}

// Handle form submission
document.getElementById('edit-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const gesture = document.getElementById('edit-gesture').value;
    const actionType = document.getElementById('edit-action-type').value;
    const actionConfig = document.getElementById('edit-action-config').value;
    const description = document.getElementById('edit-description').value;
    
    try {
        const config = JSON.parse(actionConfig);
        config.action = actionType;
        config.description = description;
        
        // Update local config
        gestureConfig[gesture] = config;
        
        // Save to backend (in production)
        // await fetch('/api/config/gestures', { method: 'POST', body: JSON.stringify(gestureConfig) });
        
        // For now, save to localStorage
        localStorage.setItem('gestureConfig', JSON.stringify(gestureConfig));
        
        renderGestureConfig();
        closeEditModal();
        
        alert(`Saved configuration for "${gesture}"`);
    } catch (error) {
        alert('Invalid JSON configuration: ' + error.message);
    }
});

// ========== GESTURE HISTORY MANAGEMENT ==========

// Load gesture history from localStorage
function loadGestureHistory() {
    try {
        const stored = localStorage.getItem('gestureHistory');
        if (stored) {
            gestureHistory = JSON.parse(stored);
            console.log('Loaded gesture history:', gestureHistory.length, 'entries');
        } else {
            gestureHistory = [];
        }
        renderHistory();
    } catch (error) {
        console.error('Failed to load gesture history:', error);
        gestureHistory = [];
        renderHistory();
    }
}

// Save gesture history to localStorage
function saveGestureHistory() {
    try {
        localStorage.setItem('gestureHistory', JSON.stringify(gestureHistory));
    } catch (error) {
        console.error('Failed to save gesture history:', error);
    }
}

// Add new gesture to history
function addToHistory(gesture, confidence, hand = 'unknown', processingTime = 0) {
    const entry = {
        gesture: gesture,
        confidence: confidence,
        hand: hand,
        timestamp: new Date().toISOString(),
        processing_time_ms: processingTime
    };
    
    // Add to beginning of array
    gestureHistory.unshift(entry);
    
    // Keep only last 20 entries
    if (gestureHistory.length > MAX_HISTORY_ENTRIES) {
        gestureHistory = gestureHistory.slice(0, MAX_HISTORY_ENTRIES);
    }
    
    // Save to localStorage
    saveGestureHistory();
    
    // Re-render history at most every 200ms to avoid heavy DOM churn.
    if (historyRenderTimeout) {
        return;
    }

    historyRenderTimeout = setTimeout(() => {
        renderHistory();
        historyRenderTimeout = null;
    }, 200);
}

// Render history list
function renderHistory() {
    const listEl = document.getElementById('history-list');
    
    if (gestureHistory.length === 0) {
        listEl.innerHTML = '<div class="history-empty">No gestures detected yet</div>';
        return;
    }
    
    listEl.innerHTML = '';
    
    gestureHistory.forEach(entry => {
        const item = document.createElement('div');
        item.className = 'history-item';
        
        // Add confidence class
        if (entry.confidence > 0.8) {
            item.classList.add('high-confidence');
        } else if (entry.confidence > 0.6) {
            item.classList.add('medium-confidence');
        } else {
            item.classList.add('low-confidence');
        }
        
        // Format timestamp
        const date = new Date(entry.timestamp);
        const timeStr = date.toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit', 
            second: '2-digit' 
        });
        
        item.innerHTML = `
            <div class="history-item-header">
                <span class="history-gesture">${entry.gesture}</span>
                <span class="history-confidence">${Math.round(entry.confidence * 100)}%</span>
            </div>
            <div class="history-item-footer">
                <span>🕐 ${timeStr}</span>
                <span>✋ ${entry.hand}</span>
                <span>⚡ ${entry.processing_time_ms}ms</span>
            </div>
        `;
        
        listEl.appendChild(item);
    });
}

// Clear all history
function clearHistory() {
    if (confirm('Are you sure you want to clear all gesture history?')) {
        gestureHistory = [];
        saveGestureHistory();
        renderHistory();
        console.log('Gesture history cleared');
    }
}

// Export history to JSON file
function exportHistory() {
    if (gestureHistory.length === 0) {
        alert('No history to export');
        return;
    }
    
    const dataStr = JSON.stringify(gestureHistory, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    
    // Generate filename with timestamp
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
    link.download = `gesture-history-${timestamp}.json`;
    
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    
    console.log('Exported', gestureHistory.length, 'history entries');
}

// Initialize on load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
