import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "data" / "members.db"


def get_connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    return connection


def get_member(member_id):
    connection = get_connection()

    try:
        member = connection.execute(
            """
            SELECT
                member_id,
                name,
                email,
                phone,
                date_of_birth,
                status
            FROM members
            WHERE member_id = ?
            """,
            (member_id,),
        ).fetchone()

        if member is None:
            return None

        accounts = connection.execute(
            """
            SELECT
                account_id,
                account_type,
                balance,
                status
            FROM accounts
            WHERE member_id = ?
            ORDER BY account_id
            """,
            (member_id,),
        ).fetchall()

        transactions = connection.execute(
            """
            SELECT
                t.transaction_id,
                t.account_id,
                t.transaction_date,
                t.merchant,
                t.amount,
                t.transaction_type
            FROM transactions t
            JOIN accounts a
                ON t.account_id = a.account_id
            WHERE a.member_id = ?
            ORDER BY t.transaction_date DESC,
                     t.transaction_id DESC
            """,
            (member_id,),
        ).fetchall()

        claims = connection.execute(
            """
            SELECT
                claim_id,
                claim_date,
                amount,
                status
            FROM claims
            WHERE member_id = ?
            ORDER BY claim_date DESC,
                     claim_id DESC
            """,
            (member_id,),
        ).fetchall()

        result = dict(member)

        result["accounts"] = [
            dict(account)
            for account in accounts
        ]

        result["transactions"] = [
            dict(transaction)
            for transaction in transactions
        ]

        result["claims"] = [
            dict(claim)
            for claim in claims
        ]

        return result

    finally:
        connection.close()