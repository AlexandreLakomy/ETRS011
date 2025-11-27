import signal
import sys
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash # type: ignore
from pysnmp.hlapi import getCmd, SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity # type: ignore
from datetime import datetime
from functools import wraps
try:
    from werkzeug.security import generate_password_hash, check_password_hash
except Exception:
    # Fallback simple implementation using PBKDF2 if werkzeug is not installed.
    import hashlib, binascii, os, hmac

    def generate_password_hash(password: str) -> str:
        salt = os.urandom(16)
        iterations = 100000
        dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, iterations)
        return f"pbkdf2:sha256:{iterations}${binascii.hexlify(salt).decode()}${binascii.hexlify(dk).decode()}"

    def check_password_hash(pwhash: str, password: str) -> bool:
        try:
            algo, salt_hex, hash_hex = pwhash.split('$', 2)
            parts = algo.split(':')
            iterations = int(parts[-1])
            salt = binascii.unhexlify(salt_hex)
            dk = binascii.unhexlify(hash_hex)
            newdk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, iterations)
            return hmac.compare_digest(newdk, dk)
        except Exception:
            return False

import sqlite3
import os
import datetime
import asyncio
import threading, time


app = Flask(__name__)
app.secret_key = "Cle_super_secrete_que_personne_ne_doit_connaitre"

# --------------------------------------------------------------------
# 🔌 Connexion à la base SQLite
# --------------------------------------------------------------------
def get_db_connection():
    db_path = r"C:\Users\Alexa\OneDrive\Documents\M2\ETRS011\Flask\BDD\BDD_LeFlour"

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Base de données introuvable à l'emplacement : {db_path}")

    # Timeout de 5 secondes → SQLite réessaie si la base est temporairement bloquée
    conn = sqlite3.connect(db_path, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn

# --------------------------------------------------------------------
# Protection des routes Admin & Utilisateur
# --------------------------------------------------------------------
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Vérifie si l'utilisateur est connecté ET admin
        if not session.get("user_id"):
            flash("")
            return redirect(url_for("login"))
        if not session.get("is_admin"):
            flash("Accès réservé à l’administrateur.")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return decorated_function


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# --------------------------------------------------------------------
# 🏠 Page d'accueil
# --------------------------------------------------------------------
@app.route('/')
def index():
    return render_template('index.html')

# --------------------------------------------------------------------
# 🏠 Page d'accueil utilisateur connecté
# --------------------------------------------------------------------
@app.route("/home")
@login_required
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_nom = session.get("user_nom", "")
    user_prenom = session.get("user_prenom", "")

    return render_template("home.html", user_nom=user_nom, user_prenom=user_prenom)

# --------------------------------------------------------------------
# 📊 Tableau de bord (données SQLite)
# --------------------------------------------------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            D.id AS id_donnee,
            E.nom AS equipement,
            E.ip AS ip,
            O.nomParametre AS parametre,
            O.identifiant AS oid,
            D.valeur AS valeur,
            D.timestamp AS date
        FROM DonneeEquipement D
        JOIN Equipement E ON D.equipement_id = E.id
        JOIN OID O ON D.oid_id = O.id
        ORDER BY D.timestamp DESC;
    """)

    data = cur.fetchall()
    conn.close()

    return render_template('dashboard.html', data=data)

# --------------------------------------------------------------------
# ⚙️ Configurations
# --------------------------------------------------------------------
@app.route('/config')
@login_required
def config():
    conn = get_db_connection()
    cur = conn.cursor()

    # 🔹 Récupération des équipements + statut demande suppression
    cur.execute("""
        SELECT 
            e.id,
            e.nom,
            e.ip,
            e.type,
            e.community,
            e.intervalle,
            (
                SELECT status
                FROM ValidationAdmin
                WHERE action_type = 'DELETE_EQ'
                AND target_id = e.id
                ORDER BY id DESC LIMIT 1
            ) AS demande_status
        FROM Equipement e;
    """)
    equipements = cur.fetchall()

    # 🔹 Récupération des OIDs avec seuils + alerte_active + statut demande suppression
    cur.execute("""
        SELECT 
            O.id,
            O.identifiant,
            O.nomParametre,
            O.typeValeur,
            O.seuilMin,
            O.seuilWarning,
            O.seuilMax,
            O.alerte_active,
            E.nom AS equipement_nom,
            (
                SELECT status
                FROM ValidationAdmin
                WHERE action_type = 'DELETE_OID'
                AND target_id = O.id
                ORDER BY id DESC LIMIT 1
            ) AS demande_status
        FROM OID O
        LEFT JOIN Equipement E ON O.equipement_id = E.id
        ORDER BY O.id ASC;
    """)
    oids = cur.fetchall()

    conn.close()

    return render_template('config.html', equipements=equipements, oids=oids)


# --------------------------------------------------------------------
# ⚙️ Alerting Dynamique
# --------------------------------------------------------------------
@app.route('/update_alert/<int:oid_id>', methods=['POST'])
@login_required
def update_alert(oid_id):
    data = request.get_json()
    new_state = data.get('alerte_active', False)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE OID SET alerte_active = ? WHERE id = ?", (1 if new_state else 0, oid_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "oid_id": oid_id, "alerte_active": new_state})

# --------------------------------------------------------------------
#  Ajouter/Modifier/Supprimer un équipement
# --------------------------------------------------------------------
@app.route('/ajouter_equipement', methods=['GET', 'POST'])
@login_required
def ajouter_equipement():

    if request.method == "POST":
        nom = request.form["nom"]
        ip = request.form["ip"]
        type_eq = request.form["type"]
        community = request.form["community"]
        intervalle = request.form["intervalle"]

        conn = get_db_connection()
        cur = conn.cursor()

        try:
            cur.execute("""
                INSERT INTO Equipement (nom, ip, type, community, intervalle)
                VALUES (?, ?, ?, ?, ?)
            """, (nom, ip, type_eq, community, intervalle))

            conn.commit()
            flash("✅ Machine ajoutée avec succès !", "success")
            return redirect(url_for("config"))

        except sqlite3.IntegrityError as e:
            conn.rollback()

            if "UNIQUE constraint failed: Equipement.ip" in str(e):
                flash("❌ La machine n’a pas été ajoutée : cette adresse IP existe déjà.", "error")
            else:
                flash("❌ Une erreur est survenue lors de l’ajout de la machine.", "error")

            return redirect(url_for("ajouter_equipement"))

        finally:
            conn.close()

    return render_template("ajouter_equipement.html")



@app.route('/supprimer_equipement/<int:id>')
@login_required
def supprimer_equipement(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM Equipement WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('config'))


@app.route('/modifier_equipement/<int:id>', methods=['GET', 'POST'])
@login_required
def modifier_equipement(id):
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        nom = request.form['nom']
        ip = request.form['ip']
        type_eq = request.form['type']
        community = request.form['community']
        intervalle = request.form['intervalle']

        cur.execute("""
            UPDATE Equipement
            SET nom = ?, ip = ?, type = ?, community = ?, intervalle = ?
            WHERE id = ?
        """, (nom, ip, type_eq, community, intervalle, id))
        conn.commit()
        conn.close()
        return redirect(url_for('config'))

    cur.execute("SELECT * FROM Equipement WHERE id = ?", (id,))
    equipement = cur.fetchone()
    conn.close()

    if equipement is None:
        return "Équipement introuvable", 404

    return render_template('modifier_equipement.html', equipement=equipement)


# --------------------------------------------------------------------
# 🧩 Ajouter/Modifier/Supprimer d'un OID
# --------------------------------------------------------------------
@app.route('/oids')
@login_required
def oids():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT O.id, O.identifiant, O.nomParametre, O.typeValeur, 
               O.seuilMin, O.seuilWarning, O.seuilMax, O.alerte_active, 
               E.nom AS equipement_nom
        FROM OID O
        LEFT JOIN Equipement E ON O.equipement_id = E.id
    """)
    oids = cur.fetchall()
    conn.close()
    return render_template('oids.html', oids=oids)


@app.route('/ajouter_oid', methods=['GET', 'POST'])
@login_required
def ajouter_oid():
    conn = get_db_connection()
    cur = conn.cursor()

    # Charger équipements
    cur.execute("SELECT id, nom FROM Equipement;")
    equipements = cur.fetchall()

    # Charger les OIDs validés (APPROVED) dans CatalogueOID
    cur.execute("""
        SELECT id, nomParametre, identifiant, typeValeur
        FROM CatalogueOID
        WHERE status = 'APPROVED'
        ORDER BY nomParametre ASC;
    """)
    oids_catalogue = cur.fetchall()

    if request.method == 'POST':

        # 1️⃣ Récupération de l'identifiant sélectionné
        identifiant = request.form.get('identifiant')

        if not identifiant:
            conn.close()
            return "Erreur : aucun identifiant reçu.", 400

        # 2️⃣ Récupérer le nomParametre + typeValeur depuis CatalogueOID
        cur.execute("""
            SELECT nomParametre, typeValeur
            FROM CatalogueOID
            WHERE identifiant = ?
            AND status = 'APPROVED'
        """, (identifiant,))
        row = cur.fetchone()

        if not row:
            conn.close()
            return "Erreur : OID introuvable ou non validé.", 400

        nom_parametre = row["nomParametre"]
        type_valeur = row["typeValeur"]

        # 3️⃣ Récupération du reste du formulaire
        equipement_id = request.form['equipement_id']
        seuil_min = request.form['seuilMin'] or None
        seuil_warning = request.form['seuilWarning'] or None
        seuil_max = request.form['seuilMax'] or None
        alerte_active = 1 if 'alerte_active' in request.form else 0

        # 4️⃣ Insertion dans la table OID
        cur.execute("""
            INSERT INTO OID (identifiant, nomParametre, typeValeur, equipement_id,
                             seuilMin, seuilWarning, seuilMax, alerte_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (identifiant, nom_parametre, type_valeur, equipement_id,
              seuil_min, seuil_warning, seuil_max, alerte_active))

        conn.commit()
        conn.close()
        return redirect(url_for('config'))

    conn.close()
    return render_template('ajouter_oid.html', equipements=equipements, oids=oids_catalogue)


@app.route("/demande_oid", methods=["GET", "POST"])
@login_required
def demande_oid():
    if request.method == "GET":
        return render_template("demande_oid.html")

    try:
        nom = request.form["nomParametre"]
        identifiant = request.form["identifiant"]
        type_valeur = request.form["typeValeur"]
        commentaire = request.form.get("commentaire")
        user_id = session.get("user_id")

        conn = get_db_connection()
        cur = conn.cursor()

        # Étape 1 : insérer dans CatalogueOID
        cur.execute("""
            INSERT INTO CatalogueOID (nomParametre, identifiant, typeValeur, status)
            VALUES (?, ?, ?, 'PENDING')
        """, (nom, identifiant, type_valeur))
        oid_id = cur.lastrowid

        # Étape 2 : insérer dans ValidationAdmin
        cur.execute("""
            INSERT INTO ValidationAdmin (user_id, action_type, target_id, status, commentaire)
            VALUES (?, 'NEW_OID', ?, 'PENDING', ?)
        """, (user_id, oid_id, commentaire))

        conn.commit()
        flash("✅ Votre demande d’ajout d’OID a bien été envoyée à l’administrateur.")
        return redirect(url_for('oids'))

    except Exception as e:
        print("⚠️ ERREUR lors de la demande OID :", e)
        if conn:
            conn.rollback()
        return "Erreur lors de la création de la demande", 500

    finally:
        if conn:
            conn.close()



@app.route('/modifier_oid/<int:id>', methods=['GET', 'POST'])
@login_required
def modifier_oid(id):
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        identifiant = request.form.get('identifiant')
        nom_parametre = request.form.get('nomParametre')
        type_valeur = request.form.get('typeValeur')
        equipement_id = request.form.get('equipement_id')

        seuil_min = request.form.get('seuilMin') or None
        seuil_warning = request.form.get('seuilWarning') or None
        seuil_max = request.form.get('seuilMax') or None
        alerte_active = 1 if 'alerte_active' in request.form else 0

        cur.execute("""
            UPDATE OID
            SET identifiant=?, nomParametre=?, typeValeur=?, equipement_id=?, 
                seuilMin=?, seuilWarning=?, seuilMax=?, alerte_active=?
            WHERE id=?
        """, (identifiant, nom_parametre, type_valeur, equipement_id,
              seuil_min, seuil_warning, seuil_max, alerte_active, id))

        conn.commit()
        conn.close()
        return redirect(url_for('config'))

    cur.execute("SELECT * FROM OID WHERE id=?", (id,))
    oid = cur.fetchone()

    cur.execute("SELECT id, nom FROM Equipement;")
    equipements = cur.fetchall()

    conn.close()
    return render_template('modifier_oid.html', oid=oid, equipements=equipements)


@app.route('/demande_suppression_equipement/<int:eq_id>', methods=['POST'])
@login_required
def demande_suppression_equipement(eq_id):
    user_id = session.get("user_id")
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id FROM ValidationAdmin
            WHERE action_type='DELETE_EQ' AND target_id=? AND status='PENDING'
        """, (eq_id,))
        if cur.fetchone():
            return "OK"

        cur.execute("""
            INSERT INTO ValidationAdmin (user_id, action_type, target_id, status)
            VALUES (?, 'DELETE_EQ', ?, 'PENDING')
        """, (user_id, eq_id))

        conn.commit()
        return "OK"
    except Exception as e:
        print("Erreur suppression équipement :", e)
        return "ERROR", 500
    finally:
        conn.close()

@app.route('/demande_suppression_oid/<int:oid_id>', methods=['POST'])
@login_required
def demande_suppression_oid(oid_id):
    conn = get_db_connection()
    cur = conn.cursor()

    # Vérifier si une demande existe déjà
    cur.execute("""
        SELECT id FROM ValidationAdmin
        WHERE action_type = 'DELETE_OID' 
        AND target_id = ? AND status = 'PENDING'
    """, (oid_id,))
    if cur.fetchone():
        conn.close()
        return jsonify(success=True)

    # Créer la demande
    cur.execute("""
        INSERT INTO ValidationAdmin (user_id, action_type, target_id, status)
        VALUES (?, 'DELETE_OID', ?, 'PENDING')
    """, (session["user_id"], oid_id))

    conn.commit()
    conn.close()
    return jsonify(success=True)


@app.route("/mes_demandes_oid")
@login_required
def mes_demandes_oid():
    conn = get_db_connection()
    cur = conn.cursor()

    # Récupérer toutes les demandes de l'utilisateur
    cur.execute("""
        SELECT 
            V.id AS demande_id,
            V.action_type,
            V.target_id,
            V.status AS validation_status,
            V.created_at AS demande_date,
            V.commentaire,
            
            -- Infos pour NEW_OID
            C.nomParametre AS oid_nom,
            C.identifiant AS oid_identifiant,
            C.typeValeur AS oid_type,

            -- Infos pour DELETE_OID
            O.nomParametre AS oid_nom_delete,
            O.identifiant AS oid_identifiant_delete,

            -- Infos pour DELETE_EQ
            E.nom AS equipement_nom,
            E.ip AS equipement_ip,

            -- Infos pour NEW_TEMPLATE
            T.nom AS template_nom

        FROM ValidationAdmin V
        LEFT JOIN CatalogueOID C ON (V.action_type = 'NEW_OID' AND C.id = V.target_id)
        LEFT JOIN OID O ON (V.action_type = 'DELETE_OID' AND O.id = V.target_id)
        LEFT JOIN Equipement E ON (V.action_type = 'DELETE_EQ' AND E.id = V.target_id)
        LEFT JOIN Template T ON (V.action_type = 'NEW_TEMPLATE' AND T.id = V.target_id)
        
        WHERE V.user_id = ?
        ORDER BY V.created_at DESC
    """, (session["user_id"],))

    demandes = cur.fetchall()
    conn.close()

    return render_template("mes_demandes_oid.html", demandes=demandes)




# --------------------------------------------------------------------
#  ⚠️ Seuil
# --------------------------------------------------------------------
def verifier_seuils(oid_id, equipement_id, valeur_actuelle):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT seuilMin, seuilWarning, seuilMax FROM OID WHERE id=?", (oid_id,))
    seuils = cur.fetchone()

    if not seuils:
        conn.close()
        return

    seuil_min, seuil_warning, seuil_max = seuils
    type_alerte, seuil_declencheur, niveau = None, None, None

    try:
        valeur_actuelle = float(valeur_actuelle)
        if seuil_min is not None:
            seuil_min = float(seuil_min)
        if seuil_warning is not None:
            seuil_warning = float(seuil_warning)
        if seuil_max is not None:
            seuil_max = float(seuil_max)
    except Exception as e:
        print(f"⚠️ Erreur de conversion numérique : {e}")
        conn.close()
        return

    # 🔥 Seuil critique — priorité absolue
    if seuil_max is not None and valeur_actuelle > seuil_max:
        type_alerte = "SeuilMax"
        seuil_declencheur = seuil_max
        niveau = "CRITICAL"

    # ⚠️ Seuil warning
    elif seuil_warning is not None and valeur_actuelle > seuil_warning:
        type_alerte = "SeuilWarning"
        seuil_declencheur = seuil_warning
        niveau = "WARNING"

    # 🔽 Seuil minimal
    elif seuil_min is not None and valeur_actuelle < seuil_min:
        type_alerte = "SeuilMin"
        seuil_declencheur = seuil_min
        niveau = "LOW"


    if type_alerte:
        message = f"Alerte {niveau} : valeur {valeur_actuelle} dépasse {seuil_declencheur}"
        cur.execute("""
            INSERT INTO Event (oid_id, equipement_id, type_alerte, valeur_actuelle, seuil_declencheur, message, niveau)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (oid_id, equipement_id, type_alerte, valeur_actuelle, seuil_declencheur, message, niveau))
        conn.commit()
        print(f"🚨 Alerte générée : {message}")  # 👈 Ajout pour debug

    conn.close()


# --------------------------------------------------------------------
# 📜 Event
# --------------------------------------------------------------------
@app.route('/events')
@login_required
def events():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            E.id,
            O.nomParametre,
            Q.nom AS equipement_nom,
            E.type_alerte,
            E.valeur_actuelle,
            E.seuil_declencheur,
            E.message,
            E.niveau,
            E.horodatage
        FROM Event E
        LEFT JOIN OID O ON E.oid_id = O.id
        LEFT JOIN Equipement Q ON E.equipement_id = Q.id
        ORDER BY E.horodatage DESC;
    """)
    events = cur.fetchall()
    conn.close()
    return render_template('events.html', events=events)


# --------------------------------------------------------------------
# Enregistrement
# --------------------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    message = None

    if request.method == "POST":
        nom = request.form.get("nom")
        prenom = request.form.get("prenom")
        email = request.form.get("email")
        mot_de_passe = request.form.get("mot_de_passe")

        if not all([nom, prenom, email, mot_de_passe]):
            message = "Tous les champs sont obligatoires."
        else:
            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute("SELECT id FROM utilisateur WHERE email = ?", (email,))
            existing_user = cur.fetchone()

            if existing_user:
                message = "Cette adresse e-mail est déjà utilisée."
            else:
                mot_de_passe_hash = generate_password_hash(mot_de_passe)
                date_creation = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                cur.execute("""
                    INSERT INTO utilisateur (nom, prenom, email, mot_de_passe, date_creation, is_admin)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (nom, prenom, email, mot_de_passe_hash, date_creation, 0))

                conn.commit()
                cur.close()
                conn.close()

                return redirect(url_for("register_success"))

            cur.close()
            conn.close()

    return render_template("register.html", message=message)


@app.route("/register_success")
def register_success():
    return render_template("register_success.html")


# --------------------------------------------------------------------
# Connexion / Déconnexion
# --------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    message = None

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        mot_de_passe = request.form.get("mot_de_passe", "").strip()

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nom, prenom, mot_de_passe, is_admin FROM utilisateur WHERE email = ?", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and check_password_hash(user["mot_de_passe"], mot_de_passe):
            session["user_id"] = user["id"]
            session["user_nom"] = user["nom"]
            session["user_prenom"] = user["prenom"]  # ✅ ajout du prénom
            session["is_admin"] = user["is_admin"]
            # 🔥 Si admin → dashboard admin
            if user["is_admin"] == 1:
                return redirect(url_for("admin_dashboard"))

            # Sinon → page d’accueil utilisateur
            return redirect(url_for("home"))
        else:
            message = "Le login ou le mot de passe saisi ne correspond pas."

    return render_template("login.html", message=message)



@app.route("/logout")
def logout():
    session.clear()  # Vide toutes les infos de session
    return redirect(url_for("index"))

@app.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# --------------------------------------------------------------------
# 👥 Administration
# --------------------------------------------------------------------
@app.route('/admin')
@login_required
def admin():
    return render_template('admin.html')


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM ValidationAdmin WHERE status = 'PENDING'")
    demandes = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("admin_dashboard.html", demandes=demandes)


@app.route("/admin/backup")
@admin_required
def admin_backup():
    return render_template("admin_backup.html")


@app.route("/admin/users")
@admin_required
def admin_users():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, nom, prenom, email, is_admin FROM utilisateur")
    users = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("admin_users.html", users=users)


@app.route("/admin/valider/<int:id>", methods=["POST"])
@admin_required
def admin_valider(id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM ValidationAdmin WHERE id = ?", (id,))
    demande = cur.fetchone()

    if not demande:
        return jsonify({"success": False}), 404

    action = demande["action_type"]
    target_id = demande["target_id"]

    # ------------------------
    # 1️⃣ Validation d’un NOUVEL OID
    # ------------------------
    if action == "NEW_OID":
        cur.execute("""
            UPDATE CatalogueOID 
            SET status = 'APPROVED' 
            WHERE id = ?
        """, (target_id,))

    # ------------------------
    # 2️⃣ Suppression d'un OID
    # ------------------------
    elif action == "DELETE_OID":
        cur.execute("DELETE FROM OID WHERE id = ?", (target_id,))

    # ------------------------
    # 3️⃣ Suppression d'un ÉQUIPEMENT
    # ------------------------
    elif action == "DELETE_EQ":
        # Supprimer les OIDs liés (FK)
        cur.execute("DELETE FROM OID WHERE equipement_id = ?", (target_id,))
        # Supprimer l'équipement
        cur.execute("DELETE FROM Equipement WHERE id = ?", (target_id,))

    # ------------------------
    # 4️⃣ Suppression d'un TEMPLATE
    # ------------------------
    elif action == "NEW_TEMPLATE":
        cur.execute("UPDATE Template SET status='APPROVED' WHERE id = ?", (target_id,))

    # ------------------------
    # 5️⃣ Marquer la demande comme validée
    # ------------------------
    cur.execute("""
        UPDATE ValidationAdmin 
        SET status = 'APPROVED'
        WHERE id = ?
    """, (id,))

    conn.commit()
    conn.close()

    return jsonify({"success": True})


@app.route("/admin/refuser/<int:id>", methods=["POST"])
@admin_required
def admin_refuser(id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM ValidationAdmin WHERE id = ?", (id,))
    demande = cur.fetchone()
    if not demande:
        return jsonify({"success": False}), 404

    if demande["action_type"] == "NEW_OID":
        cur.execute("UPDATE CatalogueOID SET status = 'REJECTED' WHERE id = ?", (demande["target_id"],))

    cur.execute("UPDATE ValidationAdmin SET status = 'REJECTED' WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

# --------------------------------------------------------------------
# 📡 Fonction SNMP
# --------------------------------------------------------------------
def check_snmp_device(ip, community, oid):
    try:
        iterator = getCmd(
            SnmpEngine(),
            CommunityData(community, mpModel=1),  # SNMPv2c
            UdpTransportTarget((ip, 161), timeout=3, retries=1),
            ContextData(),
            ObjectType(ObjectIdentity(oid))
        )

        errorIndication, errorStatus, errorIndex, varBinds = next(iterator)

        if errorIndication:
            return {"status": "DOWN", "info": str(errorIndication)}
        elif errorStatus:
            return {"status": "DOWN", "info": str(errorStatus.prettyPrint())}
        else:
            # 🔍 On récupère la valeur SNMP
            raw_value = str(varBinds[0])
            if "No Such" in raw_value or "Timeout" in raw_value:
                return {"status": "DOWN", "info": raw_value}
            else:
                return {"status": "UP", "info": raw_value}

    except Exception as e:
        return {"status": "DOWN", "info": str(e)}

# --------------------------------------------------------------------
# 🛰️ Vérification SNMP
# --------------------------------------------------------------------
@app.route("/snmp_check")
def snmp_check():
    conn = get_db_connection()
    cur = conn.cursor()

    # 🔍 Récupère uniquement les équipements qui ont des OIDs liés
    cur.execute("""
        SELECT 
            E.id AS equipement_id,
            E.nom AS equipement_nom,
            E.ip,
            E.community,
            O.id AS oid_id,
            O.identifiant AS oid,
            O.nomParametre
        FROM Equipement E
        JOIN OID O ON E.id = O.equipement_id
    """)

    devices = cur.fetchall()
    conn.close()

    results = []

    for device in devices:
        res = check_snmp_device(device["ip"], device["community"], device["oid"])

        results.append({
            "name": device["equipement_nom"],
            "ip": device["ip"],
            "oid": device["oid"],
            "parametre": device["nomParametre"],
            "status": res["status"],
            "info": res["info"]
        })

        # 💾 Enregistre la valeur si l'équipement répond
        if res["status"] == "UP":
            try:
                valeur = float(res["info"].split("=")[-1].strip())
                insert_snmp_value(device["equipement_id"], device["oid_id"], valeur)
            except Exception:
                pass

    return render_template("snmp_check.html", results=results)

# --------------------------------------------------------------------
# 💎 Templates
# --------------------------------------------------------------------

@app.route("/creer_template", methods=["GET", "POST"])
@login_required
def creer_template():
    conn = get_db_connection()
    cur = conn.cursor()

    # -----------------------
    # POST : création template
    # -----------------------
    if request.method == "POST":
        nom_template = request.form.get("nom_template")

        # les OIDs validés sélectionnés (id de CatalogueOID)
        oids = request.form.getlist("oid[]")

        if not nom_template:
            flash("⚠️ Le nom du template est obligatoire.", "error")
            return redirect(url_for("creer_template"))

        # Créer le template (status = PENDING)
        cur.execute("""
            INSERT INTO Template (user_id, nom, status)
            VALUES (?, ?, 'PENDING')
        """, (session["user_id"], nom_template))
        template_id = cur.lastrowid

        # Ajouter les OIDs sélectionnés
        for oid_id in oids:
            cur.execute("""
                INSERT INTO TemplateOID (template_id, catalogue_oid_id)
                VALUES (?, ?)
            """, (template_id, oid_id))

        # Créer une entrée ValidationAdmin
        cur.execute("""
            INSERT INTO ValidationAdmin (user_id, action_type, target_id, status)
            VALUES (?, 'NEW_TEMPLATE', ?, 'PENDING')
        """, (session["user_id"], template_id))

        conn.commit()
        conn.close()

        flash("📩 Votre template a été envoyé pour validation.", "success")
        return redirect(url_for("home"))

    # -----------------------
    # GET : afficher la page
    # -----------------------

    # 🔥 Récupérer les OIDs validés
    cur.execute("""
        SELECT id, nomParametre, identifiant, typeValeur
        FROM CatalogueOID
        WHERE status = 'APPROVED'
        ORDER BY nomParametre ASC
    """)
    catalogue_oids = cur.fetchall()

    # 🔥 Charger toutes les templates validées
    cur.execute("SELECT id, nom FROM Template WHERE status = 'APPROVED'")
    templates = cur.fetchall()

    # 🔥 Récupérer les OIDs appartenant à chaque template
    cur.execute("""
        SELECT T.template_id, C.nomParametre, C.identifiant
        FROM TemplateOID T
        JOIN CatalogueOID C ON C.id = T.catalogue_oid_id
    """)
    rows = cur.fetchall()

    # Transformer en dict : template_id → [liste d'OIDs]
    template_oids = {}
    for row in rows:
        tid = row["template_id"]
        if tid not in template_oids:
            template_oids[tid] = []
        template_oids[tid].append(row)

    conn.close()

    return render_template(
        "creer_template.html",
        catalogue_oids=catalogue_oids,
        templates=templates,
        template_oids=template_oids
    )


# --------------------------------------------------------------------
# 🚀 Stocker les données SNMP dans la BDD
# --------------------------------------------------------------------
def insert_snmp_value(equipement_id, oid_id, valeur):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO DonneeEquipement (equipement_id, oid_id, valeur) VALUES (?, ?, ?)",
        (equipement_id, oid_id, valeur)
    )
    conn.commit()
    conn.close()


def collect_snmp_data():
    """Collecte et stocke les données SNMP de tous les équipements présents dans la BDD."""
    conn = get_db_connection()
    cur = conn.cursor()

    # 1️⃣ Récupérer tous les équipements
    cur.execute("SELECT id, nom, ip, community FROM Equipement;")
    equipements = cur.fetchall()

    for equipement in equipements:
        equipement_id = equipement["id"]
        equipement_nom = equipement["nom"]
        equipement_ip = equipement["ip"]
        community = equipement["community"]

        # 2️⃣ Récupérer les OID associés à cet équipement (incluant alerte_active)
        cur.execute("SELECT id, identifiant, nomParametre, alerte_active FROM OID WHERE equipement_id = ?", (equipement_id,))
        oids = cur.fetchall()

        for oid in oids:
            oid_id = oid["id"]
            oid_value = oid["identifiant"]
            param_name = oid["nomParametre"]

            # ⛔ Ne rien faire si l’alerte est désactivée
            if not oid["alerte_active"]:
                continue

            # 3️⃣ Interroger le périphérique via SNMP
            res = check_snmp_device(equipement_ip, community, oid_value)

            if res["status"] == "UP":
                try:
                    valeur_str = res["info"].split("=")[-1].strip()

                    # ⛔ Ignore les valeurs texte (ex : "No Such Object")
                    if not valeur_str.replace('.', '', 1).isdigit():
                        print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] ⚠️ Valeur non numérique pour {param_name} ({equipement_nom}) : {valeur_str}")
                        continue

                    valeur = float(valeur_str)
                    insert_snmp_value(equipement_id, oid_id, valeur)

                    print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] ✅ {param_name} ({equipement_nom}) = {valeur}")

                    # 🔔 Vérifie les seuils après récupération de la valeur
                    verifier_seuils(oid_id, equipement_id, valeur)

                except ValueError:
                    print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] ⚠️ Valeur non numérique reçue pour {param_name} ({equipement_nom}) : {res['info']}")
                except Exception as e:
                    print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] ⚠️ Erreur d’insertion pour {param_name} ({equipement_nom}) : {e}")
            else:
                print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] ❌ {equipement_nom} injoignable : {res['info']}")

    conn.close()


async def poll_snmp_device(equipement):
    """Tâche asynchrone individuelle pour chaque équipement."""
    while True:
        try:
            with app.app_context():
                equipement_id = equipement["id"]
                equipement_nom = equipement["nom"]
                ip = equipement["ip"]
                community = equipement["community"]

                # 🔍 Récupérer les OID associés (incluant alerte_active)
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("SELECT id, identifiant, nomParametre, alerte_active FROM OID WHERE equipement_id = ?", (equipement_id,))
                oids = cur.fetchall()
                conn.close()

                for oid in oids:
                    # ⛔ Si l’alerte est désactivée → on passe
                    if not oid["alerte_active"]:
                        continue

                    oid_id = oid["id"]
                    oid_value = oid["identifiant"]
                    param_name = oid["nomParametre"]

                    res = check_snmp_device(ip, community, oid_value)

                    if res["status"] == "UP":
                        try:
                            valeur_str = res["info"].split("=")[-1].strip()
                            valeur = float(valeur_str)
                            insert_snmp_value(equipement_id, oid_id, valeur)
                            print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] ✅ {param_name} ({equipement_nom}) = {valeur}")
                            verifier_seuils(oid_id, equipement_id, valeur)
                        except Exception as e:
                            print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] ⚠️ Erreur d’insertion ({equipement_nom}): {e}")
                    else:
                        print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] ❌ {equipement_nom} injoignable : {res['info']}")

        except Exception as e:
            print(f"⚠️ Erreur sur {equipement['nom']} : {e}")

        # 🕐 Attente selon l’intervalle défini pour cet équipement
        await asyncio.sleep(equipement["intervalle"])


async def poll_snmp_data():
    """Lance une tâche asynchrone pour chaque équipement SNMP."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, nom, ip, community, intervalle FROM Equipement;")
    equipements = cur.fetchall()
    conn.close()

    tasks = []
    for equipement in equipements:
        tasks.append(asyncio.create_task(poll_snmp_device(equipement)))

    await asyncio.gather(*tasks)

# --------------------------------------------------------------------
# 🚀 Lancement du serveur
# --------------------------------------------------------------------
def run_flask():
    app.run(host="192.168.141.72", port=5000, debug=True, use_reloader=False)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(poll_snmp_data())

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True  # 👈 ce flag rend le thread “tuable”
    flask_thread.start()

    # Gestion du Ctrl+C
    def shutdown(signal_received=None, frame=None):
        print("\n🛑 Arrêt demandé par l’utilisateur. Fermeture propre...")
        for task in asyncio.all_tasks(loop):
            task.cancel()
        loop.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        shutdown()
