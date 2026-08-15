# target_app/app.py
# This is the fake legacy bank website the AI will learn to operate

from flask import Flask, request, render_template, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "supersecret123"

# ── FAKE MEMBER DATABASE ──────────────────────────────────────
# These are the fake bank members. Member 99999 is missing on purpose
# so we can test "member not found" error handling.
MEMBERS = {
    "12345": {
        "name": "Alice Johnson",
        "account": "ACC-12345",
        "branch": "Downtown",
        "status": "Active",
        "savings_balance": "$5,432.10",
        "checking_balance": "$1,200.00",
    },
    "67890": {
        "name": "Bob Smith",
        "account": "ACC-67890",
        "branch": "Westside",
        "status": "Active",
        "savings_balance": "$12,750.50",
        "checking_balance": "$3,400.75",
    },
    "11111": {
        "name": "Carol Davis",
        "account": "ACC-11111",
        "branch": "Eastside",
        "status": "Frozen",
        "savings_balance": "$0.00",
        "checking_balance": "$89.20",
    },
}

# ── LOGIN PAGE ────────────────────────────────────────────────
@app.route("/", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == "admin" and password == "password123":
            session["logged_in"] = True
            return redirect(url_for("search"))
        else:
            error = "Invalid username or password"
    return render_template("login.html", error=error)

# ── SEARCH PAGE ───────────────────────────────────────────────
@app.route("/search", methods=["GET", "POST"])
def search():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    error = ""
    if request.method == "POST":
        member_id = request.form.get("member_id", "").strip()
        if member_id in MEMBERS:
            return redirect(url_for("member_detail", member_id=member_id))
        else:
            error = f"No record found for member ID: {member_id}"
    return render_template("search.html", error=error)

# ── MEMBER DETAIL PAGE ────────────────────────────────────────
@app.route("/member/<member_id>")
def member_detail(member_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    member = MEMBERS.get(member_id)
    if not member:
        return render_template("search.html", error=f"No record found for member ID: {member_id}")
    return render_template("member.html", member=member, member_id=member_id)

# ── LOGOUT ────────────────────────────────────────────────────
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ── TRANSFER PAGE ─────────────────────────────────────────────
@app.route("/transfer/<member_id>", methods=["GET", "POST"])
def transfer(member_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    member = MEMBERS.get(member_id)
    if not member:
        return redirect(url_for("search"))
    if request.method == "POST":
        return redirect(url_for("transfer_done", member_id=member_id))
    return render_template("transfer.html", member=member, member_id=member_id)

# ── TRANSFER DONE PAGE ────────────────────────────────────────
@app.route("/transfer/<member_id>/done")
def transfer_done(member_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("transfer_done.html", member_id=member_id)

if __name__ == "__main__":
    app.run(debug=True, port=5000)



# http://127.0.0.1:5000

# to find -      lsof -i :5000
#kill pid(number)