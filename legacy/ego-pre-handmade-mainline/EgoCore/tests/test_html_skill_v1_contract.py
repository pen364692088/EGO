from app.runtime.artifact_skill_contract import ArtifactSkillRequest, ArtifactEdit
from app.runtime.html_skill import execute_html_skill


def test_html_skill_observation_contract_for_edit(tmp_path):
    p = tmp_path / "test.html"
    p.write_text(
        """<!DOCTYPE html><html><body><h1>Hello</h1></body></html>""",
        encoding="utf-8",
    )

    def loader(path):
        try:
            return True, (tmp_path / "test.html").read_text(encoding="utf-8")
        except Exception as e:
            return False, str(e)

    def writer(path, content):
        try:
            (tmp_path / "test.html").write_text(content, encoding="utf-8")
            return True, None
        except Exception as e:
            return False, str(e)

    req = ArtifactSkillRequest(
        action="edit_artifact",
        artifact_type="html",
        targets=[{"path": str(p)}],
        edits=[ArtifactEdit(target_path=str(p), scope="body", property="background_color", operation="choose_and_set", value="agent_choice")],
    )
    result = execute_html_skill(req, loader, writer)
    assert result.success is True
    assert result.observations
    obs = result.observations[0]
    assert "target_path" in obs
    assert "applied_edit" in obs
    assert "current_state" in obs
    assert obs["target_path"].endswith("test.html")
    assert obs["applied_edit"]["operation"] == "choose_and_set"
    assert obs["current_state"].get("background_color")
