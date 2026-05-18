"""
Pytest configuration for OpenEmotion tests
"""
import os
import sys
import importlib
import pytest
import pytest_asyncio
import asyncio
import tempfile
import shutil
import socket
from pathlib import Path
from emotiond.db import init_db
from emotiond import api


OPENEMOTION_ROOT = Path(__file__).resolve().parents[1]
OPENEMOTION_TOOLS_ROOT = OPENEMOTION_ROOT / "tools"


def _ensure_openemotion_tools_namespace() -> None:
    openemotion_root_str = str(OPENEMOTION_ROOT)
    if openemotion_root_str not in sys.path:
        sys.path.insert(0, openemotion_root_str)

    loaded_tools = sys.modules.get("tools")
    loaded_tools_file = getattr(loaded_tools, "__file__", None)
    if loaded_tools_file:
        loaded_tools_path = Path(loaded_tools_file).resolve()
        if not loaded_tools_path.is_relative_to(OPENEMOTION_TOOLS_ROOT):
            for module_name in list(sys.modules):
                if module_name == "tools" or module_name.startswith("tools."):
                    del sys.modules[module_name]

    importlib.import_module("tools")


_ensure_openemotion_tools_namespace()


def pytest_addoption(parser):
    """Add custom command line options for live integration tests."""
    parser.addoption(
        "--no-live",
        action="store_true",
        default=False,
        help="Disable live integration tests that auto-start emotiond"
    )


# Test tokens for MVP-2.1.1 security
TEST_SYSTEM_TOKEN = "test-system-token-for-tests"
TEST_OPENCLAW_TOKEN = "test-openclaw-token-for-tests"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def isolated_db():
    """Setup isolated database for tests with proper cleanup"""
    from emotiond import config, db, core
    import importlib

    test_data_dir = tempfile.mkdtemp(prefix="emotiond_test_")
    original_db_path = os.environ.get("EMOTIOND_DB_PATH")
    original_system_token = os.environ.get("EMOTIOND_SYSTEM_TOKEN")
    original_openclaw_token = os.environ.get("EMOTIOND_OPENCLAW_TOKEN")

    os.environ["EMOTIOND_DB_PATH"] = os.path.join(test_data_dir, "test_emotiond.db")
    os.environ["EMOTIOND_SYSTEM_TOKEN"] = TEST_SYSTEM_TOKEN
    os.environ["EMOTIOND_OPENCLAW_TOKEN"] = TEST_OPENCLAW_TOKEN

    importlib.reload(config)
    importlib.reload(db)
    importlib.reload(core)
    importlib.reload(api)

    # Reset global state (including MVP-2 fields)
    core.emotion_state.valence = 0.0
    core.emotion_state.arousal = 0.3
    core.emotion_state.subjective_time = 0
    core.emotion_state.prediction_error = 0.0
    core.emotion_state.anger = 0.0
    core.emotion_state.sadness = 0.0
    core.emotion_state.anxiety = 0.0
    core.emotion_state.joy = 0.0
    core.emotion_state.loneliness = 0.0
    core.emotion_state.regulation_budget = 1.0
    core.emotion_state.social_safety = 0.6
    core.emotion_state.energy = 0.7
    core.relationship_manager.relationships = {}
    core.relationship_manager.last_actions = {}

    await db.init_db()

    yield

    if original_db_path:
        os.environ["EMOTIOND_DB_PATH"] = original_db_path
    else:
        os.environ.pop("EMOTIOND_DB_PATH", None)

    if original_system_token:
        os.environ["EMOTIOND_SYSTEM_TOKEN"] = original_system_token
    else:
        os.environ.pop("EMOTIOND_SYSTEM_TOKEN", None)

    if original_openclaw_token:
        os.environ["EMOTIOND_OPENCLAW_TOKEN"] = original_openclaw_token
    else:
        os.environ.pop("EMOTIOND_OPENCLAW_TOKEN", None)

    # Reset state after test
    core.emotion_state.valence = 0.0
    core.emotion_state.arousal = 0.3
    core.emotion_state.subjective_time = 0
    core.emotion_state.prediction_error = 0.0
    core.emotion_state.anger = 0.0
    core.emotion_state.sadness = 0.0
    core.emotion_state.anxiety = 0.0
    core.emotion_state.joy = 0.0
    core.emotion_state.loneliness = 0.0
    core.emotion_state.regulation_budget = 1.0
    core.emotion_state.social_safety = 0.6
    core.emotion_state.energy = 0.7
    core.relationship_manager.relationships = {}
    core.relationship_manager.last_actions = {}

    shutil.rmtree(test_data_dir, ignore_errors=True)


@pytest.fixture
def test_db_path():
    return "data/test_emotiond.db"


@pytest_asyncio.fixture(scope="function")
async def setup_db():
    """Alias for isolated_db - backward compatibility"""
    from emotiond import config, db, core
    import importlib

    test_data_dir = tempfile.mkdtemp(prefix="emotiond_test_")
    original_db_path = os.environ.get("EMOTIOND_DB_PATH")
    original_system_token = os.environ.get("EMOTIOND_SYSTEM_TOKEN")
    original_openclaw_token = os.environ.get("EMOTIOND_OPENCLAW_TOKEN")

    os.environ["EMOTIOND_DB_PATH"] = os.path.join(test_data_dir, "test_emotiond.db")
    os.environ["EMOTIOND_SYSTEM_TOKEN"] = TEST_SYSTEM_TOKEN
    os.environ["EMOTIOND_OPENCLAW_TOKEN"] = TEST_OPENCLAW_TOKEN

    importlib.reload(config)
    importlib.reload(db)
    importlib.reload(core)
    importlib.reload(api)

    core.emotion_state.valence = 0.0
    core.emotion_state.arousal = 0.3
    core.emotion_state.subjective_time = 0
    core.emotion_state.prediction_error = 0.0
    core.emotion_state.anger = 0.0
    core.emotion_state.sadness = 0.0
    core.emotion_state.anxiety = 0.0
    core.emotion_state.joy = 0.0
    core.emotion_state.loneliness = 0.0
    core.emotion_state.regulation_budget = 1.0
    core.emotion_state.social_safety = 0.6
    core.emotion_state.energy = 0.7
    core.relationship_manager.relationships = {}
    core.relationship_manager.last_actions = {}

    await db.init_db()

    yield

    if original_db_path:
        os.environ["EMOTIOND_DB_PATH"] = original_db_path
    else:
        os.environ.pop("EMOTIOND_DB_PATH", None)

    if original_system_token:
        os.environ["EMOTIOND_SYSTEM_TOKEN"] = original_system_token
    else:
        os.environ.pop("EMOTIOND_SYSTEM_TOKEN", None)

    if original_openclaw_token:
        os.environ["EMOTIOND_OPENCLAW_TOKEN"] = original_openclaw_token
    else:
        os.environ.pop("EMOTIOND_OPENCLAW_TOKEN", None)

    core.emotion_state.valence = 0.0
    core.emotion_state.arousal = 0.3
    core.emotion_state.subjective_time = 0
    core.emotion_state.prediction_error = 0.0
    core.emotion_state.anger = 0.0
    core.emotion_state.sadness = 0.0
    core.emotion_state.anxiety = 0.0
    core.emotion_state.joy = 0.0
    core.emotion_state.loneliness = 0.0
    core.emotion_state.regulation_budget = 1.0
    core.emotion_state.social_safety = 0.6
    core.emotion_state.energy = 0.7
    core.relationship_manager.relationships = {}
    core.relationship_manager.last_actions = {}

    shutil.rmtree(test_data_dir, ignore_errors=True)


def get_system_headers():
    """Return headers for system-authenticated requests"""
    return {"Authorization": f"Bearer {TEST_SYSTEM_TOKEN}"}


def get_openclaw_headers():
    """Return headers for openclaw-authenticated requests"""
    return {"Authorization": f"Bearer {TEST_OPENCLAW_TOKEN}"}


@pytest.fixture(scope="function")
def mock_emotiond_service():
    """Start mock emotiond service for integration tests."""
    import subprocess
    import time
    import requests
    import os
    from contextlib import closing

    def get_free_port():
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.bind(("127.0.0.1", 0))
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            return sock.getsockname()[1]

    mock_port = get_free_port()
    mock_base_url = f"http://127.0.0.1:{mock_port}"
    original_emotiond_url = os.environ.get("EMOTIOND_URL")
    original_emotiond_base_url = os.environ.get("EMOTIOND_BASE_URL")
    original_mock_port = os.environ.get("EMOTIOND_MOCK_PORT")

    os.environ["EMOTIOND_URL"] = mock_base_url
    os.environ["EMOTIOND_BASE_URL"] = mock_base_url
    os.environ["EMOTIOND_MOCK_PORT"] = str(mock_port)

    # Start mock service
    mock_script = os.path.join(os.path.dirname(__file__), "fixtures", "mock_emotiond.py")
    proc = subprocess.Popen(
        [sys.executable, mock_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for service to be ready
    max_wait = 10
    for i in range(max_wait):
        try:
            r = requests.get(f"{mock_base_url}/health", timeout=1)
            if r.status_code == 200:
                yield
                break
        except:
            time.sleep(0.5)
    else:
        # Clean up if service never started
        proc.terminate()
        proc.wait()
        if original_emotiond_url is not None:
            os.environ["EMOTIOND_URL"] = original_emotiond_url
        else:
            os.environ.pop("EMOTIOND_URL", None)
        if original_emotiond_base_url is not None:
            os.environ["EMOTIOND_BASE_URL"] = original_emotiond_base_url
        else:
            os.environ.pop("EMOTIOND_BASE_URL", None)
        if original_mock_port is not None:
            os.environ["EMOTIOND_MOCK_PORT"] = original_mock_port
        else:
            os.environ.pop("EMOTIOND_MOCK_PORT", None)
        pytest.fail("Mock emotiond service failed to start")

    # Clean up
    proc.terminate()
    proc.wait()
    if original_emotiond_url is not None:
        os.environ["EMOTIOND_URL"] = original_emotiond_url
    else:
        os.environ.pop("EMOTIOND_URL", None)
    if original_emotiond_base_url is not None:
        os.environ["EMOTIOND_BASE_URL"] = original_emotiond_base_url
    else:
        os.environ.pop("EMOTIOND_BASE_URL", None)
    if original_mock_port is not None:
        os.environ["EMOTIOND_MOCK_PORT"] = original_mock_port
    else:
        os.environ.pop("EMOTIOND_MOCK_PORT", None)


# Override emotiond_available fixture to use mock service
@pytest.fixture(scope="function")
def emotiond_available(mock_emotiond_service):
    """Check if emotiond is running (using mock service)."""
    return True
