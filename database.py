
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "smart_token.db")


def get_db_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_tables():
    connection = get_db_connection()

    try:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                age INTEGER,
                gender TEXT,
                phone TEXT,
                is_active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS doctors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                specialization TEXT,
                phone TEXT,
                availability TEXT DEFAULT 'Available'
            );

            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER,
                doctor_id INTEGER,
                appointment_date TEXT,
                appointment_time TEXT DEFAULT '',
                reason TEXT DEFAULT '',
                status TEXT DEFAULT 'Scheduled',
                FOREIGN KEY(patient_id) REFERENCES patients(id),
                FOREIGN KEY(doctor_id) REFERENCES doctors(id)
            );

            CREATE TABLE IF NOT EXISTS tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_number INTEGER NOT NULL UNIQUE,
                patient_id INTEGER,
                doctor_id INTEGER,
                purpose TEXT DEFAULT '',
                status TEXT DEFAULT 'Waiting',
                created_at TEXT DEFAULT '',
                FOREIGN KEY(patient_id) REFERENCES patients(id),
                FOREIGN KEY(doctor_id) REFERENCES doctors(id)
            );
        """)

        # Add missing columns without deleting existing records.
        migrations = {
            "patients": {
                "age": "INTEGER",
                "gender": "TEXT",
                "phone": "TEXT",
                "is_active": "INTEGER NOT NULL DEFAULT 1"
            },
            "doctors": {
                "specialization": "TEXT",
                "phone": "TEXT",
                "availability": "TEXT DEFAULT 'Available'"
            },
            "appointments": {
                "appointment_time": "TEXT DEFAULT ''",
                "reason": "TEXT DEFAULT ''",
                "status": "TEXT DEFAULT 'Scheduled'"
            },
            "tokens": {
                "token_number": "INTEGER",
                "patient_id": "INTEGER",
                "doctor_id": "INTEGER",
                "purpose": "TEXT DEFAULT ''",
                "status": "TEXT DEFAULT 'Waiting'",
                "created_at": "TEXT DEFAULT ''"
            }
        }

        for table, columns in migrations.items():
            existing = {
                row["name"]
                for row in connection.execute(
                    f"PRAGMA table_info({table})"
                ).fetchall()
            }

            for column, definition in columns.items():
                if column not in existing:
                    connection.execute(
                        f"ALTER TABLE {table} ADD COLUMN "
                        f"{column} {definition}"
                    )

        connection.commit()

    except sqlite3.Error:
        connection.rollback()
        raise

    finally:
        connection.close()
