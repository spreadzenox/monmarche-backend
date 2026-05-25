def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_is_public(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_recipes_requires_auth(client):
    response = client.get("/recipes")
    assert response.status_code == 401
