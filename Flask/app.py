from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "Clément !"

if __name__ == "__main__":
    app.run(host="192.168.141.70", port=5000, debug=True)

