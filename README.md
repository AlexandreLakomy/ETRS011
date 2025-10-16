# ETRS011
Creér un environnement VSCode adapté

Sur VSCode, accéder au dossier ETRS011 :
py -3.11 -m venv .venv
.\.venv\Scripts\activate
python.exe -m pip install --upgrade pip
pip install pysnmp==4.4.12 pyasn1==0.4.8
pip install flask
pip install psycopg2
python Flask/app.py