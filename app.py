from flask import Flask, request, jsonify, g
from flask_cors import CORS
from scipy import stats
import numpy as np
import time
from collections import defaultdict
import sqlite3
import statistics
from flask_socketio import SocketIO


app = Flask(__name__)
CORS(app)
socketIO = SocketIO(app, cors_allowed_origins="*", async_mode = "threading") # Might want to update allowed CORS origins list to enhance security

# def get_conn():
#     if 'db' not in g:
#         g.db = sqlite3.connect("leaderboard.db", timeout=10)
#         g.db.row_factory = sqlite3.Row
#         g.db.execute("PRAGMA journal_mode=WAL")
#     return g.db

def get_conn():
    conn = sqlite3.connect("leaderboard.db", timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn



def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leaderboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            score FLOAT NOT NULL,
            time FLOAT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

def emit_leaderboard():
    try:
        conn = get_conn()
        rows = conn.execute(
            "SELECT name, score, time FROM leaderboard ORDER BY score DESC"
        ).fetchall()
        conn.close()
        socketIO.emit("leaderboard_update", [dict(row) for row in rows])
    except Exception:
        pass

@app.delete("/reset")
def reset():
    conn = get_conn()
    conn.execute("DELETE FROM leaderboard")
    conn.commit()
    conn.close()
    return {"success": "leaderboard cleared"}, 200

@app.post("/add")
def add():
    if request.is_json: 
        data = request.get_json()
        current = time.asctime()
        if not data or "name" not in data or "score" not in data: return {"error": "Bad request"}, 400
        try:
            score = float(data["score"])
        except (TypeError, ValueError):
            return {"error": "score must be a number"}, 400
        conn = get_conn()
        conn.execute("INSERT INTO leaderboard (name, score, time) VALUES (?, ?, ?)",
                     (data["name"], data["score"], current))
        conn.commit()
        conn.close()
        emit_leaderboard()
        return {"success": "entry added"}, 201
    else: return {"error": "Bad request"}, 400

@app.get("/leaderboard")
def get_leaderboard():
    conn = get_conn()
    rows = conn.execute(
        "SELECT name, score, time FROM leaderboard WHERE id IN (SELECT MAX(id) FROM leaderboard GROUP BY name) ORDER BY CAST (score as float) DESC LIMIT 10"
    ).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

    

@app.delete("/remove")
def deleteEntry():
    rq = request.get_json(silent=True)
    if not rq or "name" not in rq: return {"error": "bad request"}, 400
    else: 
        conn = get_conn()
        conn.execute("DELETE FROM leaderboard WHERE name = ?", (rq["name"],))
        conn.commit()
        conn.close()
        emit_leaderboard()
        return {"success": "entry removed"}, 200
    
@app.get("/info")
def info():
    conn = get_conn()
    scores = [row["score"] for row in conn.execute("SELECT score FROM leaderboard").fetchall()]
    conn.close()
    if not scores:
        return {"error": "no entries yet"}, 400
    meanValue = statistics.mean(scores)
    median = statistics.median(scores)
    q4, q3, q2, q1 = np.quantile(scores, [1, 0.75, .5, 0.25])
    iqr = abs(q3 - q1)
    standardDeviation = statistics.stdev(scores) if len(scores) > 1 else 0.0
    skew = float(stats.skew(scores))
    return jsonify({
        "mean": meanValue,
        "median":median,
        "quartiles":(float(q1), float(q2), float(q3), float(q4)),
        "iqr": float(iqr),
        "skew": skew,
        "standard deviation": standardDeviation
        })

endpoint_times = defaultdict(list)

@app.before_request
def start_timer():
    request.start_time = time.time()

@app.after_request
def record_time(response):
    duration = time.time() - request.start_time
    endpoint_times[request.endpoint].append(duration)
    return response 

@app.get("/performance")
def performance():
    averages = {
        endpoint: sum(times) / len(times)
        for endpoint, times in endpoint_times.items()
    }
    return jsonify(averages)

@app.get("/predictions")
def predict():
    conn = get_conn()
    teams = [r["name"] for r in conn.execute("SELECT DISTINCT name FROM leaderboard").fetchall()]
    if not teams:
        return {"error": "unpopulated"}, 400

    predictions = []
    for team in teams:
        laps = [r["score"] for r in conn.execute(
            "SELECT score FROM leaderboard WHERE name = ? ORDER BY time", (team,)
        ).fetchall()]
        if not laps:
            continue
        avg = sum(laps) / len(laps)
        recent = laps[-3:] if len(laps) > 3 else laps
        trend = (sum(recent) / len(recent)) - avg

        predictions.append({
            "team": team,
            "avg_lap_time": round(avg, 3),
            "trend": round(trend, 3),
            "predicted_score": round(avg + trend * .5 , 3),
            "laps_recorded": len(laps),
            "laps_by_time_recorded": laps
        })
    
    conn.close()
    predictions.sort(key= lambda x: x["predicted_score"])
    if predictions:
        predictions[0]["predicted_winner"] = True
    return jsonify(predictions)

socketIO.run(app)


   