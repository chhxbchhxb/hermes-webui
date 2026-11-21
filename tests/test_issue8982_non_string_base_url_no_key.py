"""#8982: a non-string base_url is no URL, so the lookup carries no key with it.

The session context-length lookup hands (URL, key) to the Agent's ``get_model_context_length``. In the
chat-route branch of ``_session_context_length_lookup_state`` the route's ``base_url`` was turned into a URL
string unconditionally (``str(route.get("base_url") or "").strip()``), so a record or legacy
``custom_providers`` entry declaring a non-string ``base_url`` (the YAML integer ``base_url: 123``, a boolean,
a mapping) handed the lookup the URL-shaped ``"123"`` together with the route's key. The key's own gate already
checked ``isinstance`` (only a string key travels); the URL's did not. Both GET /api/session (#8928) and the
model switch (#8963) read the pair from this one helper, so both are covered here.

The fix: accept the route's ``base_url`` only when it is a ``str``. Anything else counts as no URL -- exactly
as with an empty or missing one -- so the pair the consumers hand to the lookup is the empty one: no URL and no
key, and nothing is requested.

``_custom_provider_runtime_bundle_with_provenance`` is stubbed with a controlled ``(route, custom)`` pair (the
merge's output shape), which drives the URL line directly without resolving a live provider connection. A spy
``agent.model_metadata.get_model_context_length`` records every (URL, key) pair the consumers would send.
"""
import pathlib
import sys
import types

import pytest

from api import routes

PROVIDER = "custom:my-proxy"
MODEL = "m-x"
BUNDLE_KEY = "K-BUNDLE"

# Valid base_url shapes: these must reach the lookup byte-for-byte unchanged.
GOOD_URLS = [
    "https://api.example.com/v1",
    "https://api.example.com:8443/v1",
    "https://api.example.com/v1/",
    "https://UPPER.EXAMPLE.COM/v1",
    "https://api.example.com/v1?foo=bar&baz=1",
    "http://localhost:11434/v1",
]

# Non-string base_url shapes. None of them is a URL, so the lookup gets no URL and no key.
NOT_URLS = [
    pytest.param(123, id="int"),
    pytest.param(True, id="true"),
    pytest.param(False, id="false"),
    pytest.param([], id="list"),
    pytest.param({}, id="dict"),
    pytest.param(None, id="none"),
]


def _install_bundle_route(monkeypatch, route, custom=None):
    """Point the chat-route bundle at a controllable ``(route, custom)`` pair.

    ``_custom_provider_runtime_bundle_with_provenance`` is imported inside the helper
    (``from api.config import ...``), so monkeypatching the attribute on ``api.config``
    reaches it. ``cfg`` is bound empty so the real config file is never read.
    """
    import api.config as config

    cfg = {}
    monkeypatch.setattr(config, "cfg", cfg)
    monkeypatch.setattr(config, "get_config", lambda *a, **k: cfg)
    monkeypatch.setattr(
        config, "_custom_provider_runtime_bundle_with_provenance",
        lambda *a, **k: (route, custom if custom is not None else {}),
    )


def _lookup_state(monkeypatch, base_url, api_key=BUNDLE_KEY, provider=PROVIDER):
    """Return ``(base_url, api_key)`` as GET /api/session / the switch read them from the helper."""
    _install_bundle_route(monkeypatch, {"base_url": base_url, "api_key": api_key})
    _m, _p, url, key = routes._session_context_length_lookup_state(MODEL, provider)
    return url, key


def _install_lookup_spy(monkeypatch):
    """Record every (base_url, api_key) pair handed to the Agent's ``get_model_context_length``."""
    seen = []

    def get_model_context_length(model, base_url="", *args, api_key=None, **kwargs):
        seen.append((base_url, api_key))
        return 8192

    stub = types.ModuleType("agent.model_metadata")
    stub.get_model_context_length = get_model_context_length
    monkeypatch.setitem(sys.modules, "agent.model_metadata", stub)
    return seen


def _keyed(seen):
    return [pair for pair in seen if pair[1]]


# ── The rule at the helper's chat-route branch ─────────────────────────────────


@pytest.mark.parametrize("base_url", NOT_URLS)
def test_a_non_string_base_url_is_exactly_an_empty_one(monkeypatch, base_url):
    """A non-string base_url declares no endpoint: the pair is the empty-URL pair, byte for byte."""
    assert _lookup_state(monkeypatch, base_url) == _lookup_state(monkeypatch, "")


def test_a_string_base_url_is_unchanged_and_carries_the_key(monkeypatch):
    assert _lookup_state(monkeypatch, "https://api.example.com/v1") == ("https://api.example.com/v1", BUNDLE_KEY)


@pytest.mark.parametrize("base_url", GOOD_URLS)
def test_good_base_urls_reach_the_lookup_byte_for_byte(monkeypatch, base_url):
    url, key = _lookup_state(monkeypatch, base_url)
    assert url == base_url
    assert key == BUNDLE_KEY


@pytest.mark.parametrize("base_url", NOT_URLS)
def test_a_keyless_record_still_drops_the_key(monkeypatch, base_url):
    """Keylessness stays the record's own verdict; the URL rule must not resurrect a key for it."""
    _install_bundle_route(monkeypatch, {"base_url": base_url, "api_key": BUNDLE_KEY}, custom={"keyless": True})
    _m, _p, url, key = routes._session_context_length_lookup_state(MODEL, PROVIDER)
    assert url == ""
    assert key == ""


# ── Consumer 1: GET /api/session (#8928) ───────────────────────────────────────


def _get_session_lookup_received(monkeypatch, base_url):
    """Drive the GET /api/session shape: the helper's pair, forwarded to the resolver, into the lookup spy."""
    _install_bundle_route(monkeypatch, {"base_url": base_url, "api_key": BUNDLE_KEY})
    seen = _install_lookup_spy(monkeypatch)
    _m, _p, url, key = routes._session_context_length_lookup_state(MODEL, PROVIDER)
    routes._resolve_context_length_for_session_model(
        MODEL, PROVIDER, base_url=url, api_key=key, caller_key_only=True,
    )
    return seen


@pytest.mark.parametrize("base_url", NOT_URLS)
def test_get_api_session_hands_the_lookup_no_pair_for_a_non_string_base_url(monkeypatch, base_url):
    seen = _get_session_lookup_received(monkeypatch, base_url)
    assert seen, "control: the resolver does consult the lookup, so an empty record would prove nothing"
    assert _keyed(seen) == [], f"the lookup received a key: {_keyed(seen)}"
    assert all(url == "" for url, _key in seen), f"the malformed value must not become the URL: {seen}"


@pytest.mark.parametrize("base_url", GOOD_URLS)
def test_get_api_session_still_hands_a_string_base_url_pair(monkeypatch, base_url):
    seen = _get_session_lookup_received(monkeypatch, base_url)
    assert (base_url, BUNDLE_KEY) in seen, f"a good URL's pair must reach the lookup unchanged: {seen}"


def test_get_api_session_empty_url_behaves_as_today(monkeypatch):
    """Control: the empty-URL behaviour is the reference the non-string shapes must match."""
    seen = _get_session_lookup_received(monkeypatch, "")
    assert seen
    assert _keyed(seen) == []


# ── Consumer 2: the model switch (#8963) ─────────────────────────────────────


def _switch_perceived_pair(monkeypatch, base_url):
    """Drive the model switch: a session route change resolves the context length for the new route."""
    _install_bundle_route(monkeypatch, {"base_url": base_url, "api_key": BUNDLE_KEY})
    seen = _install_lookup_spy(monkeypatch)
    session = types.SimpleNamespace(
        model=MODEL,
        model_provider="deepseek",
        last_used_model=None,
        gateway_routing=None,
        context_length=0,
        threshold_tokens=0,
        last_prompt_tokens=0,
    )
    changed = routes._invalidate_session_route_state_if_changed(
        session, model=MODEL, provider=PROVIDER, provider_specified=True
    )
    return changed, seen


@pytest.mark.parametrize("base_url", NOT_URLS)
def test_the_model_switch_hands_the_lookup_no_pair_for_a_non_string_base_url(monkeypatch, base_url):
    changed, seen = _switch_perceived_pair(monkeypatch, base_url)
    assert changed is True, "control: the switch is the path under test, so it must actually fire"
    assert seen, "control: the switch must resolve the context length for the new route"
    assert _keyed(seen) == [], f"the switch handed the lookup a key: {_keyed(seen)}"
    assert all(url == "" for url, _key in seen), f"the malformed value must not become the URL: {seen}"


@pytest.mark.parametrize("base_url", GOOD_URLS)
def test_the_model_switch_still_hands_a_string_base_url_pair(monkeypatch, base_url):
    changed, seen = _switch_perceived_pair(monkeypatch, base_url)
    assert changed is True
    assert (base_url, BUNDLE_KEY) in seen, f"a good URL's pair must reach the lookup unchanged: {seen}"


def test_the_model_switch_empty_url_behaves_as_today(monkeypatch):
    changed, seen = _switch_perceived_pair(monkeypatch, "")
    assert changed is True
    assert seen
    assert _keyed(seen) == []


# ── Real config path: the merged route bundle, no stub ────────────────────────
#
# The issue's own shape: a record/legacy entry in config.yaml with ``base_url: 123``.
# Here the real merge runs (``api.config._custom_record_base_url`` is the merge's
# endpoint read), so this is the test that would still fail if the guard lived only
# in the helper: the merge stringifies 123 to "123" before the helper sees it.


def _providers_record_cfg(base_url):
    return {"model": {"provider": PROVIDER},
            "providers": {PROVIDER: {"base_url": base_url, "api_key": BUNDLE_KEY}},
            "custom_providers": []}


def _legacy_entry_cfg(base_url):
    return {"model": {"provider": PROVIDER},
            "providers": {},
            "custom_providers": [{"name": "my-proxy", "base_url": base_url, "api_key": BUNDLE_KEY}]}


REAL_CFG_SHAPES = [
    pytest.param(_providers_record_cfg, id="providers-record"),
    pytest.param(_legacy_entry_cfg, id="legacy-entry"),
]


def _install_real_config(monkeypatch, cfg):
    import api.config as config

    monkeypatch.setattr(config, "cfg", cfg)
    monkeypatch.setattr(config, "get_config", lambda *a, **k: cfg)
    return cfg


@pytest.mark.parametrize("make_cfg", REAL_CFG_SHAPES)
@pytest.mark.parametrize("base_url", NOT_URLS)
def test_the_merged_route_bundle_never_carries_a_non_string_base_url(monkeypatch, make_cfg, base_url):
    _install_real_config(monkeypatch, make_cfg(base_url))
    _m, _p, url, key = routes._session_context_length_lookup_state(MODEL, PROVIDER)
    assert url == "", f"the merged bundle carried the URL-shaped {url!r}"
    assert key == "", f"the route key rode along with no URL: {key!r}"


@pytest.mark.parametrize("make_cfg", REAL_CFG_SHAPES)
@pytest.mark.parametrize("base_url", NOT_URLS)
def test_the_real_merge_hands_the_lookup_no_pair(monkeypatch, make_cfg, base_url):
    _install_real_config(monkeypatch, make_cfg(base_url))
    seen = _install_lookup_spy(monkeypatch)
    _m, _p, url, key = routes._session_context_length_lookup_state(MODEL, PROVIDER)
    routes._resolve_context_length_for_session_model(
        MODEL, PROVIDER, base_url=url, api_key=key, caller_key_only=True,
    )
    assert seen, "control: the resolver still consults the lookup"
    assert _keyed(seen) == [], f"the lookup received a key: {_keyed(seen)}"
    assert all(url == "" for url, _key in seen), f"the malformed value became a lookup URL: {seen}"


@pytest.mark.parametrize("make_cfg", REAL_CFG_SHAPES)
def test_the_real_merge_keeps_a_string_base_url_pair(monkeypatch, make_cfg):
    _install_real_config(monkeypatch, make_cfg("https://api.example.com:8443/v1"))
    _m, _p, url, key = routes._session_context_length_lookup_state(MODEL, PROVIDER)
    assert url == "https://api.example.com:8443/v1"
    assert key == BUNDLE_KEY


# ── Both consumers read the same helper ────────────────────────────────────────


def test_get_session_and_the_model_switch_read_the_same_helper():
    """The two consumers share one pair: one definition plus the GET and switch call sites."""
    src = (pathlib.Path(routes.__file__)).read_text(encoding="utf-8")
    calls = [line for line in src.splitlines() if "_session_context_length_lookup_state(" in line]
    assert len(calls) == 3, f"expected the definition and two call sites, got {len(calls)}: {calls}"
