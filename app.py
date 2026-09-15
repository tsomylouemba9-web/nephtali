from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import json
import random
import string
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "linkservice.db")

app = Flask(__name__)
app.secret_key = "linkservice-secret-key-demo-2026"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            prenom TEXT NOT NULL,
            date_naissance TEXT NOT NULL,
            lieu_naissance TEXT NOT NULL,
            nature TEXT NOT NULL,
            telephone TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            prestation TEXT,
            bio TEXT,
            ville TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            media_type TEXT DEFAULT 'text',
            media_url TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(sender_id) REFERENCES users(id),
            FOREIGN KEY(receiver_id) REFERENCES users(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ludo_rooms (
            code TEXT PRIMARY KEY,
            state TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def new_room_code():
    conn = get_db()
    while True:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
        if not conn.execute("SELECT 1 FROM ludo_rooms WHERE code = ?", (code,)).fetchone():
            conn.close()
            return code


def read_room(code):
    conn = get_db()
    room = conn.execute("SELECT state FROM ludo_rooms WHERE code = ?", (code.upper(),)).fetchone()
    conn.close()
    return json.loads(room["state"]) if room else None


def save_room(code, state):
    conn = get_db()
    conn.execute("UPDATE ludo_rooms SET state = ? WHERE code = ?", (json.dumps(state), code.upper()))
    conn.commit()
    conn.close()


init_db()


@app.context_processor
def inject_user():
    return {"current_user": session.get("user")}


@app.route("/")
def home():
    return render_template("home.html")


@app.post("/api/ludo/create")
def create_ludo_room():
    code = new_room_code()
    state = {"players": 1, "turn": 1, "dice": None, "positions": [0, 0], "winner": None}
    conn = get_db()
    conn.execute("INSERT INTO ludo_rooms (code, state) VALUES (?, ?)", (code, json.dumps(state)))
    conn.commit()
    conn.close()
    return {"code": code, "player": 1, "state": state}


@app.post("/api/ludo/join")
def join_ludo_room():
    data = request.get_json(silent=True) or {}
    code = data.get("code", "").strip().upper()
    state = read_room(code)
    if not state:
        return {"error": "Salon introuvable."}, 404
    if state["players"] >= 2:
        return {"error": "Ce salon est déjà complet."}, 409
    state["players"] = 2
    save_room(code, state)
    return {"code": code, "player": 2, "state": state}


@app.get("/api/ludo/<code>")
def ludo_state(code):
    state = read_room(code)
    if not state:
        return {"error": "Salon introuvable."}, 404
    return state


@app.post("/api/ludo/<code>/move")
def ludo_move(code):
    data = request.get_json(silent=True) or {}
    player = int(data.get("player", 0))
    state = read_room(code)
    if not state:
        return {"error": "Salon introuvable."}, 404
    if state["players"] < 2:
        return {"error": "Invite un deuxième joueur avant de jouer."}, 409
    if player != state["turn"] or state["winner"]:
        return {"error": "Ce n'est pas ton tour."}, 409
    roll = random.randint(1, 6)
    state["dice"] = roll
    state["positions"][player - 1] = min(24, state["positions"][player - 1] + roll)
    if state["positions"][player - 1] >= 24:
        state["winner"] = player
    else:
        state["turn"] = 2 if player == 1 else 1
    save_room(code, state)
    return state


@app.route("/auth", methods=["GET", "POST"])
def auth():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "login":
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "")
            if not email or not password:
                flash("Veuillez remplir tous les champs.", "error")
                return redirect(url_for("auth"))

            conn = get_db()
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            conn.close()
            if user and check_password_hash(user["password"], password):
                session["user"] = {
                    "id": user["id"],
                    "nom": user["nom"],
                    "prenom": user["prenom"],
                    "email": user["email"],
                    "nature": user["nature"],
                    "telephone": user["telephone"],
                    "prestation": user["prestation"] or "",
                    "bio": user["bio"] or "",
                    "ville": user["ville"] or "",
                }
                return redirect(url_for("dashboard"))
            flash("E-mail ou mot de passe incorrect.", "error")
            return redirect(url_for("auth"))

        if action == "register":
            data = {
                "nom": request.form.get("nom", "").strip(),
                "prenom": request.form.get("prenom", "").strip(),
                "date_naissance": request.form.get("date_naissance", "").strip(),
                "lieu_naissance": request.form.get("lieu_naissance", "").strip(),
                "nature": request.form.get("nature", "Demandeur de services").strip(),
                "telephone": request.form.get("telephone", "").strip(),
                "email": request.form.get("email", "").strip(),
                "password": request.form.get("password", ""),
                "confirm": request.form.get("confirm_password", ""),
                "prestation": request.form.get("prestation", "").strip(),
                "ville": request.form.get("ville", "").strip(),
                "bio": request.form.get("bio", "").strip(),
            }

            required = ["nom", "prenom", "date_naissance", "lieu_naissance", "nature", "telephone", "email", "password", "confirm"]
            if any(not data[k] for k in required):
                flash("Veuillez remplir tous les champs obligatoires.", "error")
                return redirect(url_for("auth"))
            if data["password"] != data["confirm"]:
                flash("La confirmation du mot de passe est incorrecte.", "error")
                return redirect(url_for("auth"))
            if len(data["password"]) < 6:
                flash("Le mot de passe doit contenir au moins 6 caractères.", "error")
                return redirect(url_for("auth"))
            if "@" not in data["email"] or "." not in data["email"]:
                flash("Adresse e-mail invalide.", "error")
                return redirect(url_for("auth"))
            if data["nature"] == "Prestataire" and not data["prestation"]:
                flash("Le prestataire doit préciser la nature de sa prestation.", "error")
                return redirect(url_for("auth"))

            conn = get_db()
            existing = conn.execute("SELECT id FROM users WHERE email = ?", (data["email"],)).fetchone()
            if existing:
                conn.close()
                flash("Un compte existe déjà avec cette adresse e-mail.", "error")
                return redirect(url_for("auth"))

            hashed = generate_password_hash(data["password"])
            conn.execute(
                """
                INSERT INTO users (nom, prenom, date_naissance, lieu_naissance, nature, telephone, email, password, prestation, bio, ville)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["nom"],
                    data["prenom"],
                    data["date_naissance"],
                    data["lieu_naissance"],
                    data["nature"],
                    data["telephone"],
                    data["email"],
                    hashed,
                    data["prestation"] if data["nature"] == "Prestataire" else "",
                    data["bio"],
                    data["ville"],
                ),
            )
            conn.commit()
            user = conn.execute("SELECT * FROM users WHERE email = ?", (data["email"],)).fetchone()
            conn.close()
            session["user"] = {
                "id": user["id"],
                "nom": user["nom"],
                "prenom": user["prenom"],
                "email": user["email"],
                "nature": user["nature"],
                "telephone": user["telephone"],
                "prestation": user["prestation"] or "",
                "bio": user["bio"] or "",
                "ville": user["ville"] or "",
            }
            flash("Compte créé avec succès.", "success")
            return redirect(url_for("dashboard"))

    return render_template("auth.html")


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("auth"))

    conn = get_db()
    posts = conn.execute(
        """
        SELECT posts.*, users.prenom, users.nom, users.nature
        FROM posts
        JOIN users ON users.id = posts.user_id
        ORDER BY posts.id DESC
        """
    ).fetchall()
    conn.close()
    return render_template("dashboard.html", user=session["user"], posts=posts)


@app.route("/post", methods=["POST"])
def create_post():
    if "user" not in session:
        return redirect(url_for("auth"))

    content = request.form.get("content", "").strip()
    if not content:
        flash("Écrivez quelque chose avant de publier.", "error")
        return redirect(url_for("dashboard"))

    conn = get_db()
    conn.execute(
        "INSERT INTO posts (user_id, content, media_type, media_url) VALUES (?, ?, ?, ?)",
        (session["user"]["id"], content, "text", ""),
    )
    conn.commit()
    conn.close()
    flash("Publication créée avec succès.", "success")
    return redirect(url_for("dashboard"))


@app.route("/messages", methods=["GET", "POST"])
def messages():
    if "user" not in session:
        return redirect(url_for("auth"))

    if request.method == "POST":
        receiver_id = request.form.get("receiver_id")
        content = request.form.get("content", "").strip()
        if receiver_id and content:
            conn = get_db()
            conn.execute(
                "INSERT INTO messages (sender_id, receiver_id, content) VALUES (?, ?, ?)",
                (session["user"]["id"], int(receiver_id), content),
            )
            conn.commit()
            conn.close()
        return redirect(url_for("messages"))

    conn = get_db()
    users = conn.execute(
        "SELECT id, nom, prenom, nature, ville FROM users WHERE id != ? ORDER BY prenom ASC",
        (session["user"]["id"],),
    ).fetchall()
    messages_list = conn.execute(
        """
        SELECT m.*, u.prenom, u.nom
        FROM messages m
        JOIN users u ON u.id = m.sender_id
        WHERE (m.sender_id = ? OR m.receiver_id = ?) AND (m.sender_id = ? OR m.receiver_id = ?)
        ORDER BY m.id ASC
        """,
        (session["user"]["id"], session["user"]["id"], session["user"]["id"], session["user"]["id"]),
    ).fetchall()
    conn.close()
    return render_template("messages.html", user=session["user"], users=users, messages=messages_list)


@app.route("/profile")
def profile():
    if "user" not in session:
        return redirect(url_for("auth"))
    return render_template("profile.html", user=session["user"])


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug, host="0.0.0.0", port=port)
