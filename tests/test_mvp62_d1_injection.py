import random

import pytest

from emotiond.injection import (
    Injection,
    InjectionAllocatorConfig,
    assemble_injections,
)


def mk(text, p, source=None, token_budget=128, ttl=10, safety="normal"):
    return Injection(
        text=text,
        priority=p,
        token_budget=token_budget,
        ttl=ttl,
        source=source or f"src-{p}",
        safety_level=safety,
    )


def parse_sources(block: str):
    # for tests that encode source in content
    return [line.split(":", 1)[0] for line in block.split("\n\n") if ":" in line]


class TestDeterminismAndSort:
    def test_high_priority_near_tail(self):
        items = [
            mk("A:low", 0.1, "A"),
            mk("B:mid", 0.5, "B"),
            mk("C:high", 0.9, "C"),
        ]
        out = assemble_injections(items, InjectionAllocatorConfig(max_bytes=3072))
        assert parse_sources(out.prompt_block) == ["A", "B", "C"]

    def test_stable_sort_equal_priority_preserves_input_order(self):
        items = [mk("A:first", 0.5, "A"), mk("B:second", 0.5, "B"), mk("C:third", 0.5, "C")]
        out = assemble_injections(items)
        assert parse_sources(out.prompt_block) == ["A", "B", "C"]

    @pytest.mark.parametrize("seed", list(range(10)))
    def test_same_input_same_output(self, seed):
        rng = random.Random(seed)
        items = []
        for i in range(12):
            p = rng.choice([0.2, 0.4, 0.6, 0.8])
            t = f"s{i}:" + ("x" * rng.randint(20, 120))
            items.append(mk(t, p, source=f"s{i}"))

        cfg = InjectionAllocatorConfig(max_bytes=700, summary_max_chars=50)
        out1 = assemble_injections(items, cfg)
        out2 = assemble_injections(items, cfg)
        assert out1.prompt_block == out2.prompt_block
        assert out1.total_bytes == out2.total_bytes
        assert [x.truncation_reason for x in out1.items] == [x.truncation_reason for x in out2.items]


class TestBudgetEnforcement:
    @pytest.mark.parametrize("budget", [64, 128, 256, 512, 1024, 2048, 3072])
    def test_never_exceeds_budget(self, budget):
        items = [mk(f"S{i}:" + ("x" * 700), i / 10.0, source=f"S{i}") for i in range(8)]
        out = assemble_injections(items, InjectionAllocatorConfig(max_bytes=budget, summary_max_chars=40))
        assert out.total_bytes <= budget
        assert len(out.prompt_block.encode("utf-8")) <= budget

    @pytest.mark.parametrize("n", [1, 2, 4, 8, 16, 24])
    def test_3kb_hard_cap_default(self, n):
        items = [mk(f"s{i}:" + ("z" * 1000), (i % 10) / 10.0, source=f"s{i}") for i in range(n)]
        out = assemble_injections(items, InjectionAllocatorConfig())
        assert out.total_bytes <= 3072

    def test_utf8_multibyte_budget_respected(self):
        text = "多字节" * 300
        items = [mk(f"A:{text}", 0.1, "A"), mk(f"B:{text}", 0.2, "B")]
        out = assemble_injections(items, InjectionAllocatorConfig(max_bytes=500, summary_max_chars=20))
        assert out.total_bytes <= 500


class TestDegradeOrder:
    def test_drop_low_priority_before_summary(self):
        items = [
            mk("L:" + ("a" * 900), 0.1, "L"),
            mk("H:" + ("b" * 200), 0.9, "H"),
        ]
        out = assemble_injections(items, InjectionAllocatorConfig(max_bytes=260, summary_max_chars=180))
        reasons = {x.source: x.truncation_reason for x in out.items}
        assert reasons["L"] == "dropped_low_priority"

    def test_summary_before_pointer_only_when_possible(self):
        items = [
            mk("L:" + ("a" * 350), 0.1, "L"),
            mk("H:" + ("b" * 350), 0.9, "H"),
        ]
        out = assemble_injections(items, InjectionAllocatorConfig(max_bytes=420, summary_max_chars=40))
        reasons = [x.truncation_reason for x in out.items]
        assert "summarized" in reasons or "dropped_low_priority" in reasons

    def test_pointer_only_kicks_in_for_tiny_budget(self):
        items = [
            mk("L:" + ("a" * 600), 0.1, "L"),
            mk("H:" + ("b" * 600), 0.9, "H"),
        ]
        out = assemble_injections(items, InjectionAllocatorConfig(max_bytes=40, summary_max_chars=20))
        assert out.total_bytes <= 40
        assert any(x.truncation_reason in {"pointer_only", "dropped_low_priority"} for x in out.items)

    def test_low_priority_degraded_first_across_many(self):
        items = [mk(f"S{i}:" + ("x" * 500), i / 10.0, source=f"S{i}") for i in range(10)]
        out = assemble_injections(items, InjectionAllocatorConfig(max_bytes=300, summary_max_chars=30))
        reasons = {x.source: x.truncation_reason for x in out.items}
        assert reasons["S0"] in {"dropped_low_priority", "pointer_only", "summarized"}


class TestTraceAudit:
    def test_audit_contains_required_fields(self):
        out = assemble_injections([mk("A:hello", 0.2, "A")])
        entry = out.items[0]
        assert entry.source == "A"
        assert isinstance(entry.priority, float)
        assert isinstance(entry.original_bytes, int)
        assert isinstance(entry.final_bytes, int)
        assert entry.truncation_reason in {"kept", "dropped_low_priority", "summarized", "pointer_only"}

    def test_dropped_entry_has_zero_final_bytes(self):
        items = [mk("L:" + ("x" * 1000), 0.1, "L"), mk("H:ok", 0.9, "H")]
        out = assemble_injections(items, InjectionAllocatorConfig(max_bytes=16, summary_max_chars=10))
        low = [x for x in out.items if x.source == "L"][0]
        if low.truncation_reason == "dropped_low_priority":
            assert low.final_bytes == 0

    def test_audit_length_equals_input_length(self):
        items = [mk(f"S{i}:v", i / 10.0, source=f"S{i}") for i in range(7)]
        out = assemble_injections(items)
        assert len(out.items) == 7


class TestTunableParameters:
    @pytest.mark.parametrize("summary_chars", [24, 30, 40, 60, 100])
    def test_summary_max_chars_tunable(self, summary_chars):
        items = [mk("A:" + ("x" * 400), 0.5, "A")]
        out = assemble_injections(items, InjectionAllocatorConfig(max_bytes=80, summary_max_chars=summary_chars))
        assert out.total_bytes <= 80

    @pytest.mark.parametrize("suffix", [" ... [s]", " [cut]", " ~"])
    def test_summary_suffix_tunable(self, suffix):
        items = [mk("A:" + ("x" * 400), 0.5, "A")]
        out = assemble_injections(
            items,
            InjectionAllocatorConfig(max_bytes=60, summary_max_chars=20, summary_suffix=suffix),
        )
        assert out.total_bytes <= 60

    @pytest.mark.parametrize("tpl", ["[P {source} {idx}]", "<{source}:{idx}>", "PTR({source})#{idx}"])
    def test_pointer_template_tunable(self, tpl):
        items = [mk("A:" + ("x" * 900), 0.5, "A")]
        out = assemble_injections(items, InjectionAllocatorConfig(max_bytes=16, summary_max_chars=8, pointer_template=tpl))
        assert out.total_bytes <= 16


class TestEdgeCases:
    def test_empty_input(self):
        out = assemble_injections([])
        assert out.prompt_block == ""
        assert out.total_bytes == 0
        assert out.items == []

    def test_empty_text_allowed(self):
        out = assemble_injections([mk("", 0.1, "A")])
        assert out.total_bytes <= 3072

    def test_negative_priority_sorted_before_positive(self):
        items = [mk("P:pos", 0.1, "P"), mk("N:neg", -1.0, "N")]
        out = assemble_injections(items)
        assert parse_sources(out.prompt_block) == ["N", "P"]

    def test_large_input_set_deterministic(self):
        rng = random.Random(123)
        items = []
        for i in range(100):
            p = round(rng.random(), 2)
            items.append(mk(f"S{i}:" + ("k" * rng.randint(20, 90)), p, source=f"S{i}"))
        cfg = InjectionAllocatorConfig(max_bytes=900, summary_max_chars=45)
        out1 = assemble_injections(items, cfg)
        out2 = assemble_injections(items, cfg)
        assert out1.prompt_block == out2.prompt_block

    def test_budget_guard_exact_fit(self):
        text = "A:" + ("x" * 98)
        out = assemble_injections([mk(text, 0.5, "A")], InjectionAllocatorConfig(max_bytes=len(text.encode("utf-8")), summary_max_chars=98))
        assert out.total_bytes <= len(text.encode("utf-8"))

    def test_single_high_priority_may_be_degraded_if_needed(self):
        item = mk("H:" + ("x" * 5000), 1.0, "H")
        out = assemble_injections([item], InjectionAllocatorConfig(max_bytes=120, summary_max_chars=30))
        assert out.total_bytes <= 120

    @pytest.mark.parametrize("count", [3, 5, 7, 9, 11])
    def test_stable_sort_with_repeated_priorities(self, count):
        items = [mk(f"S{i}:v", 0.5 if i % 2 == 0 else 0.2, source=f"S{i}") for i in range(count)]
        out = assemble_injections(items, InjectionAllocatorConfig(max_bytes=4096))
        sources = parse_sources(out.prompt_block)
        low = [f"S{i}" for i in range(count) if i % 2 == 1]
        high = [f"S{i}" for i in range(count) if i % 2 == 0]
        assert sources == low + high
