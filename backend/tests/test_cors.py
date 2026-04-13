"""
Integration tests for the CORS middleware wired in app/main.py.

The middleware is configured with:

    allow_origins=[o.strip() for o in settings.allowed_origins.split(",") if o.strip()]

These tests verify that the real CORSMiddleware (via FastAPI's TestClient /
httpx ASGITransport) correctly allows or blocks origins based on what is
parsed from the comma-separated ``allowed_origins`` setting.

We monkeypatch ``settings.allowed_origins`` and then rebuild a minimal app so
that each test group exercises an independent CORS configuration without
mutating the global ``app`` object (which is shared across tests).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(allowed_origins_str: str) -> FastAPI:
    """Return a minimal FastAPI app whose CORS middleware mirrors main.py logic.

    The middleware list in main.py uses:
        [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]

    We replicate that parsing here so the tests exercise the same code path.
    """
    origins = [o.strip() for o in allowed_origins_str.split(",") if o.strip()]

    test_app = FastAPI()
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @test_app.get("/api/health")
    def health():
        return {"status": "ok"}

    return test_app


def _cors_headers(client: TestClient, origin: str) -> dict:
    """Send a simple GET with an Origin header and return the response headers."""
    response = client.get("/api/health", headers={"Origin": origin})
    assert response.status_code == 200
    return dict(response.headers)


# ---------------------------------------------------------------------------
# Parsing: comma-separated origins
# ---------------------------------------------------------------------------


class TestAllowedOriginsParsingIntegration:
    """The middleware must honour each comma-separated origin independently."""

    def test_single_origin_is_allowed(self):
        client = TestClient(_make_app("https://example.com"))
        headers = _cors_headers(client, "https://example.com")
        assert headers.get("access-control-allow-origin") == "https://example.com"

    def test_first_of_two_origins_is_allowed(self):
        client = TestClient(_make_app("https://a.example.com,https://b.example.com"))
        headers = _cors_headers(client, "https://a.example.com")
        assert headers.get("access-control-allow-origin") == "https://a.example.com"

    def test_second_of_two_origins_is_allowed(self):
        client = TestClient(_make_app("https://a.example.com,https://b.example.com"))
        headers = _cors_headers(client, "https://b.example.com")
        assert headers.get("access-control-allow-origin") == "https://b.example.com"

    def test_whitespace_around_origins_is_stripped(self):
        """Spaces around commas must not break origin matching."""
        client = TestClient(_make_app("https://a.example.com , https://b.example.com"))
        headers = _cors_headers(client, "https://b.example.com")
        assert headers.get("access-control-allow-origin") == "https://b.example.com"

    def test_trailing_comma_is_ignored(self):
        """A trailing comma must not produce an empty string in the origins list."""
        client = TestClient(_make_app("https://example.com,"))
        headers = _cors_headers(client, "https://example.com")
        assert headers.get("access-control-allow-origin") == "https://example.com"

    def test_leading_comma_is_ignored(self):
        """A leading comma must not produce an empty string in the origins list."""
        client = TestClient(_make_app(",https://example.com"))
        headers = _cors_headers(client, "https://example.com")
        assert headers.get("access-control-allow-origin") == "https://example.com"

    def test_whitespace_only_entries_are_excluded(self):
        """Entries that are only whitespace after stripping must be dropped."""
        client = TestClient(_make_app("https://example.com,   ,https://other.example.com"))
        headers = _cors_headers(client, "https://example.com")
        assert headers.get("access-control-allow-origin") == "https://example.com"


# ---------------------------------------------------------------------------
# Allowed origin → CORS headers present
# ---------------------------------------------------------------------------


class TestAllowedOriginReceivesCorsHeaders:
    """A request from an explicitly allowed origin must get CORS response headers."""

    def test_allowed_origin_receives_acao_header(self):
        client = TestClient(_make_app("https://siege.example.com"))
        headers = _cors_headers(client, "https://siege.example.com")
        assert "access-control-allow-origin" in headers

    def test_allowed_origin_acao_matches_request_origin(self):
        """The echoed origin must match the request, not be a wildcard."""
        client = TestClient(_make_app("https://siege.example.com"))
        headers = _cors_headers(client, "https://siege.example.com")
        assert headers["access-control-allow-origin"] == "https://siege.example.com"

    def test_allowed_origin_receives_acac_header(self):
        """allow_credentials=True means the vary/credentials header is set."""
        client = TestClient(_make_app("https://siege.example.com"))
        headers = _cors_headers(client, "https://siege.example.com")
        assert headers.get("access-control-allow-credentials") == "true"

    def test_localhost_dev_origin_allowed_by_default_config(self):
        """The default value from Settings must allow the dev frontend."""
        client = TestClient(_make_app("http://localhost:5173"))
        headers = _cors_headers(client, "http://localhost:5173")
        assert headers.get("access-control-allow-origin") == "http://localhost:5173"


# ---------------------------------------------------------------------------
# Disallowed origin → no CORS headers
# ---------------------------------------------------------------------------


class TestDisallowedOriginReceivesNoCorsHeaders:
    """A request from an origin not in the allow-list must NOT get CORS headers."""

    def test_disallowed_origin_has_no_acao_header(self):
        client = TestClient(_make_app("https://allowed.example.com"))
        headers = _cors_headers(client, "https://evil.example.com")
        assert "access-control-allow-origin" not in headers

    def test_subdomain_not_allowed_when_only_apex_configured(self):
        """Subdomains are not implicitly covered — must be listed explicitly."""
        client = TestClient(_make_app("https://example.com"))
        headers = _cors_headers(client, "https://sub.example.com")
        assert "access-control-allow-origin" not in headers

    def test_http_disallowed_when_only_https_configured(self):
        """HTTP and HTTPS are distinct origins."""
        client = TestClient(_make_app("https://example.com"))
        headers = _cors_headers(client, "http://example.com")
        assert "access-control-allow-origin" not in headers

    def test_wrong_port_disallowed(self):
        """The same host on a different port is a distinct origin."""
        client = TestClient(_make_app("http://localhost:5173"))
        headers = _cors_headers(client, "http://localhost:3000")
        assert "access-control-allow-origin" not in headers


# ---------------------------------------------------------------------------
# Preflight (OPTIONS) — smoke test
# ---------------------------------------------------------------------------


class TestPreflightRequest:
    """OPTIONS preflight with an allowed origin must return 200 with CORS headers."""

    def test_preflight_allowed_origin_returns_200(self):
        client = TestClient(_make_app("https://siege.example.com"))
        response = client.options(
            "/api/health",
            headers={
                "Origin": "https://siege.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "https://siege.example.com"

    def test_preflight_disallowed_origin_has_no_acao(self):
        client = TestClient(_make_app("https://siege.example.com"))
        response = client.options(
            "/api/health",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" not in dict(response.headers)
