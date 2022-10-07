""" Payer Service """

from datetime import datetime
from collections import defaultdict
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field, validator


TRANSACTIONS = []
DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class Transaction(BaseModel):
    """ Model represents transaction payload """
    payer: str = Field(max_length=100)
    points: int
    timestamp: str = Field(default=datetime.now().strftime(DATE_FORMAT))

    @validator("timestamp", pre=True)
    def validate_datetime_format(cls, v: str) -> str:
        """ make sure value is datetime formatted """
        if not isinstance(v, str):
            raise ValueError("timestamp must be a datetime string")
        try:
            datetime.strptime(v, DATE_FORMAT)
            return v
        except ValueError:
            raise ValueError("timestamp has invalid format")

    @validator("points", pre=True)
    def validate_int_and_zero(cls, v: int) -> int:
        """ make sure value is int and not zero"""
        if not isinstance(v, int):
            raise ValueError("points must integer")
        if v == 0:
            raise ValueError("points cannot be zero")
        return v


class Spend(BaseModel):
    """ Model represents spend payload """
    points: int = Field(ge=1)


app = FastAPI()


@app.post("/add/")
async def add(transaction: Transaction) -> Response:
    """ Add transaction endpoint """
    total_points = transaction.points
    for curr_txn in TRANSACTIONS:
        if transaction.payer == curr_txn.payer:
            total_points += curr_txn.points
    if total_points < 0:
        raise HTTPException(status_code=400, detail=[{"msg": "payer's points cannot be negative"}])
    TRANSACTIONS.append(transaction)
    return Response(status_code=201)


@app.post("/spend/")
async def spend(data: Spend) -> list:
    """ Spend points endpoint """
    points_to_spend = data.points
    movements = defaultdict(int)
    curr_points = defaultdict(int)
    total_points = defaultdict(int)
    for transaction in TRANSACTIONS:
        total_points[transaction.payer] += transaction.points
    # The ISO 8601 format strings are lexicographically ordered
    for curr_txn in sorted(TRANSACTIONS, key=lambda x: x.timestamp):
        curr_points[curr_txn.payer] += curr_txn.points
        amount = min(points_to_spend, total_points[curr_txn.payer], curr_points[curr_txn.payer])
        points_to_spend -= amount
        movements[curr_txn.payer] -= amount
        curr_points[curr_txn.payer] -= amount
        total_points[curr_txn.payer] -= amount
        if points_to_spend == 0:
            break
    if points_to_spend != 0:
        raise HTTPException(status_code=400, detail=[{"msg": "not enough points to spend"}])
    response = []
    for payer, points in movements.items():
        if points == 0:
            continue
        response.append({"payer": payer, "points": points})
        TRANSACTIONS.append(Transaction(**{
            "payer": payer,
            "points": points
        }))
    return response


@app.get("/balance/")
async def balance() -> dict:
    """ Points balance endpoint """
    response = defaultdict(int)
    for transaction in TRANSACTIONS:
        response[transaction.payer] += transaction.points
    return response
