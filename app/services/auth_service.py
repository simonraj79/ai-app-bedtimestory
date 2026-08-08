import os

import psycopg
from psycopg.rows import dict_row
from fastapi import Depends, HTTPException, Request
from google.auth.exceptions import TransportError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.database import get_conn
from app.schemas import CurrentUser

# The client ID is public — it ships in the frontend — but it is the value the
# token's `aud` claim is checked against, so a wrong one silently rejects every
# sign-in. Bracket access makes that a startup failure instead.
GOOGLE_CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]

# The single address allowed to read /admin/usage.
ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]


def current_user(request: Request) -> CurrentUser:
    """Verify the caller's Google ID token and return the user row it belongs to."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Please sign in with Google.")

    try:
        # Checks the signature, `aud` against our client id, `iss`, and `exp`.
        claims = id_token.verify_oauth2_token(
            header.removeprefix("Bearer "),
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Your sign-in has expired. Please sign in again.",
        )
    # Verification fetches Google's signing certs over the network, so "we could
    # not check the token" is a different failure from "the token is bad", and
    # TransportError is not a ValueError. Collapsing the two would tell a user
    # with a perfectly good sign-in to sign in again, forever.
    except TransportError:
        raise HTTPException(
            status_code=502,
            detail="Could not reach Google to verify your sign-in. Try again in a moment.",
        )

    # A signed token proves Google issued it, not that the address belongs to
    # the signer. Without this, an unverified address could impersonate a user
    # who later signs up with the same one.
    if not claims.get("email_verified"):
        raise HTTPException(
            status_code=401,
            detail="Your sign-in has expired. Please sign in again.",
        )

    try:
        with get_conn() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                # One statement for first sign-in and every one after, so
                # last_seen_at is maintained by simply using the app.
                cur.execute(
                    "INSERT INTO users (google_sub, email, name, picture) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (google_sub) DO UPDATE SET "
                    "    email = EXCLUDED.email, "
                    "    name = EXCLUDED.name, "
                    "    picture = EXCLUDED.picture, "
                    "    last_seen_at = NOW() "
                    "RETURNING id, email, name",
                    # email is guaranteed here — it is what email_verified
                    # describes. name and picture need the profile scope, which
                    # a caller can decline, so they are read defensively.
                    (
                        claims["sub"],
                        claims["email"],
                        claims.get("name", ""),
                        claims.get("picture"),
                    ),
                )
                row = cur.fetchone()
            conn.commit()
            return CurrentUser(**row)
    except psycopg.Error:
        raise HTTPException(
            status_code=502,
            detail="Postgres is not reachable. Check your database connection."
        )


def admin_user(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    """A signed-in caller who is also the owner of this deployment."""
    if user.email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Not authorised.")
    return user
