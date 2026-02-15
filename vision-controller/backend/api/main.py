"""Vision Controller FastAPI Server

Provides WebSocket endpoint for real-time gesture detection streaming
and health check endpoint for monitoring.

Tech Stack:
- FastAPI: Modern, fast web framework
- WebSocket: Real-time bidirectional communication
- Uvicorn: ASGI server with auto-reload

Usage:
    cd /Users/matthew/Desktop/vision-controller/backend
    uvicorn api.main:app --host 127.0.0.1 --port 8765

API Endpoints:
    GET /health - Health check
    WS /ws/gestures - Real-time gesture WebSocket
    POST /api/train-gesture - Train custom gesture
"""

import json
import time
import base64
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketState
from pydantic import BaseModel
from typing import List, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"
COMBINED_LOG_FILE = BACKEND_ROOT / "combined.log"

# Ensure local backend package imports resolve regardless of working directory.
sys.path.insert(0, str(BACKEND_ROOT))
from ml.hand_detector import HandDetector
from ml.gesture_classifier import GestureClassifier
from ml.combo_detector import ComboDetector


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    print(f"[{datetime.now().isoformat()}] Vision Controller API starting...")
    print(f"  Health endpoint: http://127.0.0.1:8765/health")
    print(f"  WebSocket endpoint: ws://127.0.0.1:8765/ws/gestures")

    # OPTIMIZED: Use lite model (model_complexity=0) and frame skipping for <100ms latency
    app.state.hand_detector = HandDetector(
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
        model_complexity=0,  # Lite model for speed
        frame_skip=1  # Process every frame (adjust to 2 if needed)
    )
    app.state.gesture_classifier = GestureClassifier()
    app.state.combo_detector = ComboDetector(timeout_window=2.0)
    
    # Load combo definitions from config
    config_path = CONFIG_DIR / "gestures.json"
    app.state.combo_detector.load_combos_from_config(config_path)
    
    print(f"[{datetime.now().isoformat()}] ML models loaded: HandDetector (LITE/OPTIMIZED) + GestureClassifier + ComboDetector")
    print(f"  ⚡ Latency mode: <100ms target with model_complexity=0")

    yield

    if hasattr(app.state, 'hand_detector') and app.state.hand_detector:
        app.state.hand_detector.close()
    print(f"[{datetime.now().isoformat()}] Vision Controller API shutting down...")


app = FastAPI(
    title="Vision Controller API",
    description="Real-time hand gesture detection WebSocket server",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TrainGestureRequest(BaseModel):
    """Request model for training a custom gesture."""
    name: str
    samples: List[List[Dict[str, float]]]  # List of landmark sequences


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "service": "Vision Controller API"
    }


@app.post("/api/log")
async def log_frontend(request: dict):
    """Log frontend messages to backend log file."""
    timestamp = request.get("timestamp", "")
    category = request.get("category", "Frontend")
    message = request.get("message", "")
    
    # Write to shared log file
    COMBINED_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    log_file = COMBINED_LOG_FILE
    with open(log_file, "a") as f:
        f.write(f"[{timestamp}] [FRONTEND:{category}] {message}\n")
    
    return {"ok": True}


@app.post("/api/train-gesture")
async def train_gesture(request: TrainGestureRequest):
    """
    Train a custom gesture with provided landmark samples.
    
    Args:
        request: Contains gesture name and list of landmark frame sequences
        
    Returns:
        Success message with saved gesture info
    """
    try:
        # Validate gesture name
        if not request.name or len(request.name.strip()) == 0:
            raise HTTPException(status_code=400, detail="Gesture name cannot be empty")
        
        gesture_name = request.name.strip().lower().replace(" ", "_")
        
        # Validate samples
        if not request.samples or len(request.samples) == 0:
            raise HTTPException(status_code=400, detail="At least one sample is required")
        
        # Validate landmark structure
        for i, sample in enumerate(request.samples):
            if len(sample) != 21:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Sample {i} must have exactly 21 landmarks, got {len(sample)}"
                )
            
            for j, landmark in enumerate(sample):
                if not all(k in landmark for k in ['x', 'y', 'z']):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Sample {i}, landmark {j} missing required keys (x, y, z)"
                    )
        
        # Load existing custom gestures or create new file
        config_path = CONFIG_DIR
        custom_gestures_file = config_path / "custom_gestures.json"
        
        if custom_gestures_file.exists():
            with open(custom_gestures_file, 'r') as f:
                custom_gestures = json.load(f)
        else:
            custom_gestures = {}
        
        # Save the new gesture (overwrite if exists)
        custom_gestures[gesture_name] = {
            "name": gesture_name,
            "samples": request.samples,
            "created_at": datetime.now().isoformat(),
            "num_samples": len(request.samples)
        }
        
        # Write back to file
        config_path.mkdir(parents=True, exist_ok=True)
        with open(custom_gestures_file, 'w') as f:
            json.dump(custom_gestures, f, indent=2)
        
        # Reload custom gestures in the gesture classifier
        if hasattr(app.state, 'gesture_classifier'):
            app.state.gesture_classifier.load_custom_gestures()
        
        print(f"[API] Trained custom gesture '{gesture_name}' with {len(request.samples)} samples")
        
        return {
            "status": "success",
            "message": f"Gesture '{gesture_name}' trained successfully",
            "gesture_name": gesture_name,
            "num_samples": len(request.samples),
            "saved_to": str(custom_gestures_file)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[API] Error training gesture: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[WebSocket] Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"[WebSocket] Client disconnected. Total: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send a message safely; return False on send/backpressure errors."""
        if websocket not in self.active_connections:
            return False

        if websocket.client_state != WebSocketState.CONNECTED:
            self.disconnect(websocket)
            return False

        try:
            await websocket.send_json(message)
            return True
        except (WebSocketDisconnect, RuntimeError, ConnectionError) as e:
            print(f"[WebSocket] Send failed, disconnecting client: {e}")
            self.disconnect(websocket)
            return False
        except Exception as e:
            # Non-fatal send errors (e.g. temporary congestion) should not crash loop
            print(f"[WebSocket] Non-fatal send error: {e}")
            return False


manager = ConnectionManager()


def decode_base64_frame(frame_data: str):
    """Decode base64 string to numpy array (image).
    
    OPTIMIZED for low latency:
    - Uses cv2.imdecode (faster than PIL)
    - INTER_LINEAR instead of LANCZOS (3x faster)
    - Direct numpy operations
    """
    if ',' in frame_data:
        frame_data = frame_data.split(',', 1)[1]

    # OPTIMIZATION: Direct numpy decode (faster than PIL)
    img_bytes = base64.b64decode(frame_data)
    nparr = np.frombuffer(img_bytes, np.uint8)
    img_array = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if img_array is None:
        raise ValueError("Failed to decode frame")

    # OPTIMIZATION: Use INTER_LINEAR (faster than LANCZOS, minimal quality loss)
    # Resize to 320x240 for faster processing
    img_array = cv2.resize(img_array, (320, 240), interpolation=cv2.INTER_LINEAR)

    return img_array


@app.websocket("/ws/gestures")
async def websocket_endpoint(websocket: WebSocket):
    """Real-time gesture detection WebSocket."""
    await manager.connect(websocket)

    # Track last gesture to detect changes
    last_gesture = None
    last_confidence = 0.0
    no_gesture_count = 0
    confidence_threshold = 0.7  # Only report gestures above 70% confidence
    last_emit_time = 0.0
    min_emit_interval_sec = 0.12  # Hard cap burst rate from backend
    same_gesture_refresh_interval_sec = 0.40  # Keep UI fresh without flooding

    try:
        await manager.send_personal_message({
            "type": "status",
            "message": "Connected to Vision Controller",
            "timestamp": int(time.time() * 1000)
        }, websocket)

        hand_detector = app.state.hand_detector
        gesture_classifier = app.state.gesture_classifier
        combo_detector = app.state.combo_detector

        while True:
            try:
                data = await websocket.receive_json()
                message_type = data.get("type", "unknown")

                if message_type == "video_frame":
                    receive_time = time.time()
                    frame_data = data.get("frame", "")
                    timestamp = data.get("timestamp", int(time.time() * 1000))
                    sequence = data.get("sequence", 0)  # Get sequence number from client

                    if not frame_data:
                        await manager.send_personal_message({
                            "type": "error",
                            "message": "Empty frame data",
                            "sequence": sequence
                        }, websocket)
                        continue

                    start_time = time.time()
                    decode_start = start_time

                    try:
                        frame = decode_base64_frame(frame_data)
                        decode_time = (time.time() - decode_start) * 1000
                        
                        detect_start = time.time()
                        detected_hands = hand_detector.detect(frame)
                        detect_time = (time.time() - detect_start) * 1000

                        if not detected_hands:
                            processing_time_ms = int((time.time() - start_time) * 1000)
                            no_gesture_count += 1
                            
                            # Only send "no gesture" event after 5 consecutive frames with no hand
                            # AND if we previously had a gesture
                            if no_gesture_count >= 5 and last_gesture is not None:
                                print(f"[CLEAR] No hand detected for 5 frames, clearing {last_gesture}")
                                await manager.send_personal_message({
                                    "type": "gesture_detected",
                                    "gesture": None,
                                    "confidence": 0,
                                    "hand": None,
                                    "timestamp": timestamp,
                                    "sequence": sequence,
                                    "processing_time_ms": processing_time_ms
                                }, websocket)
                                last_gesture = None
                                last_confidence = 0.0
                                no_gesture_count = 0  # Reset after sending clear

                            # ACK even when no hand is detected so frontend flow-control can continue.
                            await manager.send_personal_message({
                                "type": "frame_ack",
                                "sequence": sequence,
                                "timestamp": int(time.time() * 1000)
                            }, websocket)
                            continue

                        hand = detected_hands[0]
                        landmarks = hand["landmarks"]
                        landmarks_tuples = [(lm["x"], lm["y"], lm["z"]) for lm in landmarks]
                        hand_label = hand["handedness"]

                        classify_start = time.time()
                        result = gesture_classifier.classify(landmarks_tuples, hand_label)
                        classify_time = (time.time() - classify_start) * 1000
                        
                        processing_time_ms = int((time.time() - start_time) * 1000)
                        total_latency = int((time.time() - receive_time) * 1000)

                        current_gesture = result["gesture"]
                        current_confidence = result["confidence"]
                        
                        # Reset no-gesture counter if we detect a hand
                        no_gesture_count = 0

                        gesture_changed = current_gesture != last_gesture
                        confidence_high = current_confidence >= confidence_threshold
                        
                        if confidence_high:
                            now = time.time()
                            time_since_emit = now - last_emit_time
                            can_emit_now = time_since_emit >= min_emit_interval_sec
                            should_refresh_same_gesture = (
                                not gesture_changed
                                and time_since_emit >= same_gesture_refresh_interval_sec
                            )
                            should_send = gesture_changed or should_refresh_same_gesture

                            if should_send and can_emit_now:
                                log_msg = (
                                    f"[CHANGE] {last_gesture} → {current_gesture} | "
                                    f"conf: {current_confidence:.2f} | decode: {decode_time:.0f}ms | "
                                    f"detect: {detect_time:.0f}ms | classify: {classify_time:.0f}ms | "
                                    f"total: {total_latency}ms"
                                )
                                print(log_msg)

                                # Write to combined log
                                log_file = Path("/Users/matthew/Desktop/vision-controller/backend/combined.log")
                                with open(log_file, "a") as f:
                                    f.write(f"[{datetime.now().isoformat()[11:23]}] [BACKEND:CHANGE] {log_msg}\n")

                                send_start = time.time()
                                sent = await manager.send_personal_message({
                                    "type": "gesture_detected",
                                    "gesture": current_gesture,
                                    "confidence": current_confidence,
                                    "hand": result["hand"],
                                    "timestamp": timestamp,
                                    "sequence": sequence,
                                    "processing_time_ms": processing_time_ms
                                }, websocket)
                                send_time = (time.time() - send_start) * 1000
                                send_log = f"[SEND] WebSocket send took {send_time:.0f}ms (ok={sent})"
                                print(send_log)

                                with open(log_file, "a") as f:
                                    f.write(f"[{datetime.now().isoformat()[11:23]}] [BACKEND:SEND] {send_log}\n")

                                if sent:
                                    last_emit_time = now
                                    last_gesture = current_gesture
                                    last_confidence = current_confidence
                        else:
                            # Log every 30 frames even if no change
                            if int(time.time() * 10) % 30 == 0:
                                print(f"[SKIP] {current_gesture} (no change) | conf: {current_confidence:.2f} | total: {total_latency}ms")

                        # ACK every processed frame to keep frontend sender in sync.
                        await manager.send_personal_message({
                            "type": "frame_ack",
                            "sequence": sequence,
                            "timestamp": int(time.time() * 1000)
                        }, websocket)
                        
                        # Add gesture to combo detector
                        combo_detector.add_gesture(
                            result["gesture"],
                            result["confidence"],
                            result["hand"]
                        )
                        
                        # Check for combo matches
                        combo_result = combo_detector.check_combos()
                        if combo_result:
                            await manager.send_personal_message({
                                "type": "combo_detected",
                                "combo_name": combo_result["name"],
                                "sequence": combo_result["sequence"],
                                "confidence": combo_result["confidence"],
                                "action": combo_result["action"],
                                "description": combo_result.get("description", ""),
                                "matched_gestures": combo_result["matched_gestures"],
                                "timestamp": int(combo_result["timestamp"] * 1000)
                            }, websocket)

                    except Exception as e:
                        print(f"[WebSocket] ML processing error: {e}")
                        await manager.send_personal_message({
                            "type": "error",
                            "message": str(e)
                        }, websocket)

                elif message_type == "ping":
                    await manager.send_personal_message({
                        "type": "pong",
                        "timestamp": data.get("timestamp")
                    }, websocket)

                elif message_type == "subscribe":
                    await manager.send_personal_message({
                        "type": "subscribed",
                        "message": "Subscribed to gesture updates"
                    }, websocket)

                else:
                    print(f"[WebSocket] Unknown message type: {message_type}")

            except WebSocketDisconnect:
                raise
            except Exception as e:
                print(f"[WebSocket] Error processing message: {e}")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("[WebSocket] Client disconnected")
    except Exception as e:
        print(f"[WebSocket] Error: {e}")
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="127.0.0.1",
        port=8765,
        reload=False,
        log_level="info"
    )
