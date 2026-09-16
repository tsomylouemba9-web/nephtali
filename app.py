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
    if not room:
        return None
    state = json.loads(room["state"])
    if state.get("positions") and isinstance(state["positions"][0], list):
        state["positions"] = [min(48, state["positions"][0][0] if state["positions"][0] else 0), min(48, state["positions"][1][0] if state["positions"][1] else 0)]
    if state.get("positions") and isinstance(state["positions"][0], int) and "pending_steps" not in state:
        state["positions"] = [min(48, state["positions"][0]), min(48, state["positions"][1])]
    state.setdefault("dice", None)
    state.setdefault("winner", None)
    state.setdefault("pending_steps", 0)
    state.setdefault("obstacle", None)
    state.setdefault("trust", 3)
    state.setdefault("harmony", 0)
    return state


def save_room(code, state):
    conn = get_db()
    conn.execute("UPDATE ludo_rooms SET state = ? WHERE code = ?", (json.dumps(state), code.upper()))
    conn.commit()
    conn.close()


LOVE_OBSTACLES = {
    7: {"title": "Le doute", "text": "Un message ambigu vient troubler la confiance.", "options": ["Rester fidèle et en parler", "Suivre la tentation"]},
    14: {"title": "La distance", "text": "Une occasion éloigne les deux cœurs.", "options": ["Se choisir malgré la distance", "S'échapper vers une autre histoire"]},
    22: {"title": "La jalousie", "text": "Un partenaire ennemi apparaît sur le chemin.", "options": ["Faire confiance", "Répondre à la tentation"]},
    30: {"title": "La dispute", "text": "Les mots dépassent la pensée. Il faut réparer ensemble.", "options": ["Écouter et pardonner", "Garder son orgueil"]},
    38: {"title": "Le sacrifice", "text": "Le chemin propose un raccourci, mais il faut laisser l'autre derrière.", "options": ["Avancer ensemble", "Prendre le raccourci seul"]},
    44: {"title": "La dernière tentation", "text": "L'ennemi amoureux promet une route plus facile.", "options": ["Rester fidèle jusqu'au cœur", "Céder à la facilité"]},
}


def fresh_ludo_state():
    return {
        "players": 1,
        "turn": 1,
        "dice": None,
        "positions": [0, 0],
        "pending_steps": 0,
        "obstacle": None,
        "winner": None,
        "trust": 3,
        "harmony": 0,
    }


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
    state = fresh_ludo_state()
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
    if state.get("pending_steps", 0) or state.get("obstacle"):
        return {"error": "Termine le mouvement ou la décision en cours."}, 409
    state["dice"] = random.randint(1, 6)
    state["pending_steps"] = state["dice"]
    state["last_action"] = f"Le joueur {player} a lancé un {state['dice']}."
    save_room(code, state)
    return state


@app.post("/api/ludo/<code>/step")
def ludo_step(code):
    data = request.get_json(silent=True) or {}
    player = int(data.get("player", 0))
    state = read_room(code)
    if not state:
        return {"error": "Salon introuvable."}, 404
    if player != state["turn"] or state.get("pending_steps", 0) <= 0:
        return {"error": "Aucun pas ne peut être joué maintenant."}, 409
    state["positions"][player - 1] = min(48, state["positions"][player - 1] + 1)
    state["pending_steps"] -= 1
    position = state["positions"][player - 1]
    if position in LOVE_OBSTACLES and not state.get("obstacle"):
        state["obstacle"] = {"position": position, **LOVE_OBSTACLES[position]}
        state["pending_steps"] = 0
    elif position >= 48 and state["positions"][0] >= 48 and state["positions"][1] >= 48:
        state["winner"] = "coop"
    elif state["pending_steps"] == 0:
        state["turn"] = 2 if player == 1 else 1
        state["last_action"] = f"Le cœur du joueur {player} avance à l'étape {position}."
    save_room(code, state)
    return state


@app.post("/api/ludo/<code>/decision")
def ludo_decision(code):
    data = request.get_json(silent=True) or {}
    player = int(data.get("player", 0))
    choice = data.get("choice", "")
    state = read_room(code)
    if not state or not state.get("obstacle"):
        return {"error": "Aucune décision n'est en attente."}, 409
    if player not in (1, 2) or choice not in ("faithful", "temptation"):
        return {"error": "Décision invalide."}, 400
    if choice == "faithful":
        state["harmony"] += 1
        state["trust"] = min(5, state["trust"] + 1)
        state["last_action"] = "Les deux cœurs sont restés fidèles."
    else:
        state["trust"] = max(0, state["trust"] - 1)
        state["positions"][player - 1] = max(0, state["positions"][player - 1] - 3)
        state["last_action"] = "La tentation a laissé une distance entre les deux cœurs."
    state["obstacle"] = None
    state["turn"] = 2 if state["turn"] == 1 else 1
    save_room(code, state)
    return state


@app.post("/api/ludo/<code>/emotion")
def ludo_emotion(code):
    data = request.get_json(silent=True) or {}
    player = int(data.get("player", 0))
    emoji = data.get("emoji", "").strip()
    state = read_room(code)
    if not state:
        return {"error": "Salon introuvable."}, 404
    if player not in (1, 2) or emoji not in {"❤️", "😂", "🔥", "😮", "👏", "✨"}:
        return {"error": "Réaction invalide."}, 400
    state["reaction"] = {"player": player, "emoji": emoji, "id": random.randint(100000, 999999)}
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
