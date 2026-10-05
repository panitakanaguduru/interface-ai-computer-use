import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "data" / "members.db"

random.seed(42)


FIRST_NAMES = [
    "Alex", "Sarah", "Michael", "Priya", "Daniel",
    "Emily", "James", "Sophia", "David", "Olivia",
    "Ethan", "Maya", "Noah", "Ava", "Liam",
    "Isabella", "Lucas", "Amelia", "Ryan", "Nina",
]

LAST_NAMES = [
    "Johnson", "Miller", "Chen", "Patel", "Williams",
    "Garcia", "Brown", "Davis", "Wilson", "Martinez",
    "Anderson", "Taylor", "Thomas", "Moore", "Jackson",
    "Martin", "Lee", "Thompson", "White", "Harris",
]

MERCHANTS = [
    "Fresh Market",
    "Metro Pharmacy",
    "City Utilities",
    "Bluebird Cafe",
    "Tech World",
    "Green Grocery",
    "Sunrise Medical",
    "Central Gas",
    "Home Supply",
    "Online Marketplace",
]

ACCOUNT_TYPES = [
    "Checking",
    "Savings",
]

MEMBER_STATUSES = [
    "Active",
    "Active",
    "Active",
    "Active",
    "Inactive",
]

CLAIM_STATUSES = [
    "Approved",
    "Pending",
    "Processing",
    "Denied",
]


def random_date(start_date, end_date):
    days = (end_date - start_date).days
    return start_date + timedelta(
        days=random.randint(0, days)
    )


def create_database():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    connection = sqlite3.connect(DATABASE_PATH)
    cursor = connection.cursor()

    cursor.executescript(
        """
        CREATE TABLE members (
            member_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            date_of_birth TEXT NOT NULL,
            status TEXT NOT NULL
        );

        CREATE TABLE accounts (
            account_id TEXT PRIMARY KEY,
            member_id TEXT NOT NULL,
            account_type TEXT NOT NULL,
            balance REAL NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (member_id)
                REFERENCES members(member_id)
        );

        CREATE TABLE transactions (
            transaction_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            transaction_date TEXT NOT NULL,
            merchant TEXT NOT NULL,
            amount REAL NOT NULL,
            transaction_type TEXT NOT NULL,
            FOREIGN KEY (account_id)
                REFERENCES accounts(account_id)
        );

        CREATE TABLE claims (
            claim_id TEXT PRIMARY KEY,
            member_id TEXT NOT NULL,
            claim_date TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (member_id)
                REFERENCES members(member_id)
        );
        """
    )

    transaction_counter = 1
    claim_counter = 1

    today = date.today()

    for index in range(1, 101):

        member_id = str(10000 + index)

        first_name = FIRST_NAMES[
            (index - 1) % len(FIRST_NAMES)
        ]

        last_name = LAST_NAMES[
            ((index - 1) * 3) % len(LAST_NAMES)
        ]

        name = f"{first_name} {last_name}"

        email = (
            f"{first_name.lower()}."
            f"{last_name.lower()}{index}"
            f"@example.com"
        )

        phone = (
            f"555-"
            f"{100 + (index % 900):03d}-"
            f"{1000 + index:04d}"
        )

        dob = random_date(
            date(1955, 1, 1),
            date(2002, 12, 31),
        )

        member_status = random.choice(
            MEMBER_STATUSES
        )

        cursor.execute(
            """
            INSERT INTO members (
                member_id,
                name,
                email,
                phone,
                date_of_birth,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                member_id,
                name,
                email,
                phone,
                dob.isoformat(),
                member_status,
            ),
        )

        number_of_accounts = random.choice(
            [1, 1, 1, 2]
        )

        for account_number in range(
            1,
            number_of_accounts + 1
        ):

            account_id = (
                f"A{member_id}{account_number}"
            )

            account_type = ACCOUNT_TYPES[
                (index + account_number) % 2
            ]

            balance = round(
                random.uniform(250, 25000),
                2,
            )

            cursor.execute(
                """
                INSERT INTO accounts (
                    account_id,
                    member_id,
                    account_type,
                    balance,
                    status
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    account_id,
                    member_id,
                    account_type,
                    balance,
                    "Open",
                ),
            )

            transaction_count = random.randint(
                5,
                10,
            )

            for _ in range(transaction_count):

                transaction_id = (
                    f"T{transaction_counter:06d}"
                )

                transaction_counter += 1

                transaction_date = (
                    today
                    - timedelta(
                        days=random.randint(1, 180)
                    )
                )

                merchant = random.choice(
                    MERCHANTS
                )

                amount = round(
                    random.uniform(10, 2500),
                    2,
                )

                transaction_type = random.choice(
                    ["Debit", "Debit", "Debit", "Credit"]
                )

                cursor.execute(
                    """
                    INSERT INTO transactions (
                        transaction_id,
                        account_id,
                        transaction_date,
                        merchant,
                        amount,
                        transaction_type
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        transaction_id,
                        account_id,
                        transaction_date.isoformat(),
                        merchant,
                        amount,
                        transaction_type,
                    ),
                )

        claim_count = random.randint(1, 4)

        for _ in range(claim_count):

            claim_id = (
                f"C{claim_counter:05d}"
            )

            claim_counter += 1

            claim_date = (
                today
                - timedelta(
                    days=random.randint(1, 365)
                )
            )

            claim_amount = round(
                random.uniform(100, 8000),
                2,
            )

            claim_status = random.choice(
                CLAIM_STATUSES
            )

            cursor.execute(
                """
                INSERT INTO claims (
                    claim_id,
                    member_id,
                    claim_date,
                    amount,
                    status
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    claim_id,
                    member_id,
                    claim_date.isoformat(),
                    claim_amount,
                    claim_status,
                ),
            )

    connection.commit()

    counts = {}

    for table in [
        "members",
        "accounts",
        "transactions",
        "claims",
    ]:
        counts[table] = cursor.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]

    connection.close()

    print("\nDatabase created successfully!")
    print("Location:", DATABASE_PATH)
    print("Members:", counts["members"])
    print("Accounts:", counts["accounts"])
    print("Transactions:", counts["transactions"])
    print("Claims:", counts["claims"])


if __name__ == "__main__":
    create_database()