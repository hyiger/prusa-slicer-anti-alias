
def is_binary_gcode(path: str) -> bool:
    if path.lower().endswith(".bgcode"):
        return True
    try:
        with open(path, "rb") as f:
            return b"\x00" in f.read(1024)
    except OSError:
        return False


#!/usr/bin/env python3
from anti_alias_prusaslicer.core import main

if __name__ == "__main__":
    raise SystemExit(main())
