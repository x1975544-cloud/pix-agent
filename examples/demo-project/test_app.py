import pytest
from fastapi.testclient import TestClient

from app import app, fizzbuzz


def test_root_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        (1, "1"),
        (3, "Fizz"),
        (5, "Buzz"),
        (15, "FizzBuzz"),
    ],
)
def test_fizzbuzz(number: int, expected: str) -> None:
    assert fizzbuzz(number) == expected


def test_fizzbuzz_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/fizzbuzz/15")
    assert response.status_code == 200
    assert response.json() == {"value": "FizzBuzz"}
