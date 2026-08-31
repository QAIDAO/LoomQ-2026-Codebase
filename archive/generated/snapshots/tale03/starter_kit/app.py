from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    from adapter import agent_chat
    prompt = request.json["prompt"]
    reply = agent_chat(prompt)
    return jsonify({"reply": reply})

@app.route("/run", methods=["POST"])
def run_circuit():
    from adapter import run
    qasm = request.json["qasm"]
    target = request.json.get("target", "spinq")
    result = run(qasm, target, 8192)
    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True, port=5000)