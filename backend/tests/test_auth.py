"""Sign-in, and proof that one user can never reach another user's data."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app import auth, mailer, store
from app.main import app
from tests.conftest import start_claim


def account():
    return {"email": f"{uuid.uuid4().hex}@test.in", "password": "testing-123", "name": "Asha Rao"}


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def signed_in(c, a=None):
    out = c.post("/auth/signup", json=a or account()).json()
    return {"Authorization": f"Bearer {out['token']}"}


def test_signup_then_login_then_logout(client):
    a = account()
    out = client.post("/auth/signup", json=a).json()
    assert out["user"] == {"email": a["email"], "name": "Asha Rao"} and out["token"]
    token = client.post("/auth/login", json={"email": a["email"].upper(), "password": a["password"]}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/auth/me", headers=h).json()["name"] == "Asha Rao"
    assert client.post("/auth/logout", headers=h).status_code == 200
    assert client.get("/auth/me", headers=h).status_code == 401


@pytest.mark.parametrize("path", ["/policies", "/claims", "/profile", "/audit", "/assistant/thread", "/consents"])
def test_routes_need_a_session(client, path):
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer made-up"}).status_code == 401


def test_only_health_languages_and_auth_are_public(client):
    assert client.get("/health").status_code == 200 and client.get("/languages").status_code == 200
    assert client.post("/i18n", json={"lang": "hi-IN", "strings": {}}).status_code == 401
    assert client.post("/mock/upi/pay", json={"amount": 1, "payee": "x"}).status_code == 401


def test_nothing_secret_is_stored_or_returned(client):
    a = account()
    out = client.post("/auth/signup", json=a).json()
    stored = store.get("account", a["email"], user=store.SYSTEM)
    assert a["password"] not in str(stored) and "hash" not in out["user"]
    assert store.get("session", out["token"], user=store.SYSTEM) is None  # only the hash of the token is kept


@pytest.mark.parametrize("email,password,name", [("bad", "testing-123", "A"), ("a@b.in", "short", "A"), ("a@b.in", "testing-123", " ")])
def test_bad_signups_are_refused(client, email, password, name):
    assert client.post("/auth/signup", json={"email": email, "password": password, "name": name}).status_code == 422


def test_an_email_can_only_sign_up_once(client):
    a = account()
    client.post("/auth/signup", json=a)
    assert client.post("/auth/signup", json=a).status_code == 409


def test_wrong_password_and_unknown_email_look_the_same(client):
    a = account()
    client.post("/auth/signup", json=a)
    wrong = client.post("/auth/login", json={"email": a["email"], "password": "nope-nope"})
    unknown = client.post("/auth/login", json={"email": "nobody@test.in", "password": "nope-nope"})
    assert wrong.status_code == unknown.status_code == 401 and wrong.json() == unknown.json()


def test_repeated_wrong_passwords_lock_the_account(client):
    a = account()
    client.post("/auth/signup", json=a)
    for _ in range(auth.MAX_FAILS):
        client.post("/auth/login", json={"email": a["email"], "password": "nope-nope"})
    assert client.post("/auth/login", json={"email": a["email"], "password": a["password"]}).status_code == 429


def test_expired_session_is_refused(client):
    token = client.post("/auth/signup", json=account()).json()["token"]
    s = store.get("session", auth._token_id(token), user=store.SYSTEM)
    s["expires"] = "2020-01-01T00:00:00+00:00"
    store.put("session", s, user=store.SYSTEM)
    assert client.get("/profile", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_a_new_user_starts_empty_with_their_own_name(client):
    h = signed_in(client)
    p = client.get("/profile", headers=h).json()
    assert p["name"] == "Asha Rao" and p["onboarded"] is False and p["mobile"] == ""
    assert client.get("/policies", headers=h).json() == []


def test_users_cannot_see_each_others_data(api, client):
    cid = start_claim(api)
    other = signed_in(client)
    assert client.get(f"/claims/{cid}", headers=other).status_code == 404
    assert client.get("/claims", headers=other).json() == []
    assert client.get("/policies", headers=other).json() == []
    assert client.get(f"/claims/{cid}/form.pdf", headers=other).status_code == 404
    assert client.post(f"/claims/{cid}/advance", headers=other).status_code == 404
    assert client.get("/audit", headers=other).json() == []


def test_two_users_can_hold_the_same_sample_policy(api, client):
    other = signed_in(client)
    assert api.post("/samples/sunita_gallbladder/policy").json()["id"] == "pol_shield"
    assert client.post("/samples/sunita_gallbladder/policy", headers=other).json()["id"] == "pol_shield"
    client.delete("/policies/pol_shield", headers=other)
    assert len(api.get("/policies").json()) == 1


def test_deleting_my_data_keeps_my_login_and_leaves_others_alone(api, client):
    other = signed_in(client)
    client.post("/samples/sunita_gallbladder/policy", headers=other)
    api.post("/samples/sunita_gallbladder/policy")
    api.delete("/me/data")
    assert api.get("/policies").json() == [] and api.get("/profile").json()["name"] == "Test User"
    assert len(client.get("/policies", headers=other).json()) == 1


def test_media_links_can_use_a_query_token_but_nothing_else_can(api, client):
    cid = start_claim(api)
    token = api.headers["Authorization"][7:]
    assert client.get(f"/claims/{cid}/form.pdf?access_token={token}").status_code == 200
    assert client.get(f"/claims/{cid}?access_token={token}").status_code == 401
    assert client.get("/policies?access_token=" + token).status_code == 401


@pytest.fixture()
def inbox(monkeypatch):
    sent = []
    monkeypatch.setattr(mailer, "available", lambda: True)
    monkeypatch.setattr(mailer, "send", lambda to, subject, text: sent.append((to, text)))
    return sent


def code_in(inbox):
    return next(w for w in inbox[-1][1].replace(".", " ").split() if w.isdigit() and len(w) == 6)


def test_root_answers(client):
    assert client.get("/").json()["ok"] is True


def test_reset_password_end_to_end(client, inbox):
    a = account()
    old = client.post("/auth/signup", json=a).json()["token"]
    assert client.post("/auth/forgot-password", json={"email": a["email"]}).status_code == 200
    assert inbox[-1][0] == a["email"]
    r = client.post("/auth/reset-password", json={"email": a["email"], "code": code_in(inbox), "password": "brand-new-pass"})
    assert r.status_code == 200
    assert client.post("/auth/login", json={"email": a["email"], "password": a["password"]}).status_code == 401
    assert client.post("/auth/login", json={"email": a["email"], "password": "brand-new-pass"}).status_code == 200
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {old}"}).status_code == 401  # old devices are out


def test_reset_keeps_the_users_data(api, client, inbox):
    api.post("/samples/sunita_gallbladder/policy")
    email = api.get("/auth/me").json()["email"]
    client.post("/auth/forgot-password", json={"email": email})
    client.post("/auth/reset-password", json={"email": email, "code": code_in(inbox), "password": "brand-new-pass"})
    t = client.post("/auth/login", json={"email": email, "password": "brand-new-pass"}).json()["token"]
    assert len(client.get("/policies", headers={"Authorization": f"Bearer {t}"}).json()) == 1


def test_forgot_does_not_reveal_who_has_an_account(client, inbox):
    a = account()
    client.post("/auth/signup", json=a)
    known = client.post("/auth/forgot-password", json={"email": a["email"]})
    unknown = client.post("/auth/forgot-password", json={"email": "nobody-here@test.in"})
    assert known.json() == unknown.json() and known.status_code == unknown.status_code == 200
    assert len(inbox) == 1


def test_code_is_stored_hashed_and_works_once(client, inbox):
    a = account()
    client.post("/auth/signup", json=a)
    client.post("/auth/forgot-password", json={"email": a["email"]})
    code = code_in(inbox)
    assert code not in str(store.get("reset", a["email"], user=store.SYSTEM))
    body = {"email": a["email"], "code": code, "password": "brand-new-pass"}
    assert client.post("/auth/reset-password", json=body).status_code == 200
    assert client.post("/auth/reset-password", json={**body, "password": "another-pass"}).status_code == 400


def test_five_wrong_codes_kill_the_code(client, inbox):
    a = account()
    client.post("/auth/signup", json=a)
    client.post("/auth/forgot-password", json={"email": a["email"]})
    code = code_in(inbox)
    bad = "000000" if code != "000000" else "111111"
    for _ in range(auth.RESET_TRIES):
        assert client.post("/auth/reset-password", json={"email": a["email"], "code": bad, "password": "brand-new-pass"}).status_code == 400
    assert client.post("/auth/reset-password", json={"email": a["email"], "code": code, "password": "brand-new-pass"}).status_code == 400


def test_expired_code_is_refused(client, inbox):
    a = account()
    client.post("/auth/signup", json=a)
    client.post("/auth/forgot-password", json={"email": a["email"]})
    r = store.get("reset", a["email"], user=store.SYSTEM)
    r["expires"] = "2020-01-01T00:00:00+00:00"
    store.put("reset", r, user=store.SYSTEM)
    assert client.post("/auth/reset-password", json={"email": a["email"], "code": code_in(inbox), "password": "brand-new-pass"}).status_code == 400


def test_a_second_request_within_a_minute_sends_nothing(client, inbox):
    a = account()
    client.post("/auth/signup", json=a)
    for _ in range(3):
        assert client.post("/auth/forgot-password", json={"email": a["email"]}).status_code == 200
    assert len(inbox) == 1


def test_weak_new_password_is_refused_and_code_survives(client, inbox):
    a = account()
    client.post("/auth/signup", json=a)
    client.post("/auth/forgot-password", json={"email": a["email"]})
    assert client.post("/auth/reset-password", json={"email": a["email"], "code": code_in(inbox), "password": "short"}).status_code == 422
    assert client.post("/auth/reset-password", json={"email": a["email"], "code": code_in(inbox), "password": "long-enough-now"}).status_code == 200


def test_reset_clears_a_lockout(client, inbox):
    a = account()
    client.post("/auth/signup", json=a)
    for _ in range(auth.MAX_FAILS):
        client.post("/auth/login", json={"email": a["email"], "password": "nope-nope"})
    client.post("/auth/forgot-password", json={"email": a["email"]})
    client.post("/auth/reset-password", json={"email": a["email"], "code": code_in(inbox), "password": "brand-new-pass"})
    assert client.post("/auth/login", json={"email": a["email"], "password": "brand-new-pass"}).status_code == 200


def test_without_email_configured_forgot_is_an_honest_503(client):
    assert client.post("/auth/forgot-password", json={"email": "a@test.in"}).status_code == 503


def test_change_password_needs_the_current_one_and_signs_out_other_devices(client):
    a = account()
    here = client.post("/auth/signup", json=a).json()["token"]
    there = client.post("/auth/login", json={"email": a["email"], "password": a["password"]}).json()["token"]
    h = {"Authorization": f"Bearer {here}"}
    assert client.post("/auth/change-password", headers=h, json={"current_password": "wrong-one", "new_password": "brand-new-pass"}).status_code == 400
    assert client.post("/auth/change-password", headers=h, json={"current_password": a["password"], "new_password": "brand-new-pass"}).status_code == 200
    assert client.get("/auth/me", headers=h).status_code == 200
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {there}"}).status_code == 401
    assert client.post("/auth/login", json={"email": a["email"], "password": "brand-new-pass"}).status_code == 200


def test_change_password_needs_a_session(client):
    assert client.post("/auth/change-password", json={"current_password": "a", "new_password": "brand-new-pass"}).status_code == 401
