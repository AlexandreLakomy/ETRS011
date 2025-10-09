from flask import Flask, render_template, redirect, url_for
import psycopg2
from psycopg2.extras import RealDictCursor
from pysnmp.hlapi import getCmd, SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity

app = Flask(__name__)

# Page d'accueil
@app.route('/')
def index():
    return render_template('index.html')

# Page de connexion
@app.route('/login')
def login():
    return render_template('login.html')

# Tableau de bord
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

# Page de logs
@app.route('/logs')
def logs():
    return render_template('logs.html')

# Page de configuration (admin)
@app.route('/config')
def config():
    return render_template('config.html')

# Page admin (gestion utilisateurs)
@app.route('/admin')
def admin():
    return render_template('admin.html')

def get_db_connection():
    conn = psycopg2.connect(
        host="localhost",
        database="postgres",
        user="postgres",
        password="alex"  # ton mot de passe PostgreSQL
    )
    return conn

@app.route('/test_base_de_donnee')
def test_base_de_donnee():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
        tables = cur.fetchall()
        cur.close()
        conn.close()
        return render_template('test_base_de_donnee.html', tables=tables)
    except Exception as e:
        return f"Erreur de connexion à la base de données : {e}"
    

# --- Fonction SNMP ---
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


# --- Route Flask ---
@app.route("/snmp_check")
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


if __name__ == "__main__":
    app.run(host="192.168.141.145", port=5000, debug=True)