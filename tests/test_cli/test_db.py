"""Test database CLI commands."""

import pytest
from click.testing import CliRunner
from unittest.mock import Mock, patch, MagicMock

from kg_forge.cli.db import db_group
from kg_forge.graph.exceptions import ConnectionError as GraphConnectionError, GraphError


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def mock_settings():
    """Mock settings object."""
    settings = Mock()
    settings.neo4j.uri = "bolt://localhost:7687"
    settings.validate_namespace = Mock()
    return settings


@pytest.fixture
def mock_client():
    """Mock graph client."""
    client = Mock()
    client.connect = Mock()
    client.close = Mock()
    return client


@pytest.fixture
def mock_schema_manager():
    """Mock schema manager."""
    schema_mgr = Mock()
    schema_mgr.create_schema = Mock()
    schema_mgr.verify_schema = Mock(return_value=True)
    schema_mgr.clear_namespace = Mock(return_value=42)
    schema_mgr.get_statistics = Mock(return_value={'total_nodes': 100, 'message': 'test'})
    return schema_mgr


class TestDbInit:
    """Test db init command."""
    
    @patch('kg_forge.cli.db.get_settings')
    @patch('kg_forge.cli.db.get_graph_client')
    @patch('kg_forge.cli.db.get_schema_manager')
    def test_init_default_namespace(self, mock_get_schema, mock_get_client, mock_get_settings, 
                                    runner, mock_settings, mock_client, mock_schema_manager):
        """Test db init with default namespace."""
        mock_get_settings.return_value = mock_settings
        mock_get_client.return_value = mock_client
        mock_get_schema.return_value = mock_schema_manager
        
        result = runner.invoke(db_group, ['init'])
        
        assert result.exit_code == 0
        assert "Schema created successfully" in result.output
        mock_settings.validate_namespace.assert_called_once_with('default')
        mock_client.connect.assert_called_once()
        mock_schema_manager.create_schema.assert_called_once()
        mock_client.close.assert_called_once()
    
    @patch('kg_forge.cli.db.get_settings')
    @patch('kg_forge.cli.db.get_graph_client')
    @patch('kg_forge.cli.db.get_schema_manager')
    def test_init_custom_namespace(self, mock_get_schema, mock_get_client, mock_get_settings,
                                   runner, mock_settings, mock_client, mock_schema_manager):
        """Test db init with custom namespace."""
        mock_get_settings.return_value = mock_settings
        mock_get_client.return_value = mock_client
        mock_get_schema.return_value = mock_schema_manager
        
        result = runner.invoke(db_group, ['init', '--namespace', 'production'])
        
        assert result.exit_code == 0
        mock_settings.validate_namespace.assert_called_once_with('production')
    
    @patch('kg_forge.cli.db.get_settings')
    @patch('kg_forge.cli.db.get_graph_client')
    @patch('kg_forge.cli.db.get_schema_manager')
    def test_init_drop_existing(self, mock_get_schema, mock_get_client, mock_get_settings,
                                runner, mock_settings, mock_client, mock_schema_manager):
        """Test db init with drop existing flag."""
        mock_get_settings.return_value = mock_settings
        mock_get_client.return_value = mock_client
        mock_get_schema.return_value = mock_schema_manager
        
        result = runner.invoke(db_group, ['init', '--drop-existing'])
        
        assert result.exit_code == 0
        assert "Deleted 42 nodes" in result.output
        mock_schema_manager.clear_namespace.assert_called_once_with('default')
    
    @patch('kg_forge.cli.db.get_settings')
    def test_init_invalid_namespace(self, mock_get_settings, runner, mock_settings):
        """Test db init with invalid namespace."""
        mock_get_settings.return_value = mock_settings
        mock_settings.validate_namespace.side_effect = ValueError("Invalid namespace")
        
        result = runner.invoke(db_group, ['init', '--namespace', 'invalid!@#'])
        
        assert result.exit_code == 1
        assert "Invalid namespace" in result.output
    
    @patch('kg_forge.cli.db.get_settings')
    @patch('kg_forge.cli.db.get_graph_client')
    @patch('kg_forge.cli.db.get_schema_manager')
    def test_init_connection_error(self, mock_get_schema, mock_get_client, mock_get_settings, 
                                   runner, mock_settings, mock_client, mock_schema_manager):
        """Test db init with connection error."""
        mock_get_settings.return_value = mock_settings
        mock_get_client.return_value = mock_client
        mock_get_schema.return_value = mock_schema_manager
        mock_client.connect.side_effect = GraphConnectionError("Connection failed")
        
        result = runner.invoke(db_group, ['init'])
        
        assert result.exit_code == 1
        assert "Connection Error" in result.output
        assert "Make sure Neo4j is running" in result.output


class TestDbStatus:
    """Test db status command."""
    
    @patch('kg_forge.cli.db.get_settings')
    @patch('kg_forge.cli.db.get_graph_client')
    @patch('kg_forge.cli.db.get_schema_manager')
    def test_status_no_namespace(self, mock_get_schema, mock_get_client, mock_get_settings,
                                 runner, mock_settings, mock_client, mock_schema_manager):
        """Test db status without namespace."""
        mock_get_settings.return_value = mock_settings
        mock_get_client.return_value = mock_client
        mock_get_schema.return_value = mock_schema_manager
        
        result = runner.invoke(db_group, ['status'])
        
        assert result.exit_code == 0
        assert "Connected to Neo4j" in result.output
        assert "Total Nodes: 100" in result.output
        mock_client.connect.assert_called_once()
        mock_schema_manager.verify_schema.assert_called_once()
    
    @patch('kg_forge.cli.db.get_settings')
    @patch('kg_forge.cli.db.get_graph_client')
    @patch('kg_forge.cli.db.get_schema_manager')
    def test_status_with_namespace(self, mock_get_schema, mock_get_client, mock_get_settings,
                                   runner, mock_settings, mock_client, mock_schema_manager):
        """Test db status with namespace."""
        mock_get_settings.return_value = mock_settings
        mock_get_client.return_value = mock_client
        mock_get_schema.return_value = mock_schema_manager
        mock_schema_manager.get_statistics.return_value = {
            'nodes': {'Entity': 50, 'Doc': 25},
            'relationships': {'MENTIONS': 100}
        }
        
        result = runner.invoke(db_group, ['status', '--namespace', 'test'])
        
        assert result.exit_code == 0
        assert "Namespace: test" in result.output
        assert "Entity: 50" in result.output
        assert "MENTIONS: 100" in result.output


class TestDbClear:
    """Test db clear command."""
    
    @patch('kg_forge.cli.db.get_settings')
    @patch('kg_forge.cli.db.get_graph_client')
    @patch('kg_forge.cli.db.get_schema_manager')
    @patch('kg_forge.cli.db.click.confirm')
    def test_clear_with_confirmation(self, mock_confirm, mock_get_schema, mock_get_client,
                                    mock_get_settings, runner, mock_settings, mock_client,
                                    mock_schema_manager):
        """Test db clear with interactive confirmation."""
        mock_get_settings.return_value = mock_settings
        mock_get_client.return_value = mock_client
        mock_get_schema.return_value = mock_schema_manager
        mock_confirm.return_value = True
        
        result = runner.invoke(db_group, ['clear', '--namespace', 'test'])
        
        assert result.exit_code == 0
        assert "Deleted 42 nodes" in result.output
        mock_confirm.assert_called_once()
        mock_schema_manager.clear_namespace.assert_called_once_with('test')
    
    @patch('kg_forge.cli.db.get_settings')
    @patch('kg_forge.cli.db.click.confirm')
    def test_clear_cancelled(self, mock_confirm, mock_get_settings, 
                           runner, mock_settings):
        """Test db clear when user cancels."""
        mock_get_settings.return_value = mock_settings
        mock_confirm.return_value = False
        
        result = runner.invoke(db_group, ['clear', '--namespace', 'test'])
        
        assert result.exit_code == 0
        assert "Operation cancelled" in result.output
    
    @patch('kg_forge.cli.db.get_settings')
    @patch('kg_forge.cli.db.get_graph_client')
    @patch('kg_forge.cli.db.get_schema_manager')
    def test_clear_with_confirm_flag(self, mock_get_schema, mock_get_client, mock_get_settings,
                                     runner, mock_settings, mock_client, mock_schema_manager):
        """Test db clear with --confirm flag (no prompt)."""
        mock_get_settings.return_value = mock_settings
        mock_get_client.return_value = mock_client
        mock_get_schema.return_value = mock_schema_manager
        
        result = runner.invoke(db_group, ['clear', '--namespace', 'test', '--confirm'])
        
        assert result.exit_code == 0
        assert "Deleted 42 nodes" in result.output
        mock_schema_manager.clear_namespace.assert_called_once_with('test')


class TestDbStartStop:
    """Test db start and stop commands."""
    
    @patch('kg_forge.cli.db.subprocess.run')
    @patch('kg_forge.cli.db.get_settings')
    def test_start_success(self, mock_get_settings, mock_subprocess, runner, mock_settings):
        """Test db start command success."""
        mock_get_settings.return_value = mock_settings
        mock_subprocess.return_value = Mock(returncode=0)
        
        result = runner.invoke(db_group, ['start'])
        
        assert result.exit_code == 0
        assert "Neo4j container started" in result.output
        # Check the first call was docker-compose up
        first_call = mock_subprocess.call_args_list[0]
        assert "docker-compose" in str(first_call)
        assert "up" in str(first_call)
    
    @patch('kg_forge.cli.db.subprocess.run')
    def test_start_docker_not_found(self, mock_subprocess, runner):
        """Test db start when docker-compose not found."""
        mock_subprocess.side_effect = FileNotFoundError()
        
        result = runner.invoke(db_group, ['start'])
        
        assert result.exit_code == 1
        assert "docker-compose not found" in result.output
    
    @patch('kg_forge.cli.db.subprocess.run')
    @patch('kg_forge.cli.db.get_settings')
    def test_stop_success(self, mock_get_settings, mock_subprocess, runner, mock_settings):
        """Test db stop command success."""
        mock_get_settings.return_value = mock_settings
        mock_subprocess.return_value = Mock(returncode=0)
        
        result = runner.invoke(db_group, ['stop'])
        
        assert result.exit_code == 0
        assert "Neo4j container stopped" in result.output
        assert "Data is preserved" in result.output


class TestDbHelp:
    """Test db command help messages."""
    
    def test_db_group_help(self, runner):
        """Test db group help."""
        result = runner.invoke(db_group, ['--help'])
        
        assert result.exit_code == 0
        assert "Database management commands" in result.output
        assert "init" in result.output
        assert "start" in result.output
        assert "stop" in result.output
        assert "status" in result.output
        assert "clear" in result.output
    
    def test_init_help(self, runner):
        """Test db init help."""
        result = runner.invoke(db_group, ['init', '--help'])
        
        assert result.exit_code == 0
        assert "Initialize database schema" in result.output
        assert "--namespace" in result.output
        assert "--drop-existing" in result.output
    
    def test_status_help(self, runner):
        """Test db status help."""
        result = runner.invoke(db_group, ['status', '--help'])
        
        assert result.exit_code == 0
        assert "Show database connection status" in result.output
    
    def test_clear_help(self, runner):
        """Test db clear help."""
        result = runner.invoke(db_group, ['clear', '--help'])
        
        assert result.exit_code == 0
        assert "Clear all data for a specific namespace" in result.output
        assert "--namespace" in result.output
        assert "--confirm" in result.output
