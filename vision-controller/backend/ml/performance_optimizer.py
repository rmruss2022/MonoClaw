"""
Performance Optimizer for Vision Controller
Reduces latency through frame skipping, downscaling, and caching
"""

import time
import cv2
import numpy as np
from typing import Tuple, Optional, Dict, Any
from collections import deque
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PerformanceOptimizer:
    """
    Optimize vision processing performance
    
    Strategies:
    1. Frame skipping - process every Nth frame
    2. Frame downscaling - reduce resolution
    3. ROI detection - process only hand regions
    4. Result caching - reuse recent results
    """
    
    def __init__(self, 
                 target_fps: int = 30,
                 process_every_n_frames: int = 2,
                 downscale_factor: float = 0.75,
                 enable_roi: bool = True):
        """
        Initialize performance optimizer
        
        Args:
            target_fps: Target frames per second
            process_every_n_frames: Process every Nth frame (1 = every frame)
            downscale_factor: Scale factor for frame downscaling (0.5 = half size)
            enable_roi: Enable region of interest optimization
        """
        self.target_fps = target_fps
        self.process_every_n_frames = process_every_n_frames
        self.downscale_factor = downscale_factor
        self.enable_roi = enable_roi
        
        # Frame counter
        self.frame_count = 0
        
        # Performance tracking
        self.processing_times = deque(maxlen=30)
        self.frame_times = deque(maxlen=30)
        self.last_frame_time = time.time()
        
        # Result caching
        self.last_result = None
        self.result_cache_duration = 0.1  # 100ms
        self.last_result_time = 0
        
        # ROI tracking
        self.last_hand_bbox = None
        self.roi_padding = 50  # pixels
        
    def should_process_frame(self) -> bool:
        """
        Determine if current frame should be processed
        
        Returns:
            True if frame should be processed
        """
        self.frame_count += 1
        
        # Track frame timing
        current_time = time.time()
        frame_delta = current_time - self.last_frame_time
        self.frame_times.append(frame_delta)
        self.last_frame_time = current_time
        
        # Skip frames based on configured interval
        return (self.frame_count % self.process_every_n_frames) == 0
    
    def preprocess_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Preprocess frame for optimal performance
        
        Args:
            frame: Input frame (BGR format)
            
        Returns:
            Tuple of (processed_frame, metadata)
        """
        start_time = time.time()
        metadata = {
            'original_shape': frame.shape,
            'downscaled': False,
            'roi_applied': False
        }
        
        processed_frame = frame
        
        # 1. Apply ROI if available
        if self.enable_roi and self.last_hand_bbox is not None:
            processed_frame = self._apply_roi(processed_frame)
            metadata['roi_applied'] = True
        
        # 2. Downscale frame
        if self.downscale_factor < 1.0:
            h, w = processed_frame.shape[:2]
            new_w = int(w * self.downscale_factor)
            new_h = int(h * self.downscale_factor)
            processed_frame = cv2.resize(processed_frame, (new_w, new_h), 
                                        interpolation=cv2.INTER_LINEAR)
            metadata['downscaled'] = True
            metadata['downscale_shape'] = processed_frame.shape
        
        # Track preprocessing time
        preprocess_time = time.time() - start_time
        metadata['preprocess_time_ms'] = preprocess_time * 1000
        
        return processed_frame, metadata
    
    def _apply_roi(self, frame: np.ndarray) -> np.ndarray:
        """
        Extract region of interest around last detected hand
        
        Args:
            frame: Input frame
            
        Returns:
            Cropped frame
        """
        if self.last_hand_bbox is None:
            return frame
        
        x, y, w, h = self.last_hand_bbox
        
        # Add padding
        x1 = max(0, x - self.roi_padding)
        y1 = max(0, y - self.roi_padding)
        x2 = min(frame.shape[1], x + w + self.roi_padding)
        y2 = min(frame.shape[0], y + h + self.roi_padding)
        
        return frame[y1:y2, x1:x2]
    
    def update_hand_bbox(self, bbox: Optional[Tuple[int, int, int, int]]):
        """
        Update tracked hand bounding box for ROI optimization
        
        Args:
            bbox: (x, y, width, height) or None
        """
        self.last_hand_bbox = bbox
    
    def cache_result(self, result: Dict[str, Any]):
        """
        Cache processing result for reuse
        
        Args:
            result: Processing result to cache
        """
        self.last_result = result
        self.last_result_time = time.time()
    
    def get_cached_result(self) -> Optional[Dict[str, Any]]:
        """
        Get cached result if still valid
        
        Returns:
            Cached result or None if expired
        """
        if self.last_result is None:
            return None
        
        age = time.time() - self.last_result_time
        if age > self.result_cache_duration:
            return None
        
        return self.last_result
    
    def record_processing_time(self, duration: float):
        """
        Record processing time for metrics
        
        Args:
            duration: Processing duration in seconds
        """
        self.processing_times.append(duration)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get current performance statistics
        
        Returns:
            Dict with performance metrics
        """
        if len(self.processing_times) == 0:
            avg_processing_time = 0
        else:
            avg_processing_time = sum(self.processing_times) / len(self.processing_times)
        
        if len(self.frame_times) == 0:
            avg_fps = 0
        else:
            avg_frame_time = sum(self.frame_times) / len(self.frame_times)
            avg_fps = 1.0 / avg_frame_time if avg_frame_time > 0 else 0
        
        return {
            'avg_processing_time_ms': avg_processing_time * 1000,
            'avg_fps': avg_fps,
            'target_fps': self.target_fps,
            'frame_skip': self.process_every_n_frames,
            'downscale_factor': self.downscale_factor,
            'total_frames': self.frame_count,
            'processed_frames': self.frame_count // self.process_every_n_frames
        }
    
    def adjust_performance(self, current_latency_ms: float):
        """
        Dynamically adjust performance settings based on latency
        
        Args:
            current_latency_ms: Current processing latency in milliseconds
        """
        target_latency_ms = (1000.0 / self.target_fps) * 0.8  # 80% of target frame time
        
        if current_latency_ms > target_latency_ms:
            # Latency too high - increase optimizations
            if self.downscale_factor > 0.5:
                self.downscale_factor -= 0.05
                logger.info(f"Reduced downscale to {self.downscale_factor:.2f}")
            elif self.process_every_n_frames < 4:
                self.process_every_n_frames += 1
                logger.info(f"Increased frame skip to {self.process_every_n_frames}")
        elif current_latency_ms < target_latency_ms * 0.5:
            # Latency good - can reduce optimizations
            if self.process_every_n_frames > 1:
                self.process_every_n_frames -= 1
                logger.info(f"Decreased frame skip to {self.process_every_n_frames}")
            elif self.downscale_factor < 1.0:
                self.downscale_factor = min(1.0, self.downscale_factor + 0.05)
                logger.info(f"Increased downscale to {self.downscale_factor:.2f}")


if __name__ == "__main__":
    # Test performance optimizer
    optimizer = PerformanceOptimizer(
        target_fps=30,
        process_every_n_frames=2,
        downscale_factor=0.75
    )
    
    print("Performance Optimizer Test")
    print("=" * 50)
    
    # Simulate frame processing
    print("\nSimulating 10 frames:")
    for i in range(10):
        should_process = optimizer.should_process_frame()
        print(f"Frame {i+1}: {'PROCESS' if should_process else 'SKIP'}")
        
        if should_process:
            # Simulate processing time
            time.sleep(0.02)  # 20ms
            optimizer.record_processing_time(0.02)
    
    # Get stats
    stats = optimizer.get_performance_stats()
    print("\nPerformance Stats:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\nPerformance Optimizer initialized successfully")
