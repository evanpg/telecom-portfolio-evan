"""Shared IP network helpers for the subnetting lab."""

from __future__ import annotations

import ipaddress


def parse_cidr(value: str) -> ipaddress.IPv4Network | ipaddress.IPv6Network:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("CIDR notation cannot be empty.")
    try:
        return ipaddress.ip_network(cleaned, strict=False)
    except ValueError as exc:
        raise ValueError(f"Invalid CIDR notation: {exc}") from exc


def usable_hosts(network: ipaddress.IPv4Network | ipaddress.IPv6Network) -> int:
    total = network.num_addresses
    prefix = network.prefixlen

    if network.version == 4:
        if prefix >= 31:
            return total
        return total - 2

    if prefix == 128:
        return 1
    return total - 1


def iter_usable_addresses(
    network: ipaddress.IPv4Network | ipaddress.IPv6Network,
) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Return assignable host addresses for a network block."""
    if network.version == 4 and network.prefixlen <= 30:
        return list(network.hosts())
    return [addr for addr in network if addr != network.network_address]


def is_assignable(
    network: ipaddress.IPv4Network | ipaddress.IPv6Network,
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> bool:
    if address not in network:
        return False
    usable = {str(ip) for ip in iter_usable_addresses(network)}
    return str(address) in usable


def max_equal_subnets(network: ipaddress.IPv4Network | ipaddress.IPv6Network) -> int:
    if network.version == 4:
        return 2 ** (32 - network.prefixlen)
    return 2 ** (128 - network.prefixlen)


def subnet_count(network: ipaddress.IPv4Network | ipaddress.IPv6Network) -> int:
    return 1


def subnets_overlap(
    left: ipaddress.IPv4Network | ipaddress.IPv6Network,
    right: ipaddress.IPv4Network | ipaddress.IPv6Network,
) -> bool:
    """Return True if two networks share any address space."""
    if left.version != right.version:
        return False
    return left.overlaps(right)
