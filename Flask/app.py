from flask import Flask, render_template
from pysnmp.hlapi import getCmd, SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
import sqlite3

app = Flask(__name__)

# --- Connexion à la base SQLite ---
def get_db_connection():
    conn = sqlite3.connect("BDD/ETRS711DBROWSER.db")
    conn.row_factory = sqlite3.Row
    return conn


# --------------------------------------------------------------------
# 🏠 Page d'accueil
# --------------------------------------------------------------------
@app.route('/')
def home():
    return render_template('index.html')


# --------------------------------------------------------------------
# 🔍 Test de la base de données (SQLite)
# --------------------------------------------------------------------
@app.route('/bdd')
def test_bdd():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row['name'] for row in cur.fetchall()]
        conn.close()
        return render_template('test_base_de_donnee.html', tables=tables)
    except Exception as e:
        return f"Erreur lors de la connexion à la base SQLite : {e}"


# --------------------------------------------------------------------
# 📊 Tableau de bord : affichage des données SQLite
# --------------------------------------------------------------------
@app.route('/dashboard')
def dashboard():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT E.nom AS equipement, O.nomParametre, DV.valeur, DE.timestamp
        FROM DonneesValeurs DV
        JOIN DonneesEquipement DE ON DV.donneesEquipement_id = DE.id
        JOIN MoniteurSNMP M ON DE.moniteur_id = M.id
        JOIN Equipement E ON M.equipement_id = E.id
        JOIN OID O ON DV.oid_id = O.id
        ORDER BY DE.timestamp DESC
        LIMIT 20
    """)
    data = cur.fetchall()
    conn.close()
    return render_template('dashboard.html', data=data)


# --------------------------------------------------------------------
# 🧠 Fonction SNMP : vérifie l’état des équipements
# --------------------------------------------------------------------
def check_snmp_device(ip, community):
    try:
        iterator = getCmd(
            SnmpEngine(),
            CommunityData(community, mpModel=1),
            UdpTransportTarget((ip, 161), timeout=2, retries=1),
            ContextData(),
            ObjectType(ObjectIdentity('1.3.6.1.2.1.1.1.0'))
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
# 📡 Vérification SNMP
# --------------------------------------------------------------------
@app.route('/snmp')
def snmp_check():
    devices = [
        {"name": "NAS", "ip": "192.168.176.2", "community": "passprojet"},
        {"name": "Switch", "ip": "192.168.140.141", "community": "passprojet"}
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

    return render_template("snmp_check.html", results=results)


# --------------------------------------------------------------------
# ⚙️ Autres pages du site
# --------------------------------------------------------------------
@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/logs')
def logs():
    return render_template('logs.html')

@app.route('/config')
def config():
    return render_template('config.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')


# --------------------------------------------------------------------
# 🚀 Lancement du serveur Flask
# --------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="192.168.141.145", port=5000, debug=True)
