from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.db import get_db
from app.core.logging import app_logger
from app.models.entities import User
from app.services.ingestion.gmail_sync import sync_gmail
from app.services.ingestion.plaid_sync import sync_plaid

router = APIRouter(prefix="/integrations", tags=["integrations"])


# ---------------------------------------------------------------------------
# Gmail — OAuth
# ---------------------------------------------------------------------------


@router.get("/gmail/oauth/init")
def gmail_oauth_init(request: Request, user: User = Depends(get_current_user)):
    """Return the Google OAuth authorization URL for this user.

    The client should redirect the user's browser to the returned auth_url.
    Requires authentication.
    """
    try:
        from app.services.ingestion.gmail_real import get_oauth_authorization_url  # noqa: PLC0415
    except ImportError as exc:
        app_logger.warning(
            "gmail_oauth_init_import_error",
            extra={
                "request_id": getattr(request.state, "request_id", ""),
                "path": request.url.path,
                "method": request.method,
                "status_code": 503,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    try:
        auth_url, _state = get_oauth_authorization_url(str(user.id))
    except (ValueError, ImportError) as exc:
        app_logger.warning(
            f"gmail_oauth_init_failed user_id={user.id} error={str(exc)[:300]}",
            extra={
                "request_id": getattr(request.state, "request_id", ""),
                "path": request.url.path,
                "method": request.method,
                "status_code": 400,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    app_logger.info(
        f"gmail_oauth_init_ok user_id={user.id}",
        extra={
            "request_id": getattr(request.state, "request_id", ""),
            "path": request.url.path,
            "method": request.method,
            "status_code": 200,
        },
    )

    return {"auth_url": auth_url}


@router.get("/gmail/oauth/callback")
def gmail_oauth_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """Handle the Google OAuth callback.

    Google redirects here with ?code=...&state=... after user consent.
    The state encodes the user_id, so no session auth is required.
    """
    try:
        from app.services.ingestion.gmail_real import exchange_oauth_code  # noqa: PLC0415
    except ImportError as exc:
        app_logger.warning(
            "gmail_oauth_callback_import_error",
            extra={
                "request_id": getattr(request.state, "request_id", ""),
                "path": request.url.path,
                "method": request.method,
                "status_code": 503,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    # Look up the user from the state parameter (which encodes user_id).
    user = db.get(User, state)
    if user is None:
        error_msg = "Invalid OAuth state: user not found."
        app_logger.warning(
            f"gmail_oauth_callback_invalid_state state={state}",
            extra={
                "request_id": getattr(request.state, "request_id", ""),
                "path": request.url.path,
                "method": request.method,
                "status_code": 200,
            },
        )
        html = f"""<html><body><script>
try {{
  if (window.opener) {{
    window.opener.postMessage({{type:'gmail_oauth_error',error:'{error_msg}'}},'*');
  }}
}} catch (e) {{}}
setTimeout(() => window.close(), 150);
</script><p>Error: {error_msg}</p></body></html>"""
        return HTMLResponse(content=html, status_code=200)

    try:
        result = exchange_oauth_code(db, user, code=code, state=state)
        db.commit()
        app_logger.info(
            f"gmail_oauth_callback_exchange_ok user_id={user.id}",
            extra={
                "request_id": getattr(request.state, "request_id", ""),
                "path": request.url.path,
                "method": request.method,
                "status_code": 200,
            },
        )
        
        # Automatically sync Gmail after successful OAuth connection
        try:
            sync_gmail(db, user)
            db.commit()
            app_logger.info(
                f"gmail_oauth_callback_sync_ok user_id={user.id}",
                extra={
                    "request_id": getattr(request.state, "request_id", ""),
                    "path": request.url.path,
                    "method": request.method,
                    "status_code": 200,
                },
            )
        except Exception:  # noqa: BLE001
            # Don't fail the OAuth flow if sync fails
            app_logger.warning(
                f"gmail_oauth_callback_sync_failed user_id={user.id}",
                extra={
                    "request_id": getattr(request.state, "request_id", ""),
                    "path": request.url.path,
                    "method": request.method,
                    "status_code": 200,
                },
            )
        
        email = result.get("email", "") if isinstance(result, dict) else ""
        html = f"""<html><body><script>
try {{
  if (window.opener) {{
    window.opener.postMessage({{type:'gmail_oauth_success',email:'{email}'}},'*');
  }}
}} catch (e) {{}}
setTimeout(() => window.close(), 150);
</script><p>Gmail connected! You can close this window.</p></body></html>"""
        return HTMLResponse(content=html)
    except Exception as exc:  # noqa: BLE001
        error_msg = str(exc).replace("'", "\\'")
        app_logger.warning(
            f"gmail_oauth_callback_failed state={state} error={str(exc)[:300]}",
            extra={
                "request_id": getattr(request.state, "request_id", ""),
                "path": request.url.path,
                "method": request.method,
                "status_code": 200,
            },
        )
        html = f"""<html><body><script>
try {{
  if (window.opener) {{
    window.opener.postMessage({{type:'gmail_oauth_error',error:'{error_msg}'}},'*');
  }}
}} catch (e) {{}}
setTimeout(() => window.close(), 150);
</script><p>Error: {error_msg}</p></body></html>"""
        return HTMLResponse(content=html, status_code=200)


@router.post("/gmail/revoke")
def gmail_revoke_route(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Revoke the authenticated user's Gmail OAuth access.

    Calls Google's token revocation endpoint and marks the local token row
    as revoked. Requires authentication.
    """
    try:
        from app.services.ingestion.gmail_real import revoke_gmail_access  # noqa: PLC0415
    except ImportError as exc:
        app_logger.warning(
            "gmail_revoke_import_error",
            extra={
                "request_id": getattr(request.state, "request_id", ""),
                "path": request.url.path,
                "method": request.method,
                "status_code": 503,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    try:
        result = revoke_gmail_access(db, user)
        db.commit()
    except ValueError as exc:
        app_logger.warning(
            f"gmail_revoke_failed user_id={user.id} error={str(exc)[:300]}",
            extra={
                "request_id": getattr(request.state, "request_id", ""),
                "path": request.url.path,
                "method": request.method,
                "status_code": 400,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    app_logger.info(
        f"gmail_revoke_ok user_id={user.id}",
        extra={
            "request_id": getattr(request.state, "request_id", ""),
            "path": request.url.path,
            "method": request.method,
            "status_code": 200,
        },
    )

    return result


# ---------------------------------------------------------------------------
# Gmail — sync
# ---------------------------------------------------------------------------


@router.post("/gmail/sync")
def gmail_sync_route(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Run Gmail sync for the authenticated user.

    Dispatches to mock or real sync depending on settings.mock_gmail.
    """
    try:
        result = sync_gmail(db, user)
        db.commit()
        app_logger.info(
            f"gmail_sync_ok user_id={user.id} inserted_messages={result.get('inserted_messages', 'n/a')}",
            extra={
                "request_id": getattr(request.state, "request_id", ""),
                "path": request.url.path,
                "method": request.method,
                "status_code": 200,
            },
        )
        return result
    except ValueError as exc:
        app_logger.warning(
            f"gmail_sync_failed user_id={user.id} error={str(exc)[:300]}",
            extra={
                "request_id": getattr(request.state, "request_id", ""),
                "path": request.url.path,
                "method": request.method,
                "status_code": 400,
            },
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        app_logger.warning(
            f"gmail_sync_failed user_id={user.id} error={str(exc)[:300]}",
            extra={
                "request_id": getattr(request.state, "request_id", ""),
                "path": request.url.path,
                "method": request.method,
                "status_code": 400,
            },
        )
        raise


# ---------------------------------------------------------------------------
# Plaid — existing sync (now dispatched through sync_plaid)
# ---------------------------------------------------------------------------


@router.post("/plaid/sync")
def plaid_sync_route(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        result = sync_plaid(db, user)
        db.commit()
        app_logger.info(
            f"plaid_sync_ok user_id={user.id} inserted_transactions={result.get('inserted_transactions', 'n/a')}",
            extra={
                "request_id": getattr(request.state, "request_id", ""),
                "path": request.url.path,
                "method": request.method,
                "status_code": 200,
            },
        )
        return result
    except ValueError as exc:
        # Commit any state changes (e.g. requires_reauth flag) before returning the error.
        try:
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
        app_logger.warning(
            f"plaid_sync_failed user_id={user.id} error={str(exc)[:300]}",
            extra={
                "request_id": getattr(request.state, "request_id", ""),
                "path": request.url.path,
                "method": request.method,
                "status_code": 400,
            },
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Plaid — Link token
# ---------------------------------------------------------------------------


@router.post("/plaid/link-token")
def plaid_link_token_route(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a Plaid Link token for the authenticated user."""
    from app.services.ingestion.plaid_real import create_link_token

    try:
        result = create_link_token(str(user.id))
    except ValueError as exc:
        app_logger.warning(
            f"plaid_link_token_failed user_id={user.id} error={str(exc)[:300]}",
            extra={
                "request_id": getattr(request.state, "request_id", ""),
                "path": request.url.path,
                "method": request.method,
                "status_code": 400,
            },
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    app_logger.info(
        f"plaid_link_token_ok user_id={user.id}",
        extra={
            "request_id": getattr(request.state, "request_id", ""),
            "path": request.url.path,
            "method": request.method,
            "status_code": 200,
        },
    )
    return result


# ---------------------------------------------------------------------------
# Plaid — Token exchange
# ---------------------------------------------------------------------------


class PlaidExchangeRequest(BaseModel):
    public_token: str
    institution_id: str | None = None
    institution_name: str | None = None


@router.post("/plaid/exchange")
def plaid_exchange_route(
    request: Request,
    body: PlaidExchangeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Exchange a Plaid public token for a persistent access token."""
    from app.services.ingestion.plaid_real import exchange_public_token

    try:
        result = exchange_public_token(
            db,
            user,
            body.public_token,
            body.institution_id,
            body.institution_name,
        )
    except ValueError as exc:
        app_logger.warning(
            f"plaid_exchange_failed user_id={user.id} error={str(exc)[:300]}",
            extra={
                "request_id": getattr(request.state, "request_id", ""),
                "path": request.url.path,
                "method": request.method,
                "status_code": 400,
            },
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    app_logger.info(
        f"plaid_exchange_ok user_id={user.id}",
        extra={
            "request_id": getattr(request.state, "request_id", ""),
            "path": request.url.path,
            "method": request.method,
            "status_code": 200,
        },
    )
    
    # Automatically sync Plaid after successful token exchange
    try:
        sync_plaid(db, user)
        db.commit()
        app_logger.info(
            f"plaid_exchange_post_sync_ok user_id={user.id}",
            extra={
                "request_id": getattr(request.state, "request_id", ""),
                "path": request.url.path,
                "method": request.method,
                "status_code": 200,
            },
        )
    except Exception:  # noqa: BLE001
        # Don't fail the exchange flow if sync fails
        app_logger.warning(
            f"plaid_exchange_post_sync_failed user_id={user.id}",
            extra={
                "request_id": getattr(request.state, "request_id", ""),
                "path": request.url.path,
                "method": request.method,
                "status_code": 200,
            },
        )
    
    return result


# ---------------------------------------------------------------------------
# Plaid — Disconnect
# ---------------------------------------------------------------------------


@router.post("/plaid/disconnect")
def plaid_disconnect_route(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Disconnect the authenticated user's Plaid item."""
    from app.services.ingestion.plaid_real import disconnect_item

    try:
        result = disconnect_item(db, user)
    except ValueError as exc:
        app_logger.warning(
            f"plaid_disconnect_failed user_id={user.id} error={str(exc)[:300]}",
            extra={
                "request_id": getattr(request.state, "request_id", ""),
                "path": request.url.path,
                "method": request.method,
                "status_code": 400,
            },
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    app_logger.info(
        f"plaid_disconnect_ok user_id={user.id}",
        extra={
            "request_id": getattr(request.state, "request_id", ""),
            "path": request.url.path,
            "method": request.method,
            "status_code": 200,
        },
    )
    return result
