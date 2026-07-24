import numpy as np
import pandas as pd

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

# Force headers to uppercase and strip trailing spaces/hidden characters
df_basic.columns = df_basic.columns.str.strip().str.upper()
df_advanced.columns = df_advanced.columns.str.strip().str.upper()

for data_frame in [df_basic, df_advanced]:
    data_frame.drop(data_frame[data_frame["PLAYER"] == "PLAYER"].index, inplace=True)
    if "TEAM" in data_frame.columns:
        data_frame.drop(data_frame[data_frame["TEAM"] == "TOT"].index, inplace=True)
    data_frame.drop_duplicates(subset="PLAYER", keep="first", inplace=True)
    data_frame.reset_index(drop=True, inplace=True)

# Standardize PLAYER column
df_basic = df_basic.rename(columns={col: f"{col.upper()}_basic" for col in df_basic.columns if col != "PLAYER"})
df = pd.merge(df_basic, df_advanced, left_on="PLAYER", right_on="PLAYER")
df = df.rename(columns={"PLAYER": "Player"})

# Encode positions cleanly (PG=0, SG=1, SF=2, PF=3, C=4)
pos_col = "POS_BASIC" if "POS_BASIC" in df.columns else ("POS" if "POS" in df.columns else "POS_ADVANCED")
position_map = {"PG": 0, "SG": 1, "SF": 2, "PF": 3, "C": 4}
df["Pos_code"] = df.get(pos_col, "SF").map(position_map).fillna(2).astype(int)

# ------------------------
# 2. FEATURE ARCHITECTURE & WEIGHTS
# ------------------------
category_features = {
    "production": ["TRB%", "AST%", "STL%", "BLK%"],
    "style": ["3PAr", "USG%", "OBPM", "DBPM"],
    "aesthetic": ["TS%", "EFG%", "WS/48"]  # Re-introduced efficiency footprint
}

# Dynamic column matcher
for cat, feats in category_features.items():
    for idx, feat in enumerate(feats):
        for actual_col in df.columns:
            if feat.upper() == actual_col.upper():
                category_features[cat][idx] = actual_col

sub_weights = {
    "production": np.array([0.30, 0.30, 0.20, 0.20]),
    "style": np.array([0.30, 0.30, 0.20, 0.20]),
    "aesthetic": np.array([0.40, 0.40, 0.20])
}

MACRO_WEIGHTS = {
    "physical": 0.10,
    "production": 0.35,
    "style": 0.35,
    "aesthetic": 0.20
}

POSITION_MATRIX = np.array([
    [1.0, 0.8, 0.4, 0.2, 0.1],  # PG
    [0.8, 1.0, 0.8, 0.3, 0.1],  # SG
    [0.4, 0.8, 1.0, 0.7, 0.3],  # SF
    [0.2, 0.3, 0.7, 1.0, 0.8],  # PF
    [0.1, 0.1, 0.3, 0.8, 1.0]   # C
])

all_numeric = category_features["production"] + category_features["style"] + category_features["aesthetic"] + ["AGE_BASIC", "POS_CODE"]
for col in all_numeric:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    else:
        df[col] = 0.0

df = df.dropna(subset=all_numeric).reset_index(drop=True)
print(f"Data engine ready. Total active players: {len(df)}")

# ------------------------
# 3. SAFE VECTOR NORMALIZATION (Z-SCORE)
# ------------------------
def normalize_category(dataframe, features):
    X = dataframe[features].values.astype(float)
    stds = np.std(X, axis=0)
    means = np.mean(X, axis=0)
    
    # Safe handling: if std is 0, assign zero array instead of dropping dimensions
    X_norm = np.zeros_like(X)
    nonzero_idx = stds != 0
    X_norm[:, nonzero_idx] = (X[:, nonzero_idx] - means[nonzero_idx]) / stds[nonzero_idx]
    return X_norm

X_categories = {cat: normalize_category(df, feats) for cat, feats in category_features.items()}

# ------------------------
# 4. SIMILARITY LOGIC MATH
# ------------------------
def calculate_physical_sim(player_a, player_b):
    pos_sim = POSITION_MATRIX[int(player_a["POS_CODE"])][int(player_b["POS_CODE"])]
    
    age_a = player_a.get("AGE_BASIC", player_a.get("AGE", 25))
    age_b = player_b.get("AGE_BASIC", player_b.get("AGE", 25))
    age_diff = abs(age_a - age_b)
    age_sim = max(0.0, 1.0 - (age_diff * 0.15))
    
    return (0.70 * pos_sim) + (0.30 * age_sim)

def weighted_cosine_similarity(a, b, weights):
    a_weighted = a * weights
    b_weighted = b * weights
    denominator = np.linalg.norm(a_weighted) * np.linalg.norm(b_weighted)
    if denominator == 0: 
        return 0.0
    similarity = np.dot(a_weighted, b_weighted) / denominator
    # Clip negative correlation to 0.0 to prevent scaling distortion
    return max(0.0, similarity)

# ------------------------
# 5. CLI TESTING ENTRY POINT
# ------------------------
def find_similar(player_name, top_n=5):
    matches = df[df["Player"].str.upper() == player_name.upper()]
    if matches.empty:
        print(f"Player '{player_name}' not found.")
        return

    idx_target = matches.index[0]
    target_data = df.iloc[idx_target]
    similarities = []

    for i in range(len(df)):
        if i == idx_target:
            continue
            
        comp_data = df.iloc[i]
        
        sim_physical = calculate_physical_sim(target_data, comp_data)
        sim_production = weighted_cosine_similarity(X_categories["production"][idx_target], X_categories["production"][i], sub_weights["production"])
        sim_style = weighted_cosine_similarity(X_categories["style"][idx_target], X_categories["style"][i], sub_weights["style"])
        sim_aesthetic = weighted_cosine_similarity(X_categories["aesthetic"][idx_target], X_categories["aesthetic"][i], sub_weights["aesthetic"])
        
        total_score = (
            (MACRO_WEIGHTS["physical"] * sim_physical) +
            (MACRO_WEIGHTS["production"] * sim_production) +
            (MACRO_WEIGHTS["style"] * sim_style) +
            (MACRO_WEIGHTS["aesthetic"] * sim_aesthetic)
        ) * 100  # Scale cleanly to 1-100 range
        
        similarities.append((df.iloc[i]["Player"], total_score))

    similarities.sort(key=lambda x: x[1], reverse=True)
    print(f"\nTop {top_n} most similar to {target_data['Player']}:")
    for name, score in similarities[:top_n]:
        print(f"{name} — Score: {round(score, 1)} / 100")

if __name__ == "__main__":
    find_similar("Stephen Curry", top_n=5)