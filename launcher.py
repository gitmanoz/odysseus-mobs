"""Windows desktop entrypoint for the frozen Odysseus application."""

import multiprocessing
import runpy
import sys
from pathlib import Path


_FROZEN_CHILD_SCRIPTS = {
    "email_server.py",
    "image_gen_server.py",
    "memory_server.py",
    "rag_server.py",
}


def _run_frozen_child(argv: list[str] | None = None) -> int | None:
    """Run only packaged built-in MCP scripts requested by frozen subprocesses."""
    args = list(sys.argv if argv is None else argv)
    if not getattr(sys, "frozen", False) or len(args) < 2:
        return None
    requested = Path(args[1]).resolve()
    internal_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)).resolve()
    allowed_root = (internal_root / "mcp_servers").resolve()
    if requested.name not in _FROZEN_CHILD_SCRIPTS or requested.parent != allowed_root:
        return None
    sys.argv = args[1:]
    runpy.run_path(str(requested), run_name="__main__")
    return 0


def frozen_main() -> int:
    """Enter the desktop host only after PyInstaller handles spawn children."""
    multiprocessing.freeze_support()
    child_exit = _run_frozen_child()
    if child_exit is not None:
        return child_exit
    from src.desktop_host import main

    return main()


if __name__ == "__main__":
    raise SystemExit(frozen_main())
