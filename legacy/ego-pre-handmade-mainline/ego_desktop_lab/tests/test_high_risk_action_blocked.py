from ego_desktop_lab.gate import evaluate_gate


def test_high_risk_actions_are_blocked() -> None:
    assert evaluate_gate("file_delete").status == "block"
    assert evaluate_gate("system_command").status == "block"
    assert evaluate_gate("external_send").status == "block"


def test_file_read_and_write_require_approval() -> None:
    assert evaluate_gate("file_read").status == "ask"
    assert evaluate_gate("file_write").status == "ask"
