import json
import pytest
from dispatch_hub.triage import (
    Proposal, parse_response, classify, build_user_payload, NONE_ROLE,
)

ITEMS = ["fix spotter pipeline", "make a distortion plugin"]
ROLES = ["Backend", "QA", "Research"]
DIRS = ["C:/ship/spotter", "C:/ship/distortion"]


def _canned(role0, dir0):
    return json.dumps([
        {"item_index": 0, "role": role0, "directory": dir0,
         "startup_prompt": "Check whether the spotter pipeline finished on the new fixes.",
         "reason": "ops check"},
        {"item_index": 1, "role": "Backend", "directory": "C:/ship/distortion",
         "startup_prompt": "", "reason": "build it"},
    ])


def test_parse_maps_fields_and_clamps_known_role():
    props = parse_response(_canned("QA", "C:/ship/spotter"), ITEMS, ROLES, DIRS)
    assert props[0].role == "QA"
    assert props[0].directory == "C:/ship/spotter"
    assert props[0].unresolved is False


def test_parse_unknown_role_becomes_none():
    props = parse_response(_canned("Wizard", "C:/ship/spotter"), ITEMS, ROLES, DIRS)
    assert props[0].role is None


def test_parse_unknown_directory_flags_unresolved():
    props = parse_response(_canned("QA", "C:/nope"), ITEMS, ROLES, DIRS)
    assert props[0].unresolved is True


def test_parse_blank_prompt_falls_back_to_item_text():
    props = parse_response(_canned("QA", "C:/ship/spotter"), ITEMS, ROLES, DIRS)
    assert props[1].startup_prompt == "make a distortion plugin"


class _FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def complete(self, system, user):
        self.calls += 1
        return self._responses.pop(0)


def test_classify_happy_path_single_call():
    client = _FakeClient([_canned("QA", "C:/ship/spotter")])
    props = classify(ITEMS, ROLES, DIRS, client)
    assert client.calls == 1
    assert len(props) == 2


def test_classify_retries_once_then_succeeds():
    client = _FakeClient(["not json at all", _canned("QA", "C:/ship/spotter")])
    props = classify(ITEMS, ROLES, DIRS, client)
    assert client.calls == 2
    assert len(props) == 2


def test_classify_raises_after_second_bad_response():
    client = _FakeClient(["nope", "still nope"])
    with pytest.raises(ValueError):
        classify(ITEMS, ROLES, DIRS, client)
    assert client.calls == 2
