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

# Force headers to uppercase and strip hidden trailing spaces or newlines
df_basic.columns = df_basic.columns.str.strip().str.upper()
df_advanced.columns = df_advanced.columns.str.strip().str.upper()

# Strip out formatting/duplicate artifacts from Basketball-Reference
for data_frame in [df_basic, df_advanced]:
    data_frame.drop(data_frame[data_frame["PLAYER"] == "PLAYER"].index, inplace=True)
    data_frame.drop(data_frame[data_frame["TEAM"] == "TOT"].index, inplace=True)
    data_frame.drop_duplicates(subset="PLAYER", keep="first", inplace=True)
    data_frame.reset_index(drop=True, inplace=True)

# Post-Merge Suffix Cleanup Fix:
# Explicitly map basic stats columns to have the lowercase '_basic' suffix while protecting 'PLAYER'
basic_rename_map = {col: f"{col.upper()}_basic" for col in df_basic.columns if col != "PLAYER"}
df_basic = df_basic.rename(columns=basic_rename_map)

# Merge on standardized uppercase 'PLAYER' key column
df = pd.merge(df_basic, df_advanced, left_on="PLAYER", right_on="PLAYER")
df = df.rename(columns={"PLAYER": "Player"})  # Retain compatibility for app.py

# Encode positions cleanly (PG=0, SG=1, SF=2, PF=3, C=4)


pos_col = "POS_BASIC" if "POS_BASIC" in df.columns else ("POS" if "POS" in df.columns else None)
if pos_col:
    position_map = {"PG": 0, "SG": 1, "SF": 2, "PF": 3, "C": 4}
    # Map, and fill any weird/missing positions with a default center/forward index (2)
    df["Pos_code"] = df[pos_col].map(position_map).fillna(2).astype(int)
else:
    df["Pos_code"] = 2

# ------------------------
# 2. FEATURE ARCHITECTURE & INTERNAL WEIGHTS
# ------------------------
category_features = {
    "production": ["PTS_basic", "MP_basic", "AST_basic", "TRB_basic", "STL_basic", "BLK_basic"],
    "style": ["3PAr", "USG%", "AST%", "TS%", "FTr", "PER"]
}

# Dynamically clean/match case styles for the advanced metrics if they are uppercase in your source CSV
for idx, style_feat in enumerate(category_features["style"]):
    for actual_col in df.columns:
        if style_feat.upper() == actual_col.upper():
            category_features["style"][idx] = actual_col

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

# Clean columns and drop incomplete rows safely
all_numeric = category_features["production"] + category_features["style"] + ["Age_basic", "Pos_code"]
for col in all_numeric:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    else:
        # Fallback layout to guarantee Render won't crash your server on boot
        print(f"⚠️ Warning: Expected column {col} was missing from DataFrame. Creating fallback empty array values.")
        df[col] = 0.0

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
    
    # Safe lookup for age (handles 'Age_basic', 'Age', or defaults to 0)
    age_a = player_a.get("Age_basic", player_a.get("Age", 0))
    age_b = player_b.get("Age_basic", player_b.get("Age", 0))
    age_diff = abs(age_a - age_b)
    age_sim = max(0.0, 1.0 - (age_diff * 0.15))
    
    # Safe lookup for team (handles 'Team_basic', 'Team', or defaults to '')
    team_a = player_a.get("Team_basic", player_a.get("Team", ""))
    team_b = player_b.get("Team_basic", player_b.get("Team", ""))
    team_sim = 1.0 if team_a == team_b else 0.0
    
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