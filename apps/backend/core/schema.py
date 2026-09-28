from drf_spectacular.authentication import SessionScheme


class ApiSessionScheme(SessionScheme):  # type: ignore[no-untyped-call]  # untyped upstream hook
    """Documents core.authentication.SessionAuthentication as cookie auth in OpenAPI."""

    target_class = "core.authentication.SessionAuthentication"
