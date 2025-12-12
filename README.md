# PyDexer: Python Code Graph Indexer

PyDexer is an AST-based Python code indexer that extracts structural metadata from Python codebases, building a graph of nodes (classes, functions, etc.) and relationships (calls, imports, etc.). It outputs JSON for analysis or ingestion into Neo4j for querying and visualization. Ideal for code intelligence, refactoring, and AI-driven insights.

## Features

- **AST-Powered Extraction**: Precise parsing of classes, functions, control flow, imports, and more.
- **Qualified Naming**: Tracks scoped names (e.g., `mypackage.MyClass.method`) and hierarchies.
- **Bidirectional Relations**: Captures calls, definitions, and their inverses (e.g., CALLS/CALLED_BY).
- **Position Tracking**: Line/column positions for IDE-like navigation.
- **Flat JSON Schema**: Normalized output with embedded relations for easy graph building.
- **CLI & API**: Command-line tool and Python imports for integration.
- **Neo4j Ingestion**: Bulk loading with batching and indexes for large graphs.
- **Git Support**: Clone and index remote repositories.

## Installation

### Prerequisites
- **Python 3.8+**: For AST parsing.
- **Neo4j (Optional)**: For graph storage. Install Neo4j Desktop/Server and set env vars:
  ```bash
  export NEO4J_URI="neo4j://localhost:7687"
  export NEO4J_USER="neo4j"
  export NEO4J_PASSWORD="your_password"
  ```
- **Git (Optional)**: For repo cloning.

### Setup
1. Clone/download pydexer.
2. Core extraction uses only Python stdlib (`ast`, `json`, etc.).
3. For Neo4j: `pip install neo4j`.
4. (Optional) `.env` file for credentials.

## Usage

### CLI
Index directories or Git repos to JSON.

```bash
python extract.py --pkg myproject --dir ./src --out graph.json
python extract.py --repo https://github.com/user/repo.git --out repo_graph.json
```

Options: `--pkg` (prefix), `--dir` (local path), `--repo` (Git URL), `--ref` (branch), `--out` (output file).

### Programmatic
```python
from extract import extract, extract_ast_nodes

result, time = extract("myproject", "./src")
nodes = extract_ast_nodes("file.py", "module", "./src")
```

### Neo4j Ingestion
1. Create indexes in Neo4j:
   ```cypher
   CREATE INDEX FOR (n:CodeNode) ON (n.id);
   CREATE INDEX FOR (n:CodeNode) ON (n.qualified_name);
   CREATE INDEX FOR (n:CodeNode) ON (n.parent_qualified_name);
   ```
2. Ingest: `python ingest.py` (uses `output/output.json`).
3. Query: `MATCH (a)-[:CALLS]->(b) RETURN a.name, b.name`.

## Output Schema

Flat JSON: `{"qualified_name": {"kind": "...", "relations": [...]}}`.

Example:
```json
{
  "mymodule.MyClass": {
    "kind": "class",
    "name": "MyClass",
    "pos": {"start": 10, "end": 25},
    "relations": [{"rel_type": "CLASS_DEF", "target": "mymodule", "pos": {"start": 10}}]
  }
}
```

Relations: `CLASS_DEF`, `FUNCTION_DEF`, `CALLS`/`CALLED_BY`, `IMPORTS`, etc.

## Architecture

- extract.py: CLI and file processing.
- NodeCollector.py: AST visitor for node/relation extraction.
- rel_types.py: Relation definitions.
- ingest.py: Neo4j bulk loader.
- `git_support.py`: Git utilities.

## Performance & Limitations

- Fast extraction; ingestion optimized with batching/indexes.
- AST-accurate but static (no runtime).
- Scales to large repos with Neo4j tuning.

## Contributing

PRs welcome for new features or fixes. License: MIT.