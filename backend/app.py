from flask import Flask, request, jsonify
from flask_cors import CORS
import random
import unicodedata
import uuid
import hashlib
from datetime import datetime, timezone
import os
import numpy as np
import pandas as pd

# Directly import exact definitions exported by similarity_engine.py
from similarity_engine import (
    df,
    X_categories,
    MACRO_WEIGHTS,
    sub_weights,
    hybrid_similarity,
    calculate_physical_sim,
)

app = Flask(__name__)
CORS(app)

# Session memory map tracking active match profiles
active_games = {}


def normalize_name(name):
    if not name:
        return ""
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("utf-8")
    return name.lower().strip()


df["normalized_name"] = df["Player"].apply(normalize_name)

# ---------------------------------------------------------------------------
# Dynamic Percentile & Similarity Metric Computations
# ---------------------------------------------------------------------------
def compute_percentiles(target_player):
    idx_target = df.index[df["Player"] == target_player][0]
    target_data = df.iloc[idx_target]

    raw_scores = []

    # Pass 1: Compute raw macro similarity scores across active dataset
    for i in range(len(df)):
        if i == idx_target:
            raw_scores.append(-999)  # Self placeholder
            continue

        comp_data = df.iloc[i]

        sim_physical = calculate_physical_sim(target_data, comp_data)
        sim_production = hybrid_similarity(
            X_categories["production"][idx_target],
            X_categories["production"][i],
            sub_weights["production"],
        )
        sim_style = hybrid_similarity(
            X_categories["style"][idx_target],
            X_categories["style"][i],
            sub_weights["style"],
        )
        sim_aesthetic = hybrid_similarity(
            X_categories["aesthetic"][idx_target],
            X_categories["aesthetic"][i],
            sub_weights["aesthetic"],
        )

        raw_score = (
            (MACRO_WEIGHTS["physical"] * sim_physical)
            + (MACRO_WEIGHTS["production"] * sim_production)
            + (MACRO_WEIGHTS["style"] * sim_style)
            + (MACRO_WEIGHTS["aesthetic"] * sim_aesthetic)
        )
        raw_scores.append(raw_score)

    raw_scores = np.array(raw_scores)

    # Pass 2: Global Min-Max Stretch (scale score dynamically from 1 to 100)
    valid_scores = raw_scores[raw_scores != -999]
    min_s, max_s = valid_scores.min(), valid_scores.max()

    percentile_dict = {}
    for i in range(len(df)):
        if i == idx_target:
            continue

        if max_s - min_s == 0:
            scaled_score = 50.0
        else:
            scaled_score = 1.0 + (raw_scores[i] - min_s) * (99.0 / (max_s - min_s))

        percentile_dict[df.iloc[i]["Player"]] = int(round(scaled_score))

    return percentile_dict


# ---------------------------------------------------------------------------
# API ROUTE PIPELINES
# ---------------------------------------------------------------------------


@app.route("/players", methods=["GET"])
def get_players():
    return jsonify(sorted(df["Player"].unique().tolist()))


@app.route("/new_game", methods=["GET"])
def new_game():
    """Infinite Mode: Purely randomized selection on every request."""
    difficulty = request.args.get("difficulty", "hard")

    if difficulty == "easy":
        df_pool = df.sort_values("MP_basic", ascending=False).head(150)
    else:
        df_pool = df.copy()

    players_list = df_pool["Player"].tolist()
    chosen_player = random.choice(players_list)

    computed_percentiles = compute_percentiles(chosen_player)

    game_id = str(uuid.uuid4())
    active_games[game_id] = {
        "player": chosen_player,
        "percentiles": computed_percentiles,
        "mode": "infinite",
    }

    return jsonify(
        {
            "message": "New infinite game started",
            "difficulty": difficulty,
            "game_id": game_id,
        }
    )


@app.route("/new_daily_game", methods=["GET"])
def new_daily_game():
    """Daily Challenge: Deterministic selection based on current global calendar date."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    players_list = sorted(df["Player"].unique().tolist())

    hash_object = hashlib.md5(today_str.encode("utf-8"))
    hash_hex = hash_object.hexdigest()

    seed_index = int(hash_hex, 16) % len(players_list)
    chosen_player = players_list[seed_index]

    computed_percentiles = compute_percentiles(chosen_player)

    game_id = f"daily_{today_str}_{str(uuid.uuid4())[:8]}"
    active_games[game_id] = {
        "player": chosen_player,
        "percentiles": computed_percentiles,
        "mode": "daily",
    }

    return jsonify(
        {
            "message": "Daily challenge loaded",
            "game_id": game_id,
            "date": today_str,
        }
    )


@app.route("/guess", methods=["POST"])
def guess():
    data = request.json
    player_guess = data.get("player")
    game_id = data.get("game_id")

    if not game_id or game_id not in active_games:
        return (
            jsonify({"error": "Session expired or missing. Please restart."}),
            400,
        )

    current_game = active_games[game_id]
    hidden_player = current_game["player"]
    percentiles = current_game["percentiles"]

    guess_normalized = normalize_name(player_guess)

    if guess_normalized not in df["normalized_name"].values:
        return jsonify({"error": "Player not found"}), 400

    actual_row = df[df["normalized_name"] == guess_normalized].iloc[0]
    actual_name = actual_row["Player"]

    if actual_name == hidden_player:
        # Extract top 3 closest matches
        sorted_matches = sorted(
            percentiles.items(), key=lambda x: x[1], reverse=True
        )
        top_matches = [
            m[0] for m in sorted_matches if m[0] != hidden_player
        ][:3]

        if current_game["mode"] == "infinite":
            active_games.pop(game_id, None)

        return jsonify(
            {
                "correct": True,
                "player": hidden_player,
                "top_matches": top_matches,
            }
        )

    closeness = percentiles.get(actual_name, 0)

    return jsonify({"correct": False, "closeness": closeness})


@app.route("/hint/<hint_type>", methods=["GET"])
def hint(hint_type):
    game_id = request.args.get("game_id")

    if not game_id or game_id not in active_games:
        return jsonify({"error": "Game not found"}), 400

    hidden_player = active_games[game_id]["player"]
    info = df[df["Player"] == hidden_player].iloc[0]

    try:
        if hint_type == "age":
            val = info.get(
                "AGE",
                info.get(
                    "Age", info.get("AGE_BASIC", info.get("Age_basic", None))
                ),
            )
            if pd.isna(val) or val == 0 or val == 0.0:
                hint_str = "Unknown"
            else:
                hint_str = str(int(float(val)))
            return jsonify({"hint": hint_str})
        elif hint_type == "position":
            val = info.get(
                "Pos_basic",
                info.get(
                    "POS_BASIC", info.get("Pos", info.get("POS", "Unknown"))
                ),
            )
            return jsonify({"hint": str(val)})
        elif hint_type == "team":
            val = info.get(
                "Team_basic",
                info.get(
                    "TEAM_BASIC", info.get("Team", info.get("TEAM", "Unknown"))
                ),
            )
            return jsonify({"hint": str(val)})
        else:
            return jsonify({"error": "Invalid hint type"}), 400
    except Exception as e:
        return jsonify({"error": f"Could not fetch hint: {str(e)}"}), 500


@app.route("/reveal_answer", methods=["GET"])
def reveal_answer():
    game_id = request.args.get("game_id")

    if not game_id or game_id not in active_games:
        return jsonify({"error": "Game session not found"}), 400

    current_game = active_games[game_id]
    hidden_player = current_game["player"]
    percentiles = current_game["percentiles"]

    # Extract top 3 closest matches on reveal/forfeit
    sorted_matches = sorted(
        percentiles.items(), key=lambda x: x[1], reverse=True
    )
    top_matches = [m[0] for m in sorted_matches if m[0] != hidden_player][:3]

    active_games.pop(game_id, None)

    return jsonify({"player": hidden_player, "top_matches": top_matches})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Deploy Sync: Binding explicitly to port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)