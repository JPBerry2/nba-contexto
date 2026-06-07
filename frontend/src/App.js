import React, { useState, useEffect } from "react";
import "./App.css";

// ---------------------------------------------
// CONFIG: Change this ONE line when deploying
// ---------------------------------------------
const API = "https://nba-contexto.onrender.com";

function App() {
  const [difficulty, setDifficulty] = useState("hard");
  const [players, setPlayers] = useState([]);
  const [guess, setGuess] = useState("");
  const [filteredPlayers, setFilteredPlayers] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [feedback, setFeedback] = useState([]);
  const [gameOver, setGameOver] = useState(false);

  // ------------------------
  // Load players + start game
  // ------------------------
  useEffect(() => {
    fetch(`${API}/players`)
      .then(res => res.json())
      .then(data => setPlayers(data))
      .catch(err => console.error("Error loading players:", err));

    startNewGame(difficulty);
  }, []);

  // ------------------------
  // Start new game
  // ------------------------
  const startNewGame = async (level) => {
    try {
      const res = await fetch(`${API}/new_game?difficulty=${level}`);
      const data = await res.json();

      setFeedback([{ type: "system", message: `🎮 New game started! Difficulty: ${data.difficulty}` }]);
      setGameOver(false);
      setGuess("");
      setFilteredPlayers([]);
      setShowSuggestions(false);
    } catch (err) {
      console.error("Error starting game:", err);
      setFeedback([{ type: "system", message: "⚠️ Could not start game." }]);
    }
  };

  // ------------------------
  // Dynamic color (red → green)
  // ------------------------
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

      if (res.status !== 200) {
        setFeedback(prev => [{ type: "system", message: `❌ ${data.error}` }, ...prev]);
      } else if (data.correct) {
        setFeedback(prev => [
          { type: "system", message: `🎉 Correct! You guessed ${data.player}!` },
          ...prev,
        ]);
        setGameOver(true);
      } else {
        // Storing as data objects instead of raw JSX elements
        setFeedback(prev => [
          { type: "guess", player: guess, closeness: data.closeness },
          ...prev,
        ]);
      }
    } catch (err) {
      console.error("Error sending guess:", err);
      setFeedback(prev => [{ type: "system", message: "⚠️ Network error." }, ...prev]);
    }

    setGuess("");
    setFilteredPlayers([]);
    setShowSuggestions(false);
  };

  // ------------------------
  // Hint
  // ------------------------
  const getHint = async (type) => {
    if (gameOver) return;

    try {
      const res = await fetch(`${API}/hint/${type}`);
      const data = await res.json();

      setFeedback(prev => [
        { type: "system", message: `💡 ${type.toUpperCase()} Hint: ${data.hint}` },
        ...prev,
      ]);
    } catch (err) {
      console.error("Error getting hint:", err);
      setFeedback(prev => [{ type: "system", message: "⚠️ Could not fetch hint." }, ...prev]);
    }
  };

  // ------------------------
  // Quit
  // ------------------------
  const handleQuit = () => {
    setGameOver(true);
    setFeedback(prev => [{ type: "system", message: "You quit. Restart to play again." }, ...prev]);
  };

  return (
    <div className="App">
      <h1>NBA Contexto</h1>

      {!gameOver && (
        <>
          <label>
            Difficulty:
            <select
              value={difficulty}
              onChange={(e) => {
                setDifficulty(e.target.value);
                startNewGame(e.target.value);
              }}
            >
              <option value="easy">Easy</option>
              <option value="hard">Hard</option>
            </select>
          </label>

          {/* ------------------------
              AUTOCOMPLETE INPUT
          ------------------------ */}
          <div className="guess-section">
            <div className="autocomplete">
              <input
                type="text"
                value={guess}
                placeholder="Type a player name..."
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
                  setShowSuggestions(true);
                }}
                onFocus={() => {
                  if (guess.length > 0) setShowSuggestions(true);
                }}
              />

              {showSuggestions && filteredPlayers.length > 0 && (
                <ul className="suggestions">
                  {filteredPlayers.map((player, idx) => (
                    <li
                      key={idx}
                      onClick={() => {
                        setGuess(player);
                        setShowSuggestions(false);
                      }}
                    >
                      {player}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <button onClick={handleGuessSubmit}>
              Guess
            </button>
          </div>

          <div className="buttons">
            <button onClick={() => getHint("age")}>Hint: Age</button>
            <button onClick={() => getHint("position")}>Hint: Position</button>
            <button onClick={() => getHint("team")}>Hint: Team</button>
            <button onClick={handleQuit}>Quit</button>
          </div>
        </>
      )}

      {gameOver && (
        <>
          <h2>Game Over</h2>
          <button onClick={() => startNewGame(difficulty)}>
            Restart
          </button>
        </>
      )}

      {/* ------------------------
          FEEDBACK / GUESS LIST RENDERING
      ------------------------ */}
      <div className="feedback">
        <h2>Guesses</h2>
        {feedback.map((item, idx) => {
          // If it's a simple text message / system notification
          if (item.type === "system") {
            return <div key={idx}>{item.message}</div>;
          }

          // If it's a structural guess item with a progress bar
          return (
            <div key={idx}>
              <strong>{item.player}</strong>
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
        })}
      </div>
    </div>
  );
}

export default App;