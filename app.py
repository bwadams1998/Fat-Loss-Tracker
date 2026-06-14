import os
import sqlite3
from datetime import date, datetime, timedelta
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

        CREATE TABLE IF NOT EXISTS profiles (
            user_id INTEGER PRIMARY KEY,
            height_inches REAL DEFAULT 74,
            age INTEGER DEFAULT 27,
            sex TEXT DEFAULT 'male',
            activity_level TEXT DEFAULT 'moderate',
            training_days INTEGER DEFAULT 5,
            deficit_rate REAL DEFAULT 1.25,
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
            actual_reps TEXT,
            notes TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """
    )
    # Lightweight migration for existing Railway databases.
    columns = [row[1] for row in connection.execute("PRAGMA table_info(workouts)").fetchall()]
    if "actual_reps" not in columns:
        connection.execute("ALTER TABLE workouts ADD COLUMN actual_reps TEXT")
    connection.commit()
    connection.close()


WORKOUT_PLAN = {
    "Push": [
        {"exercise": "Bench Press", "sets": "3 to 4", "reps": "5 to 8"},
        {"exercise": "Incline Dumbbell Press", "sets": "3", "reps": "8 to 10"},
        {"exercise": "Overhead Press", "sets": "3", "reps": "6 to 10"},
        {"exercise": "Lateral Raises", "sets": "4", "reps": "12 to 20"},
        {"exercise": "Triceps Pushdown", "sets": "3", "reps": "10 to 15"},
        {"exercise": "Overhead Triceps Extension", "sets": "2 to 3", "reps": "10 to 15"},
    ],
    "Pull": [
        {"exercise": "Lat Pulldown or Pull Ups", "sets": "4", "reps": "6 to 12"},
        {"exercise": "Barbell Row or Chest Supported Row", "sets": "3 to 4", "reps": "6 to 10"},
        {"exercise": "Seated Cable Row", "sets": "3", "reps": "8 to 12"},
        {"exercise": "Rear Delt Fly", "sets": "3", "reps": "12 to 20"},
        {"exercise": "Barbell Curls", "sets": "3", "reps": "8 to 12"},
        {"exercise": "Hammer Curls", "sets": "2 to 3", "reps": "10 to 15"},
    ],
    "Legs": [
        {"exercise": "Smith Squat", "sets": "4", "reps": "5 to 8"},
        {"exercise": "Romanian Deadlift", "sets": "3 to 4", "reps": "6 to 10"},
        {"exercise": "Leg Curl", "sets": "3", "reps": "10 to 15"},
        {"exercise": "Leg Extension", "sets": "3", "reps": "10 to 15"},
        {"exercise": "Calf Raises", "sets": "4", "reps": "10 to 20"},
        {"exercise": "Core Work", "sets": "10 to 15 min", "reps": "Planks, cable crunch, or leg raises"},
    ],
    "Shoulders and Arms": [
        {"exercise": "Overhead Press", "sets": "3", "reps": "6 to 10"},
        {"exercise": "Lateral Raises", "sets": "4 to 5", "reps": "12 to 20"},
        {"exercise": "Rear Delt Fly", "sets": "3", "reps": "12 to 20"},
        {"exercise": "Barbell Curls", "sets": "3", "reps": "8 to 12"},
        {"exercise": "Incline Curls", "sets": "2 to 3", "reps": "10 to 15"},
        {"exercise": "Skull Crushers", "sets": "3", "reps": "8 to 12"},
        {"exercise": "Cable Pushdowns", "sets": "2 to 3", "reps": "10 to 15"},
    ],
    "Chest and Back": [
        {"exercise": "Incline Bench Press", "sets": "3 to 4", "reps": "5 to 8"},
        {"exercise": "Flat Dumbbell Press", "sets": "3", "reps": "8 to 10"},
        {"exercise": "Cable Fly", "sets": "2 to 3", "reps": "12 to 15"},
        {"exercise": "Pulldowns", "sets": "3", "reps": "8 to 12"},
        {"exercise": "Rows", "sets": "3", "reps": "8 to 12"},
        {"exercise": "Straight Arm Pulldown", "sets": "2", "reps": "12 to 15"},
    ],
    "Rest": [
        {"exercise": "Steps", "sets": "1", "reps": "8,000 to 12,000 steps"},
        {"exercise": "Optional Incline Walk", "sets": "1", "reps": "20 to 40 minutes"},
    ],
}


init_db()


def safe_float(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None



def get_profile(uid):
    profile = db().execute("SELECT * FROM profiles WHERE user_id = ?", (uid,)).fetchone()
    if not profile:
        db().execute("INSERT INTO profiles (user_id) VALUES (?)", (uid,))
        db().commit()
        profile = db().execute("SELECT * FROM profiles WHERE user_id = ?", (uid,)).fetchone()
    return profile


def activity_multiplier(activity_level):
    return {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "high": 1.725,
        "athlete": 1.9,
    }.get(activity_level or "moderate", 1.55)


def calculate_bmr(weight_lb, height_inches, age, sex):
    if not weight_lb or not height_inches or not age:
        return None
    weight_kg = weight_lb * 0.45359237
    height_cm = height_inches * 2.54
    sex_offset = 5 if (sex or "male") == "male" else -161
    return round((10 * weight_kg) + (6.25 * height_cm) - (5 * int(age)) + sex_offset)


def adaptive_macro_targets(goals, logs, profile=None):
    weights_by_date = []
    for row in logs:
        weight = safe_float(row["weight"])
        if weight is not None:
            weights_by_date.append((row["log_date"], weight))

    weights_by_date = sorted(weights_by_date, key=lambda x: x[0], reverse=True)
    latest_weight = weights_by_date[0][1] if weights_by_date else None

    target_weight = safe_float(goals["target_weight"]) if goals else None
    start_weight = safe_float(goals["start_weight"]) if goals else None
    base_weight = latest_weight or start_weight or target_weight or 235

    recent_weights = [w for _, w in weights_by_date[:7]]
    previous_weights = [w for _, w in weights_by_date[7:14]]
    recent_avg = round(sum(recent_weights) / len(recent_weights), 1) if recent_weights else None
    previous_avg = round(sum(previous_weights) / len(previous_weights), 1) if previous_weights else None
    weekly_change = round(previous_avg - recent_avg, 1) if recent_avg is not None and previous_avg is not None else None

    height_inches = safe_float(profile["height_inches"]) if profile else 74
    age = int(profile["age"] or 27) if profile else 27
    sex = profile["sex"] if profile else "male"
    activity_level = profile["activity_level"] if profile else "moderate"
    training_days = int(profile["training_days"] or 5) if profile else 5
    deficit_rate = safe_float(profile["deficit_rate"]) if profile else 1.25

    bmr = calculate_bmr(base_weight, height_inches, age, sex)
    tdee = round(bmr * activity_multiplier(activity_level)) if bmr else None
    weekly_deficit = (deficit_rate or 1.25) * 3500
    daily_deficit = round(weekly_deficit / 7)
    calculated_calories = max(1800, round((tdee or int(goals["calories"] or 2300)) - daily_deficit))

    adjustment = 0
    status = "Profile based targets. Log 7 to 14 weigh ins for adaptive changes."
    if weekly_change is not None:
        if weekly_change < 0.5:
            adjustment = -150
            status = "Loss is slow. Drop calories by 150 or add steps."
        elif weekly_change > 2.0:
            adjustment = 100
            status = "Loss is fast. Add 100 calories to protect performance."
        else:
            adjustment = 0
            status = "Pace is on target. Keep calories the same."

    recommended_calories = max(1800, calculated_calories + adjustment)

    protein = int(round(max(170, min(230, base_weight * 0.9))))
    fat = int(round(max(55, min(90, recommended_calories * 0.25 / 9))))
    carb_calories = recommended_calories - (protein * 4) - (fat * 9)
    carbs = int(round(max(75, carb_calories / 4)))

    remaining_lb = None
    weeks_to_goal = None
    estimated_goal_date = None
    if latest_weight and target_weight and latest_weight > target_weight:
        remaining_lb = round(latest_weight - target_weight, 1)
        pace = weekly_change if weekly_change and weekly_change > 0.25 else deficit_rate
        if pace and pace > 0:
            weeks_to_goal = round(remaining_lb / pace, 1)
            estimated_goal_date = (date.today() + timedelta(days=int(weeks_to_goal * 7))).isoformat()

    return {
        "calories": recommended_calories,
        "protein": protein,
        "carbs": carbs,
        "fat": fat,
        "bmr": bmr,
        "tdee": tdee,
        "daily_deficit": daily_deficit,
        "calculated_calories": calculated_calories,
        "adjustment": adjustment,
        "recent_avg": recent_avg,
        "previous_avg": previous_avg,
        "weekly_change": weekly_change,
        "status": status,
        "estimated_goal_date": estimated_goal_date,
        "weeks_to_goal": weeks_to_goal,
        "remaining_lb": remaining_lb,
        "activity_level": activity_level,
        "training_days": training_days,
        "deficit_rate": deficit_rate,
    }

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
            db().execute("INSERT INTO profiles (user_id) VALUES (?)", (cursor.lastrowid,))
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
    profile = get_profile(uid)
    macro_targets = adaptive_macro_targets(goals, logs, profile)
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
        macro_targets=macro_targets,
        profile=profile,
    )


@app.route("/workouts", methods=["GET", "POST"])
@login_required
def workouts():
    uid = session["user_id"]
    today = date.today().isoformat()
    split_days = list(WORKOUT_PLAN.keys())

    if request.method == "POST":
        workout_date = request.form.get("workout_date") or today
        split_day = request.form.get("split_day") or "Push"
        exercises = request.form.getlist("exercise")
        sets_list = request.form.getlist("sets")
        reps_list = request.form.getlist("reps")
        weights = request.form.getlist("weight")
        actual_reps_list = request.form.getlist("actual_reps")
        notes_list = request.form.getlist("notes")

        for index, exercise in enumerate(exercises):
            weight = weights[index].strip() if index < len(weights) else ""
            actual_reps = actual_reps_list[index].strip() if index < len(actual_reps_list) else ""
            notes = notes_list[index].strip() if index < len(notes_list) else ""
            if not weight and not actual_reps and not notes:
                continue
            db().execute(
                """
                INSERT INTO workouts (user_id, workout_date, split_day, exercise, sets, reps, weight, actual_reps, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uid,
                    workout_date,
                    split_day,
                    exercise,
                    sets_list[index] if index < len(sets_list) else "",
                    reps_list[index] if index < len(reps_list) else "",
                    weight,
                    actual_reps,
                    notes,
                ),
            )
        db().commit()
        return redirect(url_for("workouts", day=split_day))

    selected_day = request.args.get("day") or "Push"
    if selected_day not in WORKOUT_PLAN:
        selected_day = "Push"

    plan_items = []
    for item in WORKOUT_PLAN[selected_day]:
        last = db().execute(
            """
            SELECT weight, actual_reps, workout_date FROM workouts
            WHERE user_id = ? AND exercise = ? AND weight IS NOT NULL AND weight != ''
            ORDER BY workout_date DESC, id DESC LIMIT 1
            """,
            (uid, item["exercise"]),
        ).fetchone()
        plan_items.append({**item, "last": last})

    items = db().execute(
        "SELECT * FROM workouts WHERE user_id = ? ORDER BY workout_date DESC, id DESC LIMIT 80",
        (uid,),
    ).fetchall()
    return render_template(
        "workouts.html",
        today=today,
        split_days=split_days,
        selected_day=selected_day,
        plan_items=plan_items,
        items=items,
    )


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


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    uid = session["user_id"]
    current = get_profile(uid)
    if request.method == "POST":
        feet = request.form.get("height_feet") or "0"
        inches = request.form.get("height_inches_extra") or "0"
        try:
            total_inches = (int(feet) * 12) + float(inches)
        except ValueError:
            total_inches = 74
        db().execute(
            """
            UPDATE profiles
            SET height_inches=?, age=?, sex=?, activity_level=?, training_days=?, deficit_rate=?
            WHERE user_id=?
            """,
            (
                total_inches,
                request.form.get("age") or 27,
                request.form.get("sex") or "male",
                request.form.get("activity_level") or "moderate",
                request.form.get("training_days") or 5,
                request.form.get("deficit_rate") or 1.25,
                uid,
            ),
        )
        db().commit()
        flash("Profile updated.")
        return redirect(url_for("profile"))

    goals = db().execute("SELECT * FROM goals WHERE user_id = ?", (uid,)).fetchone()
    logs = db().execute("SELECT * FROM daily_logs WHERE user_id = ? ORDER BY log_date DESC LIMIT 30", (uid,)).fetchall()
    macro_targets = adaptive_macro_targets(goals, logs, current)
    height = safe_float(current["height_inches"]) or 74
    return render_template(
        "profile.html",
        profile=current,
        macro_targets=macro_targets,
        height_feet=int(height // 12),
        height_inches_extra=round(height % 12, 1),
    )


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


@app.route("/data")
@login_required
def data_management():
    uid = session["user_id"]
    logs = db().execute(
        "SELECT * FROM daily_logs WHERE user_id = ? ORDER BY log_date DESC LIMIT 90", (uid,)
    ).fetchall()
    measurements = db().execute(
        "SELECT * FROM measurements WHERE user_id = ? ORDER BY measure_date DESC, id DESC LIMIT 90", (uid,)
    ).fetchall()
    workout_entries = db().execute(
        "SELECT * FROM workouts WHERE user_id = ? ORDER BY workout_date DESC, id DESC LIMIT 150", (uid,)
    ).fetchall()
    return render_template(
        "data.html",
        logs=logs,
        measurements=measurements,
        workout_entries=workout_entries,
    )


@app.route("/data/daily/<int:entry_id>/edit", methods=["GET", "POST"])
@login_required
def edit_daily_log(entry_id):
    uid = session["user_id"]
    entry = db().execute(
        "SELECT * FROM daily_logs WHERE id = ? AND user_id = ?", (entry_id, uid)
    ).fetchone()
    if not entry:
        flash("Entry not found.")
        return redirect(url_for("data_management"))
    if request.method == "POST":
        db().execute(
            """
            UPDATE daily_logs
            SET log_date=?, weight=?, calories=?, protein=?, steps=?, cardio_minutes=?, notes=?
            WHERE id=? AND user_id=?
            """,
            (
                request.form.get("log_date") or date.today().isoformat(),
                request.form.get("weight") or None,
                request.form.get("calories") or None,
                request.form.get("protein") or None,
                request.form.get("steps") or None,
                request.form.get("cardio_minutes") or None,
                request.form.get("notes") or None,
                entry_id,
                uid,
            ),
        )
        db().commit()
        flash("Daily log updated.")
        return redirect(url_for("data_management"))
    return render_template("edit_daily.html", entry=entry)


@app.route("/data/daily/<int:entry_id>/delete", methods=["POST"])
@login_required
def delete_daily_log(entry_id):
    uid = session["user_id"]
    db().execute("DELETE FROM daily_logs WHERE id = ? AND user_id = ?", (entry_id, uid))
    db().commit()
    flash("Daily log deleted.")
    return redirect(url_for("data_management"))


@app.route("/data/measurement/<int:entry_id>/edit", methods=["GET", "POST"])
@login_required
def edit_measurement(entry_id):
    uid = session["user_id"]
    entry = db().execute(
        "SELECT * FROM measurements WHERE id = ? AND user_id = ?", (entry_id, uid)
    ).fetchone()
    if not entry:
        flash("Measurement not found.")
        return redirect(url_for("data_management"))
    if request.method == "POST":
        db().execute(
            """
            UPDATE measurements
            SET measure_date=?, waist=?, chest=?, arm=?, thigh=?, notes=?
            WHERE id=? AND user_id=?
            """,
            (
                request.form.get("measure_date") or date.today().isoformat(),
                request.form.get("waist") or None,
                request.form.get("chest") or None,
                request.form.get("arm") or None,
                request.form.get("thigh") or None,
                request.form.get("notes") or None,
                entry_id,
                uid,
            ),
        )
        db().commit()
        flash("Measurement updated.")
        return redirect(url_for("data_management"))
    return render_template("edit_measurement.html", entry=entry)


@app.route("/data/measurement/<int:entry_id>/delete", methods=["POST"])
@login_required
def delete_measurement(entry_id):
    uid = session["user_id"]
    db().execute("DELETE FROM measurements WHERE id = ? AND user_id = ?", (entry_id, uid))
    db().commit()
    flash("Measurement deleted.")
    return redirect(url_for("data_management"))


@app.route("/data/workout/<int:entry_id>/edit", methods=["GET", "POST"])
@login_required
def edit_workout_entry(entry_id):
    uid = session["user_id"]
    entry = db().execute(
        "SELECT * FROM workouts WHERE id = ? AND user_id = ?", (entry_id, uid)
    ).fetchone()
    if not entry:
        flash("Workout entry not found.")
        return redirect(url_for("data_management"))
    if request.method == "POST":
        db().execute(
            """
            UPDATE workouts
            SET workout_date=?, split_day=?, exercise=?, sets=?, reps=?, weight=?, actual_reps=?, notes=?
            WHERE id=? AND user_id=?
            """,
            (
                request.form.get("workout_date") or date.today().isoformat(),
                request.form.get("split_day") or "Push",
                request.form.get("exercise") or "",
                request.form.get("sets") or "",
                request.form.get("reps") or "",
                request.form.get("weight") or "",
                request.form.get("actual_reps") or "",
                request.form.get("notes") or "",
                entry_id,
                uid,
            ),
        )
        db().commit()
        flash("Workout entry updated.")
        return redirect(url_for("data_management"))
    return render_template("edit_workout.html", entry=entry, split_days=list(WORKOUT_PLAN.keys()))


@app.route("/data/workout/<int:entry_id>/delete", methods=["POST"])
@login_required
def delete_workout_entry(entry_id):
    uid = session["user_id"]
    db().execute("DELETE FROM workouts WHERE id = ? AND user_id = ?", (entry_id, uid))
    db().commit()
    flash("Workout entry deleted.")
    return redirect(url_for("data_management"))


@app.route("/plan")
@login_required
def plan():
    return render_template("plan.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
