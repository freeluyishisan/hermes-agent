"""Provider-specific HTTP client identity helpers.

Keep this module narrow: it exists for provider fingerprints that must be
applied consistently across main, auxiliary, and adapter clients without
expanding the model tool surface.
"""

from __future__ import annotations

from typing import Any, Mapping

from utils import base_url_hostname


ZAI_OPENCODE_USER_AGENT = "opencode/1.17.11"
_ZAI_HOSTS = frozenset({"api.z.ai", "open.bigmodel.cn"})


def canonical_header_name(existing_names: Any, header_name: str) -> str:
    """Return the casing to use when replacing a header value."""
    lower = header_name.lower()
    if lower == "user-agent":
        # The OpenAI SDK's built-in User-Agent suppression is sensitive to
        # this canonical spelling, so preserve it even if config says
        # ``user-agent``.
        return "User-Agent"
    for existing in existing_names:
        existing_name = str(existing)
        if existing_name.lower() == lower:
            return existing_name
    return header_name


def set_merged_header(headers: dict[str, str], key: Any, value: Any) -> None:
    """Set a header case-insensitively while preserving useful casing."""
    if value is None:
        return
    header_name = str(key)
    target_name = canonical_header_name(headers.keys(), header_name)
    target_lower = target_name.lower()
    for existing in list(headers.keys()):
        if str(existing).lower() == target_lower and existing != target_name:
            headers.pop(existing, None)
    headers[target_name] = str(value)


def is_zai_endpoint(base_url: str | None) -> bool:
    """Return True for Z.ai/Zhipu hosts that need OpenCode-shaped identity."""
    return base_url_hostname(base_url or "") in _ZAI_HOSTS


def zai_opencode_headers() -> dict[str, str]:
    """Headers matching OpenCode's non-hosted-provider LLM request identity."""
    # Do not send Hermes session ids or parent ids here. Those are stable
    # third-party identifiers and require a broader user-facing opt-in policy.
    return {"User-Agent": ZAI_OPENCODE_USER_AGENT}


def merge_zai_opencode_headers(
    base_url: str | None,
    headers: Mapping[str, Any] | None = None,
) -> dict[str, str] | None:
    """Apply Z.ai OpenCode defaults while preserving caller override order."""
    if not is_zai_endpoint(base_url):
        return dict(headers) if headers else None
    merged = zai_opencode_headers()
    for key, value in (headers or {}).items():
        set_merged_header(merged, key, value)
    return merged


def strip_stainless_headers(request: Any) -> None:
    """Remove OpenAI/Anthropic SDK fingerprint headers from an httpx request."""
    headers = getattr(request, "headers", None)
    if headers is None:
        return
    for name in list(headers.keys()):
        if str(name).lower().startswith("x-stainless-"):
            try:
                del headers[name]
            except KeyError:
                pass


def apply_zai_request_identity(request: Any) -> None:
    """Apply per-request Z.ai identity cleanup that must run last."""
    strip_stainless_headers(request)


def make_zai_request_hook():
    def _hook(request: Any) -> None:
        apply_zai_request_identity(request)

    return _hook


def make_async_zai_request_hook():
    async def _hook(request: Any) -> None:
        apply_zai_request_identity(request)

    return _hook


def sync_zai_event_hooks(
    event_hooks: Mapping[str, list[Any]] | None = None,
) -> dict[str, list[Any]]:
    hooks = {str(name): list(values) for name, values in (event_hooks or {}).items()}
    hooks.setdefault("request", []).append(make_zai_request_hook())
    return hooks


def async_zai_event_hooks(
    event_hooks: Mapping[str, list[Any]] | None = None,
) -> dict[str, list[Any]]:
    hooks = {str(name): list(values) for name, values in (event_hooks or {}).items()}
    hooks.setdefault("request", []).append(make_async_zai_request_hook())
    return hooks


def build_zai_sync_http_client(**kwargs: Any) -> Any:
    """Build an ``httpx.Client`` with the Z.ai Stainless-strip request hook."""
    import httpx

    kwargs = dict(kwargs)
    kwargs["event_hooks"] = sync_zai_event_hooks(kwargs.get("event_hooks"))
    return httpx.Client(**kwargs)


def build_zai_async_http_client(**kwargs: Any) -> Any:
    """Build an ``httpx.AsyncClient`` with the Z.ai Stainless-strip hook."""
    import httpx

    kwargs = dict(kwargs)
    kwargs["event_hooks"] = async_zai_event_hooks(kwargs.get("event_hooks"))
    return httpx.AsyncClient(**kwargs)
