"""Browser rehearsal service with test-only no-data children, never a feed proof."""

import sys
from pathlib import Path

from aurex.signal_gateway import native_lifecycle

if __name__ == "__main__":
    spawn = native_lifecycle.subprocess.Popen

    def waiting_child(command, **kwargs):
        command = list(command)
        expected = str(native_lifecycle.ROOT / "scripts/run_native_supervisor.py")
        if len(command) < 2 or command[1] != expected:
            raise ValueError("unexpected rehearsal subprocess")
        command[1] = str(native_lifecycle.ROOT / "tests/fixtures/native_managed_wait_child.py")
        return spawn(command, **kwargs)

    native_lifecycle.subprocess.Popen = waiting_child
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.run_private_operator import main

    raise SystemExit(main())
