from aurex.signal_gateway.tradingview_delivery import (
    TRADINGVIEW_DOCUMENTED_IPV4_HOST_NETWORKS,
    tradingview_origin_status,
    tradingview_source_network_snapshot,
    tradingview_source_networks_sha256,
)


def test_documented_source_networks_are_canonical_and_hash_bound() -> None:
    snapshot = tradingview_source_network_snapshot(
        "52.89.214.238/32,34.212.75.30,54.218.53.128/32,52.32.178.7"
    )

    assert (
        snapshot.configuration_status
        == "SOURCE_NETWORK_CONFIGURATION_DOCUMENTED_IPV4_HOSTS"
    )
    assert snapshot.networks == TRADINGVIEW_DOCUMENTED_IPV4_HOST_NETWORKS
    assert snapshot.networks_sha256 == tradingview_source_networks_sha256(
        snapshot.networks
    )
    assert tradingview_origin_status("52.89.214.238", snapshot) == (
        "TRADINGVIEW_SOURCE_IP_MATCHED"
    )


def test_broad_source_network_can_match_but_is_not_safe_proof_configuration() -> None:
    snapshot = tradingview_source_network_snapshot("52.89.214.0/24")

    assert (
        snapshot.configuration_status
        == "SOURCE_NETWORK_CONFIGURATION_UNSAFE_SCOPE"
    )
    assert tradingview_origin_status("52.89.214.238", snapshot) == (
        "TRADINGVIEW_SOURCE_IP_MATCHED"
    )


def test_undocumented_exact_host_is_not_accepted_as_documented_sender() -> None:
    snapshot = tradingview_source_network_snapshot("203.0.113.7/32")

    assert (
        snapshot.configuration_status
        == "SOURCE_NETWORK_CONFIGURATION_UNVERIFIED_IPV4_HOSTS"
    )
    assert tradingview_origin_status("203.0.113.7", snapshot) == (
        "TRADINGVIEW_SOURCE_IP_MATCHED"
    )


def test_invalid_and_empty_source_network_configurations_are_explicit() -> None:
    invalid = tradingview_source_network_snapshot("not-a-network")
    empty = tradingview_source_network_snapshot(" ")

    assert (
        invalid.configuration_status
        == "SOURCE_NETWORK_CONFIGURATION_INVALID"
    )
    assert tradingview_origin_status("52.89.214.238", invalid) == (
        "SOURCE_NETWORK_CONFIGURATION_INVALID"
    )
    assert empty.configuration_status == "SOURCE_NETWORKS_NOT_CONFIGURED"
    assert tradingview_origin_status("52.89.214.238", empty) == (
        "SOURCE_NETWORKS_NOT_CONFIGURED"
    )


def test_remote_ip_failures_are_preserved_before_network_matching() -> None:
    snapshot = tradingview_source_network_snapshot("52.89.214.238/32")

    assert tradingview_origin_status(None, snapshot) == "REMOTE_IP_MISSING"
    assert tradingview_origin_status("testclient", snapshot) == "REMOTE_IP_INVALID"
