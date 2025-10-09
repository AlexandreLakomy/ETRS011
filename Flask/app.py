from flask import Flask, render_template, redirect, url_for

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

if __name__ == "__main__":
    app.run(host="192.168.141.145", port=5000, debug=True)