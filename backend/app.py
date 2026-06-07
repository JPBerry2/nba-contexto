from flask import Flask, request, jsonify
from flask_cors import CORS
import random
import unicodedata
import uuid
from similarity_engine import df, X_categories, category_weights, cosine_similarity, position_similarity

app = Flask(__name__)
CORS(app)

# Infinite Mode In-Memory Sessions Storage
# Format: { "game_uuid_string": { "player": "Name", "percentiles": {...} } }
active_games = {}

# ------------------------
# Normalize names (ignore case + accents)
# ------------------------
def normalize_name(name):
    if not name:
        return ""
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("utf-8")
    return name.lower().strip()

# Create normalized column once globally
df["normalized_name"] = df["Player"].apply(normalize_name)

# ------------------------
# Similarity computation
# ------------------------
def compute_percentiles(target_player):
    idx_target = df.index[df["Player"] == target_player][0]
    target_pos = df.iloc[idx_target]["Pos_code"]

    sims = []
    for i in range(len(df)):
        if i == idx_target:
            continue

        sim_total = 0
        for cat, weight in category_weights.items():
            sim_cat = cosine_similarity(
                X_categories[cat][idx_target],
                X_categories[cat][i]
            )
            sim_total += sim_cat * weight

        sim_total = 0.8 * sim_total + 0.2 * position_similarity(
            target_pos,
            df.iloc[i]["Pos_code"]
        )

        sims.append((df.iloc[i]["Player"], sim_total))

    sims.sort(key=lambda x: x[1], reverse=True)

    n = len(sims)
    percentile_dict = {}
    for rank, (player, score) in enumerate(sims, start=1):
        percentile = int((n - rank) / n * 100)
        percentile_dict[player] = percentile

    return percentile_dict

# ------------------------
# Routes
# ------------------------

@app.route("/players", methods=["GET"])
def get_players():
    return jsonify(sorted(df["Player"].unique().tolist()))

@app.route("/new_game", methods=["GET"])
def new_game():
    difficulty = request.args.get("difficulty", "hard")

    # 1. Filter the pool inside the route based on difficulty selection
    if difficulty == "easy":
        df_pool = df.sort_values("MP_basic", ascending=False).head(150)
    else:
        df_pool = df.copy()

    players_list = df_pool["Player"].tolist()
    
    # 2. CRITICAL FIX: Pick the random player here, dynamically, on EVERY call!
    chosen_player = random.choice(players_list)

    # 3. Compute metric mappings dynamically for this precise random instance
    computed_percentiles = compute_percentiles(chosen_player)
    
    # 4. Save this specific instance linked directly to a fresh tracking ID
    game_id = str(uuid.uuid4())
    active_games[game_id] = {
        "player": chosen_player,
        "percentiles": computed_percentiles
    }

    return jsonify({
        "message": "New game started",
        "difficulty": difficulty,
        "game_id": game_id
    })

@app.route("/guess", methods=["POST"])
def guess():
    data = request.json
    player_guess = data.get("player")
    game_id = data.get("game_id")

    # Validate active instance session lookup
    if not game_id or game_id not in active_games:
        return jsonify({"error": "Session expired or missing. Please restart."}), 400

    current_game = active_games[game_id]
    hidden_player = current_game["player"]
    percentiles = current_game["percentiles"]

    guess_normalized = normalize_name(player_guess)

    if guess_normalized not in df["normalized_name"].values:
        return jsonify({"error": "Player not found"}), 400

    actual_row = df[df["normalized_name"] == guess_normalized].iloc[0]
    actual_name = actual_row["Player"]

    if actual_name == hidden_player:
        # Cleanup memory once a game instance is successfully completed
        active_games.pop(game_id, None)
        return jsonify({
            "correct": True,
            "player": hidden_player
        })

    closeness = percentiles.get(actual_name, 0)

    return jsonify({
        "correct": False,
        "closeness": closeness
    })

@app.route("/hint/<hint_type>", methods=["GET"])
def hint(hint_type):
    game_id = request.args.get("game_id")
    
    if not game_id or game_id not in active_games:
        return jsonify({"error": "Game not found"}), 400

    hidden_player = active_games[game_id]["player"]
    info = df[df["Player"] == hidden_player].iloc[0]

    if hint_type == "age":
        return jsonify({"hint": str(info["Age_basic"])})
    elif hint_type == "position":
        return jsonify({"hint": str(info["Pos_basic"])})
    elif hint_type == "team":
        return jsonify({"hint": str(info["Team_basic"])})
    else:
        return jsonify({"error": "Invalid hint type"}), 400

@app.route("/reveal_answer", methods=["GET"])
def reveal_answer():
    game_id = request.args.get("game_id")
    
    if not game_id or game_id not in active_games:
        return jsonify({"error": "Game session not found"}), 400

    hidden_player = active_games[game_id]["player"]
    
    # Remove instance tracking data upon direct resignation
    active_games.pop(game_id, None)

    return jsonify({
        "player": hidden_player
    })

import os

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)