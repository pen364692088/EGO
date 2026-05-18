from app.runtime.request_resolution_policy import RequestResolutionPolicy


policy = RequestResolutionPolicy()


def test_abbreviated_path_binds_to_active_target_when_unique():
    state = {
        "active_target": "/home/moonlight/Project/Github/MyProject/TestProject/hello.html",
        "active_artifact_path": "/home/moonlight/Project/Github/MyProject/TestProject/hello.html",
        "artifact_context_by_path": {
            "/home/moonlight/Project/Github/MyProject/TestProject/hello.html": {}
        },
    }
    result = policy.resolve("/home/.../hello.html 配色不太好看,你换一个好看的颜色", state)
    assert result["kind"] == "follow_up"
    assert result["force_target_path"] == "/home/moonlight/Project/Github/MyProject/TestProject/hello.html"


def test_abbreviated_path_asks_when_ambiguous():
    state = {
        "artifact_context_by_path": {
            "/home/a/hello.html": {},
            "/home/b/hello.html": {},
        }
    }
    result = policy.resolve("/home/.../hello.html 配色不太好看,你换一个好看的颜色", state)
    assert result["kind"] == "ask_for_clarification"


def test_unresolved_query_stays_query_not_followup():
    state = {
        "active_target": "/tmp/hello.html",
        "artifact_context_by_path": {"/tmp/hello.html": {}},
    }
    result = policy.resolve("那条怎么没成功", state)
    assert result["kind"] == "unresolved_request_query"


def test_unresolved_query_catches_you_did_not_change_it_variants():
    state = {
        "active_target": "/tmp/hello.html",
        "artifact_context_by_path": {"/tmp/hello.html": {}},
    }
    assert policy.resolve("你没改啊", state)["kind"] == "unresolved_request_query"
    assert policy.resolve("你还是没改啊", state)["kind"] == "unresolved_request_query"


def test_affirmative_and_style_bind_to_active_target():
    state = {
        "active_target": "/tmp/hello.html",
        "active_artifact_path": "/tmp/hello.html",
        "artifact_context_by_path": {"/tmp/hello.html": {}},
    }
    assert policy.resolve("对", state)["kind"] == "follow_up"
    assert policy.resolve("复古科技朋克", state)["kind"] == "follow_up"
