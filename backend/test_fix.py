from similarity_engine import df, X_categories, MACRO_WEIGHTS, sub_weights, hybrid_similarity, calculate_physical_sim
from app import compute_percentiles

# Pick a hidden player to test (e.g., Josh Minott)
target = "Josh Minott"
print(f"🔍 Testing similarity engine for target player: {target}")

# Run your backend's exact percentile/scoring function
percentiles = compute_percentiles(target)

# Find what score Jordan Walsh gets
walsh_score = percentiles.get("Jordan Walsh", "Not found")
print(f"👉 Jordan Walsh's score against {target}: {walsh_score}")

# Print the highest scores in the system to verify the cap
sorted_matches = sorted(percentiles.items(), key=lambda x: x[1], reverse=True)
print("\n🏆 Top 5 Closest Matches in the Engine:")
for player, score in sorted_matches[:5]:
    print(f"   - {player}: {score}")