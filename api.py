import os
import sqlite3

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")


class PersonInput(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None


@app.post("/check-duplicate")
def check_duplicate(person: PersonInput):
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    email = (
        person.email.strip().lower()
        if person.email
        else None
    )

    phone = (
        "".join(filter(str.isdigit, person.phone))
        if person.phone
        else None
    )

    result = None
    matched_by = None

    if email:
        cursor.execute(
            """
            SELECT *
            FROM people
            WHERE lower(email) = ?
            LIMIT 1
            """,
            (email,),
        )

        result = cursor.fetchone()

        if result:
            matched_by = "email"

    if not result and phone:
        cursor.execute(
            """
            SELECT *
            FROM people
            WHERE phone = ?
            LIMIT 1
            """,
            (phone,),
        )

        result = cursor.fetchone()

        if result:
            matched_by = "phone"

    connection.close()

    if result:
        return {
            "duplicate": True,
            "matched_by": matched_by,
            "person": {
                "id": result["id"],
                "name": result["name"],
                "email": result["email"],
                "phone": result["phone"],
                "city": result["city"],
            },
        }

    return {
        "duplicate": False,
        "matched_by": None,
        "person": None,
    }