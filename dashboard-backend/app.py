from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# MongoDB connection
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/dashboard")
client = MongoClient(MONGO_URI)
db = client.get_database()  # Uses the database from the URI

@app.route("/api/progress", methods=["GET"])
def get_progress():
    doc = db.progress.find_one() or {"progress": 0, "current_task": ""}
    return jsonify({"progress": doc.get("progress", 0), "current_task": doc.get("current_task", "")})

@app.route("/api/progress", methods=["POST"])
def set_progress():
    data = request.get_json()
    db.progress.update_one({}, {"$set": {
        "progress": data.get("progress", 0),
        "current_task": data.get("current_task", "")
    }}, upsert=True)
    return jsonify({"status": "ok"})

@app.route("/api/chat", methods=["GET"])
def get_chat():
    messages = list(db.chat.find({}, {"_id": 0}))
    return jsonify(messages)

@app.route("/api/chat", methods=["POST"])
def post_chat():
    data = request.get_json()
    msg = {
        "sender": data.get("sender", "Anonymous"),
        "message": data.get("message", ""),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    db.chat.insert_one(msg)
    return jsonify({"status": "ok", "message": msg})

if __name__ == "__main__":
    app.run(debug=True)