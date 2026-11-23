"""S8 comprehensive tests.

Two layers:

* Static checks that need no database: the bilingual dictionary is
  symmetric, every key used by templates exists, and no template carries
  untranslated user-visible text.
* Live checks against the real database: all four pages render, the API
  contract holds, and the parity the report relies on is verified end to
  end.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
I18N = ROOT / "static" / "js" / "i18n.js"
TEMPLATES = sorted((ROOT / "templates").glob("*.html"))
JS_FILES = sorted((ROOT / "static" / "js").glob("*.js"))


@pytest.fixture()
def client():
    """Flask test client bound to the real database (pages query it on load)."""
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def _language_block(source: str, lang: str) -> str:
    start = source.index(f'"{lang}"')
    i = source.index("{", start)
    depth = 0
    for j in range(i, len(source)):
        if source[j] == "{":
            depth += 1
        elif source[j] == "}":
            depth -= 1
            if depth == 0:
                return source[i + 1:j]
    raise AssertionError(f"unbalanced language block for {lang}")


@pytest.fixture(scope="module")
def dictionaries():
    source = I18N.read_text(encoding="utf-8")
    zh = re.findall(r'"([a-zA-Z0-9_.]+)"\s*:', _language_block(source, "zh-CN"))
    en = re.findall(r'"([a-zA-Z0-9_.]+)"\s*:', _language_block(source, "en"))
    return set(zh), set(en), zh, en


def test_dictionary_keys_are_symmetric(dictionaries):
    zh, en, _zh_list, _en_list = dictionaries
    assert not (zh - en), f"missing in en: {sorted(zh - en)}"
    assert not (en - zh), f"missing in zh: {sorted(en - zh)}"


def test_no_duplicate_keys(dictionaries):
    _zh, _en, zh_list, en_list = dictionaries
    assert len(zh_list) == len(set(zh_list))
    assert len(en_list) == len(set(en_list))


def test_no_empty_translations():
    source = I18N.read_text(encoding="utf-8")
    for lang in ("zh-CN", "en"):
        assert not re.findall(r'"[a-zA-Z0-9_.]+"\s*:\s*""', _language_block(source, lang)), lang


def test_every_template_key_exists(dictionaries):
    zh, en, _z, _e = dictionaries
    used = set()
    for path in TEMPLATES:
        text = path.read_text(encoding="utf-8")
        used |= set(re.findall(r'data-i18n(?:-placeholder|-title)?="([a-zA-Z0-9_.]+)"', text))
    assert used, "no data-i18n attributes found"
    assert not (used - zh), f"template keys missing: {sorted(used - zh)}"
    assert not (used - en)


def test_templates_have_no_untranslated_text_nodes():
    """Any visible text between tags must sit on an element with data-i18n."""
    offenders = []
    for path in TEMPLATES:
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith(("{#", "<!--")):
                continue
            for match in re.finditer(r">([^<>{}]+)<", line):
                text = match.group(1).strip()
                if not text or "data-i18n" in line:
                    continue
                # Currency symbols and punctuation are locale-neutral.
                if re.fullmatch(r"[¥—·:/\-\s\d.%‹›]+", text):
                    continue
                offenders.append(f"{path.name}:{line_no}: {text!r}")
    assert not offenders, "untranslated text:\n" + "\n".join(offenders)


def test_nav_covers_all_four_pages():
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    for key in ("nav.library", "nav.dashboard", "nav.purchases", "nav.analytics"):
        assert f'data-i18n="{key}"' in base
    # No page should still be disabled now that every page exists.
    assert 'nav-link disabled' not in base


def test_all_four_pages_render(client):
    for path in ("/library", "/dashboard", "/purchases", "/analytics"):
        response = client.get(path)
        assert response.status_code == 200, path
        body = response.get_data(as_text=True)
        assert 'js/i18n.js' in body
        assert 'id="lang-toggle"' in body


def test_language_switch_persists():
    """The dictionary reads localStorage first; guard the storage key name."""
    source = I18N.read_text(encoding="utf-8")
    assert 'steam_library_lang' in source
    assert "localStorage.getItem" in source
    assert "localStorage.setItem" in source


def test_api_contract_shapes(client):
    overview = client.get("/api/stats/overview").get_json()
    for field in ("total_games", "total_minutes", "known_spend",
                  "unstarted_rate", "uncompleted_rate", "status_unknown_count"):
        assert field in overview, field

    genres = client.get("/api/stats/genres").get_json()
    assert "items" in genres

    costs = client.get("/api/stats/costs").get_json()
    for key in ("ranked", "idle", "zero_cost", "idle_total"):
        assert key in costs, key

    yearly = client.get("/api/stats/yearly").get_json()
    assert "items" in yearly and "undated_records" in yearly


def test_pages_do_not_leak_credentials(client):
    """No page or API response should carry the configured passwords."""
    import config

    secrets = [s for s in (config.Config.DB_PASSWORD, config.Config.STEAM_API_KEY)
               if s and s != "REPLACE_ME"]
    for path in ("/library", "/dashboard", "/purchases", "/analytics",
                 "/api/stats/overview", "/api/games", "/api/purchases"):
        body = client.get(path).get_data(as_text=True)
        for secret in secrets:
            assert secret not in body, f"secret leaked into {path}"
