import os
import sqlite3
from datetime import date, datetime
from functools import wraps
from flask import Flask, g, redirect, render_template, request, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "fat_loss_tracker.sqlite3"))

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db():
    connection = sqlite3.connect(DB_PATH)
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS goals (
            user_id INTEGER PRIMARY KEY,
            start_weight REAL,
            target_weight REAL,
            target_date TEXT,
            calories INTEGER DEFAULT 2300,
            protein INTEGER DEFAULT 180,
            steps INTEGER DEFAULT 10000,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS daily_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            log_date TEXT NOT NULL,
            weight REAL,
            calories INTEGER,
            protein INTEGER,
            steps INTEGER,
            cardio_minutes INTEGER,
            notes TEXT,
            UNIQUE(user_id, log_date),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            measure_date TEXT NOT NULL,
            waist REAL,
            chest REAL,
            arm REAL,
            thigh REAL,
            notes TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            workout_date TEXT NOT NULL,
            split_day TEXT NOT NULL,
            exercise TEXT NOT NULL,
            sets TEXT,
            reps TEXT,
            weight TEXT,
            notes TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """
    )
    connection.commit()
    connection.close()


init_db()


def user_count():
    return db().execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    first_user = user_count() == 0
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or not password:
            flash("Enter an email and password.")
            return redirect(url_for("login"))

        if first_user:
            password_hash = generate_password_hash(password)
            cursor = db().execute(
                "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
                (email, password_hash, datetime.utcnow().isoformat()),
            )
            db().execute("INSERT INTO goals (user_id) VALUES (?)", (cursor.lastrowid,))
            db().commit()
            session["user_id"] = cursor.lastrowid
            return redirect(url_for("dashboard"))

        user = db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))
        flash("Wrong login.")
    return render_template("login.html", first_user=first_user)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/", methods=["GET", "POST"])
@login_required
def dashboard():
    uid = session["user_id"]
    today = date.today().isoformat()
    if request.method == "POST":
        data = (
            uid,
            request.form.get("log_date") or today,
            request.form.get("weight") or None,
            request.form.get("calories") or None,
            request.form.get("protein") or None,
            request.form.get("steps") or None,
            request.form.get("cardio_minutes") or None,
            request.form.get("notes") or None,
        )
        db().execute(
            """
            INSERT INTO daily_logs (user_id, log_date, weight, calories, protein, steps, cardio_minutes, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, log_date) DO UPDATE SET
                weight=excluded.weight,
                calories=excluded.calories,
                protein=excluded.protein,
                steps=excluded.steps,
                cardio_minutes=excluded.cardio_minutes,
                notes=excluded.notes
            """,
            data,
        )
        db().commit()
        return redirect(url_for("dashboard"))

    goals = db().execute("SELECT * FROM goals WHERE user_id = ?", (uid,)).fetchone()
    logs = db().execute(
        "SELECT * FROM daily_logs WHERE user_id = ? ORDER BY log_date DESC LIMIT 30", (uid,)
    ).fetchall()
    weights = [row["weight"] for row in logs if row["weight"] is not None]
    latest_weight = weights[0] if weights else None
    start_weight = goals["start_weight"] if goals else None
    target_weight = goals["target_weight"] if goals else None
    lost = round(start_weight - latest_weight, 1) if start_weight and latest_weight else None
    remaining = round(latest_weight - target_weight, 1) if latest_weight and target_weight else None
    return render_template(
        "dashboard.html",
        today=today,
        goals=goals,
        logs=logs,
        latest_weight=latest_weight,
        lost=lost,
        remaining=remaining,
    )


@app.route("/workouts", methods=["GET", "POST"])
@login_required
def workouts():
    uid = session["user_id"]
    today = date.today().isoformat()
    split_days = ["Push", "Pull", "Legs", "Shoulders and Arms", "Chest and Back", "Rest"]
    if request.method == "POST":
        db().execute(
            """
            INSERT INTO workouts (user_id, workout_date, split_day, exercise, sets, reps, weight, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uid,
                request.form.get("workout_date") or today,
                request.form.get("split_day"),
                request.form.get("exercise"),
                request.form.get("sets"),
                request.form.get("reps"),
                request.form.get("weight"),
                request.form.get("notes"),
            ),
        )
        db().commit()
        return redirect(url_for("workouts"))
    items = db().execute(
        "SELECT * FROM workouts WHERE user_id = ? ORDER BY workout_date DESC, id DESC LIMIT 80", (uid,)
    ).fetchall()
    return render_template("workouts.html", today=today, split_days=split_days, items=items)


@app.route("/measurements", methods=["POST"])
@login_required
def add_measurement():
    uid = session["user_id"]
    db().execute(
        """
        INSERT INTO measurements (user_id, measure_date, waist, chest, arm, thigh, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uid,
            request.form.get("measure_date") or date.today().isoformat(),
            request.form.get("waist") or None,
            request.form.get("chest") or None,
            request.form.get("arm") or None,
            request.form.get("thigh") or None,
            request.form.get("notes") or None,
        ),
    )
    db().commit()
    return redirect(url_for("settings"))


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    uid = session["user_id"]
    if request.method == "POST":
        db().execute(
            """
            UPDATE goals SET start_weight=?, target_weight=?, target_date=?, calories=?, protein=?, steps=?
            WHERE user_id=?
            """,
            (
                request.form.get("start_weight") or None,
                request.form.get("target_weight") or None,
                request.form.get("target_date") or None,
                request.form.get("calories") or 2300,
                request.form.get("protein") or 180,
                request.form.get("steps") or 10000,
                uid,
            ),
        )
        db().commit()
        return redirect(url_for("settings"))
    goals = db().execute("SELECT * FROM goals WHERE user_id = ?", (uid,)).fetchone()
    measurements = db().execute(
        "SELECT * FROM measurements WHERE user_id = ? ORDER BY measure_date DESC LIMIT 20", (uid,)
    ).fetchall()
    return render_template("settings.html", goals=goals, measurements=measurements, today=date.today().isoformat())


@app.route("/plan")
@login_required
def plan():
    return render_template("plan.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
