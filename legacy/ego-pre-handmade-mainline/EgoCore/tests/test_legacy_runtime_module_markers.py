from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_legacy_agent_runner_marked_compatibility_only():
    text = (ROOT / 'app/runtime/agent_runner.py').read_text(encoding='utf-8')
    assert 'NOT the formal Telegram Runtime v2 mainline' in text
    assert 'compatibility containment' in text


def test_legacy_request_modules_marked_compatibility_only():
    classifier = (ROOT / 'app/runtime/request_classifier.py').read_text(encoding='utf-8')
    registry = (ROOT / 'app/runtime/request_registry.py').read_text(encoding='utf-8')
    assert 'Legacy request classification layer kept for compatibility' in classifier
    assert 'not the authority source for Telegram Runtime v2 mainline behavior' in classifier
    assert 'Legacy request lifecycle registry kept for compatibility' in registry
    assert 'not the formal lifecycle truth for Telegram Runtime v2 mainline' in registry


def test_legacy_runtime_module_status_doc_exists():
    text = (ROOT / 'docs/LEGACY_RUNTIME_MODULE_STATUS.md').read_text(encoding='utf-8')
    assert 'Formal Mainline' in text
    assert 'Compatibility-Only Paths' in text
    assert 'app/runtime/agent_runner.py' in text
    assert 'app/runtime/request_classifier.py' in text
    assert 'app/runtime/request_registry.py' in text
