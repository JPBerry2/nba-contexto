# ------------------------
# DIAGNOSTIC TEST: Check why two players score too high
# ------------------------
def debug_player_similarity(player_a_name, player_b_name):
    print(f"\n🔍 Running Diagnostic: {player_a_name} vs {player_b_name}")
    
    match_a = df[df["Player"].str.upper() == player_a_name.upper()]
    match_b = df[df["Player"].str.upper() == player_b_name.upper()]
    
    if match_a.empty or match_b.empty:
        print("❌ One or both players not found in active dataframe.")
        return

    idx_a = match_a.index[0]
    idx_b = match_b.index[0]
    
    data_a = df.iloc[idx_a]
    data_b = df.iloc[idx_b]
    
    print(f"Positions -> {data_a['Player']}: Code {data_a['POS_CODE']} | {data_b['Player']}: Code {data_b['POS_CODE']}")
    print(f"Physical Sim Score: {calculate_physical_sim(data_a, data_b):.3f}")
    
    # Check category vectors and hybrid similarities
    for cat_name, feats in category_features.items():
        vec_a = X_categories[cat_name][idx_a] * sub_weights[cat_name]
        vec_b = X_categories[cat_name][idx_b] * sub_weights[cat_name]
        
        sim = hybrid_similarity(X_categories[cat_name][idx_a], X_categories[cat_name][idx_b], sub_weights[cat_name])
        print(f"Category '{cat_name}' Similarity: {sim:.3f}")
        
        # Print raw features side-by-side to see if they are identical zeros or sparse data
        print(f"   Values for {cat_name}:")
        for feat in feats:
            val_a = data_a[feat] if feat in data_a else "N/A"
            val_b = data_b[feat] if feat in data_b else "N/A"
            print(f"      - {feat}: {data_a['Player']}={val_a} vs {data_b['Player']}={val_b}")

    # Final Computed Score
    raw_score = (
        (MACRO_WEIGHTS["physical"] * calculate_physical_sim(data_a, data_b)) +
        (MACRO_WEIGHTS["production"] * hybrid_similarity(X_categories["production"][idx_a], X_categories["production"][idx_b], sub_weights["production"])) +
        (MACRO_WEIGHTS["style"] * hybrid_similarity(X_categories["style"][idx_a], X_categories["style"][idx_b], sub_weights["style"])) +
        (MACRO_WEIGHTS["aesthetic"] * hybrid_similarity(X_categories["aesthetic"][idx_a], X_categories["aesthetic"][idx_b], sub_weights["aesthetic"]))
    )
    print(f"👉 Raw Combined Score: {raw_score:.4f}")

if __name__ == "__main__":
    # Test the exact pairing that caused the issue
    debug_player_similarity("Josh Minott", "Jordan Walsh")