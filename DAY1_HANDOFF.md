# Day 1 — Handoff Note

Hey! Here's a quick rundown of what got done today and what you can pick up.

---

## What was done today

### Commit 1 — Project scaffold
- `config.py` set up — every setting (city name, Redis URL, LLM provider, API port etc.)
  lives here and reads from `.env` so nothing is hardcoded
- `.env.example` added — copy it to `.env` and fill in your values before running anything
- `main.py` created — the root entry point, currently runs a smoke test for the graph loader

### Commit 2 — OSMnx graph loader (`core/graph/loader.py`)
- Downloads the real road network for any city from OpenStreetMap
- Automatically enriches every road edge with `speed_kph` and `travel_time` (seconds)
- Projects the graph to UTM so distances are in metres (important for the VRP solver later)
- Caches the downloaded graph to `data/graphs/` as a `.pkl` file —
  first run takes ~30–60s for Kolkata, every run after that is instant
- Three functions you will use directly:
  - `load_graph()` → returns the NetworkX graph
  - `nearest_node(G, lat, lon)` → snaps any coordinate to the road network
  - `graph_summary(G)` → returns node/edge count and CRS for logging

### Tests — `tests/test_graph.py`
- Checks the graph is a directed graph
- Checks nodes and edges exist
- Checks every edge has `travel_time` and `length`
- Checks `nearest_node()` returns a valid node ID

---

## How to get started

```bash
git pull
cp .env.example .env        # then open .env and check CITY_NAME etc.
uv sync                     # installs all dependencies
uv run main.py              # first run downloads Kolkata (~30-60s), prints summary
uv run pytest tests/ -v     # all 6 tests should pass
```

---

## Your task — Day 2: Distance Matrix (`core/graph/matrix.py`)

This is the bridge between the graph and the VRP solver.
The solver needs a square matrix of travel times between all delivery stops.

### What to build

Create `core/graph/matrix.py` with one main function:

```python
def build_distance_matrix(G, locations: list[dict]) -> tuple[np.ndarray, list[int]]:
    """
    Parameters
    ----------
    G         : graph from load_graph()
    locations : list of dicts, each with 'lat' and 'lon' keys
                first entry should always be the depot

    Returns
    -------
    matrix : NxN numpy array of travel times in seconds (int)
    nodes  : list of snapped graph node IDs in the same order as locations
    """
```

### How to build it

1. For each location, call `nearest_node(G, lat, lon)` to snap it to the graph
2. Use `nx.single_source_dijkstra_path_length(G, node, weight="travel_time")`
   to get distances from each node to all others in one call (much faster than
   calling `shortest_path` N² times)
3. Build the N×N matrix — `matrix[i][j]` = travel time in seconds from stop i to stop j
4. If a path doesn't exist between two nodes, use a large penalty value like `10_000_000`
   instead of crashing

### Sample data to test with

`data/sample_orders.json` has 8 delivery locations across Kolkata
plus a depot — use that as your test input.

### Expected output

```
matrix[0][1]  →  travel time in seconds from depot to order 1
matrix[1][0]  →  travel time in seconds from order 1 back to depot
matrix[i][i]  →  always 0 (same location)
```

### Tests to write — `tests/test_matrix.py`

- Matrix shape is N×N
- Diagonal is all zeros
- No negative values
- matrix[i][j] is not necessarily equal to matrix[j][i] (roads are directed)

---

## Files overview

```
hacktrek/
├── config.py                 ← all settings, read from .env
├── .env.example              ← copy to .env
├── main.py                   ← run this to smoke test
├── core/
│   └── graph/
│       ├── loader.py         ← DONE — graph download + cache
│       └── matrix.py         ← YOUR TASK for today
├── data/
│   ├── graphs/               ← auto-generated cache (.pkl files land here)
│   └── sample_orders.json   ← test data, 8 Kolkata delivery locations
└── tests/
    ├── test_graph.py         ← DONE — 6 passing tests
    └── test_matrix.py        ← YOUR TASK for today
```

---

> If anything looks off or the smoke test fails, check that `.env` has
> `CITY_NAME=Kolkata, India` and that `uv sync` ran without errors.
> Ping me and I'll sort it.