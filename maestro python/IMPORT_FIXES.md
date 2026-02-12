# Import Fixes After Subfolder Reorganization

Files moved into engine/, identity/, knowledge/, tools/ subfolders.
All cross-file imports need updating. Apply AFTER ingest finishes.

## Need `__init__.py` in each subfolder

Create empty `__init__.py` in:
- `engine/`
- `identity/`
- `knowledge/`
- `tools/`

## All three engines (engine/maestro_v13_*.py) — IDENTICAL changes

```
OLD                                                    → NEW
import tools_v13                                       → from tools import tools_v13
from experience_v13 import experience                  → from identity.experience_v13 import experience
from knowledge_v13 import load_project                 → from knowledge.knowledge_v13 import load_project
from learning_v12 import learn, save_experience        → ??? (learning_v12 doesn't exist in new structure yet)
from tools_v13 import tool_definitions                 → from tools.tools_v13 import tool_definitions
from vision import (see_page, see_pointer, ...)        → from tools.vision import (see_page, see_pointer, ...)
```

**Note:** `learning_v12.py` was moved to `old/v12/`. Need to either:
1. Copy it into `identity/` as `learning.py`
2. Or build the new GPT 5.2 learning harness to replace it

## tools/tools_v13.py

```
OLD                                    → NEW
from knowledge_v13 import load_project → from knowledge.knowledge_v13 import load_project
```

## tools/vision.py (lazy imports inside functions)

```
OLD                                                         → NEW
from gemini_service import _collect_response as collect     → from knowledge.gemini_service import _collect_response as collect
from gemini_service import _save_trace as save              → from knowledge.gemini_service import _save_trace as save
```

## knowledge/ingest.py

```
OLD                                                        → NEW
from gemini_service import _save_trace, run_pass1, run_pass2 → from knowledge.gemini_service import _save_trace, run_pass1, run_pass2
```

**BUT** ingest.py is also a CLI entry point (`python ingest.py`). If run directly from knowledge/, 
the relative import won't work. Options:
1. Run as module: `python -m knowledge.ingest "D:\Plans\..."`
2. Add sys.path hack at top of ingest.py
3. Keep a thin wrapper at maestro python/ root level

## Running engines

Same issue — engines are CLI entry points. Either:
1. `python -m engine.maestro_v13_gemini`
2. sys.path at top
3. Thin wrappers at root

**Recommended:** sys.path approach — add this to top of each entry point:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```
This makes `maestro python/` the import root regardless of which subfolder the script is in.
