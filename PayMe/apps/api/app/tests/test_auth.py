def test_signup_login_and_me(client):
    signup = client.post(
        "/auth/signup",
        json={"username": "matt", "email": "matt@example.com", "password": "password123"},
    )
    assert signup.status_code == 200
    token = signup.json()["access_token"]

    duplicate = client.post(
        "/auth/signup",
        json={"username": "matt", "email": "matt2@example.com", "password": "password123"},
    )
    assert duplicate.status_code == 400

    login = client.post("/auth/login", json={"username_or_email": "matt", "password": "password123"})
    assert login.status_code == 200

    unauthorized = client.get("/auth/me")
    assert unauthorized.status_code == 401

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "matt"


def test_login_failure(client):
    client.post(
        "/auth/signup",
        json={"username": "foo", "email": "foo@example.com", "password": "password123"},
    )
    bad = client.post("/auth/login", json={"username_or_email": "foo", "password": "wrong"})
    assert bad.status_code == 401
