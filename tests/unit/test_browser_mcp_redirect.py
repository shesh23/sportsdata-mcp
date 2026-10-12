"""Distinguish browser navigations from requests that speak the MCP HTTP protocol."""

from sportsdata_mcp.server import _is_browser_mcp_navigation


def test_browser_navigation_is_redirected():
    assert _is_browser_mcp_navigation("GET", "/mcp", "text/html", "/mcp")
    assert _is_browser_mcp_navigation("GET", "/mcp", "*/*", "/mcp")


def test_mcp_stream_request_is_not_redirected():
    assert not _is_browser_mcp_navigation(
        "GET", "/mcp", "application/json, text/event-stream", "/mcp"
    )


def test_other_paths_and_methods_are_not_redirected():
    assert not _is_browser_mcp_navigation("POST", "/mcp", "text/html", "/mcp")
    assert not _is_browser_mcp_navigation("GET", "/other", "text/html", "/mcp")
