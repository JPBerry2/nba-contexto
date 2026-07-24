import React, { useState, useEffect, useRef } from "react";
import "./App.css";

const API = "https://nba-contexto.onrender.com";

function App() {
  const [gameMode, setGameMode] = useState(null); // 'daily' or 'infinite'
  const [difficulty, setDifficulty] = useState("hard");
  const [players, setPlayers] = useState([]);
  const [guess, setGuess] = useState("");
  const [filteredPlayers, setFilteredPlayers] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [gameOver, setGameOver] = useState(false);

  // Core Game Session State
  const [gameId, setGameId] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [newestGuess, setNewestGuess] = useState(null);
  const [sortedHistory, setSortedHistory] = useState([]);
  const [guessCount, setGuessCount] = useState(0);

  // UX & Branding Feature States
  const [gameStarted, setGameStarted] = useState(false);
  const [showInstructions, setShowInstructions] = useState(false);
  const [showFeedback, setShowFeedback] = useState(false);
  const [showStats, setShowStats] = useState(false);
  const [hintsList, setHintsList] = useState([]);
  const [feedbackText, setFeedbackText] = useState("");
  const [feedbackSuccess, setFeedbackSuccess] = useState(false);

  // Local Storage Persistent Stats State
  const [stats, setStats] = useState({
    gamesPlayed: 0,
    dailyWin: false,
    lastDailyDate: "",
    currentStreak: 0,
    maxStreak: 0,
    totalGuessesInWins: 0,
    gamesWon: 0,
  });

  const autocompleteRef = useRef(null);

  // ---------------------------------------------------------------------------
  // 1. Initial Setup (Load players, setup events, & restore user stats)
  // ---------------------------------------------------------------------------
  useEffect(() => {
    setIsLoading(true);
    fetch(`${API}/players`)
      .then((res) => res.json())
      .then((data) => {
        setPlayers(data);
        setIsLoading(false);
      })
      .catch((err) => {
        console.error("Error loading players:", err);
        setIsLoading(false);
      });

    const savedStats = localStorage.getItem("wonof1_contexto_stats");
    if (savedStats) {
      setStats(JSON.parse(savedStats));
    }

    const handleClickOutside = (event) => {
      if (autocompleteRef.current && !autocompleteRef.current.contains(event.target)) {
        setShowSuggestions(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // ---------------------------------------------------------------------------
  // 2. Start Game Core Routing Orchestration
  // ---------------------------------------------------------------------------
  const startInfiniteGame = async (level) => {
    setDifficulty(level);
    setGameMode("infinite");
    setIsLoading(true);
    try {
      const res = await fetch(`${API}/new_game?difficulty=${level}`);
      const data = await res.json();
      setupGameInstance(data, `🎮 Infinite Mode (${level.toUpperCase()}) started!`);
    } catch (err) {
      console.error("Error starting game:", err);
      setNewestGuess({ type: "system", message: "⚠️ Could not contact server." });
      setIsLoading(false);
    }
  };

  const startDailyGame = async () => {
    const todayStr = new Date().toISOString().slice(0, 10);
    if (stats.lastDailyDate === todayStr && stats.dailyWin) {
      alert("🏆 You have already completed today's Daily Challenge! Try Infinite Mode!");
      return;
    }

    setGameMode("daily");
    setIsLoading(true);
    try {
      const res = await fetch(`${API}/new_daily_game`);
      const data = await res.json();
      setupGameInstance(data, `📅 WonOf1 Daily Challenge [${data.date}] Loaded!`);
    } catch (err) {
      console.error("Error starting daily game:", err);
      setNewestGuess({ type: "system", message: "⚠️ Could not load daily puzzle." });
      setIsLoading(false);
    }
  };

  const setupGameInstance = (data, welcomeMessage) => {
    setGameId(data.game_id);
    setNewestGuess({ type: "system", message: welcomeMessage });
    setSortedHistory([]);
    setHintsList([]);
    setGuessCount(0);
    setGameOver(false);
    setGameStarted(true);
    setGuess("");
    setFilteredPlayers([]);
    setShowSuggestions(false);
    setIsLoading(false);
  };

  const getColor = (value) => {
    const hue = (value * 120) / 100;
    return `hsl(${hue}, 85%, 45%)`;
  };

  // Helper to map closeness score to hot/cold indicators & labels
  const getTemperatureIndicator = (value) => {
    if (value >= 80) return { icon: "🔥", label: "Blazing Hot!" };
    if (value >= 50) return { icon: "🌡️", label: "Warm Match" };
    if (value >= 25) return { icon: "❄️", label: "Cooling Down" };
    return { icon: "🧊", label: "Freezing Cold" };
  };

  // ---------------------------------------------------------------------------
  // 3. Submit Guess Logic & LocalStorage Stats Integration
  // ---------------------------------------------------------------------------
  const handleGuessSubmit = async () => {
    if (!guess.trim() || gameOver) return;

    try {
      const res = await fetch(`${API}/guess`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ player: guess, game_id: gameId }),
      });

      const data = await res.json();
      const currentGuesses = guessCount + 1;
      setGuessCount(currentGuesses);

      let incomingItem = {};
      if (res.status !== 200) {
        incomingItem = { type: "system", message: `❌ ${data.error}` };
      } else if (data.correct) {
        incomingItem = { type: "system", message: `🎉 WonOf1 Absolute Match! You found ${data.player} in ${currentGuesses} guesses!` };
        setGameOver(true);
        updateUserStats(true, currentGuesses);
        setShowStats(true);
      } else {
        incomingItem = { type: "guess", player: guess, closeness: data.closeness };
      }

      setNewestGuess((prevNewest) => {
        if (prevNewest) {
          setSortedHistory((prevHistory) => {
            const updated = [...prevHistory, prevNewest];
            return updated.sort((a, b) => {
              if (a.type === "system") return 1;
              if (b.type === "system") return -1;
              return b.closeness - a.closeness;
            });
          });
        }
        return incomingItem;
      });

    } catch (err) {
      console.error("Error sending guess:", err);
      setNewestGuess({ type: "system", message: "⚠️ Network tracking pipeline error." });
    }

    setGuess("");
    setFilteredPlayers([]);
    setShowSuggestions(false);
  };

  const updateUserStats = (isWin, finalGuessCount) => {
    const todayStr = new Date().toISOString().slice(0, 10);
    let updated = { ...stats };

    if (gameMode === "daily") {
      updated.gamesPlayed += 1;
      if (isWin) {
        updated.gamesWon += 1;
        updated.dailyWin = true;
        updated.lastDailyDate = todayStr;
        updated.currentStreak += 1;
        updated.totalGuessesInWins += finalGuessCount;
        if (updated.currentStreak > updated.maxStreak) {
          updated.maxStreak = updated.currentStreak;
        }
      }
    } else {
      if (isWin) {
        updated.totalGuessesInWins += finalGuessCount;
        updated.gamesWon += 1;
        updated.gamesPlayed += 1;
      }
    }

    setStats(updated);
    localStorage.setItem("wonof1_contexto_stats", JSON.stringify(updated));
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") handleGuessSubmit();
  };

  // ---------------------------------------------------------------------------
  // 4. Hints & Resignation
  // ---------------------------------------------------------------------------
  const getHint = async (type) => {
    if (gameOver || hasHint(type)) return;
    try {
      const res = await fetch(`${API}/hint/${type}?game_id=${gameId}`);
      const data = await res.json();
      
      const isDuplicate = hintsList.some(h => h.type === type && h.hint === data.hint);
      if (isDuplicate) return;

      setHintsList((prev) => [...prev, { type, hint: data.hint }]);
    } catch (err) {
      console.error("Error getting hint:", err);
    }
  };

  const handleQuit = async () => {
    setGameOver(true);
    let mysteryPlayer = "Unknown Player";
    
    try {
      const res = await fetch(`${API}/reveal_answer?game_id=${gameId}`);
      const data = await res.json();
      if (data.player) mysteryPlayer = data.player;
    } catch (err) {
      console.error("Error revealing answer:", err);
    }

    if (gameMode === "daily") {
      let updated = { ...stats, currentStreak: 0, lastDailyDate: new Date().toISOString().slice(0, 10), dailyWin: false };
      setStats(updated);
      localStorage.setItem("wonof1_contexto_stats", JSON.stringify(updated));
    }

    if (newestGuess) setSortedHistory((prev) => [...prev, newestGuess]);
    setNewestGuess({ type: "system", message: `😔 Surrendered. The absolute WonOf1 player profile target was: ${mysteryPlayer}.` });
  };

  const hasHint = (type) => {
    if (type === "age" || type === "position") return hintsList.some((h) => h.type === type);
    return hintsList.some((h) => h.type === "team");
  };

  // ---------------------------------------------------------------------------
  // 5. Formspree Feedback Integration
  // ---------------------------------------------------------------------------
  const handleFeedbackSubmit = async (e) => {
    e.preventDefault();
    if (!feedbackText.trim()) return;

    try {
      const response = await fetch("https://formspree.io/f/xeeyrkqg", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: feedbackText, mode: gameMode })
      });

      if (response.ok) {
        setFeedbackSuccess(true);
        setFeedbackText("");
        setTimeout(() => {
          setFeedbackSuccess(false);
          setShowFeedback(false);
        }, 3000);
      } else {
        alert("⚠️ Failed to send report. Please try again.");
      }
    } catch (err) {
      console.error("Error submitting feedback:", err);
    }
  };

  const renderFeedbackItem = (item, isNewest = false) => {
    if (!item) return null;
    if (item.type === "system") {
      return <div className={`feedback-item system ${isNewest ? "newest" : ""}`}>{item.message}</div>;
    }

    const temp = getTemperatureIndicator(item.closeness);

    return (
      <div className={`feedback-item ${isNewest ? "newest-guess" : ""}`} style={{ marginBottom: "15px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontWeight: "bold", color: "#f8f9fa", padding: "0 10px" }}>
          <span>{item.player} {isNewest && "✨"}</span>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ fontSize: "16px" }} title={temp.label}>{temp.icon}</span>
            <span style={{ color: getColor(item.closeness) }}>{item.closeness}/100</span>
          </div>
        </div>
        <div style={{ width: "100%", height: "14px", background: "#343a40", borderRadius: "7px", margin: "6px 0", overflow: "hidden", border: "1px solid #495057" }}>
          <div style={{ width: `${item.closeness}%`, height: "100%", background: getColor(item.closeness), transition: "width 0.4s ease" }} />
        </div>
      </div>
    );
  };

  return (
    <div className="App" style={{ maxWidth: "520px", margin: "0 auto", padding: "20px", textAlign: "center", backgroundColor: "#121212", color: "#f8f9fa", minHeight: "100vh", fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" }}>
      
      {/* BRAND HEADER SECTION */}
      <div style={{ borderBottom: "2px solid #212529", paddingBottom: "15px", marginBottom: "20px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "12px" }}>
          <h1 style={{ fontSize: "32px", fontWeight: "900", background: "linear-gradient(45deg, #ff4757, #ffa502)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", margin: 0 }}>
            WonOf1 CONTEXTO
          </h1>
          <button onClick={() => setShowInstructions(!showInstructions)} style={{ borderRadius: "50%", width: "28px", height: "28px", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", fontWeight: "bold", color: "#fff", backgroundColor: "#2f3542", border: "1px solid #57606f" }}>?</button>
          <button onClick={() => setShowStats(!showStats)} style={{ borderRadius: "6px", padding: "4px 8px", cursor: "pointer", fontSize: "14px", fontWeight: "bold", color: "#fff", backgroundColor: "#2f3542", border: "1px solid #57606f" }}>📊 Stats</button>
        </div>
        <p style={{ margin: "5px 0 0 0", fontSize: "12px", color: "#a4b0be", letterSpacing: "1px" }}>POWERED BY WONOF1 CREATOR ARCHITECTURE</p>
        
        {/* YOUTUBE CHANNEL PROMO BANNER LINK */}
        <div style={{ marginTop: "12px" }}>
          <a href="https://www.youtube.com/@WonOf1" target="_blank" rel="noopener noreferrer" style={{ display: "inline-flex", alignItems: "center", gap: "6px", background: "#ff0000", color: "#ffffff", padding: "5px 12px", borderRadius: "20px", fontSize: "12px", fontWeight: "bold", textDecoration: "none", boxShadow: "0 2px 8px rgba(255,0,0,0.3)" }}>
            🔴 Subscribe to WonOf1 on YouTube
          </a>
        </div>
      </div>

      {/* MODAL VIEW SYSTEM ACCORDIONS */}
      {showInstructions && (
        <div style={{ background: "#1e272e", padding: "20px", borderRadius: "10px", margin: "15px 0", textAlign: "left", border: "1px solid #3d4a5d", color: "#dcdde1" }}>
          <h3 style={{ margin: "0 0 10px 0", color: "#ffa502" }}>💡 How to Play</h3>
          <p>Deduce the secret NBA player profile! Every guess receives an AI algorithm proximity ranking score from 0 to 100.</p>
          <ul style={{ paddingLeft: "20px", lineHeight: "1.6" }}>
            <li><strong style={{ color: "#ff4757" }}>100/100</strong> means you accurately cracked the hidden target.</li>
            <li>Higher scoring bars mean closer cross-connections across identical active metrics (teams, career era slots, position parameters).</li>
          </ul>
          <button onClick={() => setShowInstructions(false)} style={{ background: "#ff4757", color: "#fff", border: "none", padding: "6px 12px", borderRadius: "4px", cursor: "pointer", marginTop: "10px" }}>Close Rules</button>
        </div>
      )}

      {/* STATS OVERLAY HUD DISPLAY */}
      {showStats && (
        <div style={{ background: "#1e272e", padding: "20px", borderRadius: "10px", margin: "15px 0", border: "1px solid #2f3542" }}>
          <h3 style={{ color: "#ffa502", marginTop: 0 }}>📈 WonOf1 Player Statistics</h3>
          <div style={{ display: "flex", justifyContent: "space-around", margin: "15px 0" }}>
            <div><div style={{ fontSize: "24px", fontWeight: "bold" }}>{stats.gamesPlayed}</div><div style={{ fontSize: "11px", color: "#a4b0be" }}>Played</div></div>
            <div><div style={{ fontSize: "24px", fontWeight: "bold" }}>{stats.gamesPlayed > 0 ? Math.round((stats.gamesWon / stats.gamesPlayed) * 100) : 0}%</div><div style={{ fontSize: "11px", color: "#a4b0be" }}>Win %</div></div>
            <div><div style={{ fontSize: "24px", fontWeight: "bold" }}>{stats.currentStreak}</div><div style={{ fontSize: "11px", color: "#a4b0be" }}>Streak</div></div>
            <div><div style={{ fontSize: "24px", fontWeight: "bold" }}>{stats.maxStreak}</div><div style={{ fontSize: "11px", color: "#a4b0be" }}>Max Streak</div></div>
          </div>
          <div style={{ fontSize: "13px", color: "#dcdde1", borderTop: "1px solid #2f3542", paddingTop: "10px" }}>
            Average Efficiency: <strong>{stats.gamesWon > 0 ? Math.round(stats.totalGuessesInWins / stats.gamesWon) : 0}</strong> guesses/win
          </div>
          <button onClick={() => setShowStats(false)} style={{ background: "#747d8c", color: "#fff", border: "none", padding: "6px 16px", borderRadius: "4px", cursor: "pointer", marginTop: "15px" }}>Dismiss View</button>
        </div>
      )}

      {/* COLD START WAKE LOADING LAYER */}
      {isLoading && (
        <div style={{ background: "#ffb142", color: "#1e272e", padding: "12px", borderRadius: "6px", marginBottom: "15px", fontWeight: "bold" }}>
          ⏳ Computing target metric matrices... (Allow ~50s for first server initialization load)
        </div>
      )}

      {/* MODE CHOICE GAME SPLASH ARCHITECTURE */}
      {!gameStarted && !isLoading && (
        <div style={{ margin: "40px 0" }}>
          <h2 style={{ fontSize: "20px", color: "#dcdde1" }}>Select Your Arena Track:</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: "15px", marginTop: "25px" }}>
            
            <button onClick={startDailyGame} style={{ padding: "18px", fontSize: "18px", cursor: "pointer", background: "linear-gradient(135deg, #ffa502, #ff7f50)", color: "white", border: "none", borderRadius: "8px", fontWeight: "bold", boxShadow: "0 4px 15px rgba(255,165,0,0.2)" }}>
              📅 Play Daily Challenge Mode
            </button>
            <div style={{ fontSize: "12px", color: "#747d8c", marginTop: "-8px" }}>Unified global seed track. Everyone plays the exact same profile puzzle tracking list today.</div>
            
            <div style={{ display: "flex", gap: "10px", marginTop: "10px" }}>
              <button onClick={() => startInfiniteGame("easy")} style={{ flex: 1, padding: "12px", cursor: "pointer", background: "#2ed573", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold" }}>
                🟢 Infinite (Easy Pool)
              </button>
              <button onClick={() => startInfiniteGame("hard")} style={{ flex: 1, padding: "12px", cursor: "pointer", background: "#ff4757", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold" }}>
                🔴 Infinite (Hard Pool)
              </button>
            </div>
            <div style={{ fontSize: "12px", color: "#747d8c" }}>Practice matches layout. Purely randomized infinite pool extraction generation arrays.</div>
          </div>
        </div>
      )}

      {/* MAIN GAME ENVIRONMENT VIEW HUD */}
      {gameStarted && (
        <>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px", background: "#1e272e", padding: "10px 15px", borderRadius: "6px" }}>
            <span style={{ fontSize: "14px", color: "#ffa502", fontWeight: "bold" }}>
              MODE: {gameMode === "daily" ? "📅 DAILY CHALLENGE" : `🎮 INFINITE (${difficulty.toUpperCase()})`}
            </span>
            <span style={{ fontSize: "14px", color: "#a4b0be" }}>
              Guesses Made: <strong style={{ color: "#fff" }}>{guessCount}</strong>
            </span>
          </div>

          {!gameOver && (
            <>
              {/* GUESS SEARCH AUTOCOMPLETE ENGINE */}
              <div style={{ marginBottom: "25px", display: "flex", justifyContent: "space-between" }}>
                <div ref={autocompleteRef} style={{ position: "relative", width: "75%", textAlign: "left" }}>
                  <input
                    type="text"
                    value={guess}
                    placeholder="Search player profiles..."
                    onKeyDown={handleKeyDown}
                    style={{ width: "100%", padding: "12px", borderRadius: "6px", border: "1px solid #2f3542", background: "#2f3542", color: "#fff", fontSize: "16px", boxSizing: "border-box" }}
                    onChange={(e) => {
                      const value = e.target.value;
                      setGuess(value);
                      if (value.trim() === "") {
                        setFilteredPlayers([]);
                        setShowSuggestions(false);
                        return;
                      }
                      const matches = players.filter(p => p.toLowerCase().includes(value.toLowerCase()));
                      setFilteredPlayers(matches.slice(0, 8));
                      const exactMatch = matches.some(p => p.toLowerCase() === value.toLowerCase());
                      setShowSuggestions(!exactMatch);
                    }}
                  />

                  {showSuggestions && filteredPlayers.length > 0 && (
                    <ul style={{ position: "absolute", zIndex: 100, background: "#2f3542", width: "100%", listStyle: "none", padding: 0, margin: "4px 0 0 0", border: "1px solid #57606f", borderRadius: "6px", textAlign: "left", boxShadow: "0 8px 24px rgba(0,0,0,0.5)", maxHeight: "200px", overflowY: "auto" }}>
                      {filteredPlayers.map((player, idx) => (
                        <li key={idx} onClick={() => { setGuess(player); setShowSuggestions(false); }} style={{ padding: "10px 12px", cursor: "pointer", borderBottom: "1px solid #1e272e", color: "#fff" }} onMouseOver={(e) => e.target.style.backgroundColor = "#57606f"} onMouseOut={(e) => e.target.style.backgroundColor = "transparent"}>
                          {player}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <button onClick={handleGuessSubmit} disabled={!guess.trim()} style={{ width: "22%", padding: "12px 0", background: "#ffa502", color: "#121212", border: "none", borderRadius: "6px", fontWeight: "bold", fontSize: "16px", cursor: "pointer" }}>
                  Fire
                </button>
              </div>

              {/* HINTS HUD CONTROLLER PANEL */}
              <div style={{ marginBottom: "25px", borderTop: "1px solid #212529", paddingTop: "20px" }}>
                <div style={{ display: "flex", gap: "8px", justifyContent: "center" }}>
                  <button onClick={() => getHint("age")} disabled={hasHint("age")} style={{ flex: 1, padding: "8px", background: hasHint("age") ? "#2f3542" : "#57606f", color: "#fff", border: "none", borderRadius: "4px", fontSize: "12px", cursor: "pointer" }}>
                    {hasHint("age") ? "Age Unlocked" : "Hint: Age"}
                  </button>
                  <button onClick={() => getHint("position")} disabled={hasHint("position")} style={{ flex: 1, padding: "8px", background: hasHint("position") ? "#2f3542" : "#57606f", color: "#fff", border: "none", borderRadius: "4px", fontSize: "12px", cursor: "pointer" }}>
                    {hasHint("position") ? "Pos Unlocked" : "Hint: Position"}
                  </button>
                  <button onClick={() => getHint("team")} disabled={hasHint("team")} style={{ flex: 1, padding: "8px", background: hasHint("team") ? "#2f3542" : "#57606f", color: "#fff", border: "none", borderRadius: "4px", fontSize: "12px", cursor: "pointer" }}>
                    {hasHint("team") ? "Team Unlocked" : "Hint: Team"}
                  </button>
                </div>
                
                <button onClick={handleQuit} style={{ marginTop: "15px", background: "transparent", color: "#ff4757", border: "1px solid #ff4757", padding: "6px 16px", borderRadius: "4px", cursor: "pointer", fontSize: "13px", fontWeight: "bold" }}>
                  🏳️ Forfeit & Reveal Answer
                </button>
              </div>
            </>
          )}
        </>
      )}

      {/* GAME RUNTIME TERMINATION DISPLAY VIEW CARD (WITH INSTANT PLAY AGAIN BUTTON) */}
      {gameOver && (
        <div style={{ background: "#1e272e", padding: "25px", borderRadius: "10px", margin: "20px 0", border: "2px solid #ffa502" }}>
          <h2 style={{ margin: "0 0 15px 0", color: "#ffa502" }}>Battle Session Finished!</h2>
          <div style={{ display: "flex", gap: "10px", justifyContent: "center" }}>
            {gameMode === "infinite" && (
              <button onClick={() => startInfiniteGame(difficulty)} style={{ padding: "12px 20px", background: "#2ed573", color: "#fff", border: "none", borderRadius: "6px", fontSize: "15px", fontWeight: "bold", cursor: "pointer" }}>
                🔄 Play Again ({difficulty.toUpperCase()})
              </button>
            )}
            <button onClick={() => { setGameStarted(false); setGameMode(null); }} style={{ padding: "12px 20px", background: "#1e90ff", color: "#fff", border: "none", borderRadius: "6px", fontSize: "15px", fontWeight: "bold", cursor: "pointer" }}>
              🏠 Arena Lounge
            </button>
          </div>
        </div>
      )}

      {/* ACTIVE REVEALED ACCORDION SLOT */}
      {gameStarted && hintsList.length > 0 && (
        <div style={{ background: "#2f3542", border: "1px solid #57606f", borderRadius: "8px", padding: "15px", marginBottom: "25px", textAlign: "left" }}>
          <h4 style={{ margin: "0 0 10px 0", color: "#ffa502" }}>🕵️ Uncovered Intel Metrics</h4>
          {hintsList.map((h, idx) => (
            <div key={idx} style={{ marginBottom: "6px", fontSize: "14px" }}>
              <span style={{ color: "#a4b0be", textTransform: "uppercase" }}>{h.type}:</span> <strong style={{ color: "#fff" }}>{h.hint}</strong>
            </div>
          ))}
        </div>
      )}

      {/* FEEDBACK FEED LIVE DATA FEED */}
      {gameStarted && (
        <div style={{ textAlign: "left", marginTop: "20px" }}>
          <h3 style={{ fontSize: "18px", color: "#a4b0be", borderBottom: "1px solid #212529", paddingBottom: "8px" }}>Guess History Feed</h3>
          {newestGuess && (
            <div style={{ borderBottom: "2px dashed #485460", paddingBottom: "15px", marginBottom: "15px" }}>
              {renderFeedbackItem(newestGuess, true)}
            </div>
          )}
          {sortedHistory.map((item, idx) => (
            <div key={idx}>{renderFeedbackItem(item, false)}</div>
          ))}
        </div>
      )}

      {/* PROBLEMS OR CONCERNS ACCORDION COMPONENT */}
      <div style={{ marginTop: "40px", borderTop: "1px solid #212529", paddingTop: "20px", paddingBottom: "30px" }}>
        <button onClick={() => setShowFeedback(!showFeedback)} style={{ background: "none", border: "none", color: "#747d8c", cursor: "pointer", textDecoration: "underline", fontSize: "14px" }}>
          ⚠️ Spot a mistake or have a feature concern? Click to Report
        </button>

        {showFeedback && (
          <form onSubmit={handleFeedbackSubmit} style={{ marginTop: "15px", background: "#1e272e", padding: "15px", borderRadius: "8px", border: "1px solid #2f3542", textAlign: "left" }}>
            <label style={{ display: "block", fontSize: "13px", color: "#a4b0be", marginBottom: "8px" }}>Describe the concern (e.g., incorrect active player stats, bugs, UI glitches):</label>
            <textarea value={feedbackText} onChange={(e) => setFeedbackText(e.target.value)} placeholder="Type issue context here..." style={{ width: "100%", height: "70px", padding: "8px", borderRadius: "4px", background: "#2f3542", color: "#fff", border: "1px solid #485460", boxSizing: "border-box", fontSize: "14px" }} />
            <button type="submit" style={{ marginTop: "10px", background: "#ff4757", color: "#fff", border: "none", padding: "6px 16px", borderRadius: "4px", fontWeight: "bold", cursor: "pointer" }}>
              Submit Dispatch Report
            </button>
            {feedbackSuccess && (
              <div style={{ color: "#2ed573", fontSize: "13px", marginTop: "8px", fontWeight: "bold" }}>
                ✔️ Report delivered straight to the WonOf1 processing queue! Thanks for helping out!
              </div>
            )}
          </form>
        )}
      </div>

    </div>
  );
}

export default App;