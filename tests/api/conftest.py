import httpx
import pytest

REVIEWER = "rev-test"


@pytest.fixture(autouse=True)
def reviewer_code(monkeypatch):
    """Curation writes need a reviewer code: configure one and let every test client send it unless it says otherwise."""
    monkeypatch.setenv("RAI_REVIEWER_CODES", REVIEWER)
    orig = httpx.AsyncClient.__init__

    def init(self, *a, headers=None, **kw):
        h = httpx.Headers({"X-Reviewer-Code": REVIEWER})
        h.update(headers or {})
        orig(self, *a, headers=h, **kw)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", init)
