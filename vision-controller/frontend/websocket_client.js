// WebSocket Client for Vision Controller
// Handles real-time gesture updates from backend

class GestureWebSocketClient {
    constructor(url = 'ws://127.0.0.1:9000/ws/gestures') {
        this.url = url;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 2000;
        this.isConnecting = false;
        this.maxBufferedBytes = 1_000_000; // Backpressure guard for queued outbound frames
        
        // Callbacks
        this.onGestureUpdate = null;
        this.onLandmarksUpdate = null;
        this.onConnected = null;
        this.onDisconnected = null;
        this.onError = null;
    }
    
    connect() {
        if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) {
            console.log('Already connected or connecting');
            return;
        }
        
        this.isConnecting = true;
        console.log('Connecting to WebSocket:', this.url);
        
        try {
            this.ws = new WebSocket(this.url);
            
            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.isConnecting = false;
                this.reconnectAttempts = 0;
                
                // Subscribe to gesture updates
                this.send({
                    type: 'subscribe',
                    channel: 'gestures'
                });
                
                if (this.onConnected) {
                    this.onConnected();
                }
            };
            
            this.ws.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    this.handleMessage(message);
                } catch (error) {
                    console.error('Failed to parse WebSocket message:', error);
                }
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.isConnecting = false;
                
                if (this.onError) {
                    this.onError(error);
                }
            };
            
            this.ws.onclose = (event) => {
                console.log('WebSocket closed:', event.code, event.reason);
                this.isConnecting = false;
                this.ws = null;
                
                if (this.onDisconnected) {
                    this.onDisconnected();
                }
                
                // Attempt to reconnect
                if (this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.reconnectAttempts++;
                    console.log(`Reconnecting in ${this.reconnectDelay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
                    setTimeout(() => this.connect(), this.reconnectDelay);
                } else {
                    console.error('Max reconnect attempts reached');
                }
            };
            
        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            this.isConnecting = false;
        }
    }
    
    disconnect() {
        if (this.ws) {
            this.reconnectAttempts = this.maxReconnectAttempts; // Prevent auto-reconnect
            this.ws.close();
            this.ws = null;
        }
    }
    
    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        } else {
            console.warn('Cannot send message: WebSocket not open');
        }
    }
    
    sendFrame(base64Data, sequence = 0) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            if (this.ws.bufferedAmount > this.maxBufferedBytes) {
                return;
            }

            this.send({
                type: 'video_frame',
                frame: base64Data,
                timestamp: Date.now(),
                sequence: sequence  // Add sequence number for ordering
            });
        } else {
            console.warn('Cannot send frame: WebSocket not open');
        }
    }
    
    handleMessage(message) {
        const { type } = message;
        
        switch (type) {
            case 'gesture_detected':
                if (this.onGestureUpdate) {
                    this.onGestureUpdate(message);
                }
                break;
            
            case 'gesture_update':
                if (this.onGestureUpdate) {
                    this.onGestureUpdate(message);
                }
                break;
                
            case 'landmarks':
                if (this.onLandmarksUpdate) {
                    this.onLandmarksUpdate(message);
                }
                break;
                
            case 'pong':
                // Response to ping
                console.log('Received pong');
                break;
                
            case 'subscribed':
                console.log('Subscribed to updates:', message.message);
                break;
                
            case 'error':
                console.error('Server error:', message.message);
                break;
                
            default:
                console.warn('Unknown message type:', type);
        }
    }
    
    // Send periodic ping to keep connection alive
    startHeartbeat(interval = 30000) {
        this.heartbeatInterval = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.send({
                    type: 'ping',
                    timestamp: Date.now()
                });
            }
        }, interval);
    }
    
    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }
}

// Export for use in app.js
if (typeof module !== 'undefined' && module.exports) {
    module.exports = GestureWebSocketClient;
}
