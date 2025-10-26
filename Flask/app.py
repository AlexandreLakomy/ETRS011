import signal
import sys
from flask import Flask, render_template # type: ignore
from pysnmp.hlapi import getCmd, SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity # type: ignore
import sqlite3
import os
import datetime
import asyncio
import threading, time

app = Flask(__name__)

# --------------------------------------------------------------------
# 🔌 Connexion à la base SQLite
# --------------------------------------------------------------------
def get_db_connection():
    # Chemin absolu vers ta base de données
    db_path = r"C:\Users\Alexa\OneDrive\Documents\M2\ETRS011\Flask\BDD\BDD_LeFlour"
    
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Base de données introuvable à l'emplacement : {db_path}")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# --------------------------------------------------------------------
# 🏠 Page d'accueil
# --------------------------------------------------------------------
@app.route('/')
def index():
    return render_template('index.html')


# --------------------------------------------------------------------
# 🔑 Page de connexion
# --------------------------------------------------------------------
@app.route('/login')
def login():
    return render_template('login.html')


# --------------------------------------------------------------------
# 📊 Tableau de bord (données SQLite)
# --------------------------------------------------------------------
@app.route('/dashboard')
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
# 📜 Logs
# --------------------------------------------------------------------
@app.route('/logs')
def logs():
    return render_template('logs.html')

# --------------------------------------------------------------------
# ⚙️ Configuration
# --------------------------------------------------------------------
@app.route('/config')
def config():
    return render_template('config.html')


# --------------------------------------------------------------------
# 👥 Administration
# --------------------------------------------------------------------
@app.route('/admin')
def admin():
    return render_template('admin.html')


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
            return {"status": "UP", "info": str(varBinds[0])}

    except Exception as e:
        return {"status": "DOWN", "info": str(e)}


# --------------------------------------------------------------------
# 🛰️ Vérification SNMP (NAS + Switch)
# --------------------------------------------------------------------
@app.route("/snmp_check")
def snmp_check():
    devices = [
        {"name": "NAS", "ip": "192.168.176.2", "community": "passprojet", "equipement_id": 1, "oid_id": 1, "oid": "1.3.6.1.4.1.6574.1.2.0"},  # Température NAS
        {"name": "Switch", "ip": "192.168.140.141", "community": "passprojet", "equipement_id": 2, "oid_id": 2, "oid": "1.3.6.1.4.1.9.2.1.58.0"}  # Température Cisco
    ]

    results = []

    for device in devices:
        res = check_snmp_device(device["ip"], device["community"])
        results.append({
            "name": device["name"],
            "ip": device["ip"],
            "status": res["status"],
            "info": res["info"]
        })

        # Si le device répond, on enregistre la valeur
        if res["status"] == "UP":
            try:
                valeur = float(res["info"].split("=")[-1].strip())  # extrait la valeur SNMP brute
                insert_snmp_value(device["equipement_id"], device["oid_id"], valeur)
            except Exception:
                pass  # évite une erreur si la valeur n'est pas numérique

    return render_template("snmp_check.html", results=results)


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

        # 2️⃣ Récupérer les OID associés à cet équipement
        cur.execute("SELECT id, identifiant, nomParametre FROM OID WHERE equipement_id = ?", (equipement_id,))
        oids = cur.fetchall()

        for oid in oids:
            oid_id = oid["id"]
            oid_value = oid["identifiant"]
            param_name = oid["nomParametre"]

            # 3️⃣ Interroger le périphérique via SNMP
            res = check_snmp_device(equipement_ip, community, oid_value)

            if res["status"] == "UP":
                try:
                    valeur_str = res["info"].split("=")[-1].strip()
                    valeur = float(valeur_str)
                    insert_snmp_value(equipement_id, oid_id, valeur)
                    print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] ✅ {param_name} ({equipement_nom}) = {valeur}")
                except ValueError:
                    print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] ⚠️ Valeur non numérique reçue pour {param_name} ({equipement_nom}) : {res['info']}")
                except Exception as e:
                    print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] ⚠️ Erreur d’insertion pour {param_name} ({equipement_nom}) : {e}")
            else:
                print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] ❌ {equipement_nom} injoignable : {res['info']}")

    conn.close()


async def poll_snmp_data():
    """Tâche asynchrone qui interroge périodiquement les équipements SNMP."""
    while True:
        print("⏳ Vérification SNMP automatique en cours...")
        try:
            with app.app_context():
                collect_snmp_data()  # ⚡ collecte sans HTML
        except Exception as e:
            print(f"Erreur lors du polling SNMP : {e}")
        await asyncio.sleep(60 - datetime.datetime.now().second % 60)


# --------------------------------------------------------------------
# 🚀 Lancement du serveur
# --------------------------------------------------------------------
def run_flask():
    app.run(host="10.7.253.61", port=5000, debug=True, use_reloader=False)

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
