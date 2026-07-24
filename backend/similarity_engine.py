import numpy as np
import pandas as pd

print("Initializing Enhanced Similarity Engine...")

# ------------------------
# 1. LOAD, CLEAN & FILTER DATA
# ------------------------
try:
    df_basic = pd.read_csv("basic_stats.csv")
    df_advanced = pd.read_csv("advanced_stats.csv")
except FileNotFoundError:
    print("Error: CSV files not found. Ensure basic_stats.csv and advanced_stats.csv are in the workspace.")
    exit()

df_basic.columns = df_basic.columns.str.strip().str.upper()
df_advanced.columns = df_advanced.columns.str.strip().str.upper()

for data_frame in [df_basic, df_advanced]:
    data_frame.drop(data_frame[data_frame["PLAYER"] == "PLAYER"].index, inplace=True)
    if "TEAM" in data_frame.columns:
        data_frame.drop(data_frame[data_frame["TEAM"] == "TOT"].index, inplace=True)
    data_frame.drop_duplicates(subset="PLAYER", keep="first", inplace=True)
    data_frame.reset_index(drop=True, inplace=True)

df_basic = df_basic.rename(columns={col: f"{col.upper()}_basic" for col in df_basic.columns if col != "PLAYER"})
df = pd.merge(df_basic, df_advanced, left_on="PLAYER", right_on="PLAYER")
df = df.rename(columns={"PLAYER": "Player"})

# Sample-size filter to weed out low-minute noise
g_col = next((c for c in df.columns if c in ["G_BASIC", "G", "GP"] or "G_" in c), None)
mp_col = next((c for c in df.columns if c in ["MP_BASIC", "MP"] or "MP_" in c), None)

if g_col and mp_col:
    df[g_col] = pd.to_numeric(df[g_col], errors='coerce').fillna(0)
    df[mp_col] = pd.to_numeric(df[mp_col], errors='coerce').fillna(0)
    df = df[(df[g_col] >= 15) & (df[mp_col] >= 15)].reset_index(drop=True)
else:
    print("⚠️ Warning: Game or Minute columns not found for filtering. Skipping sample-size filter.")

pos_col = "POS_BASIC" if "POS_BASIC" in df.columns else ("POS" if "POS" in df.columns else "POS_ADVANCED")
position_map = {"PG": 0, "SG": 1, "SF": 2, "PF": 3, "C": 4}
df["Pos_code"] = df.get(pos_col, "SF").map(position_map).fillna(2).astype(int)

# ------------------------
# 2. FEATURE ARCHITECTURE & WEIGHTS
# ------------------------
category_features = {
    "production": ["TRB%", "AST%", "STL%", "BLK%"],
    "style": ["3PAr", "USG%", "OBPM", "DBPM"],
    "aesthetic": ["TS%", "EFG%", "WS/48", "PTS_BASIC"]
}

for cat, feats in category_features.items():
    for idx, feat in enumerate(feats):
        for actual_col in df.columns:
            if feat.upper() == actual_col.upper():
                category_features[cat][idx] = actual_col

sub_weights = {
    "production": np.array([0.30, 0.30, 0.20, 0.20]),
    "style": np.array([0.30, 0.30, 0.20, 0.20]),
    "aesthetic": np.array([0.30, 0.25, 0.15, 0.30])
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

all_numeric = category_features["production"] + category_features["style"] + category_features["aesthetic"] + ["POS_CODE"]
for col in all_numeric:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    else:
        df[col] = 0.0

df = df.dropna(subset=all_numeric).reset_index(drop=True)
print(f"Data engine ready. Qualified players post-filter: {len(df)}")

# ------------------------
# 3. VECTOR NORMALIZATION (Z-SCORE)
# ------------------------
def normalize_category(dataframe, features):
    X = dataframe[features].values.astype(float)
    stds = np.std(X, axis=0)
    means = np.mean(X, axis=0)
    
    X_norm = np.zeros_like(X)
    nonzero_idx = stds != 0
    X_norm[:, nonzero_idx] = (X[:, nonzero_idx] - means[nonzero_idx]) / stds[nonzero_idx]
    return X_norm

X_categories = {cat: normalize_category(df, feats) for cat, feats in category_features.items()}

# ------------------------
# 4. SIMILARITY MATH
# ------------------------
def calculate_physical_sim(player_a, player_b):
    return float(POSITION_MATRIX[int(player_a["POS_CODE"])][int(player_b["POS_CODE"])])

def hybrid_similarity(a, b, weights):
    a_w = a * weights
    b_w = b * weights
    
    denom = np.linalg.norm(a_w) * np.linalg.norm(b_w)
    cosine_sim = np.dot(a_w, b_w) / denom if denom != 0 else 0.0
    cosine_sim = max(0.0, cosine_sim)
    
    dist = np.linalg.norm(a_w - b_w)
    euclid_sim = 1.0 / (1.0 + 0.4 * dist)
    
    return (0.60 * cosine_sim) + (0.40 * euclid_sim)

# Helper function to compute raw score between any two dataset indices
def compute_raw_score(idx_a, idx_b):
    target_data = df.iloc[idx_a]
    comp_data = df.iloc[idx_b]
    
    sim_physical = calculate_physical_sim(target_data, comp_data)
    sim_production = hybrid_similarity(X_categories["production"][idx_a], X_categories["production"][idx_b], sub_weights["production"])
    sim_style = hybrid_similarity(X_categories["style"][idx_a], X_categories["style"][idx_b], sub_weights["style"])
    sim_aesthetic = hybrid_similarity(X_categories["aesthetic"][idx_a], X_categories["aesthetic"][idx_b], sub_weights["aesthetic"])
    
    return (
        (MACRO_WEIGHTS["physical"] * sim_physical) +
        (MACRO_WEIGHTS["production"] * sim_production) +
        (MACRO_WEIGHTS["style"] * sim_style) +
        (MACRO_WEIGHTS["aesthetic"] * sim_aesthetic)
    )

# ------------------------
# 5. GAME LOGIC: EVALUATE A USER'S GUESS
# ------------------------
def evaluate_guess(target_player_name, guessed_player_name):
    """
    Evaluates a user's guess against the target player.
    Returns 100.0 ONLY if they match. Otherwise, calculates similarity and caps at 99.0 max.
    """
    target_match = df[df["Player"].str.upper() == target_player_name.upper()]
    guess_match = df[df["Player"].str.upper() == guessed_player_name.upper()]
    
    if target_match.empty:
        return f"Target player '{target_player_name}' not found in database."
    if guess_match.empty:
        return f"Guessed player '{guessed_player_name}' not found in database."
        
    idx_target = target_match.index[0]
    idx_guess = guess_match.index[0]
    
    # RULE: Exact match gets 100.0 flat.
    if idx_target == idx_guess:
        return 100.0
        
    # Calculate self-match benchmark for scaling context
    self_raw_score = compute_raw_score(idx_target, idx_target)
    guess_raw_score = compute_raw_score(idx_target, idx_guess)
    
    if self_raw_score > 0:
        raw_ratio = guess_raw_score / self_raw_score
        # STRICT CEILING: min(99.0, ...) ensures a wrong guess can never hit 100
        scaled_score = min(99.0, max(1.0, raw_ratio * 99.0))
    else:
        scaled_score = 1.0
        
    return round(scaled_score, 1)

# ------------------------
# 6. TESTING ENTRY POINT
# ------------------------
if __name__ == "__main__":
    target = "Stephen Curry"
    
    print(f"\n--- Testing Game Guess Logic for Target: {target} ---")
    
    # Test correct guess
    print(f"Guessing 'Stephen Curry': Score -> {evaluate_guess(target, 'Stephen Curry')} / 100")
    
    # Test incorrect guesses (will now correctly max out at 99.0 or lower)
    print(f"Guessing 'Donovan Mitchell': Score -> {evaluate_guess(target, 'Donovan Mitchell')} / 100")
    print(f"Guessing 'Trae Young': Score -> {evaluate_guess(target, 'Trae Young')} / 100")