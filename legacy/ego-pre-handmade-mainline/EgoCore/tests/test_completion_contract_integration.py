from app.runtime.agent_runner import _has_verified_html_effect
from app.runtime.completion_contract import CompletionContract, HtmlEffectVerifier


def test_html_effect_verifier_contract_passes_with_required_observations():
    verifier = HtmlEffectVerifier()
    contract = CompletionContract(
        effect_type="artifact_style_change",
        expected_target="/tmp/hello.html",
        required_observations=["target_path", "applied_edit", "current_state"],
        verifier_name="html_effect_verifier",
    )
    result = verifier.verify(contract, {
        "observations": [{
            "target_path": "/tmp/hello.html",
            "applied_edit": {"operation": "choose_and_set"},
            "current_state": {"background_color": "#fff"},
        }]
    })
    assert result.passed is True


def test_agent_runner_html_completion_gate_blocks_unverified_success():
    bad = [{
        "success": True,
        "tool_name": "html_skill",
        "metadata": {
            "action": "apply_edit",
            "completed_steps": ["step_1"],
            "observations": [{
                "target_path": "/tmp/hello.html",
                "current_state": {"background_color": "#fff"},
            }],
        },
    }]
    assert _has_verified_html_effect(bad, expected_target="/tmp/hello.html") is False


def test_agent_runner_html_completion_gate_allows_verified_success():
    good = [{
        "success": True,
        "tool_name": "html_skill",
        "metadata": {
            "action": "apply_edit",
            "completed_steps": ["step_1"],
            "observations": [{
                "target_path": "/tmp/hello.html",
                "applied_edit": {"operation": "choose_and_set"},
                "current_state": {"background_color": "#fff"},
            }],
        },
    }]
    assert _has_verified_html_effect(good, expected_target="/tmp/hello.html") is True
