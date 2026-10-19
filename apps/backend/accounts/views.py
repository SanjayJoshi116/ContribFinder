import logging
import secrets
import time
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import login, logout
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.authentication import current_user
from core.serializers import error_responses
from github.models import GitHubAccount
from services import audit, data_deletion, jobs
from services.crypto import decrypt_token
from services.github import oauth
from services.github.accounts import link_github_account

from .models import AuditEvent, User
from .serializers import DisconnectResultSerializer, MeSerializer

logger = logging.getLogger(__name__)

# Pending sign-in states, {state: issued_at}: one per tab that started sign-in (several may be
# open), each single-use and short-lived.
OAUTH_STATES_SESSION_KEY = "github_oauth_states"

# Error codes the frontend understands (?auth_error=<code>).
ERROR_CANCELLED = "cancelled"
ERROR_INVALID_STATE = "invalid_state"
ERROR_FAILED = "failed"  # retryable

_REDIRECT_RESPONSE = OpenApiResponse(description="Redirect (302).")


def _frontend_redirect(path: str, **params: str) -> HttpResponseRedirect:
    query = f"?{urlencode(params)}" if params else ""
    return HttpResponseRedirect(f"{settings.FRONTEND_URL}{path}{query}")


def _auth_error(request: Request, code: str, reason: str) -> HttpResponseRedirect:
    audit.record(
        AuditEvent.Action.SIGN_IN_FAILED,
        AuditEvent.Outcome.FAILURE,
        request=request,
        metadata={"reason": reason, "error_code": code},
    )
    return _frontend_redirect(settings.FRONTEND_AUTH_ERROR_PATH, auth_error=code)


def _start_initial_sync(user: User) -> None:
    """Queue the first GitHub sync; sign-in must never fail or wait because of it."""
    try:
        if jobs.needs_initial_sync(user):
            jobs.start_profile_sync(user, enforce_cooldown=False)
    except Exception:
        logger.exception("Could not queue initial GitHub sync")


def _pending_states(request: Request) -> dict[str, float]:
    """Unexpired pending states of this session, oldest first."""
    oldest = time.time() - settings.OAUTH_STATE_TTL_SECONDS
    stored: dict[str, float] = request.session.get(OAUTH_STATES_SESSION_KEY, {})
    return {state: issued for state, issued in stored.items() if issued > oldest}


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
        states = _pending_states(request)
        states[state] = time.time()
        newest = list(states.items())[-settings.OAUTH_STATE_MAX_PENDING :]
        request.session[OAUTH_STATES_SESSION_KEY] = dict(newest)
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
        # Single use: a matching state is consumed whatever happens next; other tabs' states stay.
        # A dict lookup is fine here: states are 256-bit random values, timing reveals nothing.
        states = _pending_states(request)
        matched = states.pop(request.query_params.get("state", ""), None)
        if OAUTH_STATES_SESSION_KEY in request.session:  # no session row for stray callbacks
            request.session[OAUTH_STATES_SESSION_KEY] = states

        if matched is None:
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
        _start_initial_sync(result.user)
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
        user = User.objects.select_related("github_account").get(pk=current_user(request).pk)
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


def _revoke_and_unlink(user: User) -> str:
    """Ask GitHub to revoke the grant and delete the stored credential. Returns the revocation
    outcome; a failed revocation never keeps the credential. Jobs are cancelled by the data
    deletion that follows; a job still running meanwhile can write nothing (job_write)."""
    account = GitHubAccount.objects.filter(user=user).first()
    if account is None:
        return "not_connected"
    try:
        oauth.revoke_grant(decrypt_token(account.access_token_encrypted))
        return "revoked"
    except Exception as exc:
        # Local credentials are deleted regardless; only the failure type is logged.
        logger.warning("GitHub grant revocation failed: %s", type(exc).__name__)
        return "failed"
    finally:
        account.delete()


class GitHubDisconnectView(APIView):
    @extend_schema(
        operation_id="auth_github_disconnect",
        request=None,
        responses={200: DisconnectResultSerializer, **error_responses(401, 403)},
    )
    def post(self, request: Request) -> Response:
        user = current_user(request)
        revocation = _revoke_and_unlink(user)
        deleted = data_deletion.delete_github_data(user)
        audit.record(
            AuditEvent.Action.GITHUB_DISCONNECT,
            AuditEvent.Outcome.SUCCESS,
            user=user,
            request=request,
            metadata={"revocation": revocation, "deleted": deleted},
        )
        # A new (unusable) password value changes the session auth hash, so the user's other
        # sessions, on any device, stop authenticating; this one ends now.
        user.set_unusable_password()
        user.save(update_fields=["password"])
        logout(request)
        return Response(DisconnectResultSerializer({"revocation": revocation}).data)


class AccountView(APIView):
    @extend_schema(
        operation_id="auth_account_delete",
        responses={
            204: OpenApiResponse(description="Account and data deleted; signed out."),
            **error_responses(401, 403),
        },
    )
    def delete(self, request: Request) -> Response:
        user = current_user(request)
        revocation = _revoke_and_unlink(user)
        deleted = data_deletion.delete_github_data(user)
        # Recorded while the user still exists; the entry loses its user link (SET_NULL).
        audit.record(
            AuditEvent.Action.ACCOUNT_DELETED,
            AuditEvent.Outcome.SUCCESS,
            user=user,
            request=request,
            metadata={"revocation": revocation, "deleted": deleted},
        )
        audit.anonymize_user_entries(user)
        logout(request)
        user.delete()
        return Response(status=204)
