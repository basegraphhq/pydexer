# PyDexer

A Python code indexer that extracts and indexes code structure from Python source files using Abstract Syntax Tree (AST) parsing.

## Overview

pydexer walks through Python source directories, parses each `.py` file using Python's AST module, and extracts structured metadata about code elements including classes, functions, control flow statements, and more. The extracted data is output as JSON with qualified names, positions, and hierarchical relationships.

## Features

- **AST-based parsing**: Uses Python's built-in `ast` module for accurate code analysis
- **Comprehensive node extraction**: Indexes classes, functions (sync and async), loops, conditionals, comprehensions, and control flow statements
- **Qualified naming**: Tracks fully qualified names (e.g., `module.Class.method`) with parent-child relationships
- **Position tracking**: Records start and end line numbers for each extracted node
- **Package-aware**: Supports module/package prefix naming for proper namespace resolution
- **CLI interface**: Command-line tool for easy execution

## Installation

No external dependencies required - uses only Python standard library modules:
- `ast`
- `json`
- `argparse`
- `pathlib`

## Usage

### Command Line Interface
h
python extract.py --pkg <package_prefix> --dir <directory> --out <output_file>**Arguments:**
- `--pkg`: Package/module prefix (e.g., `github.com/org/repo`)
- `--dir`: Root directory to walk (default: current directory)
- `--out`: Path to write JSON output (default: `output/output.json`)

**Example:**

```shell
python extract.py --pkg myproject --dir ./src --out results.json
```

### Programmatic Usage
```python
from extract import extract, extract_ast_nodes

# Extract from entire directory
result, elapsed = extract(pkgstr="myproject", dir="./src")

# Extract from single file
nodes_dict = extract_ast_nodes("path/to/file.py", package_root="./src")## Output Format
```
The indexer outputs a dictionary mapping file paths to node collections. Each node contains:

- `kind`: Human-readable node type (e.g., "class", "function", "for_loop")
- `ast_type`: Exact AST node type name
- `name`: Local name of the node (if applicable)
- `qualified_name`: Fully qualified name including module and parent scopes
- `parent_qualified_name`: Qualified name of the parent scope
- `pos`: Position information with `start` and `end` line numbers

**Example output:**
```json
{
  "path/to/file.py": {
    "module.ClassName": {
      "kind": "class",
      "ast_type": "ClassDef",
      "name": "ClassName",
      "qualified_name": "module.ClassName",
      "parent_qualified_name": null,
      "pos": {"start": 10, "end": 25}
    },
    "module.ClassName.method": {
      "kind": "function",
      "ast_type": "FunctionDef",
      "name": "method",
      "qualified_name": "module.ClassName.method",
      "parent_qualified_name": "module.ClassName",
      "pos": {"start": 15, "end": 20}
    }
  }
}
```
## Supported Node Types

The indexer extracts the following node types:

**Named nodes:**
- Classes (`ClassDef`)
- Functions (`FunctionDef`)
- Async functions (`AsyncFunctionDef`)

**Control flow:**
- For loops (`For`, `AsyncFor`)
- While loops (`While`)
- If statements (`If`)
- Try statements (`Try`)
- With statements (`With`, `AsyncWith`)

**Expressions:**
- List/dict/set comprehensions
- Generator expressions
- Lambda functions

**Statements:**
- Return, yield, yield from
- Raise, assert
- Break, continue, pass

## Architecture

- **`extract.py`**: Main extraction logic, directory walking, and CLI interface
- **`NodeCollector.py`**: AST visitor class that traverses the syntax tree and collects node metadata
