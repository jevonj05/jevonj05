from flask import Flask, render_template, request, redirect, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
from dotenv import load_dotenv
from google import genai

app = Flask(__name__)
app.secret_key = "student_budget_app_secret_key"

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def budget_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monthly_budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            month TEXT NOT NULL,
            income REAL NOT NULL,
            budget_limit REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    conn.commit()
    conn.close()


def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


def login_required():
    return "user_id" in session


@app.route("/")
def home():
    if login_required():
        return redirect("/dashboard")
    return redirect("/login")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if len(username) < 3:
            return render_template("register.html", error="Username must be at least 3 characters.")

        if len(password) < 4:
            return render_template("register.html", error="Password must be at least 4 characters.")

        hashed_password = generate_password_hash(password)
        conn = get_db_connection()

        try:
            conn.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, hashed_password)
            )
            conn.commit()
            return redirect("/login")
        except sqlite3.IntegrityError:
            return render_template("register.html", error="Username already exists.")
        finally:
            conn.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect("/dashboard")

        return render_template("login.html", error="Invalid username or password.")

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect("/login")

    current_month = datetime.now().strftime("%Y-%m")
    conn = get_db_connection()

    budget = conn.execute("""
        SELECT * FROM monthly_budgets
        WHERE user_id = ? AND month = ?
        ORDER BY id DESC
    """, (session["user_id"], current_month)).fetchone()

    expenses = conn.execute("""
        SELECT * FROM expenses
        WHERE user_id = ? AND date LIKE ?
        ORDER BY date DESC
    """, (session["user_id"], current_month + "%")).fetchall()

    total_spent = conn.execute("""
        SELECT SUM(amount) AS total
        FROM expenses
        WHERE user_id = ? AND date LIKE ?
    """, (session["user_id"], current_month + "%")).fetchone()["total"]

    transaction_count = conn.execute("""
        SELECT COUNT(*) AS total
        FROM expenses
        WHERE user_id = ? AND date LIKE ?
    """, (session["user_id"], current_month + "%")).fetchone()["total"]

    category_count = conn.execute("""
        SELECT COUNT(DISTINCT category) AS total
        FROM expenses
        WHERE user_id = ? AND date LIKE ?
    """, (session["user_id"], current_month + "%")).fetchone()["total"]

    conn.close()

    if total_spent is None:
        total_spent = 0

    income = 0
    budget_limit = 0
    remaining_budget = 0
    remaining_income = 0
    alert = "No monthly budget has been set yet. Set a budget to begin tracking."

    if budget:
        income = float(budget["income"])
        budget_limit = float(budget["budget_limit"])
        remaining_budget = budget_limit - float(total_spent)
        remaining_income = income - float(total_spent)

        if total_spent > budget_limit:
            alert = "You are over your monthly spending budget."
        elif total_spent >= budget_limit * 0.8:
            alert = "Warning: You have used 80% or more of your monthly budget."
        else:
            alert = "You are within your monthly budget."

    return render_template(
        "dashboard.html",
        username=session["username"],
        current_month=current_month,
        income=income,
        budget_limit=budget_limit,
        total_spent=total_spent,
        remaining_budget=remaining_budget,
        remaining_income=remaining_income,
        transaction_count=transaction_count,
        category_count=category_count,
        expenses=expenses,
        alert=alert
    )


@app.route("/set_budget", methods=["GET", "POST"])
def set_budget():
    if not login_required():
        return redirect("/login")

    current_month = datetime.now().strftime("%Y-%m")

    if request.method == "POST":
        month = request.form["month"]
        income = request.form["income"]
        budget_limit = request.form["budget_limit"]

        if float(income) < 0 or float(budget_limit) < 0:
            return render_template(
                "set_budget.html",
                current_month=current_month,
                error="Income and budget limit must be positive numbers."
            )

        conn = get_db_connection()
        conn.execute("""
            INSERT INTO monthly_budgets (user_id, month, income, budget_limit)
            VALUES (?, ?, ?, ?)
        """, (session["user_id"], month, income, budget_limit))
        conn.commit()
        conn.close()

        return redirect("/dashboard")

    return render_template("set_budget.html", current_month=current_month)


@app.route("/add_expense", methods=["GET", "POST"])
def add_expense():
    if not login_required():
        return redirect("/login")

    today = datetime.now().strftime("%Y-%m-%d")

    if request.method == "POST":
        category = request.form["category"].strip()
        amount = request.form["amount"]
        date = request.form["date"]
        description = request.form["description"].strip()

        if not category:
            return render_template("add_expense.html", today=today, error="Category is required.")

        if float(amount) <= 0:
            return render_template("add_expense.html", today=today, error="Amount must be greater than 0.")

        conn = get_db_connection()
        conn.execute("""
            INSERT INTO expenses (user_id, category, amount, date, description)
            VALUES (?, ?, ?, ?, ?)
        """, (session["user_id"], category, amount, date, description))
        conn.commit()
        conn.close()

        return redirect("/dashboard")

    return render_template("add_expense.html", today=today)


@app.route("/education")
def education():
    if not login_required():
        return redirect("/login")

    return render_template("education.html")


@app.route("/ask_budget_ai", methods=["POST"])
def ask_budget_ai():
    if not login_required():
        return redirect("/login")

    original_question = request.form["question"].strip()

    if not original_question:
        return render_template(
            "education.html",
            error="Please enter a question for the AI Budget Coach."
        )

    current_month = datetime.now().strftime("%Y-%m")
    conn = get_db_connection()

    budget = conn.execute("""
        SELECT * FROM monthly_budgets
        WHERE user_id = ? AND month = ?
        ORDER BY id DESC
    """, (session["user_id"], current_month)).fetchone()

    expenses = conn.execute("""
        SELECT category, amount, date, description
        FROM expenses
        WHERE user_id = ? AND date LIKE ?
        ORDER BY date DESC
        LIMIT 10
    """, (session["user_id"], current_month + "%")).fetchall()

    total_spent = conn.execute("""
        SELECT SUM(amount) AS total
        FROM expenses
        WHERE user_id = ? AND date LIKE ?
    """, (session["user_id"], current_month + "%")).fetchone()["total"]

    conn.close()

    if total_spent is None:
        total_spent = 0

    income = 0
    budget_limit = 0

    if budget:
        income = float(budget["income"])
        budget_limit = float(budget["budget_limit"])

    expense_text = ""

    for expense in expenses:
        expense_text += (
            f"Date: {expense['date']}, "
            f"Category: {expense['category']}, "
            f"Amount: ${expense['amount']}, "
            f"Description: {expense['description']}\n"
        )

    if expense_text == "":
        expense_text = "No expenses have been added yet."

    ai_prompt = f"""
You are an AI budget coach for a college student.

Use the student's budget information to give helpful, simple, realistic advice.

Student username:
{session["username"]}

Current month:
{current_month}

Monthly income:
${income}

Monthly spending limit:
${budget_limit}

Total spent this month:
${total_spent}

Recent expenses:
{expense_text}

Student question:
{original_question}

Rules:
- Keep the response student-friendly.
- Give practical advice.
- Do not be too long.
- Do not give tax, legal, or investment advice.
- Focus on budgeting, saving, reducing expenses, food spending, emergency funds, and smart student money habits.
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=ai_prompt
        )
        answer = response.text

    except Exception as e:
        print(f"Gemini API Error: {str(e)}")
        if "RESOURCE_EXHAUSTED" in str(e) or "quota" in str(e).lower():
            answer = "The AI Budget Coach has reached its free usage limit. Please upgrade your Gemini API plan or wait for the quota to reset."
        elif "UNAVAILABLE" in str(e) or "high demand" in str(e).lower():
            answer = "The AI Budget Coach is temporarily unavailable due to high demand. Please try again in a few minutes."
        else:
            answer = "The AI Budget Coach is not available right now. Please check your GEMINI_API_KEY in the .env file and ensure it's valid."

    return render_template(
        "education.html",
        question=original_question,
        answer=answer
    )


@app.route("/delete_expense/<int:expense_id>", methods=["POST"])
def delete_expense(expense_id):
    if not login_required():
        return redirect("/login")

    conn = get_db_connection()
    conn.execute(
        "DELETE FROM expenses WHERE id = ? AND user_id = ?",
        (expense_id, session["user_id"])
    )
    conn.commit()
    conn.close()

    return redirect("/dashboard")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    budget_db()
    app.run(debug=True)