import pandas as pd
import numpy as np

# ------------------------
# 1. LOAD CSVs
# ------------------------
print("Script is running...")

try:
    df_basic = pd.read_csv("basic_stats.csv")
    df_advanced = pd.read_csv("advanced_stats.csv")
except FileNotFoundError:
    print("Error: CSV files not found. Make sure they are in the src folder.")
    exit()

# Remove repeated headers and TOT rows
for df in [df_basic, df_advanced]:
    df.drop(df[df["Player"] == "Player"].index, inplace=True)
    df.drop(df[df["Team"] == "TOT"].index, inplace=True)
    df.drop_duplicates(subset="Player", keep="first", inplace=True)
    df.reset_index(drop=True, inplace=True)

# Merge on Player
df = pd.merge(df_basic, df_advanced, on="Player", suffixes=('_basic', '_adv'))

print(f"Players loaded: {len(df)}")

# ------------------------
# 2. ENCODE CATEGORICAL FEATURES
# ------------------------
position_map = {"PG": 0, "SG": 1, "SF": 2, "PF": 3, "C": 4}
df["Pos_code"] = df["Pos_basic"].map(position_map)

# ------------------------
# 3. DEFINE CATEGORIES AND FEATURES
# ------------------------
category_features = {
    "offense": ["PTS_basic","AST_basic","FG%_basic","3P%_basic","FT%_basic",
                "PER","TS%","3PAr","FTr","AST%","USG%","OBPM"],
    "defense": ["TRB_basic","STL_basic","BLK_basic","DRB%","TRB%","STL%","BLK%","DBPM"],
    "role": ["MP_basic","PER","USG%","WS/48","VORP","Pos_code"]
}

category_weights = {
    "offense": 0.40,
    "defense": 0.25,
    "role": 0.35
}

# Keep only features that exist
for cat in category_features:
    category_features[cat] = [f for f in category_features[cat] if f in df.columns]

# ------------------------
# 4. FORCE NUMERIC + DROP INVALIDS
# ------------------------
numeric_features = []
for feats in category_features.values():
    numeric_features.extend(feats)

for col in numeric_features:
    df[col] = pd.to_numeric(df[col], errors='coerce')

# Drop rows with NaN in numeric features
df = df.dropna(subset=numeric_features).reset_index(drop=True)

# ------------------------
# 5. NORMALIZE FEATURES
# ------------------------
def normalize_category(df, features):
    X = df[features].values.astype(float)
    # Remove zero std columns
    stds = np.std(X, axis=0)
    nonzero_idx = stds != 0
    X_norm = (X[:, nonzero_idx] - np.mean(X[:, nonzero_idx], axis=0)) / stds[nonzero_idx]
    return X_norm

X_categories = {cat: normalize_category(df, feats) for cat, feats in category_features.items()}

# ------------------------
# 6. COSINE SIMILARITY
# ------------------------
def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def position_similarity(pos_a, pos_b):
    diff = abs(pos_a - pos_b)
    if diff == 0:
        return 1.0
    elif diff == 1:
        return 0.7
    else:
        return 0.4

# ------------------------
# 7. FIND SIMILAR PLAYERS
# ------------------------
def find_similar(player_name, top_n=5):
    if player_name not in df["Player"].values:
        print("Player not found.")
        return

    idx = df.index[df["Player"] == player_name][0]
    target_pos = df.iloc[idx]["Pos_code"]

    similarities = []

    for i in range(len(df)):
        if i == idx:
            continue

        sim_total = 0
        for cat, weight in category_weights.items():
            sim_cat = cosine_similarity(X_categories[cat][idx], X_categories[cat][i])
            sim_total += sim_cat * weight

        # Boost by position similarity
        sim_total = 0.8 * sim_total + 0.2 * position_similarity(target_pos, df.iloc[i]["Pos_code"])
        similarities.append((df.iloc[i]["Player"], sim_total))

    similarities.sort(key=lambda x: x[1], reverse=True)

    print(f"\nTop {top_n} most similar to {player_name}:\n")
    for name, score in similarities[:top_n]:
        print(f"{name} — Similarity: {round(score, 3)}")

# ------------------------
# 8. TEST
# ------------------------
if __name__ == "__main__":
    find_similar("Stephen Curry", top_n=5)

