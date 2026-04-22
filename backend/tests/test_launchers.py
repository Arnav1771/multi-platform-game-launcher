from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_launch_game_success():
    response = client.post("/api/games/1/launch")
    assert response.status_code == 200
    assert "Simulated launch command sent" in response.json()["message"]


def test_launch_game_not_installed():
    response = client.post("/api/games/2/launch")
    assert response.status_code == 400


def test_launch_game_not_found():
    response = client.post("/api/games/999/launch")
    assert response.status_code == 404
