from flask import Flask, request, jsonify
from flask_cors import CORS
import random
import unicodedata
import os
from similarity_engine import (
    df, 
    X_categories, 
    sub_weights, 
    MACRO_WEIGHTS, 
    calculate_physical_sim, 
    weighted_cosine_similarity
)

app = Flask(__name__)
CORS(app)

hidden_player = None
percentiles = {}

# Normalize incoming name string inputs
def normalize_name(name):
    if not name:
        return ""
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("utf-8")
    return name.lower().strip()

# Build index helper column
df["normalized_name"] = df["Player"].apply(normalize_name)

# ------------------------
# SIMILARITY SCHEDULER
# ------------------------
def compute_percentiles(target_player):
    idx_target = df.index[df["Player"] == target_player][0]
    target_data = df.iloc[idx_target]

    sims = []
    for i in range(len(df)):
        if i == idx_target:
            continue

        comp_data = df.iloc[i]
        
        # 20% Physical / Identity Attributes
        sim_physical = calculate_physical_sim(target_data, comp_data)
        
        # 40% Volume Production
        sim_production = weighted_cosine_similarity(
            X_categories["production"][idx_target],
            X_categories["production"][i],
            sub_weights["production"]
        )
        
        # 40% Efficiency and Playing Style Matrix
        sim_style = weighted_cosine_similarity(
            X_categories["style"][idx_target],
            X_categories["style"][i],
            sub_weights["style"]
        )

        # Balanced aggregate score
        sim_total = (
            (MACRO_WEIGHTS["physical"] * sim_physical) +
            (MACRO_WEIGHTS["production"] * sim_production) +
            (MACRO_WEIGHTS["style"] * sim_style)
        )
        sims.append((df.iloc[i]["Player"], sim_total))

    # Rank high scores first
    sims.sort(key=lambda x: x[1], reverse=True)

    n = len(sims)
    percentile_dict = {}
    for rank, (player, score) in enumerate(sims, start=1):
        percentile = int((n - rank) / n * 100)
        percentile_dict[player] = max(1, percentile) # Clamps floor at 1% instead of 0%

    return percentile_dict

# ------------------------
# API ENDPOINTS
# ------------------------
@app.route("/players", methods=["GET"])
def get_players():
    return jsonify(sorted(df["Player"].unique().tolist()))

@app.route("/new_game", methods=["GET"])
def new_game():
    global hidden_player, percentiles

    difficulty = request.args.get("difficulty", "hard")

    # Safely select player without breaking structural DataFrame index bounds
    if difficulty == "easy":
        df_pool = df.sort_values("MP_basic", ascending=False).head(150)
    else:
        df_pool = df

    players_list = df_pool["Player"].tolist()
    hidden_player = random.choice(players_list)

    # Computes scores safely utilizing complete index bounds
    percentiles = compute_percentiles(hidden_player)

    return jsonify({
        "message": "New game started",
        "difficulty": difficulty
    })

@app.route("/guess", methods=["POST"])
def guess():
    global hidden_player, percentiles

    data = request.json or {}
    player_guess = data.get("player")

    guess_normalized = normalize_name(player_guess)

    if guess_normalized not in df["normalized_name"].values:
        return jsonify({"error": "Player not found"}), 400

    actual_row = df[df["normalized_name"] == guess_normalized].iloc[0]
    actual_name = actual_row["Player"]

    if actual_name == hidden_player:
        return jsonify({
            "correct": True,
            "player": hidden_player
        })

    closeness = percentiles.get(actual_name, 1)

    return jsonify({
        "correct": False,
        "closeness": closeness
    })

@app.route("/hint/<hint_type>", methods=["GET"])
def hint(hint_type):
    global hidden_player

    if hidden_player is None:
        return jsonify({"error": "No game in progress"}), 400

    info = df[df["Player"] == hidden_player].iloc[0]

    if hint_type == "age":
        return jsonify({"hint": int(info["Age_basic"])})
    elif hint_type == "position":
        return jsonify({"hint": str(info["Pos_basic"])})
    elif hint_type == "team":
        return jsonify({"hint": str(info["Team_basic"])})
    else:
        return jsonify({"error": "Invalid hint type"}), 400

@app.route("/reveal_answer", methods=["GET"])
def reveal_answer():
    global hidden_player

    if hidden_player is None:
        return jsonify({"error": "No game in progress"}), 400

    return jsonify({
        "player": hidden_player
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)