"""
Neo4j lifecycle management utilities.

Provides functions to check, start, and stop Neo4j instances
for automated management during pipeline execution.
"""

import subprocess
import time
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


def is_neo4j_running() -> bool:
    """
    Check if Neo4j container is running.
    
    Returns:
        bool: True if Neo4j container is running, False otherwise
    """
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=kg-forge-neo4j", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return "kg-forge-neo4j" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.debug(f"Error checking Neo4j status: {e}")
        return False


def start_neo4j(wait_for_ready: bool = True, max_wait: int = 30) -> Tuple[bool, str]:
    """
    Start Neo4j using docker-compose.
    
    Args:
        wait_for_ready: Whether to wait for Neo4j to be ready
        max_wait: Maximum seconds to wait for Neo4j readiness
        
    Returns:
        Tuple of (success, message)
    """
    try:
        # Start Neo4j using docker-compose
        result = subprocess.run(
            ["docker-compose", "up", "-d", "neo4j"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            return False, f"Failed to start Neo4j: {result.stderr}"
        
        logger.info("Neo4j container started")
        
        if not wait_for_ready:
            return True, "Neo4j container started (not waiting for readiness)"
        
        # Wait for Neo4j to be ready
        logger.info("Waiting for Neo4j to be ready...")
        waited = 0
        
        while waited < max_wait:
            try:
                # Check if Neo4j is responding
                health_check = subprocess.run(
                    ["docker", "exec", "kg-forge-neo4j", "wget", "--spider", "-q", "http://localhost:7474"],
                    capture_output=True,
                    timeout=2
                )
                if health_check.returncode == 0:
                    logger.info(f"Neo4j is ready (waited {waited}s)")
                    return True, f"Neo4j started and ready after {waited}s"
            except (subprocess.TimeoutExpired, Exception):
                pass
            
            time.sleep(2)
            waited += 2
        
        # Timed out but container is running
        return True, f"Neo4j started but may still be initializing (waited {max_wait}s)"
        
    except FileNotFoundError:
        return False, "docker-compose not found. Please install Docker and docker-compose"
    except subprocess.TimeoutExpired:
        return False, "Timeout while starting Neo4j"
    except Exception as e:
        return False, f"Unexpected error starting Neo4j: {e}"


def stop_neo4j() -> Tuple[bool, str]:
    """
    Stop Neo4j using docker-compose.
    
    Returns:
        Tuple of (success, message)
    """
    try:
        result = subprocess.run(
            ["docker-compose", "stop", "neo4j"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return False, f"Failed to stop Neo4j: {result.stderr}"
        
        logger.info("Neo4j container stopped")
        return True, "Neo4j container stopped successfully"
        
    except FileNotFoundError:
        return False, "docker-compose not found"
    except subprocess.TimeoutExpired:
        return False, "Timeout while stopping Neo4j"
    except Exception as e:
        return False, f"Unexpected error stopping Neo4j: {e}"
