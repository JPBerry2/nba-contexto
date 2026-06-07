import random
import numpy as np
from similarity_engine import df, X_categories, category_weights, cosine_similarity, position_similarity

# ------------------------
# Compute similarity for a single guess
# ------------------------
def compute_similarity(player_name, guess_name):
    idx_target = df.index[df["Player"] == player_name][0]
    idx_guess = df.index[df["Player"] == guess_name][0]

    sim_total = 0
    for cat, weight in category_weights.items():
        sim_cat = cosine_similarity(X_categories[cat][idx_target], X_categories[cat][idx_guess])
        sim_total += sim_cat * weight

    # Boost with position similarity
    sim_total = 0.8 * sim_total + 0.2 * position_similarity(
        df.iloc[idx_target]["Pos_code"], df.iloc[idx_guess]["Pos_code"]
    )
    return sim_total

# ------------------------
# Compute similarity percentiles for the target player
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
            sim_cat = cosine_similarity(X_categories[cat][idx_target], X_categories[cat][i])
            sim_total += sim_cat * weight
        sim_total = 0.8 * sim_total + 0.2 * position_similarity(target_pos, df.iloc[i]["Pos_code"])
        sims.append((df.iloc[i]["Player"], sim_total))
    sims.sort(key=lambda x: x[1], reverse=True)

    # Assign percentile ranks
    n = len(sims)
    percentile_dict = {}
    for rank, (player, score) in enumerate(sims, start=1):
        percentile = int((n - rank) / n * 100)
        percentile_dict[player] = percentile
    return percentile_dict

# ------------------------
# Practice game loop
# ------------------------
def practice_game(difficulty="hard"):
    if difficulty == "easy":
        df_pool = df.sort_values("MP_basic", ascending=False).head(150)
    else:
        df_pool = df.copy()

    players_list = df_pool["Player"].tolist()
    target_player = random.choice(players_list)
    target_info = df_pool[df_pool["Player"] == target_player].iloc[0]

    # Precompute percentiles for this target
    percentiles = compute_percentiles(target_player)

    print("\n--- NBA Contexto Practice ---")
    print(f"Difficulty: {difficulty.capitalize()}")
    print("Guess the hidden player!")
    print("Type 'hint' for clues, or 'quit' to end the game.\n")

    while True:
        guess = input("Enter your guess: ").strip()

        if guess.lower() == "quit":
            print("\nYou quit the game.")
            break

        if guess.lower() == "hint":
            print(f"Hint → Position: {target_info['Pos_basic']}, Team: {target_info['Team_basic']}, Age: {target_info['Age_basic']}")
            continue

        if guess not in df_pool["Player"].values:
            print("❌ Player not found in this pool. Try again.")
            continue

        if guess == target_player:
            print(f"\n🎉 Correct! You guessed the hidden player: {target_player}")
            break

        closeness = percentiles.get(guess, 0)
        print(f"Closeness rating: {closeness}/100")

    # Reveal target and top 5
    print("\nThe hidden player was:", target_player)
    top5 = sorted(percentiles.items(), key=lambda x: x[1], reverse=True)[:5]
    print("\nTop 5 most similar players:")
    for name, pct in top5:
        print(f"{name} — {pct}/100")

# ------------------------
# Run
# ------------------------
if __name__ == "__main__":
    diff = input("Select difficulty: easy / hard: ").strip().lower()
    if diff not in ["easy", "hard"]:
        diff = "hard"
    practice_game(difficulty=diff)
