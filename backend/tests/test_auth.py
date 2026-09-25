def test_register_login_me(client):
    res = client.post(
        "/api/v1/auth/register",
        json={"username": "alice", "password": "pass123", "email": "a@b.com"},
    )
    assert res.status_code == 200
    assert res.json()["user"]["role"] == "user"
    token = res.json()["access_token"]
    assert token

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200
    assert me.json()["username"] == "alice"

    dup = client.post(
        "/api/v1/auth/register",
        json={"username": "alice", "password": "pass123"},
    )
    assert dup.status_code == 400

    bad = client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "wrong"},
    )
    assert bad.status_code == 401

    no_token = client.get("/api/v1/auth/me")
    assert no_token.status_code in (401, 403)
