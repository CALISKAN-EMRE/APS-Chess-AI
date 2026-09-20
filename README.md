# APS Chess AI

### Neural Value Network + Adversarial Search Chess Engine
*Developed by the **APS Machine Learning Team***

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.11](https://img.shields.io/badge/Python-3.11-brightgreen.svg)](https://www.python.org/)
[![TensorFlow: 2.21](https://img.shields.io/badge/TensorFlow-2.21-orange.svg)](https://www.tensorflow.org/)
[![Frontend: React + Vite](https://img.shields.io/badge/Frontend-React%20%7C%20Vite-61dafb.svg)](stage5_ui/frontend)

---

## Overview

**APS Chess AI** is an open-source, exhibition-grade chess engine and interactive kiosk application developed by the **APS Machine Learning Team**. 

The engine combines deep learning and classical adversarial game search:
1. A **deep neural value network** directly evaluates non-terminal chess positions from an 8×8×12 tensor representation.
2. An **adversarial search pipeline** (Iterative Deepening, Alpha-Beta Minimax, Transposition Table, and Principal Variation Search) selects optimal candidate moves.
3. Visitors and challengers can play directly against the AI through a responsive, low-latency web kiosk interface equipped with authoritative 3+0 and 5+0 Bullet clocks.

---

## Features

- **Human vs AI Gameplay**: Seamlessly play as either White or Black.
- **Search Depth Modes**: Configurable search depths:
  - **D1 Fast** (Depth 1 — immediate tactical response)
  - **D2 Standard** (Depth 2 — recommended balanced exhibition play)
  - **D3 Deep** (Depth 3 — thorough positional calculation)
- **Authoritative Bullet Clocks**: Backend-synchronized 3+0 and 5+0 clocks with game-start pause semantics and monotonic server-side timing.
- **Neural Position Evaluation**: Continuous dynamic evaluation scored by a trained deep neural network.
- **Modern Search Architecture**:
  - Minimax with Alpha-Beta pruning
  - Iterative Deepening
  - Transposition Tables (TT) with Zobrist hashing
  - Principal Variation Search (PVS) with move ordering
  - Deterministic move selection
- **Asynchronous Architecture**: Decoupled FastAPI backend and React 19/Vite frontend with zero UI thread blocking during search.
- **Exhibition-Ready Stand UI**: Single-screen zero-scroll layout, vector Cburnett pieces, offline typography, and native dark instrument aesthetics.

---

## Architecture

The engine operates on a structured multi-stage evaluation and search pipeline:

```
                  ┌──────────────────────┐
                  │     Chess Board      │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │    8×8×12 Tensor     │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ Neural Value Network │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ Minimax / Alpha-Beta │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ Iterative Deepening  │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ Transposition Table  │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │  Principal Variation │
                  │     Search (PVS)     │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │    Selected Move     │
                  └──────────────────────┘
```

---

## Model

- **Input Representation**: An $8 \times 8 \times 12$ binary feature tensor encoding the positions of 6 piece types for each color across 64 squares.
- **Neural Non-Terminal Output**: A scalar value in the range $[-1.0, +1.0]$:
  - Positive values favor White.
  - Negative values favor Black.
  - Neutral values (~$0.0$) represent equal or balanced positions.
  *(Note: The neural network produces a normalized value assessment rather than centipawns).*
- **Terminal State Evaluation**: Explicit terminal states (checkmate, stalemate, draw by repetition, fifty-move rule) are resolved directly by the search engine using decisive terminal bounds ($\pm 1000.0$) rather than relying on neural approximation.

---

## Validation & Benchmarks

The APS Chess AI search engine has been systematically validated through rigorous regression and reference testing:

- **Algorithm Equivalence (Alpha-Beta vs PVS)**:
  - **40-position Depth-2 regression suite**: **100% agreement** between baseline Alpha-Beta and Principal Variation Search.
  - **4-position Depth-3 regression suite**: **100% agreement** on selected moves and minimax values.
- **External Evaluation Reference (Stockfish 19 @ Depth 14)**:
  - **Depth-2 Median Centipawn Loss**: **69.5 cp** against Stockfish 19 reference evals.
  - **60.0%** of moves evaluated within **100 cp** of Stockfish best moves.
  - **72.5%** of moves evaluated within **200 cp** of Stockfish best moves.

> [!NOTE]
> Stockfish is used strictly as an **external evaluation benchmark** to quantify engine accuracy. Stockfish is not bundled in this repository and is not part of the move-selection engine. APS Chess AI does not claim grandmaster or Stockfish-level playing strength; it is an experimental neural engine designed for exhibition play and machine learning research.

---

## Performance

Stage 5 utilizes a compiled TensorFlow graph inference wrapper (`tf.function(reduce_retracing=True)`) around the frozen neural value model:

- **Evaluation Latency**: **~7.7–8.2 ms per neural evaluation** on CPU (`Intel/AMD x86_64`).
- **Human Move Latency**: **< 3 ms** round-trip time for human move verification and state update.
- **Search Latency**: Varies dynamically with position complexity, branching factor, and selected search depth:
  - **D1 Fast**: ~0.05–0.15s
  - **D2 Standard**: ~0.8–2.0s
  - **D3 Deep**: ~6.0–20.0s

---

## Requirements

- **Operating System**: Windows 10/11 (or Linux/macOS with Python 3.11)
- **Python**: `3.11.x` (required for TensorFlow 2.21 compatibility)
- **Node.js**: `v20.x` or `v22.x` + `npm`
- **Hardware**: Modern multi-core x86_64 CPU, 4 GB RAM minimum
- *(Optional)* **Stockfish**: Only required if running external benchmark comparison scripts.

---

## Installation

Clone the repository and set up both backend and frontend environments:

```bash
# 1. Clone the repository
git clone https://github.com/APS-Machine-Learning/APS-Chess-AI.git
cd APS-Chess-AI

# 2. Install Python dependencies in Python 3.11
py -3.11 -m pip install -r requirements.txt

# 3. Install frontend dependencies and build production assets
cd stage5_ui/frontend
npm install
npm run build
cd ../..
```

---

## Running the Stand UI

### Option A: 1-Click Stand Launcher (Windows)
For standalone kiosk/stand operation, double-click:
```cmd
START_APS_CHESS.bat
```
This launcher checks Python and Node.js prerequisites, launches the backend and frontend servers, verifies health readiness, and automatically opens the interface in your default browser.

### Option B: Manual Startup

**Terminal 1 — Engine Backend**:
```bash
py -3.11 -m uvicorn stage5_ui.backend.main:app --host 127.0.0.1 --port 8000
```
Verify health: `curl http://127.0.0.1:8000/api/health`

**Terminal 2 — Kiosk Frontend**:
```bash
cd stage5_ui/frontend
npm run dev
```
Open **http://localhost:5173** in your browser.

---

## Project Structure

```
APS-Chess-AI/
├── green_team_stage4_fixed.py    # Frozen core engine (search, model, PVS, Zobrist TT)
├── chess_value_model.keras.zip   # Trained neural value network weights (~7.1 MB)
├── requirements.txt              # Python runtime dependencies
├── START_APS_CHESS.bat           # 1-click Windows stand launcher
├── pyrefly.toml                  # Pyrefly type checking configuration
├── LICENSE                       # MIT License for original source code
├── THIRD_PARTY_NOTICES.md        # Third-party licensing & attributions
├── README.md                     # Project documentation
│
└── stage5_ui/
    ├── backend/
    │   ├── main.py               # FastAPI application & API routing
    │   ├── game_manager.py       # Session, move locking, and clock management
    │   ├── engine_adapter.py     # Compiled TensorFlow inference wrapper
    │   ├── schemas.py            # Pydantic state and clock schemas
    │   ├── tracing.py            # Diagnostic request tracing
    │   └── test_*.py             # Automated verification & audit test suites
    │
    └── frontend/
        ├── package.json          # Frontend dependencies & scripts
        ├── vite.config.ts        # Vite build configuration
        ├── public/               # Logos, favicons, and SVG icons
        └── src/
            ├── components/       # Board, clocks, controls, and telemetry panels
            ├── assets/pieces/    # Cburnett SVG vector piece assets
            ├── api/              # Strongly typed backend API client
            └── types.ts          # TypeScript domain and clock interfaces
```

---

## Running Verification Tests

Run the backend verification suite to validate engine integrity, clock semantics, and turn enforcement:

```bash
# Game-start paused clock and free 1st move semantics
py -3.11 -m unittest stage5_ui/backend/test_game_start_clocks.py

# Monotonic timing, turn switching, and timeout forfeits
py -3.11 -m unittest stage5_ui/backend/test_clocks.py

# Single-deduction AI clock accounting audit
py -3.11 -m unittest stage5_ui/backend/test_clock_accounting_audit.py

# Complete end-to-end API verification suite
py -3.11 stage5_ui/backend/test_complete_verification.py
```

---

## Known Limitations

- **Search Horizon**: At shallow search depths (D1/D2), the engine may occasionally fail to see tactical traps that occur just beyond the search horizon.
- **Exponential Complexity**: Adversarial search time scales exponentially with depth ($O(b^d)$). Depth 3 can require 10–20 seconds in high-branching positions on CPU.
- **Educational Scope**: APS Chess AI is designed as an educational, exhibition-ready machine learning demonstration, not a competitive replacement for multi-threaded grandmaster engines like Stockfish.

---

## Contributing & Future Work

We welcome contributions, forks, and research experiments! Suggested areas for future exploration include:
- **Quiescence Search**: Adding capture-only tactical rollouts to resolve horizon effects.
- **Richer Board Representations**: Incorporating castling rights, en passant, and move-history planes into the tensor.
- **Batched / GPU Inference**: Leveraging CUDA or DirectML for parallel leaf evaluation during search.
- **Native Stand Packaging**: Bundling into a native desktop kiosk executable via Tauri.
- **Post-Game Analysis**: Interactive review of player moves against engine evaluations.

---

## Credits & Licensing

- **Original Code**: Copyright © 2026 **APS Machine Learning Team**. Licensed under the [MIT License](LICENSE).
- **Third-Party Assets**:
  - Vector Chess Pieces: [Colin M.L. Burnett](stage5_ui/frontend/src/assets/pieces/cburnett/ATTRIBUTION.md) (CC BY-SA 3.0 / GPL).
  - Typography: [Inter](https://rsms.me/inter/), [JetBrains Mono](https://www.jetbrains.com/lp/mono/), [Space Grotesk](https://floriankarsten.github.io/space-grotesk/) (SIL Open Font License 1.1).
  - External Chess Libraries: [python-chess](https://github.com/niklasf/python-chess) (GPL-3.0+), [chess.js](https://github.com/jhlywa/chess.js) (BSD-2-Clause).
  - Full attributions and third-party licenses are documented in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
