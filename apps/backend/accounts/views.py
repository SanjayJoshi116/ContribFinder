import logging
import secrets
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import login, logout
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.serializers import error_responses
from github.models import GitHubAccount
from services import audit
from services.crypto import decrypt_token
from services.github import oauth
from services.github.accounts import link_github_account

from .models import AuditEvent, User
from .serializers import DisconnectResultSerializer, MeSerializer

logger = logging.getLogger(__name__)

OAUTH_STATE_SESSION_KEY = "github_oauth_state"

# Error codes the frontend understands (?auth_error=<code>).
ERROR_CANCELLED = "cancelled"
ERROR_INVALID_STATE = "invalid_state"
ERROR_FAILED = "failed"  # retryable

_REDIRECT_RESPONSE = OpenApiResponse(description="Redirect (302).")


def _frontend_redirect(path: str, **params: str) -> HttpResponseRedirect:
    query = f"?{urlencode(params)}" if params else ""
    return HttpResponseRedirect(f"{settings.FRONTEND_URL}{path}{query}")


def _current_user(request: Request) -> User:
    user = request.user
    if not isinstance(user, User):
        raise NotAuthenticated()
    return user


def _auth_error(request: Request, code: str, reason: str) -> HttpResponseRedirect:
    audit.record(
        AuditEvent.Action.SIGN_IN_FAILED,
        AuditEvent.Outcome.FAILURE,
        request=request,
        metadata={"reason": reason, "error_code": code},
    )
    return _frontend_redirect(settings.FRONTEND_AUTH_ERROR_PATH, auth_error=code)


class GitHubLoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    @extend_schema(
        operation_id="auth_github_start",
        responses={302: _REDIRECT_RESPONSE, **error_responses(429)},
        auth=[],
    )
    def get(self, request: Request) -> HttpResponseRedirect:
        state = secrets.token_urlsafe(32)
        request.session[OAUTH_STATE_SESSION_KEY] = state
        return HttpResponseRedirect(oauth.build_authorize_url(state))


class GitHubCallbackView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    @extend_schema(
        operation_id="auth_github_callback",
        parameters=[
            OpenApiParameter("code", str, required=False),
            OpenApiParameter("state", str, required=False),
            OpenApiParameter("error", str, required=False),
        ],
        responses={302: _REDIRECT_RESPONSE, **error_responses(429)},
        auth=[],
    )
    def get(self, request: Request) -> HttpResponseRedirect:
        # Single use: the stored state is consumed whatever happens next.
        expected_state = request.session.pop(OAUTH_STATE_SESSION_KEY, None)
        received_state = request.query_params.get("state", "")

        if (
            not expected_state
            or not received_state
            or not secrets.compare_digest(str(expected_state), received_state)
        ):
            return _auth_error(request, ERROR_INVALID_STATE, "state_mismatch")

        if error := request.query_params.get("error"):
            if error == "access_denied":
                return _auth_error(request, ERROR_CANCELLED, "access_denied")
            return _auth_error(request, ERROR_FAILED, "authorization_error")

        code = request.query_params.get("code")
        if not code:
            return _auth_error(request, ERROR_FAILED, "missing_code")

        try:
            token = oauth.exchange_code(code)
            identity = oauth.fetch_identity(token.access_token)
        except oauth.OAuthError as exc:
            logger.warning("GitHub sign-in failed: %s", exc.code)
            return _auth_error(request, ERROR_FAILED, exc.code)

        result = link_github_account(identity, token)
        login(request, result.user, backend="django.contrib.auth.backends.ModelBackend")
        audit.record(
            AuditEvent.Action.SIGN_IN,
            AuditEvent.Outcome.SUCCESS,
            user=result.user,
            request=request,
            metadata={
                "github_id": identity.github_id,
                "github_username": identity.login,
                "created_user": result.created_user,
            },
        )
        return _frontend_redirect(settings.FRONTEND_SIGNED_IN_PATH)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="auth_csrf",
        responses={204: OpenApiResponse(description="CSRF cookie set.")},
        auth=[],
    )
    def get(self, request: Request) -> Response:
        return Response(status=204)


class MeView(APIView):
    @extend_schema(operation_id="auth_me", responses={200: MeSerializer, **error_responses(401)})
    def get(self, request: Request) -> Response:
        user = User.objects.select_related("github_account").get(pk=_current_user(request).pk)
        return Response(MeSerializer(user).data)


class LogoutView(APIView):
    @extend_schema(
        operation_id="auth_logout",
        request=None,
        responses={204: OpenApiResponse(description="Signed out."), **error_responses(401, 403)},
    )
    def post(self, request: Request) -> Response:
        user = request.user
        audit.record(
            AuditEvent.Action.LOGOUT,
            AuditEvent.Outcome.SUCCESS,
            user=user if isinstance(user, User) else None,
            request=request,
        )
        logout(request)
        return Response(status=204)


class GitHubDisconnectView(APIView):
    @extend_schema(
        operation_id="auth_github_disconnect",
        request=None,
        responses={200: DisconnectResultSerializer, **error_responses(401, 403)},
    )
    def post(self, request: Request) -> Response:
        user = _current_user(request)
        account = GitHubAccount.objects.filter(user=user).first()

        revocation = "not_connected"
        if account is not None:
            try:
                oauth.revoke_grant(decrypt_token(account.access_token_encrypted))
                revocation = "revoked"
            except Exception as exc:
                # Local credentials are deleted regardless; only the failure type is logged.
                revocation = "failed"
                logger.warning("GitHub grant revocation failed: %s", type(exc).__name__)
            finally:
                account.delete()

        audit.record(
            AuditEvent.Action.GITHUB_DISCONNECT,
            AuditEvent.Outcome.SUCCESS,
            user=user,
            request=request,
            metadata={"revocation": revocation},
        )
        logout(request)
        return Response(DisconnectResultSerializer({"revocation": revocation}).data)
