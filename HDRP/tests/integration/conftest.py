"""Pytest configuration and shared fixtures for integration tests.

Provides reusable fixtures for:
- Simulated search providers
- Temporary artifact directories
- Service process management
- Dynamic port allocation
"""

import os
import sys
import time
import socket
import tempfile
import shutil
import subprocess
from pathlib import Path
from typing import Generator, List, Tuple, Optional

import pytest

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from HDRP.tools.search.simulated import SimulatedSearchProvider
from HDRP.tools.search.factory import SearchFactory


@pytest.fixture
def simulated_search_provider() -> SimulatedSearchProvider:
    """Provides a deterministic simulated search provider for testing."""
    return SimulatedSearchProvider(latency_mean=0.01)  # Fast for testing


@pytest.fixture
def temp_artifacts_dir() -> Generator[Path, None, None]:
    """Provides a temporary directory for test artifacts with automatic cleanup."""
    temp_dir = Path(tempfile.mkdtemp(prefix="hdrp_test_"))
    yield temp_dir
    # Cleanup
    if temp_dir.exists():
        shutil.rmtree(temp_dir)


@pytest.fixture
def grpc_port_pool() -> Generator[callable, None, None]:
    """Provides dynamic port allocation for parallel test execution."""
    used_ports: List[int] = []
    
    def get_port(start: int = 50060) -> int:
        """Allocate an available port starting from the given port."""
        port = start
        while port < 60000:
            if port not in used_ports:
                # Check if port is actually available
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    sock.bind(('localhost', port))
                    sock.close()
                    used_ports.append(port)
                    return port
                except OSError:
                    port += 1
            else:
                port += 1
        raise RuntimeError("No available ports in range")
    
    yield get_port


@pytest.fixture
def service_manager() -> Generator[callable, None, None]:
    """Manages service process lifecycle with automatic cleanup."""
    processes: List[Tuple[str, subprocess.Popen]] = []
    
    def start_service(name: str, script_path: str, port: int, **env_vars) -> subprocess.Popen:
        """Start a service and track it for cleanup."""
        env = os.environ.copy()
        env.update(env_vars)
        
        cmd = [sys.executable, script_path, "--port", str(port)]
        
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        
        processes.append((name, proc))
        return proc
    
    yield start_service
    
    # Cleanup: terminate all services
    for name, proc in processes:
        if proc.poll() is None:  # Still running
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()


def wait_for_service(host: str, port: int, timeout: int = 5) -> bool:
    """Wait for a service to become available on the given port."""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                return True
        except Exception:
            pass
        
        time.sleep(0.2)
    
    return False


@pytest.fixture
def ensure_search_provider_env():
    """Ensures HDRP_SEARCH_PROVIDER is set to simulated for tests."""
    original_value = os.environ.get("HDRP_SEARCH_PROVIDER")
    os.environ["HDRP_SEARCH_PROVIDER"] = "simulated"
    
    yield
    
    # Restore original value
    if original_value is not None:
        os.environ["HDRP_SEARCH_PROVIDER"] = original_value
    else:
        os.environ.pop("HDRP_SEARCH_PROVIDER", None)


@pytest.fixture
def mock_artifacts_dir(tmp_path, monkeypatch) -> Path:
    """Mock the ARTIFACTS_DIR to use a temp directory."""
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    
    # Patch the ARTIFACTS_DIR constant in cli module
    import HDRP.cli as cli_module
    monkeypatch.setattr(cli_module, "ARTIFACTS_DIR", artifacts_dir)
    
    return artifacts_dir
@pytest.fixture(autouse=True)
def mock_nli_verifier(monkeypatch):
    """Mock NLIVerifier to avoid loading heavy models during tests."""
    from HDRP.services.critic.nli_verifier import NLIVerifier
    
    mock_verifier = MagicMock()
    # Default behavior: return 0.8 entailment, 0.1 contradiction
    mock_verifier.compute_relation.return_value = {
        "entailment": 0.8,
        "contradiction": 0.1,
        "neutral": 0.1
    }
    mock_verifier.compute_entailment.return_value = 0.8
    mock_verifier.compute_entailment_batch.side_effect = lambda pairs: [0.8] * len(pairs)
    mock_verifier.compute_relation_batch.side_effect = lambda pairs: [{
        "entailment": 0.8,
        "contradiction": 0.1,
        "neutral": 0.1
    }] * len(pairs)
    
    # We need to mock the class itself to return our mock instance
    monkeypatch.setattr("HDRP.services.critic.service.NLIVerifier", lambda: mock_verifier)
    monkeypatch.setattr("HDRP.services.critic.nli_verifier.NLIVerifier", lambda: mock_verifier)
    
    return mock_verifier


from unittest.mock import MagicMock
