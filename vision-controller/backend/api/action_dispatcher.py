"""
Action Dispatcher for Vision Controller
Triggers AppleScript, OpenClaw RPC, and keyboard/mouse control
"""

import subprocess
import requests
import logging
from typing import Dict, Any, Optional
try:
    from pynput.keyboard import Controller as KeyboardController, Key
except Exception:  # pragma: no cover - runtime environment dependent
    KeyboardController = None
    Key = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ActionDispatcher:
    """Execute actions triggered by gestures"""
    
    def __init__(self, openclaw_host: str = "localhost", openclaw_port: int = 18795):
        self.openclaw_base_url = f"http://{openclaw_host}:{openclaw_port}"
        self.keyboard = KeyboardController() if KeyboardController else None
        
    def execute(self, action_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an action based on type
        
        Args:
            action_type: One of 'applescript', 'openclaw_rpc', 'keyboard'
            params: Action-specific parameters
            
        Returns:
            Dict with keys: 'success', 'message', 'data' (optional)
        """
        try:
            if action_type == "applescript":
                return self._run_applescript(params.get('script', ''))
            elif action_type == "openclaw_rpc":
                return self._openclaw_rpc(
                    params.get('method', ''),
                    params.get('args', {}),
                    params.get('params', {})
                )
            elif action_type == "keyboard":
                return self._keyboard_action(params.get('keys', []))
            else:
                return {
                    'success': False,
                    'message': f"Unknown action type: {action_type}"
                }
        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            return {
                'success': False,
                'message': str(e)
            }
    
    def _run_applescript(self, script: str) -> Dict[str, Any]:
        """
        Execute AppleScript command
        
        Args:
            script: AppleScript code to execute
            
        Returns:
            Result dict
        """
        if not script:
            return {'success': False, 'message': 'Empty script'}
        
        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logger.info(f"AppleScript executed successfully: {script[:50]}...")
                return {
                    'success': True,
                    'message': 'AppleScript executed',
                    'data': result.stdout.strip()
                }
            else:
                logger.error(f"AppleScript error: {result.stderr}")
                return {
                    'success': False,
                    'message': f"AppleScript failed: {result.stderr}"
                }
                
        except subprocess.TimeoutExpired:
            return {'success': False, 'message': 'AppleScript timeout'}
        except Exception as e:
            return {'success': False, 'message': f"AppleScript exception: {str(e)}"}
    
    def _openclaw_rpc(self, method: str, args: Dict = None, params: Dict = None) -> Dict[str, Any]:
        """
        Call OpenClaw RPC endpoint
        
        Args:
            method: API endpoint (e.g., '/api/message')
            args: Legacy args parameter (deprecated, use params)
            params: Request parameters
            
        Returns:
            Result dict
        """
        if not method:
            return {'success': False, 'message': 'Empty method'}
        
        # Use params if provided, otherwise use args for backwards compatibility
        request_data = params if params else args
        if not request_data:
            request_data = {}
        
        try:
            url = f"{self.openclaw_base_url}{method}"
            response = requests.post(
                url,
                json=request_data,
                timeout=5
            )
            
            if response.status_code == 200:
                logger.info(f"OpenClaw RPC success: {method}")
                return {
                    'success': True,
                    'message': f'RPC call to {method} succeeded',
                    'data': response.json() if response.text else None
                }
            else:
                logger.error(f"OpenClaw RPC failed: {response.status_code}")
                return {
                    'success': False,
                    'message': f"RPC failed with status {response.status_code}"
                }
                
        except requests.exceptions.Timeout:
            return {'success': False, 'message': 'RPC timeout'}
        except requests.exceptions.ConnectionError:
            return {'success': False, 'message': 'Cannot connect to OpenClaw'}
        except Exception as e:
            return {'success': False, 'message': f"RPC exception: {str(e)}"}
    
    def _keyboard_action(self, keys: list) -> Dict[str, Any]:
        """
        Send keyboard shortcuts
        
        Args:
            keys: List of keys to press (e.g., ['cmd', 'd'] or ['ctrl', 'c'])
            
        Returns:
            Result dict
        """
        if not keys:
            return {'success': False, 'message': 'Empty keys list'}
        if self.keyboard is None or Key is None:
            return {'success': False, 'message': 'Keyboard control unavailable (pynput not installed)'}
        
        try:
            # Map common key names to pynput Key objects
            key_mapping = {
                'cmd': Key.cmd,
                'command': Key.cmd,
                'ctrl': Key.ctrl,
                'control': Key.ctrl,
                'alt': Key.alt,
                'option': Key.alt,
                'shift': Key.shift,
                'enter': Key.enter,
                'return': Key.enter,
                'tab': Key.tab,
                'space': Key.space,
                'backspace': Key.backspace,
                'delete': Key.delete,
                'esc': Key.esc,
                'escape': Key.esc,
                'up': Key.up,
                'down': Key.down,
                'left': Key.left,
                'right': Key.right,
            }
            
            # Convert keys to pynput format
            pynput_keys = []
            for key in keys:
                key_lower = key.lower()
                if key_lower in key_mapping:
                    pynput_keys.append(key_mapping[key_lower])
                else:
                    # Regular character key
                    pynput_keys.append(key)
            
            # Press all keys (for combinations)
            for key in pynput_keys:
                self.keyboard.press(key)
            
            # Release all keys in reverse order
            for key in reversed(pynput_keys):
                self.keyboard.release(key)
            
            logger.info(f"Keyboard action executed: {keys}")
            return {
                'success': True,
                'message': f"Pressed keys: {keys}"
            }
            
        except Exception as e:
            return {'success': False, 'message': f"Keyboard exception: {str(e)}"}


# Test functionality
if __name__ == "__main__":
    dispatcher = ActionDispatcher()
    
    # Test AppleScript
    print("Testing AppleScript...")
    result = dispatcher.execute('applescript', {
        'script': 'display notification "Vision Controller Test" with title "Action Dispatcher"'
    })
    print(f"AppleScript result: {result}")
    
    # Test keyboard shortcut
    print("\nTesting keyboard shortcut...")
    # This would trigger Cmd+Space (Spotlight on macOS)
    # Commented out to avoid unexpected behavior during development
    # result = dispatcher.execute('keyboard', {'keys': ['cmd', 'space']})
    # print(f"Keyboard result: {result}")
    
    print("\nAction Dispatcher initialized successfully")
