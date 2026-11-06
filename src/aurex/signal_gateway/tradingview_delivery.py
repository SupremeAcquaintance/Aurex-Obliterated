import json
from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256
from ipaddress import ip_address, ip_network

TRADINGVIEW_WEBHOOK_SOURCE_AUTHORITY_URL = (
    "https://www.tradingview.com/support/solutions/"
    "43000529348-how-to-configure-webhook-alerts/"
)
TRADINGVIEW_DOCUMENTED_IPV4_HOST_NETWORKS = (
    "34.212.75.30/32",
    "52.32.178.7/32",
    "52.89.214.238/32",
    "54.218.53.128/32",
)


def has_forwarding_headers(header_names: Iterable[str]) -> bool:
    """Forwarded peers are not direct-origin evidence, even after ASGI rewriting."""
    return any(
        name.lower().startswith("x-forwarded-")
        or name.lower() in {"forwarded", "x-real-ip", "cf-connecting-ip", "true-client-ip"}
        for name in header_names
    )


@dataclass(frozen=True)
class TradingViewSourceNetworkSnapshot:
    configuration_status: str
    networks: tuple[str, ...]
    networks_sha256: str
    authority_url: str = TRADINGVIEW_WEBHOOK_SOURCE_AUTHORITY_URL

    def evidence_snapshot(self) -> dict:
        return {
            "source_network_configuration_status": self.configuration_status,
            "source_networks": list(self.networks),
            "source_networks_sha256": self.networks_sha256,
            "source_networks_authority_url": self.authority_url,
        }


def tradingview_source_networks_sha256(networks: list[str] | tuple[str, ...]) -> str:
    canonical = sorted(set(networks))
    return sha256(
        json.dumps(canonical, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def tradingview_source_network_snapshot(
    configured_networks: str,
) -> TradingViewSourceNetworkSnapshot:
    configured_values = [
        value.strip() for value in configured_networks.split(",") if value.strip()
    ]
    if not configured_values:
        return TradingViewSourceNetworkSnapshot(
            configuration_status="SOURCE_NETWORKS_NOT_CONFIGURED",
            networks=(),
            networks_sha256=tradingview_source_networks_sha256(()),
        )

    try:
        parsed_networks = [
            ip_network(value, strict=False) for value in configured_values
        ]
    except ValueError:
        return TradingViewSourceNetworkSnapshot(
            configuration_status="SOURCE_NETWORK_CONFIGURATION_INVALID",
            networks=(),
            networks_sha256=sha256(
                configured_networks.encode("utf-8")
            ).hexdigest(),
        )

    canonical_networks = tuple(
        sorted({str(network) for network in parsed_networks})
    )
    exact_ipv4_hosts = all(
        network.version == 4 and network.prefixlen == 32
        for network in parsed_networks
    )
    documented_ipv4_hosts = set(canonical_networks).issubset(
        TRADINGVIEW_DOCUMENTED_IPV4_HOST_NETWORKS
    )
    return TradingViewSourceNetworkSnapshot(
        configuration_status=(
            "SOURCE_NETWORK_CONFIGURATION_DOCUMENTED_IPV4_HOSTS"
            if exact_ipv4_hosts and documented_ipv4_hosts
            else (
                "SOURCE_NETWORK_CONFIGURATION_UNVERIFIED_IPV4_HOSTS"
                if exact_ipv4_hosts
                else "SOURCE_NETWORK_CONFIGURATION_UNSAFE_SCOPE"
            )
        ),
        networks=canonical_networks,
        networks_sha256=tradingview_source_networks_sha256(canonical_networks),
    )


def tradingview_origin_status(
    remote_ip: str | None,
    source_networks: TradingViewSourceNetworkSnapshot,
) -> str:
    if not remote_ip:
        return "REMOTE_IP_MISSING"
    try:
        candidate = ip_address(remote_ip)
    except ValueError:
        return "REMOTE_IP_INVALID"

    if (
        source_networks.configuration_status
        == "SOURCE_NETWORK_CONFIGURATION_INVALID"
    ):
        return "SOURCE_NETWORK_CONFIGURATION_INVALID"
    if not source_networks.networks:
        return "SOURCE_NETWORKS_NOT_CONFIGURED"

    networks = [ip_network(value, strict=False) for value in source_networks.networks]
    if any(candidate in network for network in networks):
        return "TRADINGVIEW_SOURCE_IP_MATCHED"
    return "TRADINGVIEW_SOURCE_IP_NOT_MATCHED"
