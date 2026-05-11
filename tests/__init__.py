from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_RUNTIME_SCRIPTS = (
    ROOT
    / "skills"
    / "researchos_skill_library"
    / "01_core_runtime_memory"
    / "research-agent-runtime"
    / "scripts"
)

if str(CANONICAL_RUNTIME_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(CANONICAL_RUNTIME_SCRIPTS))
