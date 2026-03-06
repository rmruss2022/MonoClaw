"""
Unit tests for ActionDispatcher
Tests all action types: applescript, openclaw_rpc, keyboard
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))
from action_dispatcher import ActionDispatcher


class TestActionDispatcher:
    """Tests for the ActionDispatcher class"""
    
    @pytest.fixture
    def dispatcher(self):
        """Fixture to create an ActionDispatcher instance"""
        return ActionDispatcher(openclaw_host="localhost", openclaw_port=18795)
    
    def test_initialization(self, dispatcher):
        """Test that dispatcher initializes correctly"""
        assert dispatcher.openclaw_base_url == "http://localhost:18795"
        assert dispatcher.keyboard is not None
    
    def test_execute_unknown_action_type(self, dispatcher):
        """Test execution with unknown action type"""
        result = dispatcher.execute("unknown_type", {})
        
        assert result['success'] is False
        assert "Unknown action type" in result['message']
    
    @patch('action_dispatcher.subprocess.run')
    def test_execute_applescript_success(self, mock_run, dispatcher):
        """Test successful AppleScript execution"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Test output",
            stderr=""
        )
        
        result = dispatcher.execute("applescript", {
            'script': 'display notification "Test"'
        })
        
        assert result['success'] is True
        assert "AppleScript executed" in result['message']
        assert result['data'] == "Test output"
        mock_run.assert_called_once()
    
    @patch('action_dispatcher.subprocess.run')
    def test_execute_applescript_failure(self, mock_run, dispatcher):
        """Test AppleScript execution failure"""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="Script error"
        )
        
        result = dispatcher.execute("applescript", {
            'script': 'invalid script'
        })
        
        assert result['success'] is False
        assert "AppleScript failed" in result['message']
    
    def test_execute_applescript_empty_script(self, dispatcher):
        """Test AppleScript with empty script"""
        result = dispatcher.execute("applescript", {'script': ''})
        
        assert result['success'] is False
        assert "Empty script" in result['message']
    
    @patch('action_dispatcher.subprocess.run')
    def test_execute_applescript_timeout(self, mock_run, dispatcher):
        """Test AppleScript timeout handling"""
        from subprocess import TimeoutExpired
        mock_run.side_effect = TimeoutExpired('osascript', 10)
        
        result = dispatcher.execute("applescript", {
            'script': 'delay 20'
        })
        
        assert result['success'] is False
        assert "timeout" in result['message'].lower()
    
    @patch('action_dispatcher.requests.post')
    def test_execute_openclaw_rpc_success(self, mock_post, dispatcher):
        """Test successful OpenClaw RPC call"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"result": "success"}'
        mock_response.json.return_value = {"result": "success"}
        mock_post.return_value = mock_response
        
        result = dispatcher.execute("openclaw_rpc", {
            'method': '/api/message',
            'params': {'message': 'test'}
        })
        
        assert result['success'] is True
        assert result['data'] == {"result": "success"}
    
    @patch('action_dispatcher.requests.post')
    def test_execute_openclaw_rpc_failure(self, mock_post, dispatcher):
        """Test OpenClaw RPC failure response"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response
        
        result = dispatcher.execute("openclaw_rpc", {
            'method': '/api/error',
            'params': {}
        })
        
        assert result['success'] is False
        assert "failed" in result['message'].lower()
    
    @patch('action_dispatcher.requests.post')
    def test_execute_openclaw_rpc_connection_error(self, mock_post, dispatcher):
        """Test OpenClaw RPC connection error"""
        from requests.exceptions import ConnectionError
        mock_post.side_effect = ConnectionError()
        
        result = dispatcher.execute("openclaw_rpc", {
            'method': '/api/test',
            'params': {}
        })
        
        assert result['success'] is False
        assert "Cannot connect" in result['message']
    
    @patch('action_dispatcher.requests.post')
    def test_execute_openclaw_rpc_timeout(self, mock_post, dispatcher):
        """Test OpenClaw RPC timeout"""
        from requests.exceptions import Timeout
        mock_post.side_effect = Timeout()
        
        result = dispatcher.execute("openclaw_rpc", {
            'method': '/api/test',
            'params': {}
        })
        
        assert result['success'] is False
        assert "timeout" in result['message'].lower()
    
    def test_execute_openclaw_rpc_empty_method(self, dispatcher):
        """Test OpenClaw RPC with empty method"""
        result = dispatcher.execute("openclaw_rpc", {
            'method': '',
            'params': {}
        })
        
        assert result['success'] is False
    
    @patch('action_dispatcher.KeyboardController')
    def test_execute_keyboard_success(self, mock_kb_class, dispatcher):
        """Test successful keyboard action"""
        mock_kb = Mock()
        mock_kb_class.return_value = mock_kb
        dispatcher.keyboard = mock_kb
        
        result = dispatcher.execute("keyboard", {
            'keys': ['cmd', 'c']
        })
        
        assert result['success'] is True
        assert "Pressed keys" in result['message']
        mock_kb.press.assert_called()
        mock_kb.release.assert_called()
    
    def test_execute_keyboard_empty_keys(self, dispatcher):
        """Test keyboard action with empty keys"""
        result = dispatcher.execute("keyboard", {'keys': []})
        
        assert result['success'] is False
        assert "Empty keys list" in result['message']
    
    @patch('action_dispatcher.KeyboardController')
    def test_execute_keyboard_single_key(self, mock_kb_class, dispatcher):
        """Test keyboard action with single key"""
        mock_kb = Mock()
        mock_kb_class.return_value = mock_kb
        dispatcher.keyboard = mock_kb
        
        result = dispatcher.execute("keyboard", {
            'keys': ['enter']
        })
        
        assert result['success'] is True
    
    @patch('action_dispatcher.KeyboardController')
    def test_execute_keyboard_special_keys(self, mock_kb_class, dispatcher):
        """Test keyboard action with special keys (cmd, ctrl, etc.)"""
        mock_kb = Mock()
        mock_kb_class.return_value = mock_kb
        dispatcher.keyboard = mock_kb
        
        from pynput.keyboard import Key
        result = dispatcher.execute("keyboard", {
            'keys': ['ctrl', 'alt', 'delete']
        })
        
        assert result['success'] is True
    
    def test_run_applescript_internal(self, dispatcher):
        """Test internal _run_applescript method directly"""
        with patch('action_dispatcher.subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                return