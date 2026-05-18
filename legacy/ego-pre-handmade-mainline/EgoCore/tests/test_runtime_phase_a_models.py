from app.runtime.completion_contract import CompletionContract, HtmlEffectVerifier
from app.runtime.delivery_policy import DeliveryDedupePolicy, DeliveryIdentity
from app.runtime.request_identity import derive_chain_id
from app.runtime.request_lifecycle import RequestLifecycleState, normalize_runtime_status
from app.runtime.request_registry import RequestRecord, RequestRegistry


def test_follow_up_reuses_active_chain_id():
    assert derive_chain_id(
        request_id="req_2",
        request_kind="follow_up",
        parent_request_id="req_1",
        active_chain_id="chain_active",
    ) == "chain_active"


def test_request_registry_assigns_chain_and_supersedes_cleanly():
    registry = RequestRegistry()
    old = RequestRecord(
        request_id="req_old",
        origin_turn_id="turn_old",
        session_key="telegram:dm:1",
        objective="old",
        request_type="new_task",
        status="running",
    )
    registry.record_request(old)
    assert old.chain_id == "req_old"
    assert registry.get_active_chain_id("telegram:dm:1") == "req_old"

    registry.supersede_request("req_old", "req_new")
    assert registry.requests["req_old"].status == RequestLifecycleState.SUPERSEDED.value

    new = RequestRecord(
        request_id="req_new",
        origin_turn_id="turn_new",
        session_key="telegram:dm:1",
        objective="new",
        request_type="follow_up",
        status="running",
        parent_request_id="req_old",
    )
    registry.record_request(new)
    assert new.chain_id == "req_old"
    assert registry.get_latest_unresolved_request("telegram:dm:1").request_id == "req_new"


def test_delivery_dedupe_prefers_request_identity():
    policy = DeliveryDedupePolicy()
    identity = DeliveryIdentity.build(
        session_key="telegram:dm:1",
        reply_text="文件是 /home/a/hello.html",
        delivery_kind="final",
        request_id="req_1",
        source_ingress_message_id="100",
    )
    assert policy.should_suppress(identity) is False
    policy.mark_sent(identity)
    dup = DeliveryIdentity.build(
        session_key="telegram:dm:1",
        reply_text=" 文件是 /home/a/hello.html ",
        delivery_kind="final",
        request_id="req_1",
        source_ingress_message_id="101",
    )
    assert policy.should_suppress(dup) is True


def test_html_completion_contract_requires_verified_observation():
    verifier = HtmlEffectVerifier()
    contract = CompletionContract(
        effect_type="artifact_style_change",
        expected_target="/tmp/hello.html",
        required_observations=["target_path", "applied_edit", "current_state"],
        verifier_name="html_effect_verifier",
    )
    good = {
        "observations": [{
            "target_path": "/tmp/hello.html",
            "applied_edit": {"operation": "choose_and_set"},
            "current_state": {"background_color": "#fff"},
        }]
    }
    bad = {"observations": [{"target_path": "/tmp/hello.html"}]}
    assert verifier.verify(contract, good).passed is True
    assert verifier.verify(contract, bad).passed is False


def test_status_normalization_maps_runtime_strings_to_formal_lifecycle():
    assert normalize_runtime_status("running") == RequestLifecycleState.ACTIVE
    assert normalize_runtime_status("completed") == RequestLifecycleState.COMPLETED_VERIFIED
