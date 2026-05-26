# Feature: public-share-links
# Property 4: Optional auth middleware never raises HTTP errors

import pytest
from unittest.mock import patch, MagicMock
from hypothesis import given, settings, strategies as st
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from middleware.auth import get_optional_user


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy for generating random token strings (including edge cases)
token_strings = st.one_of(
    st.text(min_size=0, max_size=500),  # arbitrary strings
    st.just(""),  # empty string
    st.just("not-a-jwt"),  # clearly invalid
    st.just("eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.invalid"),  # JWT-like but invalid
    st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N", "P"))),  # short tokens
)

# Strategy for token scenarios: valid, invalid, expired, malformed, missing, non-Bearer, empty
token_scenario = st.sampled_from([
    "valid",
    "invalid",
    "expired",
    "malformed",
    "missing_credentials",
    "empty_token",
    "non_bearer_scheme",
    "exception_generic",
])


# ---------------------------------------------------------------------------
# Property 4: Optional auth middleware never raises HTTP errors
# Validates: Requirements 6.1, 6.2, 6.3, 6.4
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=None)
@given(
    scenario=token_scenario,
    token_value=token_strings,
)
@pytest.mark.asyncio
async def test_property4_optional_auth_never_raises_http_errors(scenario, token_value):
    """
    Property 4: For any request (with valid token, invalid token, expired token,
    malformed token, missing header, non-Bearer scheme, or empty token), the
    get_optional_user dependency SHALL either return a valid user dictionary
    (when the token is valid) or None (in all other cases), and SHALL never
    raise an HTTPException or modify the response status code.

    **Validates: Requirements 6.1, 6.2, 6.3, 6.4**
    """
    from firebase_admin import auth as firebase_auth

    # Build credentials based on scenario
    if scenario == "missing_credentials":
        credentials = None
    elif scenario == "empty_token":
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="")
    elif scenario == "non_bearer_scheme":
        # Non-Bearer scheme (e.g., Basic, Digest) — FastAPI's HTTPBearer with
        # auto_error=False returns None for non-Bearer schemes, so we simulate
        # that by passing None (the dependency receives None from the framework).
        credentials = None
    else:
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token_value or "some-token")

    # Configure mock behavior based on scenario
    if scenario == "valid":
        mock_decoded = {"uid": "user-123", "email": "test@example.com", "name": "Test User"}
        side_effect = None
        return_value = mock_decoded
    elif scenario == "expired":
        side_effect = firebase_auth.ExpiredIdTokenError("Token expired", cause="expired")
        return_value = None
    elif scenario == "invalid":
        side_effect = firebase_auth.InvalidIdTokenError("Token invalid")
        return_value = None
    elif scenario == "malformed":
        side_effect = ValueError("Malformed token data")
        return_value = None
    elif scenario == "exception_generic":
        side_effect = Exception("Unexpected error during verification")
        return_value = None
    else:
        # missing_credentials or empty_token — won't reach verify_id_token
        side_effect = None
        return_value = None

    with patch("middleware.auth._get_firebase_app"):
        with patch("middleware.auth.firebase_auth.verify_id_token") as mock_verify:
            if side_effect:
                mock_verify.side_effect = side_effect
            else:
                mock_verify.return_value = return_value

            # The core assertion: get_optional_user must NEVER raise HTTPException
            try:
                result = await get_optional_user(credentials)
            except HTTPException as e:
                pytest.fail(
                    f"get_optional_user raised HTTPException (status={e.status_code}) "
                    f"for scenario='{scenario}', token='{token_value[:50]}...'. "
                    f"It should NEVER raise HTTP errors."
                )

    # Verify return type: must be dict or None
    assert result is None or isinstance(result, dict), (
        f"get_optional_user returned unexpected type {type(result)} "
        f"for scenario='{scenario}'"
    )

    # If valid scenario and credentials were provided with non-empty token,
    # result should be a dict with uid, email, name
    if scenario == "valid" and credentials is not None and credentials.credentials:
        assert result is not None, "Valid token should return a user dict"
        assert "uid" in result
        assert "email" in result
        assert "name" in result
    elif scenario in ("expired", "invalid", "malformed", "exception_generic"):
        assert result is None, f"Scenario '{scenario}' should return None"
    elif scenario == "missing_credentials":
        assert result is None, "Missing credentials should return None"
    elif scenario == "empty_token":
        assert result is None, "Empty token should return None"
    elif scenario == "non_bearer_scheme":
        assert result is None, "Non-Bearer scheme should return None"
