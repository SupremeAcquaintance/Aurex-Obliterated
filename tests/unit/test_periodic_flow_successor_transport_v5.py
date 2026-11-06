from __future__ import annotations

from types import SimpleNamespace

from scripts.run_periodic_flow_successor_acquisition_v5 import _wait_for_dns


def test_v5_dns_gate_retries_before_target_transport(monkeypatch) -> None:
    calls = []

    def resolve(host, port):  # noqa: ANN001
        calls.append((host, port))
        if len(calls) < 3:
            raise OSError("synthetic resolver outage")
        return [(None, None, None, None, ("127.0.0.1", port))]

    monkeypatch.setattr(
        "scripts.run_periodic_flow_successor_acquisition_v5.socket.getaddrinfo",
        resolve,
    )
    monkeypatch.setattr(
        "scripts.run_periodic_flow_successor_acquisition_v5.time.sleep",
        lambda seconds: None,
    )
    context = SimpleNamespace(
        protocol=SimpleNamespace(
            maximum_dns_checks_per_network_target=12,
            dns_retry_delays_seconds=(5, 20, 60, 60, 60, 60, 60, 60, 60, 60, 60),
        )
    )

    _wait_for_dns(context)

    assert len(calls) == 3
    assert all(call == ("data.binance.vision", 443) for call in calls)
