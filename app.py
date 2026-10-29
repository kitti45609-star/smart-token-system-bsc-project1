
from flask import (
    Flask, render_template, request, redirect,
    session, flash, url_for
)
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "smart_token_secret_key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "smart_token.db")


# =============== DATABASE ===============

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_tables():
    conn = get_db()

    try:
        conn.executescript("""
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
                for row in conn.execute(
                    f"PRAGMA table_info({table})"
                ).fetchall()
            }

            for column, definition in columns.items():
                if column not in existing:
                    conn.execute(
                        f"ALTER TABLE {table} ADD COLUMN "
                        f"{column} {definition}"
                    )

        conn.commit()

    except sqlite3.Error:
        conn.rollback()
        raise

    finally:
        conn.close()


# =============== LOGIN ===============

@app.route("/")
def login():
    if session.get("username"):
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def check_login():
    username = request.form.get(
        "username", ""
    ).strip().lower()

    password = request.form.get("password", "")

    accounts = {
        "admin@gmail.com": "admin123",
        "jasmine@gmail.com": "1234",
        "nurix@gmail.com": "1234",
        "rose@gmail.com": "1234"
    }

    if accounts.get(username) == password:
        session.clear()
        session["username"] = username
        return redirect(url_for("dashboard"))

    return render_template(
        "login.html",
        error="Invalid Gmail ID or password. Please try again."
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.before_request
def require_login():
    allowed_endpoints = {"login", "check_login", "static"}

    if (
        request.endpoint not in allowed_endpoints
        and not session.get("username")
    ):
        return redirect(url_for("login"))


# =============== MODULE 1: DASHBOARD ===============

@app.route("/dashboard")
@app.route("/tokens")
def dashboard():
    conn = get_db()

    try:
        stats = {
            "patients": conn.execute(
                "SELECT COUNT(*) FROM patients WHERE is_active = 1"
            ).fetchone()[0],

            "doctors": conn.execute(
                "SELECT COUNT(*) FROM doctors"
            ).fetchone()[0],

            "appointments": conn.execute(
                "SELECT COUNT(*) FROM appointments"
            ).fetchone()[0],

            "waiting": conn.execute(
                "SELECT COUNT(*) FROM tokens WHERE status = 'Waiting'"
            ).fetchone()[0]
        }
    finally:
        conn.close()

    return render_template("dashboard.html", stats=stats)


# =============== MODULE 2: APPOINTMENTS ===============

@app.route("/appointments", methods=["GET", "POST"])
def appointments():
    conn = get_db()

    if request.method == "POST":
        patient_id = request.form.get("patient_id", "").strip()
        doctor_id = request.form.get("doctor_id", "").strip()
        date = request.form.get("appointment_date", "").strip()
        time = request.form.get("appointment_time", "").strip()
        reason = request.form.get("reason", "").strip()

        try:
            patient = conn.execute(
                "SELECT id FROM patients WHERE id = ? AND is_active = 1",
                (patient_id,)
            ).fetchone() if patient_id else None

            doctor = conn.execute(
                "SELECT id FROM doctors WHERE id = ?",
                (doctor_id,)
            ).fetchone() if doctor_id else None

            if not patient or not doctor or not date:
                flash(
                    "Please select an active patient, valid doctor and date.",
                    "error"
                )
            else:
                conn.execute("""
                    INSERT INTO appointments
                    (patient_id, doctor_id, appointment_date,
                     appointment_time, reason, status)
                    VALUES (?, ?, ?, ?, ?, 'Scheduled')
                """, (patient_id, doctor_id, date, time, reason))

                conn.commit()
                flash("Appointment added successfully.", "success")

        except sqlite3.Error as error:
            conn.rollback()
            print("Appointment error:", repr(error))
            flash("Could not save appointment.", "error")

        finally:
            conn.close()

        return redirect(url_for("appointments"))

    try:
        appointment_list = conn.execute("""
            SELECT a.*, p.name AS patient_name, d.name AS doctor_name
            FROM appointments a
            LEFT JOIN patients p ON a.patient_id = p.id
            LEFT JOIN doctors d ON a.doctor_id = d.id
            ORDER BY a.id DESC
        """).fetchall()

        patients_list = conn.execute("""
            SELECT * FROM patients
            WHERE is_active = 1
            ORDER BY name
        """).fetchall()

        doctors_list = conn.execute(
            "SELECT * FROM doctors ORDER BY name"
        ).fetchall()

    finally:
        conn.close()

    return render_template(
        "appointments.html",
        appointments=appointment_list,
        patients=patients_list,
        doctors=doctors_list
    )


@app.route("/appointments/status/<int:appointment_id>", methods=["POST"])
def update_appointment(appointment_id):
    status = request.form.get("status", "")

    if status not in ["Scheduled", "Completed", "Cancelled"]:
        flash("Invalid appointment status.", "error")
        return redirect(url_for("appointments"))

    conn = get_db()

    try:
        conn.execute(
            "UPDATE appointments SET status = ? WHERE id = ?",
            (status, appointment_id)
        )
        conn.commit()
        flash("Appointment status updated.", "success")
    finally:
        conn.close()

    return redirect(url_for("appointments"))


# =============== MODULE 3: DOCTORS ===============

@app.route("/doctors", methods=["GET", "POST"])
def doctors():
    conn = get_db()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        specialization = request.form.get(
            "specialization", ""
        ).strip()
        phone = request.form.get("phone", "").strip()

        if not name:
            conn.close()
            flash("Doctor name is required.", "error")
            return redirect(url_for("doctors"))

        try:
            conn.execute("""
                INSERT INTO doctors (name, specialization, phone)
                VALUES (?, ?, ?)
            """, (name, specialization, phone))
            conn.commit()
            flash("Doctor added successfully.", "success")

        except sqlite3.Error as error:
            conn.rollback()
            print("Doctor error:", repr(error))
            flash("Could not save doctor.", "error")

        finally:
            conn.close()

        return redirect(url_for("doctors"))

    try:
        doctor_list = conn.execute(
            "SELECT * FROM doctors ORDER BY id DESC"
        ).fetchall()
    finally:
        conn.close()

    return render_template("doctors.html", doctors=doctor_list)


@app.route("/doctors/delete/<int:doctor_id>", methods=["POST"])
def delete_doctor(doctor_id):
    conn = get_db()

    try:
        linked = conn.execute("""
            SELECT
                (SELECT COUNT(*) FROM appointments WHERE doctor_id = ?)
                +
                (SELECT COUNT(*) FROM tokens WHERE doctor_id = ?)
        """, (doctor_id, doctor_id)).fetchone()[0]

        if linked:
            flash(
                "Cannot delete a doctor linked to appointments or tokens.",
                "error"
            )
        else:
            conn.execute("DELETE FROM doctors WHERE id = ?", (doctor_id,))
            conn.commit()
            flash("Doctor deleted.", "success")
    finally:
        conn.close()

    return redirect(url_for("doctors"))


# =============== MODULE 4: PATIENTS ===============

@app.route("/patients", methods=["GET", "POST"])
def patients():
    conn = get_db()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        age_text = request.form.get("age", "").strip()
        gender = request.form.get("gender", "").strip()
        phone = request.form.get("phone", "").strip()

        try:
            age = int(age_text) if age_text else None
            if age is not None and not 0 <= age <= 130:
                raise ValueError
        except ValueError:
            conn.close()
            flash("Please enter a valid age.", "error")
            return redirect(url_for("patients"))

        if not name:
            conn.close()
            flash("Patient name is required.", "error")
            return redirect(url_for("patients"))

        try:
            conn.execute("""
                INSERT INTO patients
                (name, age, gender, phone, is_active)
                VALUES (?, ?, ?, ?, 1)
            """, (name, age, gender, phone))

            conn.commit()
            flash("Patient added successfully.", "success")

        except sqlite3.Error as error:
            conn.rollback()
            print("Patient error:", repr(error))
            flash("Could not save patient.", "error")

        finally:
            conn.close()

        return redirect(url_for("patients"))

    try:
        patient_list = conn.execute("""
            SELECT * FROM patients
            ORDER BY is_active DESC, id DESC
        """).fetchall()
    finally:
        conn.close()

    return render_template("patients.html", patients=patient_list)


@app.route("/patients/deactivate/<int:patient_id>", methods=["POST"])
def deactivate_patient(patient_id):
    conn = get_db()

    try:
        cursor = conn.execute("""
            UPDATE patients
            SET is_active = 0
            WHERE id = ? AND is_active = 1
        """, (patient_id,))
        conn.commit()

        if cursor.rowcount:
            flash(
                "Patient deactivated. Appointment and token history preserved.",
                "success"
            )
        else:
            flash("Patient not found or already inactive.", "error")

    except sqlite3.Error as error:
        conn.rollback()
        print("Patient deactivation error:", repr(error))
        flash("Could not deactivate patient.", "error")

    finally:
        conn.close()

    return redirect(url_for("patients"))


@app.route("/patients/activate/<int:patient_id>", methods=["POST"])
def activate_patient(patient_id):
    conn = get_db()

    try:
        cursor = conn.execute("""
            UPDATE patients
            SET is_active = 1
            WHERE id = ? AND is_active = 0
        """, (patient_id,))
        conn.commit()

        if cursor.rowcount:
            flash("Patient reactivated successfully.", "success")
        else:
            flash("Patient not found or already active.", "error")

    except sqlite3.Error as error:
        conn.rollback()
        print("Patient activation error:", repr(error))
        flash("Could not reactivate patient.", "error")

    finally:
        conn.close()

    return redirect(url_for("patients"))


# Keep old delete URL safe: deactivate instead of deleting.

# Permanently delete a patient only when no linked records exist.
@app.route("/patients/delete/<int:patient_id>", methods=["POST"])
def delete_patient(patient_id):
    conn = get_db()

    try:
        patient = conn.execute(
            "SELECT id FROM patients WHERE id = ?",
            (patient_id,)
        ).fetchone()

        if not patient:
            flash("Patient not found.", "error")
            return redirect(url_for("patients"))

        appointment = conn.execute("""
            SELECT 1 FROM appointments
            WHERE patient_id = ?
            LIMIT 1
        """, (patient_id,)).fetchone()

        token = conn.execute("""
            SELECT 1 FROM tokens
            WHERE patient_id = ?
            LIMIT 1
        """, (patient_id,)).fetchone()

        if appointment or token:
            flash(
                "Cannot permanently delete this patient because "
                "appointments or tokens are linked to them. "
                "Deactivate the patient to preserve their history.",
                "error"
            )
            return redirect(url_for("patients"))

        conn.execute(
            "DELETE FROM patients WHERE id = ?",
            (patient_id,)
        )
        conn.commit()

        flash("Patient permanently deleted.", "success")

    except sqlite3.Error as error:
        conn.rollback()
        print("Patient deletion error:", repr(error))
        flash("Could not delete patient. Existing records were preserved.", "error")

    finally:
        conn.close()

    return redirect(url_for("patients"))



# =============== MODULE 5: TOKEN QUEUE ===============

@app.route("/queue")
def queue():
    conn = get_db()

    try:
        queue_list = conn.execute("""
            SELECT t.*, p.name AS patient_name, d.name AS doctor_name
            FROM tokens t
            LEFT JOIN patients p ON t.patient_id = p.id
            LEFT JOIN doctors d ON t.doctor_id = d.id
            WHERE t.status = 'Waiting'
            ORDER BY t.token_number
        """).fetchall()
    finally:
        conn.close()

    return render_template("queue.html", queue=queue_list)


# =============== MODULE 6: REPORTS ===============

@app.route("/reports")
def reports():
    conn = get_db()

    try:
        total_patients = conn.execute(
            "SELECT COUNT(*) FROM patients WHERE is_active = 1"
        ).fetchone()[0]

        total_doctors = conn.execute(
            "SELECT COUNT(*) FROM doctors"
        ).fetchone()[0]

        total_appointments = conn.execute(
            "SELECT COUNT(*) FROM appointments"
        ).fetchone()[0]

        total_tokens = conn.execute(
            "SELECT COUNT(*) FROM tokens"
        ).fetchone()[0]

        waiting_tokens = conn.execute(
            "SELECT COUNT(*) FROM tokens WHERE status = 'Waiting'"
        ).fetchone()[0]

        completed_tokens = conn.execute(
            "SELECT COUNT(*) FROM tokens WHERE status = 'Completed'"
        ).fetchone()[0]

    finally:
        conn.close()

    return render_template(
        "reports.html",
        total_patients=total_patients,
        total_doctors=total_doctors,
        total_appointments=total_appointments,
        total_tokens=total_tokens,
        waiting_tokens=waiting_tokens,
        completed_tokens=completed_tokens
    )


# =============== TOKEN GENERATION & MANAGEMENT ===============

@app.route("/token", methods=["GET", "POST"])
def token():
    conn = get_db()

    if request.method == "POST":
        patient_id = request.form.get("patient_id", "").strip()
        doctor_id = request.form.get("doctor_id", "").strip()
        purpose = request.form.get("purpose", "").strip()

        try:
            patient = conn.execute(
                "SELECT id FROM patients WHERE id = ? AND is_active = 1",
                (patient_id,)
            ).fetchone() if patient_id else None

            doctor = conn.execute(
                "SELECT id FROM doctors WHERE id = ?",
                (doctor_id,)
            ).fetchone() if doctor_id else None

            if not patient:
                flash("Please select an active patient.", "error")
            elif not doctor:
                flash("Please select a valid doctor.", "error")
            elif not purpose:
                flash("Please enter the purpose of the visit.", "error")
            else:
                next_number = conn.execute(
                    "SELECT COALESCE(MAX(token_number), 0) + 1 FROM tokens"
                ).fetchone()[0]

                conn.execute("""
                    INSERT INTO tokens
                    (token_number, patient_id, doctor_id, purpose,
                     status, created_at)
                    VALUES (?, ?, ?, ?, 'Waiting', ?)
                """, (
                    next_number,
                    patient_id,
                    doctor_id,
                    purpose,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ))

                conn.commit()
                flash(
                    f"Token T{next_number:03d} generated successfully.",
                    "success"
                )

        except sqlite3.Error as error:
            conn.rollback()
            print("Token error:", repr(error))
            flash("Token generation failed. Check the terminal.", "error")

        finally:
            conn.close()

        return redirect(url_for("token"))

    try:
        patients_list = conn.execute("""
            SELECT * FROM patients
            WHERE is_active = 1
            ORDER BY name
        """).fetchall()

        doctors_list = conn.execute("""
            SELECT id, name, specialization
            FROM doctors
            ORDER BY name
        """).fetchall()

        tokens_list = conn.execute("""
            SELECT t.*, p.name AS patient_name, d.name AS doctor_name
            FROM tokens t
            LEFT JOIN patients p ON t.patient_id = p.id
            LEFT JOIN doctors d ON t.doctor_id = d.id
            ORDER BY t.id DESC
        """).fetchall()

    finally:
        conn.close()

    return render_template(
        "tokens.html",
        patients=patients_list,
        doctors=doctors_list,
        tokens=tokens_list
    )


@app.route("/token/status/<int:token_id>", methods=["POST"])
def update_token_status(token_id):
    status = request.form.get("status", "")

    if status not in ["Waiting", "Called", "Completed", "Cancelled"]:
        flash("Invalid token status.", "error")
        return redirect(url_for("token"))

    conn = get_db()

    try:
        cursor = conn.execute(
            "UPDATE tokens SET status = ? WHERE id = ?",
            (status, token_id)
        )
        conn.commit()
        updated = cursor.rowcount
    finally:
        conn.close()

    if updated:
        flash(f"Token status changed to {status}.", "success")
    else:
        flash("Token not found.", "error")

    return redirect(url_for("token"))


@app.route("/token/delete/<int:token_id>", methods=["POST"])
def delete_token(token_id):
    conn = get_db()

    try:
        cursor = conn.execute(
            "DELETE FROM tokens WHERE id = ?", (token_id,)
        )
        conn.commit()
        deleted = cursor.rowcount
    finally:
        conn.close()

    if deleted:
        flash("Token deleted successfully.", "success")
    else:
        flash("Token not found.", "error")

    return redirect(url_for("token"))


# =============== START APPLICATION ===============

create_tables()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)