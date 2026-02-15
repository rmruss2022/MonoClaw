"""
Configuration Manager for Vision Controller
Load/save gesture → action mappings
"""

import json
import os
from typing import Dict, Any, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConfigManager:
    """Manage gesture configuration"""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            # Default to config/gestures.json relative to project root
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            config_path = os.path.join(project_root, 'config', 'gestures.json')
        
        self.config_path = config_path
        self.config = {}
        self.load()
    
    def load(self) -> bool:
        """
        Load configuration from JSON file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.exists(self.config_path):
                logger.warning(f"Config file not found: {self.config_path}")
                self.config = {}
                return False
            
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
            
            logger.info(f"Loaded config with {len(self.config)} gestures")
            return True
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            return False
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save configuration to JSON file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            
            logger.info(f"Saved config with {len(self.config)} gestures")
            return True
            
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False
    
    def get_action(self, gesture: str) -> Optional[Dict[str, Any]]:
        """
        Get action configuration for a gesture
        
        Args:
            gesture: Gesture name (e.g., 'peace', 'thumbs_up')
            
        Returns:
            Action config dict or None if not found
        """
        return self.config.get(gesture)
    
    def set_action(self, gesture: str, action_config: Dict[str, Any]) -> bool:
        """
        Set action configuration for a gesture
        
        Args:
            gesture: Gesture name
            action_config: Action configuration dict
            
        Returns:
            True if successful
        """
        self.config[gesture] = action_config
        return self.save()
    
    def remove_action(self, gesture: str) -> bool:
        """
        Remove action configuration for a gesture
        
        Args:
            gesture: Gesture name
            
        Returns:
            True if successful
        """
        if gesture in self.config:
            del self.config[gesture]
            return self.save()
        return False
    
    def list_gestures(self) -> list:
        """Get list of configured gesture names"""
        return list(self.config.keys())
    
    def get_all(self) -> Dict[str, Any]:
        """Get entire configuration"""
        return self.config.copy()


# Test functionality
if __name__ == "__main__":
    config_mgr = ConfigManager()
    
    print("Configuration Manager Test")
    print("=" * 50)
    
    # List gestures
    gestures = config_mgr.list_gestures()
    print(f"\nConfigured gestures ({len(gestures)}):")
    for gesture in gestures:
        action = config_mgr.get_action(gesture)
        desc = action.get('description', 'No description')
        print(f"  - {gesture}: {desc}")
    
    # Test get action
    print("\nTesting get_action('peace'):")
    peace_action = config_mgr.get_action('peace')
    print(json.dumps(peace_action, indent=2))
    
    print("\nConfiguration Manager initialized successfully")
