#!/usr/bin/env python3
"""
Subnetting Lab - CIDR calculator and device IP registry.

Prompts for CIDR notation, manages device-to-IP assignments in SQLite,
and reports subnet capacity with remaining usable addresses.
"""

from __future__ import annotations

import ipaddress

from device_registry import DeviceRegistry
from network_utils import (
    max_equal_subnets,
    parse_cidr,
    subnet_count,
    usable_hosts,
)


def format_details(network: ipaddress.IPv4Network | ipaddress.IPv6Network) -> str:
    hosts = usable_hosts(network)
    total = network.num_addresses
    max_splits = max_equal_subnets(network)

    lines = [
        "",
        "  Network Summary",
        "  " + "-" * 40,
        f"  CIDR:              {network.with_prefixlen}",
        f"  Network address:   {network.network_address}",
        f"  Broadcast:         {network.broadcast_address if network.version == 4 else 'N/A (IPv6)'}",
        f"  Subnet mask:       {network.netmask}",
        f"  Wildcard mask:     {network.hostmask if network.version == 4 else 'N/A (IPv6)'}",
        f"  Prefix length:     /{network.prefixlen}",
        "",
        f"  Subnets (this block):     {subnet_count(network)}",
        f"  Total addresses:          {total:,}",
        f"  Usable hosts:             {hosts:,}",
        f"  Max equal subnets possible: {max_splits:,}  (if subdivided to /{network.prefixlen + 1} or smaller)",
        "",
    ]

    if network.version == 4 and network.prefixlen <= 30:
        lines.append("  Common subdivisions (equal subnets):")
        for extra_bits in (1, 2, 3, 4):
            new_prefix = network.prefixlen + extra_bits
            if new_prefix > 30:
                break
            count = 2**extra_bits
            per_subnet = usable_hosts(
                ipaddress.ip_network(f"{network.network_address}/{new_prefix}", strict=False)
            )
            lines.append(f"    /{new_prefix}: {count} subnets x {per_subnet:,} usable hosts each")
        lines.append("")

    return "\n".join(lines)


def print_menu() -> None:
    print("\n  Menu")
    print("  ----")
    print("  1. Calculate subnet from CIDR")
    print("  2. Add device to IP")
    print("  3. Remove device from IP")
    print("  4. Print subnets and assignments")
    print("  5. Create tagged subnet")
    print("  6. Remove tagged subnet")
    print("  q. Quit")


def handle_calculate() -> None:
    raw = input("\n  Enter CIDR notation (e.g. 192.168.1.0/24): ").strip()
    if not raw:
        print("  Please enter a CIDR value.")
        return
    try:
        network = parse_cidr(raw)
    except ValueError as exc:
        print(f"  Error: {exc}")
        return
    print(format_details(network))


def handle_add(registry: DeviceRegistry) -> None:
    registry.print_subnets()
    subnet = input("\n  Subnet tag or CIDR (e.g. corporate or 192.168.1.0/24): ").strip()
    device = input("  Device name: ").strip()
    ip = input("  IP address: ").strip()

    try:
        assignment = registry.add_device(subnet, device, ip)
    except ValueError as exc:
        print(f"  Error: {exc}")
        return

    tag_note = f" [{assignment.tag}]" if assignment.tag else ""
    print(f"  Added {assignment.device_name} -> {assignment.ip_address} on {assignment.subnet_cidr}{tag_note}")
    print(f"  Remaining IPs on subnet: {registry.remaining_ips(assignment.subnet_cidr):,}")


def handle_remove(registry: DeviceRegistry) -> None:
    subnet = input("\n  Subnet tag or CIDR (optional, press Enter to skip): ").strip() or None
    device = input("  Device name (or press Enter): ").strip() or None
    ip = input("  IP address (or press Enter): ").strip() or None

    try:
        removed = registry.remove_device(subnet_key=subnet, device_name=device, ip_address=ip)
    except ValueError as exc:
        print(f"  Error: {exc}")
        return

    tag_note = f" [{removed.tag}]" if removed.tag else ""
    print(f"  Removed {removed.device_name} ({removed.ip_address}) from {removed.subnet_cidr}{tag_note}")
    print(f"  Remaining IPs on subnet: {registry.remaining_ips(removed.subnet_cidr):,}")


def handle_print(registry: DeviceRegistry) -> None:
    subnet = input("\n  Filter by tag or CIDR (optional, press Enter for all): ").strip() or None
    if subnet:
        try:
            registry.resolve_subnet(subnet)
        except ValueError as exc:
            print(f"  Error: {exc}")
            return
    registry.print_assignments(subnet)


def handle_create_subnet(registry: DeviceRegistry) -> None:
    tag = input("\n  Subnet tag (e.g. corporate, HR): ").strip()
    cidr = input("  CIDR notation (e.g. 192.168.10.0/24): ").strip()

    try:
        subnet = registry.create_subnet(tag, cidr)
        network = parse_cidr(subnet.subnet_cidr)
    except ValueError as exc:
        print(f"  Error: {exc}")
        return

    print(f"  Created subnet '{subnet.tag}' -> {subnet.subnet_cidr}")
    print(f"  Network address:  {subnet.network_address}")
    print(f"  Broadcast:        {subnet.broadcast_address}")
    print(f"  Usable hosts:     {usable_hosts(network):,}")
    print(f"  Remaining IPs:    {registry.remaining_ips(subnet.subnet_cidr):,}")


def handle_remove_subnet(registry: DeviceRegistry) -> None:
    registry.print_subnets()
    tag = input("\n  Subnet tag or CIDR to remove: ").strip()
    if not tag:
        print("  Please enter a registered subnet tag or CIDR.")
        return

    confirm = input(f"  Remove '{tag}' and all assignments in range? (y/N): ").strip().lower()
    if confirm not in {"y", "yes"}:
        print("  Cancelled.")
        return

    try:
        removed, count = registry.remove_subnet(tag)
    except ValueError as exc:
        print(f"  Error: {exc}")
        return

    print(f"  Removed subnet '{removed.tag}' ({removed.subnet_cidr})")
    print(f"  Deleted {count} assignment(s) within range")


def main() -> int:
    registry = DeviceRegistry()

    print("=" * 50)
    print("  Subnetting Lab - CIDR Calculator")
    print("  Device IP Registry (assignments.db)")
    print("=" * 50)

    while True:
        print_menu()
        try:
            choice = input("\n  Select option: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return 0

        if choice in {"q", "quit", "exit"}:
            print("Goodbye.")
            return 0
        if choice == "1":
            handle_calculate()
        elif choice == "2":
            handle_add(registry)
        elif choice == "3":
            handle_remove(registry)
        elif choice == "4":
            handle_print(registry)
        elif choice == "5":
            handle_create_subnet(registry)
        elif choice == "6":
            handle_remove_subnet(registry)
        else:
            print("  Invalid option. Choose 1-6 or q.")


if __name__ == "__main__":
    raise SystemExit(main())
