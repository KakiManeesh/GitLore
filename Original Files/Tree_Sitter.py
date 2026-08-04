import tree_sitter_python as tspython
from tree_sitter import Language, Parser

# 1. Load the language grammar
PY_LANGUAGE = Language(tspython.language())

# 2. Initialize and configure the parser
parser = Parser(PY_LANGUAGE)

# 3. Code must be passed as a bytes object
source_code = b"""
def greet(name):
    print("Hello, " + name)
"""

# 4. Parse the code to generate the tree
tree = parser.parse(source_code)
root_node = tree.root_node

# 5. Inspect the root node metadata
print(f"Root Node Type: {root_node.type}")  # Outputs: module (for Python files)
print(f"Child count: {root_node.child_count}")
