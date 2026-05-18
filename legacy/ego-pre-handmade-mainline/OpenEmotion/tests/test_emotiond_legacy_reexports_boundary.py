from emotiond import memory
from emotiond import self_model


def test_memory_formal_surface_excludes_legacy_symbols():
    assert not hasattr(memory, "MemorySystem")
    assert not hasattr(memory, "memory_system")
    assert not hasattr(memory, "initialize_memory_system")


def test_self_model_formal_surface_excludes_legacy_symbols():
    assert not hasattr(self_model, "SelfModelV0")
    assert not hasattr(self_model, "get_self_model_v0")
    assert not hasattr(self_model, "build_self_model_v0")
    assert not hasattr(self_model, "render_self_report")
