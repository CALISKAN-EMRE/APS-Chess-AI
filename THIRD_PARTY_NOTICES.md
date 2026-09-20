# Third-Party Notices and Licences

This document provides attribution, copyright, and licensing notices for third-party software, fonts, vector assets, and external tools utilized by or referenced in **APS Chess AI**.

---

## 1. Chess Piece Vector Graphics

### Cburnett Staunton SVG Chess Pieces
- **Designer / Artist**: Colin M.L. Burnett (User:Cburnett on Wikimedia Commons / Wikipedia)
- **Files**: `stage5_ui/frontend/src/assets/pieces/cburnett/*.svg`
- **License**: Creative Commons Attribution-ShareAlike 3.0 Unported (CC BY-SA 3.0) and GNU General Public License (GPL)
- **Sources**:
  - Wikimedia Commons: https://commons.wikimedia.org/wiki/Category:SVG_chess_pieces
  - Lichess: https://github.com/lichess-org/lila/tree/master/public/piece/cburnett
- **Notice**:
  Under the terms of CC BY-SA 3.0, attribution is provided to Colin M.L. Burnett. The vector geometries and aspect ratios are strictly preserved.

---

## 2. Typography & Fonts

### Inter
- **Creator**: Rasmus Andersson
- **License**: SIL Open Font License 1.1 (OFL-1.1)
- **Package**: `@fontsource/inter`
- **Notice**: Copyright (c) 2016-2024 The Inter Project Authors.

### JetBrains Mono
- **Creator**: JetBrains s.r.o.
- **License**: SIL Open Font License 1.1 (OFL-1.1)
- **Package**: `@fontsource/jetbrains-mono`
- **Notice**: Copyright (c) 2020 JetBrains s.r.o.

### Space Grotesk
- **Creator**: Florian Karsten
- **License**: SIL Open Font License 1.1 (OFL-1.1)
- **Package**: `@fontsource/space-grotesk`
- **Notice**: Copyright (c) 2018 The Space Grotesk Project Authors.

---

## 3. External Reference Engine (Optional)

### Stockfish Chess Engine
- **Authors**: The Stockfish developers (https://stockfishchess.org)
- **License**: GNU General Public License v3.0 (GPL-3.0)
- **Notice**:
  Stockfish is used purely as an optional, external, ground-truth reference evaluator during engine benchmarking and validation (e.g. measuring median centipawn loss against Stockfish 19 at depth 14). Stockfish binaries are **not** bundled or distributed within this repository. Contributors wishing to run the external evaluation suite can download the official Stockfish binary directly from [stockfishchess.org/download](https://stockfishchess.org/download/).

---

## 4. Python Runtime Dependencies

### python-chess
- **Author**: Niklas Fiekas
- **License**: GNU General Public License v3.0 or later (GPL-3.0+)
- **Notice**: Python chess library used for move generation, legality validation, and FEN parsing.

### TensorFlow
- **Authors**: Google LLC & TensorFlow Authors
- **License**: Apache License 2.0
- **Notice**: Machine learning platform used for neural value network inference.

### FastAPI
- **Author**: Sebastián Ramírez (tiangolo)
- **License**: MIT License
- **Notice**: Modern, fast web framework for building APIs.

### Uvicorn
- **Author**: Encode OSS
- **License**: BSD-3-Clause License
- **Notice**: Lightning-fast ASGI server implementation.

### Pydantic
- **Author**: Samuel Colvin & Pydantic contributors
- **License**: MIT License
- **Notice**: Data validation using Python type annotations.

### NumPy
- **Authors**: NumPy Developers
- **License**: BSD-3-Clause License
- **Notice**: Fundamental package for array computing.

### Requests
- **Author**: Kenneth Reitz & Requests contributors
- **License**: Apache License 2.0
- **Notice**: HTTP library for Python used in integration tests.

---

## 5. Frontend JavaScript / TypeScript Libraries

The following dependencies are distributed via npm and used in the web kiosk application:

| Package | License | Author / Copyright |
|---|---|---|
| **react** | MIT | Meta Platforms, Inc. |
| **react-dom** | MIT | Meta Platforms, Inc. |
| **vite** | MIT | Evan You & Vite contributors |
| **typescript** | Apache-2.0 | Microsoft Corporation |
| **framer-motion** | MIT | Framer |
| **lucide-react** | ISC | Lucide contributors |
| **chess.js** | BSD-2-Clause | Jeff Hlywa |
| **canvas-confetti** | ISC | Kiril Vatev |
| **oxlint** | MIT | Boshen & Oxc contributors |
