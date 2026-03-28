"""Xero OAuth 2.0 service — handles authentication and data fetching."""

import time
import requests
from urllib.parse import urlencode
from models.database import db, XeroToken


XERO_AUTH_URL = "https://login.xero.com/identity/connect/authorize"
XERO_TOKEN_URL = "https://identity.xero.com/connect/token"
XERO_CONNECTIONS_URL = "https://api.xero.com/connections"
XERO_API_BASE = "https://api.xero.com/api.xro/2.0"
XERO_SCOPES = "openid profile email accounting.transactions.read accounting.settings.read offline_access"


def get_auth_url(client_id: str, redirect_uri: str, state: str = "") -> str:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": XERO_SCOPES,
        "state": state,
    }
    return f"{XERO_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_token(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict:
    response = requests.post(
        XERO_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
        auth=(client_id, client_secret),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def refresh_access_token(refresh_token: str, client_id: str, client_secret: str) -> dict:
    response = requests.post(
        XERO_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        auth=(client_id, client_secret),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_tenants(access_token: str) -> list:
    response = requests.get(
        XERO_CONNECTIONS_URL,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def save_token(token_data: dict, tenant_id: str, tenant_name: str = "") -> XeroToken:
    existing = XeroToken.query.first()
    expires_at = time.time() + token_data.get("expires_in", 1800)

    if existing:
        existing.access_token = token_data["access_token"]
        existing.refresh_token = token_data.get("refresh_token", existing.refresh_token)
        existing.expires_at = expires_at
        existing.tenant_id = tenant_id
        existing.tenant_name = tenant_name
        db.session.commit()
        return existing
    else:
        token = XeroToken(
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_at=expires_at,
            tenant_id=tenant_id,
            tenant_name=tenant_name,
        )
        db.session.add(token)
        db.session.commit()
        return token


def get_valid_token(client_id: str, client_secret: str) -> XeroToken | None:
    token = XeroToken.query.first()
    if not token:
        return None

    # Refresh if expiring within 5 minutes
    if time.time() > token.expires_at - 300:
        try:
            new_data = refresh_access_token(token.refresh_token, client_id, client_secret)
            token = save_token(new_data, token.tenant_id, token.tenant_name)
        except Exception:
            return None

    return token


def fetch_purchase_orders(access_token: str, tenant_id: str) -> list:
    """Fetch purchase orders (bills) from Xero."""
    response = requests.get(
        f"{XERO_API_BASE}/PurchaseOrders",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Xero-tenant-id": tenant_id,
            "Accept": "application/json",
        },
        timeout=30,
    )
    if response.status_code != 200:
        return []
    data = response.json()
    return data.get("PurchaseOrders", [])


def fetch_invoices(access_token: str, tenant_id: str, invoice_type: str = "ACCPAY") -> list:
    """Fetch invoices (ACCPAY = bills/purchases, ACCREC = sales) from Xero."""
    response = requests.get(
        f"{XERO_API_BASE}/Invoices",
        params={"Type": invoice_type, "Status": "AUTHORISED,SUBMITTED"},
        headers={
            "Authorization": f"Bearer {access_token}",
            "Xero-tenant-id": tenant_id,
            "Accept": "application/json",
        },
        timeout=30,
    )
    if response.status_code != 200:
        return []
    data = response.json()
    return data.get("Invoices", [])
