import React, { useState, useEffect } from "react";
import "./App.css";

const API = "https://nba-contexto-backend.onrender.com";

function App() {
  const [difficulty, setDifficulty] = useState("hard");
  const [players, setPlayers] = useState([]);
  const [guess, setGuess] = useState("");
  const [filteredPlayers, setFilteredPlayers] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [gameOver, setGameOver] = useState(false);

  // States from previous updates
  const [isLoading, setIsLoading] = useState(true);
  const [newestGuess, setNewestGuess] = useState(null);
  const [sortedHistory, setSortedHistory] = useState([]);

  // --- NEW STATES FOR YOUR 3 FIXES ---
  const [gameStarted, setGameStarted] = useState(false); // For initial large buttons
  const [showInstructions, setShowInstructions] = useState(false); // For How to Play
  const [hintsList, setHintsList] = useState([]); // Persistent hints area

  // ------------------------
  // Load players initially
  // ------------------------
  useEffect(() => {
    setIsLoading(true);
    fetch(`${API}/players`)
      .then(res => res.json())
      .then(data => {
        setPlayers(data);
        setIsLoading(false);
      })
      .catch(err => {
        console.error("Error loading players:", err);
        setIsLoading(false);
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ------------------------
  // Start new game
  // ------------------------
  const startNewGame = async (level) => {
    setDifficulty(level);
    try {
      const res = await fetch(`${API}/new_game?difficulty=${level}`);
      const data = await res.json();

      setNewestGuess({ type: "system", message: `🎮 New game started! Difficulty: ${data.difficulty}` });
      setSortedHistory([]);
      setHintsList([]); // Clear previous game hints
      setGameOver(false);
      setGameStarted(true); // Switches UI from welcome buttons to regular gameplay
      setGuess("");
      setFilteredPlayers([]);
      setShowSuggestions(false);
    } catch (err) {
      console.error("Error starting game:", err);
      setNewestGuess({ type: "system", message: "⚠️ Could not start game." });
    }
  };

  const getColor = (value) => {
    const hue = (value * 120) / 100;
    return `hsl(${hue}, 100%, 50%)`;
  };

  // ------------------------
  // Submit guess
  // ------------------------
  const handleGuessSubmit = async () => {
    if (!guess || gameOver) return;

    try {
      const res = await fetch(`${API}/guess`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ player: guess }),
      });

      const data = await res.json();
      let incomingItem = {};

      if (res.status !== 200) {
        incomingItem = { type: "system", message: `❌ ${data.error}` };
      } else if (data.correct) {
        incomingItem = { type: "system", message: `🎉 Correct! You guessed ${data.player}!` };
        setGameOver(true);
      } else {
        incomingItem = { type: "guess", player: guess, closeness: data.closeness };
      }

      if (newestGuess) {
        setSortedHistory(prevHistory => {
          const updated = [...prevHistory, newestGuess];
          return updated.sort((a, b) => {
            if (a.type === "system") return 1;
            if (b.type === "system") return -1;
            return b.closeness - a.closeness;
          });
        });
      }

      setNewestGuess(incomingItem);
    } catch (err) {
      console.error("Error sending guess:", err);
      setNewestGuess({ type: "system", message: "⚠️ Network error." });
    }

    setGuess("");
    setFilteredPlayers([]);
    setShowSuggestions(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") {
      handleGuessSubmit();
    }
  };

  // ------------------------
  // Upgraded Hint Logic (Fix #3)
  // ------------------------
  const getHint = async (type) => {
    if (gameOver) return;
    try {
      const res = await fetch(`${API}/hint/${type}`);
      const data = await res.json();
      
      // Save hints here so they stay permanently pinned at the top
      setHintsList(prev => [...prev, { type, hint: data.hint }]);
    } catch (err) {
      console.error("Error getting hint:", err);
    }
  };

  const handleQuit = () => {
    setGameOver(true);
    if (newestGuess) {
      setSortedHistory(prev => [newestGuess, ...prev]);
    }
    setNewestGuess({ type: "system", message: "You quit. Restart to play again." });
  };

  const renderFeedbackItem = (item, isNewest = false) => {
    if (!item) return null;
    if (item.type === "system") {
      return <div className={`feedback-item system ${isNewest ? 'newest' : ''}`}>{item.message}</div>;
    }

    return (
      <div className={`feedback-item ${isNewest ? 'newest-guess' : ''}`}>
        <strong>{item.player} {isNewest && "✨"}</strong>
        <div style={{
          width: "300px",
          height: "20px",
          background: "#ddd",
          borderRadius: "10px",
          marginTop: "5px",
          overflow: "hidden"
        }}>
          <div style={{
            width: `${item.closeness}%`,
            height: "100%",
            background: getColor(item.closeness),
            transition: "width 0.4s ease"
          }} />
        </div>
        <span>{item.closeness}/100</span>
      </div>
    );
  };

  return (
    <div className="App" style={{ maxWidth: "500px", margin: "0 auto", padding: "20px", textAlign: "center" }}>
      
      {/* HEADER + HOW TO PLAY TRIGGER (Fix #2) */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "10px" }}>
        <h1>NBA Contexto</h1>
        <button 
          onClick={() => setShowInstructions(!showInstructions)}
          style={{ borderRadius: "50%", width: "30px", height: "30px", padding: "0", cursor: "pointer", fontWeight: "bold" }}
        >
          ?
        </button>
      </div>

      {/* HOW TO PLAY PANEL (Fix #2) */}
      {showInstructions && (
        <div style={{ background: "#f1f1f1", padding: "15px", borderRadius: "8px", margin: "15px 0", textAlign: "left", border: "1px solid #ccc" }}>
          <h3>💡 How to Play</h3>
          <p>Guess the secret NBA player! Every guess you make gets an AI similarity score from 0 to 100.</p>
          <ul>
            <li><strong>100/100</strong> means you found the exact player.</li>
            <li>Higher numbers mean your guess is closely linked to the target player (by team, position, era, or stats).</li>
            <li>If you get stuck, use a Hint category to uncover details.</li>
          </ul>
          <button onClick={() => setShowInstructions(false)} style={{ marginTop: "5px" }}>Close Instructions</button>
        </div>
      )}

      {/* SERVER WAKING BANNER */}
      {isLoading && (
        <div className="loading-banner" style={{ background: "#fff3cd", color: "#856404", padding: "10px", borderRadius: "5px", marginBottom: "15px" }}>
          <p>⏳ Waking up the server... Please wait roughly 50 seconds on first load!</p>
        </div>
      )}

      {/* INITIAL DIFFICULTY SELECTOR SCREEN (Fix #1) */}
      {!gameStarted && !isLoading && (
        <div style={{ margin: "40px 0" }}>
          <h2>Select Game Difficulty to Begin:</h2>
          <div style={{ display: "flex", justifyContent: "center", gap: "20px", marginTop: "20px" }}>
            <button onClick={() => startNewGame("easy")} style={{ padding: "15px 30px", fontSize: "18px", cursor: "pointer", background: "#28a745", color: "white", border: "none", borderRadius: "5px" }}>
              🟢 Easy Mode
            </button>
            <button onClick={() => startNewGame("hard")} style={{ padding: "15px 30px", fontSize: "18px", cursor: "pointer", background: "#dc3545", color: "white", border: "none", borderRadius: "5px" }}>
              🔴 Hard Mode
            </button>
          </div>
        </div>
      )}

      {/* ACTIVE GAMEBOARD */}
      {gameStarted && !gameOver && (
        <>
          {/* Subtle dropdown to toggle difficulty later if desired (Fix #1 alternative) */}
          <label style={{ display: "block", marginBottom: "20px" }}>
            Change Difficulty:{" "}
            <select
              value={difficulty}
              onChange={(e) => startNewGame(e.target.value)}
            >
              <option value="easy">Easy</option>
              <option value="hard">Hard</option>
            </select>
          </label>

          {/* AUTOCOMPLETE INPUT SECTION */}
          <div className="guess-section" style={{ marginBottom: "20px" }}>
            <div className="autocomplete" style={{ position: "relative", display: "inline-block" }}>
              <input
                type="text"
                value={guess}
                placeholder="Type a player name..."
                onKeyDown={handleKeyDown}
                onChange={(e) => {
                  const value = e.target.value;
                  setGuess(value);

                  if (value.trim() === "") {
                    setFilteredPlayers([]);
                    setShowSuggestions(false);
                    return;
                  }

                  const matches = players.filter(p =>
                    p.toLowerCase().includes(value.toLowerCase())
                  );

                  setFilteredPlayers(matches.slice(0, 10));
                  const exactMatch = matches.some(p => p.toLowerCase() === value.toLowerCase());
                  setShowSuggestions(!exactMatch);
                }}
                onFocus={() => {
                  const exactMatch = players.some(p => p.toLowerCase() === guess.toLowerCase());
                  if (guess.length > 0 && !exactMatch) setShowSuggestions(true);
                }}
              />

              {showSuggestions && filteredPlayers.length > 0 && (
                <ul className="suggestions" style={{ position: "absolute", zIndex: 100, background: "white", width: "100%", listStyle: "none", padding: 0, margin: 0, border: "1px solid #ccc", textAlign: "left" }}>
                  {filteredPlayers.map((player, idx) => (
                    <li
                      key={idx}
                      onClick={() => {
                        setGuess(player);
                        setShowSuggestions(false);
                      }}
                      style={{ padding: "8px", cursor: "pointer", borderBottom: "1px solid #eee" }}
                    >
                      {player}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <button onClick={handleGuessSubmit} disabled={!guess} style={{ marginLeft: "10px" }}>
              Guess
            </button>
          </div>

          <div className="buttons" style={{ marginBottom: "30px", display: "flex", gap: "5px", justifyContent: "center" }}>
            <button onClick={() => getHint("age")}>Hint: Age</button>
            <button onClick={() => getHint("position")}>Hint: Position</button>
            <button onClick={() => getHint("team")}>Hint: Team</button>
            <button onClick={handleQuit}>Quit</button>
          </div>
        </>
      )}

      {/* GAME OVER AREA */}
      {gameOver && (
        <div style={{ margin: "20px 0" }}>
          <h2>Game Over</h2>
          <button onClick={() => startNewGame(difficulty)} style={{ padding: "10px 20px" }}>
            Restart Game
          </button>
        </div>
      )}

      {/* DEDICATED STATIC HINTS DISPLAY (Fix #3) */}
      {gameStarted && hintsList.length > 0 && (
        <div style={{ background: "#e8f4fd", border: "1px solid #bee5eb", borderRadius: "8px", padding: "15px", marginBottom: "20px", textAlign: "left" }}>
          <h4 style={{ margin: "0 0 10px 0", color: "#17a2b8" }}>💡 Uncovered Hints</h4>
          {hintsList.map((h, idx) => (
            <div key={idx} style={{ marginBottom: "5px", fontSize: "14px" }}>
              <strong>{h.type.toUpperCase()}:</strong> {h.hint}
            </div>
          ))}
        </div>
      )}

      {/* SCOREBOARD / FEEDBACK AREA */}
      {gameStarted && (
        <div className="feedback">
          <h2>Guesses</h2>
          
          {newestGuess && (
            <div className="newest-zone" style={{ borderBottom: "2px dashed #ccc", paddingBottom: "15px", marginBottom: "15px" }}>
              {renderFeedbackItem(newestGuess, true)}
            </div>
          )}

          {sortedHistory.map((item, idx) => (
            <div key={idx} style={{ marginBottom: "10px" }}>
              {renderFeedbackItem(item, false)}
            </div>
          ))}
        </div>
      )}

    </div>
  );
}

export default App;