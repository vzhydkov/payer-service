from collections import defaultdict
from fastapi.testclient import TestClient

import main

client = TestClient(main.app)

mock_txn1 = {"payer": "DANNON", "points": 1000, "timestamp": "2020-11-02T14:00:00Z"}
mock_txn2 = {"payer": "UNILEVER", "points": 200, "timestamp": "2020-10-31T11:00:00Z"}
mock_txn3 = {"payer": "DANNON", "points": -200, "timestamp": "2020-10-31T15:00:00Z"}
mock_txn4 = {"payer": "MILLER COORS", "points": 10000, "timestamp": "2020-11-01T14:00:00Z"}
mock_txn5 = {"payer": "DANNON", "points": 300, "timestamp": "2020-10-31T10:00:00Z"}


def test_add_success():
    main.TRANSACTIONS = []
    response = client.post("/add/", json=mock_txn1)
    assert response.status_code == 201
    response = client.post("/add/", json=mock_txn2)
    assert response.status_code == 201
    response = client.post("/add/", json=mock_txn3)
    assert response.status_code == 201
    response = client.post("/add/", json=mock_txn4)
    assert response.status_code == 201
    response = client.post("/add/", json=mock_txn5)
    assert response.status_code == 201
    assert main.TRANSACTIONS == [
        main.Transaction(**mock_txn1),
        main.Transaction(**mock_txn2),
        main.Transaction(**mock_txn3),
        main.Transaction(**mock_txn4),
        main.Transaction(**mock_txn5)
    ]


def test_add_required_fields():
    main.TRANSACTIONS = []
    response = client.post("/add/", json={})
    assert response.status_code == 422
    assert len(response.json()["detail"]) == 2  # payer and points are required


def test_add_payer_too_long():
    main.TRANSACTIONS = []
    response = client.post("/add/", json={
        "payer": "".join('a' for _ in range(101)),
        "points": 1000,
        "timestamp": "2020-11-02T14:00:00Z"
    })
    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "ensure this value has at most 100 characters"


def test_add_invalid_points():
    main.TRANSACTIONS = []
    response = client.post("/add/", json={
        "payer": "DANNON", "points": 1000.1, "timestamp": "2020-11-02T14:00:00Z"
    })
    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "points must integer"
    response = client.post("/add/", json={
        "payer": "DANNON", "points": 0, "timestamp": "2020-11-02T14:00:00Z"
    })
    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "points cannot be zero"


def test_add_invalid_timestamp():
    main.TRANSACTIONS = []
    response = client.post("/add/", json={"payer": "DANNON", "points": 1000, "timestamp": 2020})
    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "timestamp must be a datetime string"
    response = client.post("/add/", json={"payer": "DANNON", "points": 1000, "timestamp": "2020"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "timestamp has invalid format"


def test_add_negative_points():
    main.TRANSACTIONS = []
    response = client.post("/add/", json={
        "payer": "DANNON", "points": -100, "timestamp": "2020-11-02T14:00:00Z"
    })
    assert response.status_code == 400
    assert response.json()["detail"][0]["msg"] == "payer's points cannot be negative"
    assert main.TRANSACTIONS == []


def test_spend_success():
    main.TRANSACTIONS = [
        main.Transaction(**mock_txn1),
        main.Transaction(**mock_txn2),
        main.Transaction(**mock_txn3),
        main.Transaction(**mock_txn4),
        main.Transaction(**mock_txn5)
    ]
    response = client.post("/spend/", json={"points": 5000})
    assert response.status_code == 200
    assert response.json() == [
        {"payer": "DANNON", "points": -100},
        {"payer": "UNILEVER", "points": -200},
        {"payer": "MILLER COORS", "points": -4700}
    ]
    response = client.post("/spend/", json={"points": 5000})
    assert response.status_code == 200
    assert response.json() == [
        {"payer": "DANNON", "points": -100},
        {"payer": "MILLER COORS", "points": -4900}
    ]
    response = client.post("/spend/", json={"points": 1300})
    assert response.status_code == 200
    assert response.json() == [
        {"payer": "DANNON", "points": -900},
        {"payer": "MILLER COORS", "points": -400}
    ]
    total_points = defaultdict(int)
    for txn in main.TRANSACTIONS:
        total_points[txn.payer] += txn.points
    assert total_points == {"DANNON": 0, "UNILEVER": 0, "MILLER COORS": 0}


def test_spend_required_field():
    main.TRANSACTIONS = []
    response = client.post("/spend/", json={})
    assert response.status_code == 422
    assert len(response.json()["detail"]) == 1  # points is required


def test_spend_invalid_points():
    main.TRANSACTIONS = []
    response = client.post("/spend/", json={"points": "1000.1"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "value is not a valid integer"


def test_spend_negative_points():
    main.TRANSACTIONS = []
    response = client.post("/spend/", json={"points": -100})
    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "ensure this value is greater than or equal to 1"


def test_spend_not_enough_points():
    main.TRANSACTIONS = []
    response = client.post("/spend/", json={"points": 1000})
    assert response.status_code == 400
    assert response.json()["detail"][0]["msg"] == "not enough points to spend"


def test_balance():
    main.TRANSACTIONS = []
    response = client.get("/balance/")
    assert response.status_code == 200
    assert response.json() == {}
    main.TRANSACTIONS = [main.Transaction(**mock_txn1)]
    response = client.get("/balance/")
    assert response.status_code == 200
    assert response.json() == {"DANNON": 1000}
    main.TRANSACTIONS.append(main.Transaction(**mock_txn2))
    response = client.get("/balance/")
    assert response.status_code == 200
    assert response.json() == {"DANNON": 1000, "UNILEVER": 200}
    main.TRANSACTIONS.append(main.Transaction(**mock_txn3))
    response = client.get("/balance/")
    assert response.status_code == 200
    assert response.json() == {"DANNON": 800, "UNILEVER": 200}
    main.TRANSACTIONS.append(main.Transaction(**mock_txn4))
    response = client.get("/balance/")
    assert response.status_code == 200
    assert response.json() == {"DANNON": 800, "UNILEVER": 200, "MILLER COORS": 10000}
    main.TRANSACTIONS.append(main.Transaction(**mock_txn5))
    response = client.get("/balance/")
    assert response.status_code == 200
    assert response.json() == {"DANNON": 1100, "UNILEVER": 200, "MILLER COORS": 10000}
