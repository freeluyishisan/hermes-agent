"""You.com web search + content extraction provider."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from agent.web_search_provider import WebSearchProvider

logger = logging.getLogger(__name__)

_YDC_SEARCH_BASE_URL = "https://api.you.com"
_YDC_CONTENTS_BASE_URL = "https://ydc-index.io"
_YDC_PLATFORM_URL = "https://you.com/platform"


def _env_value(name: str) -> str:
    """Resolve an env var through Hermes config first, then process env."""
    try:
        from hermes_cli.config import get_env_value

        val = get_env_value(name)
    except Exception:
        val = None
    if val is None:
        val = os.getenv(name, "")
    return (val or "").strip()


def _ydc_api_key() -> str:
    return _env_value("YDC_API_KEY")


def _ydc_headers() -> Dict[str, str]:
    """Return headers for You.com API requests."""
    api_key = _ydc_api_key()
    headers: Dict[str, str] = {}
    if api_key:
        headers["X-API-Key"] = api_key
    return headers


def _ydc_search_error(resp: Any, *, has_api_key: bool) -> Dict[str, Any]:
    """Return a user-actionable error dict for You.com Search failures."""
    try:
        payload = resp.json()
    except Exception:  # noqa: BLE001
        payload = {}

    if not isinstance(payload, dict):
        payload = {}

    error_code = str(payload.get("error") or "")
    message = str(payload.get("message") or resp.text or "").strip()
    details: Dict[str, Any] = {
        key: payload[key]
        for key in ("limit", "used", "period", "reset_at")
        if payload.get(key) is not None
    }

    if resp.status_code == 402 and error_code == "free_tier_limit_exceeded":
        return {
            "success": False,
            "error": (
                "You’ve used all of today’s free You.com searches. Free searches reset later, "
                "or you can add a You.com API key to keep searching for free. Get a key at "
                f"{_YDC_PLATFORM_URL} and set it as `YDC_API_KEY`."
            ).strip(),
            "error_code": error_code,
            **details,
        }

    if resp.status_code == 402 and not has_api_key:
        return {
            "success": False,
            "error": (
                f"You.com free tier error: {message or error_code or 'upgrade required'}. "
                f"Set YDC_API_KEY from {_YDC_PLATFORM_URL} to continue with authenticated search."
            ),
            "error_code": error_code or "payment_required",
            **details,
        }

    return {
        "success": False,
        "error": f"You.com Search API error {resp.status_code}: {message or resp.text}",
        "error_code": error_code or f"http_{resp.status_code}",
        **details,
    }


def _ydc_search(query: str, limit: int = 10) -> Dict[str, Any]:
    """Search via the You.com Search API and return normalized results."""
    import httpx

    from tools.interrupt import is_interrupted

    if is_interrupted():
        return {"success": False, "error": "Interrupted"}

    has_api_key = bool(_ydc_api_key())
    logger.info("You.com search: '%s' (limit=%d, livecrawl=%s)", query, limit, has_api_key)

    count = max(1, int(limit))
    if not has_api_key:
        count = min(count, 50)

    params: Dict[str, Any] = {"query": query, "count": count}
    if has_api_key:
        params["livecrawl"] = "web"
        params["livecrawl_formats"] = ["markdown"]

    resp = httpx.get(
        f"{_YDC_SEARCH_BASE_URL}/v1/agents/search",
        params=params,
        headers=_ydc_headers(),
        timeout=30,
    )
    if not resp.is_success:
        return _ydc_search_error(resp, has_api_key=has_api_key)

    data = resp.json()
    results_data = data.get("results", {}) if isinstance(data, dict) else {}
    web_items = results_data.get("web", [])
    news_items = results_data.get("news", [])

    web_results: List[Dict[str, Any]] = []
    for item in web_items[:limit]:
        result: Dict[str, Any] = {
            "url": item.get("url", ""),
            "title": item.get("title", ""),
            "description": item.get("description", ""),
            "position": len(web_results) + 1,
        }
        for key in ("snippets", "page_age", "authors"):
            value = item.get(key)
            if value:
                result[key] = value

        contents = item.get("contents")
        if isinstance(contents, dict):
            markdown = contents.get("markdown")
            if markdown:
                result["contents"] = {"markdown": markdown}

        web_results.append(result)

    remaining = max(0, limit - len(web_results))
    for item in news_items[:remaining]:
        result = {
            "url": item.get("url", ""),
            "title": item.get("title", ""),
            "description": item.get("description", ""),
            "position": len(web_results) + 1,
        }
        page_age = item.get("page_age")
        if page_age:
            result["page_age"] = page_age
        contents = item.get("contents")
        if isinstance(contents, dict):
            markdown = contents.get("markdown")
            if markdown:
                result["contents"] = {"markdown": markdown}
        web_results.append(result)

    return {"success": True, "data": {"web": web_results}}


def _ydc_extract(urls: List[str]) -> List[Dict[str, Any]]:
    """Extract content from URLs via the You.com Contents API."""
    import httpx

    from tools.interrupt import is_interrupted

    if is_interrupted():
        return [{"url": u, "error": "Interrupted", "title": ""} for u in urls]

    if not _ydc_api_key():
        raise ValueError(
            "YDC_API_KEY environment variable is required for the You.com Contents API. "
            "Get your API key at https://you.com/platform"
        )

    logger.info("You.com extract: %d URL(s)", len(urls))
    payload: Dict[str, Any] = {"urls": urls, "formats": ["markdown", "metadata"]}
    crawl_timeout = _env_value("YDC_CRAWL_TIMEOUT")
    if crawl_timeout:
        try:
            timeout_val = int(crawl_timeout)
            if 1 <= timeout_val <= 60:
                payload["crawl_timeout"] = timeout_val
        except ValueError:
            pass

    resp = httpx.post(
        f"{_YDC_CONTENTS_BASE_URL}/v1/contents",
        headers=_ydc_headers(),
        json=payload,
        timeout=60,
    )
    if not resp.is_success:
        raise RuntimeError(f"You.com Contents API error {resp.status_code}: {resp.text}")

    parsed = resp.json()
    if isinstance(parsed, dict):
        items = parsed.get("results", [])
    else:
        items = parsed

    results: List[Dict[str, Any]] = []
    for item in items or []:
        url = item.get("url", "")
        title = item.get("title", "")
        markdown = item.get("markdown", "")
        results.append(
            {
                "url": url,
                "title": title or "",
                "content": markdown or "",
                "raw_content": markdown or "",
                "metadata": item.get("metadata", {"sourceURL": url, "title": title or ""}),
            }
        )

    return results


class YoudotcomWebSearchProvider(WebSearchProvider):
    """You.com search + extract provider."""

    @property
    def name(self) -> str:
        return "youdotcom"

    @property
    def display_name(self) -> str:
        return "You.com"

    def is_available(self) -> bool:
        return True

    def supports_search(self) -> bool:
        return True

    def supports_extract(self) -> bool:
        return True

    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        try:
            return _ydc_search(query, limit)
        except Exception as exc:  # noqa: BLE001
            logger.warning("You.com search error: %s", exc)
            return {"success": False, "error": f"You.com search failed: {exc}"}

    def extract(self, urls: List[str], **kwargs: Any) -> List[Dict[str, Any]]:
        try:
            return _ydc_extract(urls)
        except ValueError as exc:
            return [{"url": u, "title": "", "content": "", "error": str(exc)} for u in urls]
        except Exception as exc:  # noqa: BLE001
            logger.warning("You.com extract error: %s", exc)
            return [
                {"url": u, "title": "", "content": "", "error": f"You.com extract failed: {exc}"}
                for u in urls
            ]

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "You.com",
            "badge": "free tier",
            "tag": "Search + extract. Search has 100 free searches/day without an API key.",
            "env_vars": [
                {
                    "key": "YDC_API_KEY",
                    "prompt": "You.com API key (optional for search, required for extract)",
                    "url": "https://you.com/platform",
                },
            ],
        }
