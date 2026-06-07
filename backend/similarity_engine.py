import pandas as pd
import numpy as np

print("Initializing Similarity Engine...")

# ------------------------
# 1. LOAD & CLEAN DATA
# ------------------------
try:
    df_basic = pd.read_csv("basic_stats.csv")
    df_advanced = pd.read_csv("advanced_stats.csv")
except FileNotFoundError:
    print("Error: CSV files not found. Ensure basic_stats.csv and advanced_stats.csv are in the workspace.")
    exit()

# Strip out formatting/duplicate artifacts from Basketball-Reference
for data_frame in [df_basic, df_advanced]:
    data_frame.drop(data_frame[data_frame["Player"] == "Player"].index, inplace=True)
    data_frame.drop(data_frame[data_frame["Team"] == "TOT"].index, inplace=True)
    data_frame.drop_duplicates(subset="Player", keep="first", inplace=True)
    data_frame.reset_index(drop=True, inplace=True)

df = pd.merge(df_basic, df_advanced, on="Player", suffixes=('_basic', '_adv'))

# Encode positions cleanly (PG=0, SG=1, SF=2, PF=3, C=4)
position_map = {"PG": 0, "SG": 1, "SF": 2, "PF": 3, "C": 4}
df["Pos_code"] = df["Pos_basic"].map(position_map)

# ------------------------
# 2. FEATURE ARCHITECTURE & INTERNAL WEIGHTS
# ------------------------
category_features = {
    "production": ["PTS_basic", "MP_basic", "AST_basic", "TRB_basic", "STL_basic", "BLK_basic"],
    "style": ["3PAr", "USG%", "AST%", "TS%", "FTr", "PER"]
}

# Sub-weights inside the vectors (must align with array order above)
sub_weights = {
    "production": np.array([0.35, 0.20, 0.15, 0.15, 0.075, 0.075]), # STL and BLK split 15% evenly
    "style": np.array([0.25, 0.20, 0.15, 0.15, 0.15, 0.10])
}

MACRO_WEIGHTS = {
    "physical": 0.20,
    "production": 0.40,
    "style": 0.40
}

# Realistic modern position mapping
POSITION_MATRIX = np.array([
    [1.0, 0.8, 0.4, 0.2, 0.1],  # PG
    [0.8, 1.0, 0.8, 0.3, 0.1],  # SG
    [0.4, 0.8, 1.0, 0.7, 0.3],  # SF
    [0.2, 0.3, 0.7, 1.0, 0.8],  # PF
    [0.1, 0.1, 0.3, 0.8, 1.0]   # C
])

# Clean columns and drop incomplete rows
all_numeric = category_features["production"] + category_features["style"] + ["Age_basic", "Pos_code"]
for col in all_numeric:
    df[col] = pd.to_numeric(df[col], errors='coerce')

df = df.dropna(subset=all_numeric).reset_index(drop=True)
print(f"Data engine ready. Total active players: {len(df)}")

# ------------------------
# 3. VECTOR NORMALIZATION (Z-SCORE)
# ------------------------
def normalize_category(dataframe, features):
    X = dataframe[features].values.astype(float)
    stds = np.std(X, axis=0)
    nonzero_idx = stds != 0
    X_norm = (X[:, nonzero_idx] - np.mean(X[:, nonzero_idx], axis=0)) / stds[nonzero_idx]
    return X_norm

X_categories = {cat: normalize_category(df, feats) for cat, feats in category_features.items()}

# ------------------------
# 4. SIMILARITY LOGIC MATH
# ------------------------
def calculate_physical_sim(player_a, player_b):
    """Calculates non-vector traits between 0.0 and 1.0"""
    # Position logic via proximity matrix
    pos_sim = POSITION_MATRIX[int(player_a["Pos_code"])][int(player_b["Pos_code"])]
    
    # Age proximity: linear penalty of 0.15 per year difference (floor at 0)
    age_diff = abs(player_a["Age_basic"] - player_b["Age_basic"])
    age_sim = max(0.0, 1.0 - (age_diff * 0.15))
    
    # Team match
    team_sim = 1.0 if player_a["Team_basic"] == player_b["Team_basic"] else 0.0
    
    # Blend: 50% Position, 30% Age, 20% Team
    return (0.50 * pos_sim) + (0.30 * age_sim) + (0.20 * team_sim)

def weighted_cosine_similarity(a, b, weights):
    """Applies custom internal attribute weights to vector space before calculation"""
    a_weighted = a * weights
    b_weighted = b * weights
    denominator = np.linalg.norm(a_weighted) * np.linalg.norm(b_weighted)
    if denominator == 0: 
        return 0.0
    return np.dot(a_weighted, b_weighted) / denominator

# ------------------------
# 5. CLI TESTING ENTRY POINT
# ------------------------
def find_similar(player_name, top_n=5):
    if player_name not in df["Player"].values:
        print("Player not found.")
        return

    idx_target = df.index[df["Player"] == player_name][0]
    target_data = df.iloc[idx_target]
    similarities = []

    for i in range(len(df)):
        if i == idx_target:
            continue
            
        comp_data = df.iloc[i]
        
        sim_physical = calculate_physical_sim(target_data, comp_data)
        sim_production = weighted_cosine_similarity(X_categories["production"][idx_target], X_categories["production"][i], sub_weights["production"])
        sim_style = weighted_cosine_similarity(X_categories["style"][idx_target], X_categories["style"][i], sub_weights["style"])
        
        total_score = (
            (MACRO_WEIGHTS["physical"] * sim_physical) +
            (MACRO_WEIGHTS["production"] * sim_production) +
            (MACRO_WEIGHTS["style"] * sim_style)
        )
        similarities.append((df.iloc[i]["Player"], total_score))

    similarities.sort(key=lambda x: x[1], reverse=True)
    print(f"\nTop {top_n} most similar to {player_name}:")
    for name, score in similarities[:top_n]:
        print(f"{name} — Score: {round(score, 3)}")

if __name__ == "__main__":
    find_similar("Stephen Curry", top_n=5)