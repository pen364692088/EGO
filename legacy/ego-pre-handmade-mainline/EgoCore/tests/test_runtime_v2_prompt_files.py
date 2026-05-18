from app.runtime_v2 import RuntimeV2DecisionEngine, RuntimeV2PromptFiles


def test_runtime_v2_prompt_files_load_default_markdown_files():
    bundle = RuntimeV2PromptFiles().load()
    assert "AGENT.md" in bundle.loaded
    assert "SOUL.md" in bundle.loaded
    assert "TOOLS.md" in bundle.loaded


def test_runtime_v2_decision_engine_builds_file_based_system_prompt():
    engine = RuntimeV2DecisionEngine()
    prompt = engine.build_system_prompt()
    assert "## AGENT.md" in prompt
    assert "## SOUL.md" in prompt
    assert "## TOOLS.md" in prompt
    assert "BUILTIN_RUNTIME_V2_CONTRACT" in prompt
