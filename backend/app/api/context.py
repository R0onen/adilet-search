"""Who is calling: client type, user-agent family and the salted session hash (no raw ids/IPs)."""

from fastapi import Request

from app.services.query_log import session_hash
from app.services.search import SearchContext

# Order matters: Edge and Opera user agents also contain "Chrome/", Chrome's contains "Safari/".
_UA_FAMILIES = (
    ("edge", "edg/"),
    ("opera", "opr/"),
    ("yandex", "yabrowser/"),
    ("chrome", "chrome/"),
    ("firefox", "firefox/"),
    ("safari", "safari/"),
    ("curl", "curl/"),
    ("python", "python"),
    ("postman", "postman"),
    ("php", "php"),
    ("java", "java/"),
    ("okhttp", "okhttp"),
)


def ua_family(user_agent: str | None) -> str | None:
    """A coarse browser/library family. The full user agent is never stored."""
    if not user_agent:
        return None
    lowered = user_agent.lower()
    for family, token in _UA_FAMILIES:
        if token in lowered:
            return family
    return "other"


def request_context(request: Request, salt: str, endpoint: str) -> SearchContext:
    session_id = request.headers.get("x-session-id")
    if request.headers.get("x-api-key"):
        client = "api-key"
    elif session_id:
        client = "web"
    else:
        client = "unknown"
    return SearchContext(
        session_hash=session_hash(session_id, salt),
        client=client,
        ua_family=ua_family(request.headers.get("user-agent")),
        endpoint=endpoint,
    )
