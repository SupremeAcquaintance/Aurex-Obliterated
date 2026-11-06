"""Test-only managed child: replaces acquisition with a no-data wait, never a feed proof."""

import sys
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from aurex.db.base import utc_now
from aurex.signal_gateway import native_supervision


class WaitingObserver:
    def __init__(self, *args):
        pass

    def observe(self, **kwargs):
        return SimpleNamespace(
            next_observation_at=utc_now() + timedelta(minutes=15), processing=None
        )


if __name__ == "__main__":
    native_supervision.NativePublicObserver = WaitingObserver
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.run_native_supervisor import main

    raise SystemExit(main())
