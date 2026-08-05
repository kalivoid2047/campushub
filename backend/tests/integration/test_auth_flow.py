"""End-to-end auth flow tests through the FastAPI app (docs/06 section 2).

Covers: login, /me, refresh rotation, rotated-token reuse (theft signal),
logout, RBAC guards, and tenant provisioning + isolation (AC-1/AC-4,
docs/02 section 7).
"""

import uuid

import pytest

from app.core.security import create_access_token
from tests.conftest import make_super_admin_token

pytestmark = pytest.mark.asyncio

LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/auth/me"
TENANTS = "/api/v1/admin/tenants"

GOOD_LOGIN = {
    "email": "student@test-college.edu",
    "password": "correct-horse",
    "tenant_slug": "test-college",
}


async def test_login_success(client, seeded_tenant):
    resp = await client.post(LOGIN, json=GOOD_LOGIN)
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["token_type"] == "bearer"


async def test_login_wrong_password(client, seeded_tenant):
    resp = await client.post(LOGIN, json={**GOOD_LOGIN, "password": "wrong-password"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"


async def test_login_wrong_tenant_same_generic_error(client, seeded_tenant):
    resp = await client.post(LOGIN, json={**GOOD_LOGIN, "tenant_slug": "no-such-college"})
    assert resp.status_code == 401
    # Same generic message as a bad password — no tenant enumeration.
    assert resp.json()["detail"] == "Invalid credentials"


async def test_me_requires_auth(client, seeded_tenant):
    assert (await client.get(ME)).status_code == 401


async def test_me_returns_profile(client, seeded_tenant):
    login = (await client.post(LOGIN, json=GOOD_LOGIN)).json()
    resp = await client.get(ME, headers={"Authorization": f"Bearer {login['access_token']}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "student@test-college.edu"
    assert body["roles"] == ["student"]


async def test_refresh_rotates_and_old_token_dies(client, seeded_tenant):
    login = (await client.post(LOGIN, json=GOOD_LOGIN)).json()
    old_refresh = login["refresh_token"]

    rotated = await client.post(REFRESH, json={"refresh_token": old_refresh})
    assert rotated.status_code == 200
    new_refresh = rotated.json()["refresh_token"]
    assert new_refresh != old_refresh

    # Reusing the rotated (revoked) token is rejected AND kills the chain.
    reuse = await client.post(REFRESH, json={"refresh_token": old_refresh})
    assert reuse.status_code == 401
    chain_killed = await client.post(REFRESH, json={"refresh_token": new_refresh})
    assert chain_killed.status_code == 401


async def test_logout_revokes_refresh(client, seeded_tenant):
    login = (await client.post(LOGIN, json=GOOD_LOGIN)).json()
    assert (
        await client.post(LOGOUT, json={"refresh_token": login["refresh_token"]})
    ).status_code == 204
    resp = await client.post(REFRESH, json={"refresh_token": login["refresh_token"]})
    assert resp.status_code == 401


async def test_tenant_creation_requires_super_admin(client, seeded_tenant):
    login = (await client.post(LOGIN, json=GOOD_LOGIN)).json()  # student token
    resp = await client.post(
        TENANTS,
        json={
            "name": "Another College",
            "slug": "another-college",
            "admin_email": "admin@another.edu",
            "admin_password": "admin-password-1",
            "admin_full_name": "Admin Person",
        },
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )
    assert resp.status_code == 403


async def test_tenant_provisioning_and_isolation(client, seeded_tenant):
    token = make_super_admin_token()
    resp = await client.post(
        TENANTS,
        json={
            "name": "Second College",
            "slug": "second-college",
            "admin_email": "admin@second.edu",
            "admin_password": "admin-password-1",
            "admin_full_name": "Second Admin",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "active"

    # New tenant's admin can log in against their own slug...
    ok = await client.post(
        LOGIN,
        json={
            "email": "admin@second.edu",
            "password": "admin-password-1",
            "tenant_slug": "second-college",
        },
    )
    assert ok.status_code == 200

    # ...but the same credentials fail against the first tenant (isolation).
    cross = await client.post(
        LOGIN,
        json={
            "email": "admin@second.edu",
            "password": "admin-password-1",
            "tenant_slug": "test-college",
        },
    )
    assert cross.status_code == 401


async def test_login_locks_out_after_repeated_failures(client, seeded_tenant):
    bad = {**GOOD_LOGIN, "password": "wrong-password"}
    for _ in range(5):
        resp = await client.post(LOGIN, json=bad)
        assert resp.status_code == 401

    # The 6th attempt — even with the *correct* password — is throttled,
    # not evaluated: the account is locked out for a stretch, not merely
    # slowed one request at a time.
    locked = await client.post(LOGIN, json=GOOD_LOGIN)
    assert locked.status_code == 429
    assert "Retry-After" in locked.headers


async def test_login_success_clears_the_lockout_counter(client, seeded_tenant):
    bad = {**GOOD_LOGIN, "password": "wrong-password"}
    for _ in range(3):
        assert (await client.post(LOGIN, json=bad)).status_code == 401

    # Below the threshold — succeeding resets the counter rather than
    # merely pausing it.
    assert (await client.post(LOGIN, json=GOOD_LOGIN)).status_code == 200

    for _ in range(3):
        assert (await client.post(LOGIN, json=bad)).status_code == 401
    assert (await client.post(LOGIN, json=GOOD_LOGIN)).status_code == 200


async def test_login_lockout_is_scoped_per_account(client, seeded_tenant):
    # httpx's ASGITransport reports the same fixed client host for every
    # request, so distinct X-Forwarded-For headers stand in for distinct
    # source IPs here — otherwise the shared IP-scoped key (below) would
    # also trip and this test would prove nothing about account scoping.
    bad = {**GOOD_LOGIN, "password": "wrong-password"}
    headers_a = {"X-Forwarded-For": "203.0.113.10"}
    for _ in range(5):
        assert (await client.post(LOGIN, json=bad, headers=headers_a)).status_code == 401
    assert (await client.post(LOGIN, json=GOOD_LOGIN, headers=headers_a)).status_code == 429

    # A different account from a different source IP is unaffected.
    unaffected = await client.post(
        LOGIN,
        json={
            "email": "nobody-else@test-college.edu",
            "password": "whatever-wrong",
            "tenant_slug": "test-college",
        },
        headers={"X-Forwarded-For": "203.0.113.20"},
    )
    assert unaffected.status_code == 401  # evaluated normally, not 429


async def test_login_lockout_also_applies_per_ip_across_accounts(client, seeded_tenant):
    # One source spraying guesses across many different (here, nonexistent)
    # accounts should still trip the IP-scoped half of the limiter, even
    # though no single account key ever reaches the threshold alone.
    headers = {"X-Forwarded-For": "198.51.100.5"}
    for i in range(5):
        resp = await client.post(
            LOGIN,
            json={
                "email": f"guess-{i}@test-college.edu",
                "password": "whatever-wrong",
                "tenant_slug": "test-college",
            },
            headers=headers,
        )
        assert resp.status_code == 401

    throttled = await client.post(LOGIN, json=GOOD_LOGIN, headers=headers)
    assert throttled.status_code == 429


def _tenant_admin_headers(tenant_id) -> dict:
    token = create_access_token(
        user_id=uuid.uuid4(), tenant_id=tenant_id, roles=["institution_admin"]
    )
    return {"Authorization": f"Bearer {token}"}


async def test_auth_events_are_audit_logged(client, seeded_tenant):
    tenant, _ = seeded_tenant
    admin_headers = _tenant_admin_headers(tenant.id)

    await client.post(LOGIN, json={**GOOD_LOGIN, "password": "wrong-password"})
    login = (await client.post(LOGIN, json=GOOD_LOGIN)).json()
    await client.post(LOGOUT, json={"refresh_token": login["refresh_token"]})

    logs = (await client.get("/api/v1/admin/audit-logs", headers=admin_headers)).json()
    actions = [entry["action"] for entry in logs]
    assert "auth.login_failed" in actions
    assert "auth.login_succeeded" in actions
    assert "auth.logout" in actions


async def test_refresh_token_reuse_is_audit_logged(client, seeded_tenant):
    tenant, _ = seeded_tenant
    admin_headers = _tenant_admin_headers(tenant.id)

    login = (await client.post(LOGIN, json=GOOD_LOGIN)).json()
    old_refresh = login["refresh_token"]
    await client.post(REFRESH, json={"refresh_token": old_refresh})
    # Reusing the now-rotated token is the theft signal.
    await client.post(REFRESH, json={"refresh_token": old_refresh})

    logs = (await client.get("/api/v1/admin/audit-logs", headers=admin_headers)).json()
    assert any(entry["action"] == "auth.refresh_token_reuse_detected" for entry in logs)


async def test_duplicate_slug_rejected(client, seeded_tenant):
    token = make_super_admin_token()
    payload = {
        "name": "Dup",
        "slug": "test-college",  # already exists
        "admin_email": "dup@dup.edu",
        "admin_password": "admin-password-1",
        "admin_full_name": "Dup Admin",
    }
    resp = await client.post(TENANTS, json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 409
