from flask import Flask, render_template, request, redirect, session
import joblib
import sqlite3

app = Flask(__name__)
app.secret_key = "smart-campus-secret-key"

# ---------------- DATABASE ----------------

def init_db():
    conn = sqlite3.connect("complaints.db")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            block TEXT,
            floor TEXT,
            complaint TEXT,
            category TEXT,
            severity TEXT,
            department TEXT,
            status TEXT,
            resolution TEXT
        )
    """)
    conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                email TEXT UNIQUE,
                password TEXT,
                role TEXT
            )
    """)
        

    conn.commit()
    conn.close()


# ---------------- LOAD ML MODEL ----------------

model = joblib.load("models/complaint_classifier.pkl")
vectorizer = joblib.load("models/vectorizer.pkl")


# ---------------- DEPARTMENT ----------------

def get_department(category):

    departments = {
        "Network": "IT Department",
        "Electrical": "Electrical Maintenance",
        "Plumbing": "Plumbing Maintenance",
        "Cleaning": "Housekeeping",
        "Infrastructure": "Infrastructure Maintenance",
        "Security": "Security Department"
    }

    return departments.get(category, "Campus Maintenance")


# ---------------- SEVERITY ----------------

def get_severity(complaint):

    complaint = complaint.lower()

    high_words = [
        "fire",
        "danger",
        "electric shock",
        "water flooding",
        "security",
        "emergency"
    ]

    for word in high_words:
        if word in complaint:
            return "High"

    return "Medium"


# ---------------- RESOLUTION ----------------

def get_resolution(category):

    resolutions = {
        "Network": "Check network connectivity, router and WiFi access point.",
        "Electrical": "Inspect the electrical connection and faulty equipment.",
        "Plumbing": "Inspect the water pipeline and repair the leakage.",
        "Cleaning": "Assign the housekeeping team to clean and resolve the issue.",
        "Infrastructure": "Inspect the damaged infrastructure and arrange maintenance.",
        "Security": "Notify the security team and inspect the reported location."
    }

    return resolutions.get(
        category,
        "Forward the complaint to the appropriate maintenance team."
    )


# ---------------- HOME PAGE ----------------

@app.route("/")
def home():
    return render_template("login.html")
@app.route("/login", methods=["POST"])
def login():

    email = request.form["email"]
    password = request.form["password"]

    conn = sqlite3.connect("complaints.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM users
        WHERE email = ? AND password = ?
    """, (email, password))

    user = cursor.fetchone()

    conn.close()

    if user:

        session["user_id"] = user[0]
        session["user_name"] = user[1]
        session["user_role"] = user[4]

    if user[4] == "admin":
        return redirect("/admin")

    return redirect("/dashboard")

    return render_template(
        "login.html",
        error="Invalid email or password."
    )
# ---------------- ADMIN LOGIN ----------------

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("complaints.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT *
            FROM users
            WHERE email = ? AND password = ? AND role = 'admin'
        """, (email, password))

        admin_user = cursor.fetchone()

        conn.close()

        if admin_user:

            session["user_id"] = admin_user[0]
            session["user_name"] = admin_user[1]
            session["user_role"] = "admin"

            return redirect("/admin")

        return render_template(
            "admin_login.html",
            error="Invalid admin email or password."
        )

    return render_template("admin_login.html")
# ---------------- STUDENT DASHBOARD ----------------

@app.route("/dashboard")
def dashboard():

    return render_template(
        "dashboard.html",
        user=None
    )
# ---------------- SUBMIT COMPLAINT ----------------

@app.route("/submit")
def submit():
    return render_template("index.html")
# ---------------- MY COMPLAINTS ----------------

@app.route("/my_complaints")
def my_complaints():

    user_id = session.get("user_id")

    if not user_id:
        return redirect("/")

    conn = sqlite3.connect("complaints.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM complaints
        WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))
        ORDER BY id DESC
    """, (session["user_name"],))

    complaints = cursor.fetchall()

    conn.close()

    return render_template(
        "my_complaints.html",
        complaints=complaints
    )
# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")
# ---------------- REGISTER ----------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("complaints.db")
        cursor = conn.cursor()

        try:

            cursor.execute("""
                INSERT INTO users
                (name, email, password, role)
                VALUES (?, ?, ?, ?)
            """, (
                name,
                email,
                password,
                "student"
            ))

            conn.commit()
            conn.close()

            return redirect("/")

        except sqlite3.IntegrityError:

            conn.close()

            return render_template(
                "register.html",
                error="Email already registered."
            )

    return render_template("register.html")


# ---------------- ADMIN DASHBOARD ----------------

@app.route("/admin")
def admin():

    conn = sqlite3.connect("complaints.db")

    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM complaints
        ORDER BY id DESC
    """)

    complaints = cursor.fetchall()

    conn.close()

    return render_template(
        "admin.html",
        complaints=complaints
    )


# ---------------- PREDICT & SUBMIT COMPLAINT ----------------

@app.route("/predict", methods=["POST"])
def predict():

    complaint = request.form["complaint"]
    name = request.form["name"]
    block = request.form["block"]
    floor = request.form["floor"]

    # Convert complaint into TF-IDF
    complaint_vector = vectorizer.transform([complaint])

    # ML prediction
    prediction = model.predict(complaint_vector)

    category = prediction[0]

    # Additional information
    department = get_department(category)
    severity = get_severity(complaint)
    resolution = get_resolution(category)

    # Store complaint in database
    conn = sqlite3.connect("complaints.db")

    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO complaints
        (name, block, floor, complaint, category, severity,
         department, status, resolution)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        name,
        block,
        floor,
        complaint,
        category,
        severity,
        department,
        "Pending",
        resolution
    ))

    complaint_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return render_template(
        "result.html",
        complaint_id=complaint_id,
        complaint=complaint,
        category=category,
        department=department,
        severity=severity,
        resolution=resolution
    )


# ---------------- UPDATE COMPLAINT STATUS ----------------

@app.route("/update_status", methods=["POST"])
def update_status():

    complaint_id = request.form["complaint_id"]
    status = request.form["status"]

    conn = sqlite3.connect("complaints.db")

    cursor = conn.cursor()

    cursor.execute("""
        UPDATE complaints
        SET status = ?
        WHERE id = ?
    """, (status, complaint_id))

    conn.commit()
    conn.close()

    return redirect("/admin")


# ---------------- TRACK COMPLAINT ----------------

@app.route("/track", methods=["GET", "POST"])
def track():

    if request.method == "POST":

        name = request.form["name"].strip()
        complaint_id = request.form["complaint_id"].strip().upper()

        # Convert CMP00001 → 1
        try:
            db_id = int(complaint_id.replace("CMP", ""))
        except ValueError:

            return render_template(
                "track.html",
                error="Invalid Complaint ID."
            )

        conn = sqlite3.connect("complaints.db")

        cursor = conn.cursor()

        cursor.execute("""
            SELECT *
            FROM complaints
            WHERE id = ? AND LOWER(name) = LOWER(?)
        """, (db_id, name))

        complaint = cursor.fetchone()

        conn.close()

        if complaint:

            return render_template(
                "track.html",
                complaint=complaint
            )

        return render_template(
            "track.html",
            error="Complaint not found. Please check your Name and Complaint ID."
        )

    return render_template("track.html")


# ---------------- RUN APPLICATION ----------------

if __name__ == "__main__":

    init_db()
    conn = sqlite3.connect("complaints.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO users
        (name, email, password, role)
        VALUES (?, ?, ?, ?)
    """, (
        "Campus Admin",
        "admin@smartcampus.com",
        "admin123",
        "admin"
    ))

    conn.commit()
    conn.close()
    app.run(debug=True)