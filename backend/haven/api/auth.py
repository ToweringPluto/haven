"""Auth0 bearer-token verification for the signed-in endpoints.

Only a few endpoints need a signed-in user (photo screening, read-aloud, ``/v1/me``); the
renter journey stays public. Tokens are RS256 JWTs issued by Auth0 for our API, verified
against the tenant's JWKS. Never log the token or the full claims.
"""

import logging
from typing import Annotated, Any

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from haven.api.errors import ServiceUnavailable, Unauthorized
from haven.api.schemas import CurrentUser
from haven.config import Settings

logger = logging.getLogger(__name__)

ALGORITHMS = ["RS256"]

bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="Auth0",
    description="Auth0 access token for the Haven API (`Authorization: Bearer <token>`).",
)


def make_jwks_client(settings: Settings) -> jwt.PyJWKClient | None:
    """One client per app: it caches the signing keys and refetches on an unknown `kid`."""
    if not settings.auth_configured:
        return None
    return jwt.PyJWKClient(
        f"https://{settings.auth0_domain}/.well-known/jwks.json",
        cache_keys=True,
        lifespan=3600,
        timeout=5,
    )


def verify_token(token: str, settings: Settings, jwks: jwt.PyJWKClient) -> dict[str, Any]:
    """Verify signature, algorithm, issuer, audience and expiry; return the claims."""
    try:
        signing_key = jwks.get_signing_key_from_jwt(token)
    except jwt.PyJWKClientConnectionError as exc:
        logger.warning("Couldn't fetch Auth0 signing keys: %s", type(exc).__name__)
        raise ServiceUnavailable("Sign-in is temporarily unavailable. Try again shortly.") from exc
    except (jwt.PyJWKClientError, jwt.InvalidTokenError) as exc:
        # Unknown kid, malformed header, etc. Log the error type only, never the token.
        logger.info("Rejected bearer token: %s", type(exc).__name__)
        raise Unauthorized() from exc

    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            signing_key.key,
            algorithms=ALGORITHMS,
            audience=settings.auth0_audience,
            issuer=f"https://{settings.auth0_domain}/",
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            leeway=30,
        )
    except jwt.InvalidTokenError as exc:
        logger.info("Rejected bearer token: %s", type(exc).__name__)
        raise Unauthorized() from exc
    return claims


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> CurrentUser:
    """FastAPI dependency: the verified signed-in user, or 401/503 problem+json.

    A plain ``def`` so FastAPI runs it in the threadpool (fetching JWKS is blocking I/O).
    """
    settings: Settings = request.app.state.settings
    jwks: jwt.PyJWKClient | None = request.app.state.jwks_client
    if jwks is None:
        raise ServiceUnavailable("Sign-in isn't configured on this server.")
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise Unauthorized()

    claims = verify_token(credentials.credentials, settings, jwks)
    email = claims.get(settings.auth0_email_claim) or claims.get("email")
    return CurrentUser(sub=claims["sub"], email=email if isinstance(email, str) else None)


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def get_optional_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> CurrentUser | None:
    """FastAPI dependency for public endpoints that do more for a signed-in user.

    No token (or sign-in not configured) gives ``None``. A token that is sent but invalid is
    still a 401, so a client never silently loses its user.
    """
    if credentials is None or request.app.state.jwks_client is None:
        return None
    return get_current_user(request, credentials)


OptionalUserDep = Annotated[CurrentUser | None, Depends(get_optional_user)]
