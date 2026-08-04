import os
import sys
import types
import importlib.util

ORIGINAL_FILES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Original Files"))
if ORIGINAL_FILES_DIR not in sys.path:
    sys.path.insert(0, ORIGINAL_FILES_DIR)

def import_module_from_path(module_name: str, filename: str) -> types.ModuleType:
    """Dynamically loads a module from the Original Files directory."""
    filepath = os.path.join(ORIGINAL_FILES_DIR, filename)
    spec = importlib.util.spec_from_file_location(module_name, filepath)
    if not spec or not spec.loader:
        raise ImportError(f"Could not load module {module_name} from {filepath}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

def load_agentic_loop() -> types.ModuleType:
    """Loads Agentic_Loop.py functions safely without running its interactive parts."""
    filepath = os.path.join(ORIGINAL_FILES_DIR, "Agentic_Loop.py")
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()
    
    # We strip the interactive CLI parts starting from Step 3
    source = source.split("# =====================================================\n# STEP 3 : Setup Chroma")[0]
    
    module = types.ModuleType("agentic_loop")
    module.__file__ = filepath
    sys.modules["agentic_loop"] = module
    
    # Needs chroma_retriever available in sys.modules
    import_module_from_path("chroma_retriever", "chroma_retriever.py")
    
    exec(source, module.__dict__)
    return module

def get_chroma_loader_func():
    """Wraps the chroma_loader.py script into a callable function."""
    filepath = os.path.join(ORIGINAL_FILES_DIR, "chroma_loader.py")
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()
    
    # Indent code and wrap in a function
    indented = "\n".join("    " + line for line in source.splitlines())
    wrapped = f"def run_chroma_loader():\n{indented}"
    
    module = types.ModuleType("chroma_loader_wrapped")
    import_module_from_path("chroma_retriever", "chroma_retriever.py")
    exec(wrapped, module.__dict__)
    return module.run_chroma_loader
