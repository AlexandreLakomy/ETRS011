import signal
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
    db_path = r"C:\Users\Alexa\OneDrive\Documents\M2\ETRS011\Flask\BDD\ETRS711DBROWSER.db"
    
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
            DV.id AS id_valeur,
            DV.donneesEquipement_id,
            DV.oid_id,
            DV.valeur,
            DE.id AS id_donnees,
            DE.moniteur_id,
            DE.timestamp,
            M.id AS id_moniteur,
            M.equipement_id,
            E.id AS id_equipement,
            E.nom AS equipement,
            O.nomParametre
        FROM DonneesValeurs DV
        JOIN DonneesEquipement DE ON DV.donneesEquipement_id = DE.id
        JOIN MoniteurSNMP M ON DE.moniteur_id = M.id
        JOIN Equipement E ON M.equipement_id = E.id
        JOIN OID O ON DV.oid_id = O.id;
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
            CommunityData(community, mpModel=1),
            UdpTransportTarget((ip, 161), timeout=2, retries=1),
            ContextData(),
            ObjectType(ObjectIdentity(oid))
        )

        errorIndication, errorStatus, errorIndex, varBinds = next(iterator)

        if errorIndication:
            return {"status": "DOWN", "info": str(errorIndication)}
        elif errorStatus:
            return {"status": "DOWN", "info": errorStatus.prettyPrint()}
        else:
            for varBind in varBinds:
                return {"status": "UP", "info": str(varBind)}
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
    conn = sqlite3.connect(r"C:\Users\Alexa\OneDrive\Documents\M2\ETRS011\Flask\BDD\ETRS711DBROWSER.db")
    cur = conn.cursor()

    # 1️⃣ Crée un enregistrement dans DonneesEquipement
    cur.execute(
        "INSERT INTO DonneesEquipement (moniteur_id, timestamp) VALUES (?, ?)",
        (equipement_id, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    donnees_equipement_id = cur.lastrowid

    # 2️⃣ Ajoute la valeur SNMP récupérée
    cur.execute(
        "INSERT INTO DonneesValeurs (donneesEquipement_id, oid_id, valeur) VALUES (?, ?, ?)",
        (donnees_equipement_id, oid_id, valeur)
    )

    conn.commit()
    conn.close()


def collect_snmp_data():
    """Collecte et stocke les données SNMP du NAS uniquement."""
    devices = [
        {
            "name": "NAS",
            "ip": "192.168.176.2",
            "community": "passprojet",
            "equipement_id": 1,
            "oid_id": 1,
            "oid": "1.3.6.1.4.1.6574.1.2.0"  # Température NAS Synology
        }
    ]

    for device in devices:
        res = check_snmp_device(device["ip"], device["community"], device["oid"])

        if res["status"] == "UP":
            try:
                # Extraction de la valeur SNMP renvoyée
                valeur_str = res["info"].split("=")[-1].strip()
                valeur = float(valeur_str)
                insert_snmp_value(device["equipement_id"], device["oid_id"], valeur)
                print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] ✅ Donnée enregistrée pour {device['name']} : {valeur}")
            except ValueError:
                print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] ⚠️ Donnée non numérique reçue : {res['info']}")
            except Exception as e:
                print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] ⚠️ Erreur conversion ou insertion SNMP : {e}")
        else:
            print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] ❌ {device['name']} injoignable : {res['info']}")


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
    app.run(host="10.7.253.55", port=5000, debug=True, use_reloader=False)

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
