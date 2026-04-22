from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_get_all_games():
    response = client.get("/api/games")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert {"id", "title", "platform", "installed", "launch_command"} <= data[0].keys()


def test_get_game_by_id_success():
    response = client.get("/api/games/1")
    assert response.status_code == 200
    assert response.json()["id"] == 1


def test_get_game_by_id_not_found():
    response = client.get("/api/games/999")
    assert response.status_code == 404
