// Vision Controller - DEBUGGED VERSION WITH TIMESTAMPS

let video, canvas, ctx, ws;
let lastGesture = null;
let capturing = false;
let gestureHistory = [];

function timestamp() {
    return new Date().toISOString().slice(11, 23); // HH:MM:SS.mmm
}

function log(category, message, ...args) {
    const ts = timestamp();
    console.log(`[${ts}] [${category}]`, message, ...args);
    // Removed backend logging to avoid WebSocket conflicts
}

// Initialize on page load
window.addEventListener('DOMContentLoaded', async () => {
    log('App', 'Initializing...');
    
    // Get elements
    video = document.getElementById('camera');
    canvas = document.createElement('canvas');
    ctx = canvas.getContext('2d');
    canvas.width = 320;
    canvas.height = 240;
    
    // Update camera status
    updateCameraStatus('Requesting camera access...', 'connecting');
    
    // Start camera
    try {
        log('Camera', 'Requesting getUserMedia...');
        const stream = await navigator.mediaDevices.getUserMedia({ 
            video: { width: 640, height: 480 } 
        });
        
        log('Camera', 'Got stream, setting srcObject...');
        video.srcObject = stream;
        
        log('Camera', 'Calling video.play()...');
        await video.play();
        
        log('Camera', 'Video playing! Ready.');
        updateCameraStatus('Active', 'connected');
        
        // Load gesture config
        loadGestureConfig();
        
        // Connect to backend
        connectWebSocket();
        
    } catch (err) {
        log('Camera', 'ERROR:', err);
        updateCameraStatus('Failed: ' + err.message, 'disconnected');
    }
});

// Load gesture configuration
async function loadGestureConfig() {
    try {
        log('Config', 'Loading gesture config...');
        const response = await fetch('/config/gestures.json');
        if (response.ok) {
            const config = await response.json();
            log('Config', 'Loaded', Object.keys(config).length, 'gestures');
            renderGestureConfig(config);
        } else {
            log('Config', 'Failed to load, using defaults');
        }
    } catch (err) {
        log('Config', 'ERROR:', err);
    }
}

// Render gesture configuration list
function renderGestureConfig(config) {
    const listEl = document.getElementById('gesture-config-list');
    if (!listEl) {
        log('Config', 'No gesture-config-list element found');
        return;
    }
    
    listEl.innerHTML = '';
    
    for (const [gesture, cfg] of Object.entries(config)) {
        const item = document.createElement('div');
        item.className = 'gesture-config-item';
        item.innerHTML = `
            <div class="gesture-header">
                <span class="gesture-name">${gesture}</span>
            </div>
            <div class="gesture-action">${cfg.description || 'No description'}</div>
        `;
        listEl.appendChild(item);
    }
    
    log('Config', 'Rendered', Object.keys(config).length, 'gesture configs');
}

// Update camera status
function updateCameraStatus(message, type) {
    const statusEl = document.getElementById('camera-status');
    if (!statusEl) {
        log('UI', 'No camera-status element found');
        return;
    }
    
    statusEl.className = `status-pill ${type}`;
    const span = statusEl.querySelector('span:last-child');
    if (span) span.textContent = message;
    
    log('UI', 'Camera status:', message);
}

// Connect to WebSocket backend
function connectWebSocket() {
    const wsUrl = 'ws://localhost:9000/ws/gestures';
    log('WS', 'Connecting to', wsUrl);
    
    updateBackendStatus('Connecting...', 'connecting');
    
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        log('WS', 'Connected!');
        updateBackendStatus('Connected', 'connected');
        startCapture();
    };
    
    ws.onmessage = (event) => {
        const receiveTime = Date.now();
        
        try {
            const data = JSON.parse(event.data);
            
            if (data.type === 'gesture_detected') {
                const serverTime = data.timestamp || 0;
                const latency = receiveTime - serverTime;
                
                log('WS', `Received gesture: ${data.gesture} | conf: ${data.confidence} | latency: ${latency}ms`);
                
                handleGestureUpdate(data, receiveTime);
            } else {
                log('WS', 'Message:', data.type);
            }
        } catch (err) {
            log('WS', 'Parse error:', err);
        }
    };
    
    ws.onerror = (err) => {
        log('WS', 'ERROR:', err);
        updateBackendStatus('Error', 'disconnected');
    };
    
    ws.onclose = () => {
        log('WS', 'Disconnected, reconnecting in 2s...');
        updateBackendStatus('Disconnected', 'disconnected');
        stopCapture();
        setTimeout(connectWebSocket, 2000);
    };
}

// Update backend status
function updateBackendStatus(message, type) {
    const statusEl = document.getElementById('backend-status');
    if (!statusEl) {
        log('UI', 'No backend-status element found');
        return;
    }
    
    statusEl.className = `status-pill ${type}`;
    const span = statusEl.querySelector('span:last-child');
    if (span) span.textContent = message;
}

// Handle gesture updates from backend
function handleGestureUpdate(data, receiveTime) {
    const gesture = data.gesture;
    const confidence = data.confidence || 0;
    const processingTime = data.processing_time_ms || 0;
    
    log('Gesture', `${gesture} | conf: ${confidence} | processing: ${processingTime}ms`);
    
    // Update UI immediately
    const uiStartTime = performance.now();
    
    requestAnimationFrame(() => {
        if (gesture && gesture !== 'unknown' && confidence > 0) {
            showGesture(gesture, confidence, data.hand);
            addToHistory(gesture, confidence, data.hand, processingTime);
            lastGesture = gesture;
        } else {
            clearGesture();
            lastGesture = null;
        }
        
        const uiTime = performance.now() - uiStartTime;
        log('UI', `Update took ${uiTime.toFixed(2)}ms`);
    });
}

// Add to gesture history
function addToHistory(gesture, confidence, hand, processingTime) {
    const entry = {
        gesture,
        confidence,
        hand,
        processingTime,
        timestamp: Date.now()
    };
    
    gestureHistory.unshift(entry);
    if (gestureHistory.length > 20) {
        gestureHistory.pop();
    }
    
    renderHistory();
}

// Render history
function renderHistory() {
    const historyEl = document.getElementById('gesture-history');
    if (!historyEl) {
        log('UI', 'No gesture-history element found');
        return;
    }
    
    historyEl.innerHTML = gestureHistory.map(entry => {
        const time = new Date(entry.timestamp).toLocaleTimeString();
        return `
            <div class="history-entry">
                <span class="history-time">${time}</span>
                <span class="history-gesture">${entry.gesture}</span>
                <span class="history-confidence">${Math.round(entry.confidence * 100)}%</span>
                <span class="history-hand">${entry.hand}</span>
            </div>
        `;
    }).join('');
}

// Show gesture in UI
function showGesture(gesture, confidence, hand) {
    const overlay = document.getElementById('overlay-display');
    const text = document.getElementById('gesture-text');
    const bar = document.getElementById('confidence-bar');
    
    if (!overlay || !text || !bar) {
        log('UI', 'Missing overlay elements');
        return;
    }
    
    overlay.style.display = 'block';
    text.textContent = `${gesture} (${Math.round(confidence * 100)}%) - ${hand || 'unknown'} hand`;
    bar.style.width = `${confidence * 100}%`;
    
    // Color based on confidence
    if (confidence >= 0.8) {
        overlay.className = 'overlay-text high-confidence';
    } else if (confidence >= 0.6) {
        overlay.className = 'overlay-text medium-confidence';
    } else {
        overlay.className = 'overlay-text low-confidence';
    }
    
    log('UI', `Displayed: ${text.textContent}`);
}

// Clear gesture display
function clearGesture() {
    const overlay = document.getElementById('overlay-display');
    const text = document.getElementById('gesture-text');
    const bar = document.getElementById('confidence-bar');
    
    if (overlay) overlay.style.display = 'none';
    if (text) text.textContent = '';
    if (bar) bar.style.width = '0%';
}

// Start capturing and sending frames
function startCapture() {
    if (capturing) return;
    capturing = true;
    
    log('Capture', 'Starting at 15 FPS...');
    
    let frameCount = 0;
    let lastLogTime = Date.now();
    
    // Capture at 15 FPS (every 66ms)
    setInterval(() => {
        if (!capturing || !ws || ws.readyState !== WebSocket.OPEN) return;
        
        const captureStart = performance.now();
        
        // Draw current video frame to canvas
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        const drawTime = performance.now() - captureStart;
        
        // Convert to JPEG and send
        const encodeStart = performance.now();
        const dataUrl = canvas.toDataURL('image/jpeg', 0.5);
        const encodeTime = performance.now() - encodeStart;
        
        const sendStart = performance.now();
        ws.send(JSON.stringify({
            type: 'video_frame',
            frame: dataUrl,
            timestamp: Date.now()
        }));
        const sendTime = performance.now() - sendStart;
        
        frameCount++;
        
        // Log FPS every 2 seconds
        const now = Date.now();
        if (now - lastLogTime >= 2000) {
            const fps = frameCount / ((now - lastLogTime) / 1000);
            log('Capture', `FPS: ${fps.toFixed(1)} | draw: ${drawTime.toFixed(1)}ms | encode: ${encodeTime.toFixed(1)}ms | send: ${sendTime.toFixed(1)}ms`);
            frameCount = 0;
            lastLogTime = now;
        }
        
    }, 66); // 15 FPS
}

// Stop capturing
function stopCapture() {
    capturing = false;
    log('Capture', 'Stopped');
}
