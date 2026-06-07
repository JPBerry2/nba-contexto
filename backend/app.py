from flask import Flask, request, jsonify
from flask_cors import CORS
import random
import unicodedata
from similarity_engine import df, X_categories, category_weights, cosine_similarity, position_similarity

app = Flask(__name__)
CORS(app)

hidden_player = None
percentiles = {}

# ------------------------
# Normalize names (ignore case + accents)
# ------------------------
def normalize_name(name):
    if not name:
        return ""
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("utf-8")
    return name.lower().strip()

# Create normalized column once
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
    global hidden_player, percentiles

    difficulty = request.args.get("difficulty", "hard")

    if difficulty == "easy":
        df_pool = df.sort_values("MP_basic", ascending=False).head(150)
    else:
        df_pool = df.copy()

    players_list = df_pool["Player"].tolist()
    hidden_player = random.choice(players_list)

    percentiles = compute_percentiles(hidden_player)

    return jsonify({
        "message": "New game started",
        "difficulty": difficulty
    })

@app.route("/guess", methods=["POST"])
def guess():
    global hidden_player, percentiles

    data = request.json
    player_guess = data.get("player")

    guess_normalized = normalize_name(player_guess)

    # Validate guess
    if guess_normalized not in df["normalized_name"].values:
        return jsonify({"error": "Player not found"}), 400

    # Get actual formatted name
    actual_row = df[df["normalized_name"] == guess_normalized].iloc[0]
    actual_name = actual_row["Player"]

    if actual_name == hidden_player:
        return jsonify({
            "correct": True,
            "player": hidden_player
        })

    closeness = percentiles.get(actual_name, 0)

    return jsonify({
        "correct": False,
        "closeness": closeness
    })

# ------------------------
# Separate Hint Routes
# ------------------------

@app.route("/hint/<hint_type>", methods=["GET"])
def hint(hint_type):
    global hidden_player

    if hidden_player is None:
        return jsonify({"error": "No game in progress"}), 400

    info = df[df["Player"] == hidden_player].iloc[0]

    if hint_type == "age":
        return jsonify({"hint": info["Age_basic"]})
    elif hint_type == "position":
        return jsonify({"hint": info["Pos_basic"]})
    elif hint_type == "team":
        return jsonify({"hint": info["Team_basic"]})
    else:
        return jsonify({"error": "Invalid hint type"}), 400


import os

if __name__ == '__main__':
    # Render tells the app which port to use; defaults to 5000 locally
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)