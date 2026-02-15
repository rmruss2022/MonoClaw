"""
Unit tests for ConfigManager
Tests load/save/update config operations
"""
import pytest
import sys
import os
import json
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))
from config_manager import ConfigManager


class TestConfigManager:
    """Tests for the ConfigManager class"""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Fixture to create a temporary config directory"""
        temp_dir = tempfile.mkdtemp()
        config_path = os.path.join(temp_dir, 'gestures.json')
        
        # Create initial config
        initial_config = {
            'peace': {
                'action_type': 'applescript',
                'description': 'Play/Pause media',
                'params': {'script': 'tell application "System Events" to key code 19'}
            },
            'thumbs_up': {
                'action_type': 'keyboard',
                'description': 'Like current track',
                'params': {'keys': ['cmd', 'l']}
            }
        }
        
        with open(config_path, 'w') as f:
            json.dump(initial_config, f)
        
        yield config_path
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def empty_config_dir(self):
        """Fixture to create an empty temporary directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_initialization_with_custom_path(self, temp_config_dir):
        """Test initialization with custom config path"""
        manager = ConfigManager(config_path=temp_config_dir)
        
        assert manager.config_path == temp_config_dir
        assert 'peace' in manager.config
        assert 'thumbs_up' in manager.config
    
    def test_load_existing_config(self, temp_config_dir):
        """Test loading an existing config file"""
        manager = ConfigManager(config_path=temp_config_dir)
        
        result = manager.load()
        
        assert result is True
        assert manager.config['peace']['action_type'] == 'applescript'
    
    def test_load_nonexistent_config(self, empty_config_dir):
        """Test loading when config file doesn't exist"""
        nonexistent_path = os.path.join(empty_config_dir, 'gestures.json')
        manager = ConfigManager(config_path=nonexistent_path)
        
        result = manager.load()
        
        assert result is False
        assert manager.config == {}
    
    def test_load_invalid_json(self, empty_config_dir):
        """Test loading invalid JSON file"""
        invalid_path = os.path.join(empty_config_dir, 'gestures.json')
        
        with open(invalid_path, 'w') as f:
            f.write('{"invalid: json}')
        
        manager = ConfigManager(config_path=invalid_path)
        result = manager.load()
        
        assert result is False
    
    def test_save_config(self, empty_config_dir):
        """Test saving configuration"""
        config_path = os.path.join(empty_config_dir, 'gestures.json')
        manager = ConfigManager(config_path=config_path)
        
        # Add config data
        manager.config = {
            'fist': {
                'action_type': 'keyboard',
                'description': 'Mute audio',
                'params': {'keys': ['cmd', 'shift', 'm']}
            }
        }
        
        result = manager.save()
        
        assert result is True
        assert os.path.exists(config_path)
        
        # Verify content
        with open(config_path, 'r') as f:
            saved = json.load(f)
        assert saved['fist']['action_type'] == 'keyboard'
    
    def test_save_creates_directory(self, empty_config_dir):
        """Test that save creates config directory if needed"""
        nested_dir = os.path.join(empty_config_dir, 'nested', 'config')
        config_path = os.path.join(nested_dir, 'gestures.json')
        
        manager = ConfigManager(config_path=config_path)
        manager.config = {'test': {'action_type': 'test'}}
        
        result = manager.save()
        
        assert result is True
        assert os.path.exists(nested_dir)
    
    def test_get_action_existing(self, temp_config_dir):
        """Test getting an existing action"""
        manager = ConfigManager(config_path=temp_config_dir)
        
        action = manager.get_action('peace')
        
        assert action is not None
        assert action['action_type'] == 'applescript'
    
    def test_get_action_nonexistent(self, temp_config_dir):
        """Test getting a non-existent action"""
        manager = ConfigManager(config_path=temp_config_dir)
        
        action = manager.get_action('nonexistent')
        
        assert action is None
    
    def test_set_action_new(self, empty_config_dir):
        """Test setting a new action"""
        config_path = os.path.join(empty_config_dir, 'gestures.json')
        manager = ConfigManager(config_path=config_path)
        
        new_action = {
            'action_type': 'openclaw_rpc',
            'description': 'Send message',
            'params': {'method': '/api/message'}
        }
        
        result = manager.set_action('wave', new_action)
        
        assert result is True
        assert manager.config['wave'] == new_action
        
        # Verify it was saved
        with open(config_path, 'r') as f:
            saved = json.load(f)
        assert saved['wave']['action_type'] == 'openclaw_rpc'
    
    def test_set_action_update_existing(self, temp_config_dir):
        """Test updating an existing action"""
        manager = ConfigManager(config_path=temp_config_dir)
        
        updated_action = {
            'action_type': 'keyboard',
            'description': 'Updated description',
            'params': {'keys': ['space']}
        }
        
        result = manager.set_action('peace', updated_action)
        
        assert result is True
        assert manager.config['peace']['action_type'] == 'keyboard'
    
    def test_remove_action_existing(self, temp_config_dir):
        """Test removing an existing action"""
        manager = ConfigManager(config_path=temp_config_dir)
        
        result = manager.remove_action('peace')
        
        assert result is True
        assert 'peace' not in manager.config
    
    def test_remove_action_nonexistent(self, temp_config_dir):
        """Test removing a non-existent action"""
        manager = ConfigManager(config_path=temp_config_dir)
