#!/usr/bin/env python3
"""
Broken Network Fix Simulation — interactive troubleshooting lab.

Load a broken scenario, run CLI diagnostics, apply fixes, and verify.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from network_state import SCENARIOS, NetworkLab


def print_header() -> None:
    print("=" * 58)
    print("  Network Troubleshooting Lab")
    print("  Broken Network Fix Simulation")
    print("=" * 58)


def print_menu() -> None:
    print("\n  Commands")
    print("  --------")
    print("  scenarios          List broken scenarios")
    print("  load <id>          Load a scenario (e.g. load wrong-gateway)")
    print("  status             Show current scenario / fault")
    print("  ipconfig [host]    Show PC settings (pc-user or pc-conflict)")
    print("  ping <host>        Ping an IP or hostname")
    print("  tracert <host>     Trace route to destination")
    print("  nslookup <name>    Query DNS")
    print("  set gateway <ip>   Set PC default gateway (wrong-gateway fix)")
    print("  set dns <ip>       Set PC DNS server (dns-misconfig fix)")
    print("  set dns-record <name> <ip>  Fix DNS zone on SRV-DNS")
    print("  ip route <net> <mask> <next-hop>  Add static route on R-CORE")
    print("  show ip route [router] Show routing table (default R-CORE)")
    print("  arp                Show ARP table")
    print("  fix                Apply the correct fix automatically")
    print("  verify             Run verification tests")
    print("  baseline           Reset to working network")
    print("  help               Show this menu")
    print("  quit               Exit")


def cmd_scenarios() -> None:
    print("\n  Available Scenarios")
    print(f"  {'ID':<18} {'Title'}")
    print(f"  {'-' * 18} {'-' * 30}")
    for s in SCENARIOS:
        print(f"  {s.id:<18} {s.title}")


def cmd_load(lab: NetworkLab, arg: str) -> None:
    if not arg:
        print("  Usage: load <scenario-id>")
        return
    try:
        scenario = lab.load_scenario(arg)
    except ValueError as exc:
        print(f"  Error: {exc}")
        return
    print(f"\n  Loaded: {scenario.title}")
    print(f"  Problem: {scenario.problem}")
    print("  Use diagnostic commands to investigate, then apply manual fixes or 'fix'.")


def cmd_ping(lab: NetworkLab, arg: str) -> None:
    if not arg:
        print("  Usage: ping <ip-or-hostname>")
        return
    print()
    print(lab.ping(arg))


def cmd_tracert(lab: NetworkLab, arg: str) -> None:
    if not arg:
        print("  Usage: tracert <ip-or-hostname>")
        return
    print()
    print(lab.traceroute(arg))


def cmd_nslookup(lab: NetworkLab, args: list[str]) -> None:
    if not args:
        print("  Usage: nslookup <name> [server]")
        return
    print()
    server = args[1] if len(args) > 1 else None
    print(lab.nslookup(args[0], server))


def cmd_verify(lab: NetworkLab) -> None:
    results = lab.verify()
    print("\n  Verification")
    print(f"  {'-' * 40}")
    passed = 0
    for name, ok, status in results:
        mark = "OK" if ok else "XX"
        print(f"  [{mark}] {name}: {status}")
        if ok:
            passed += 1
    print(f"\n  Result: {passed}/{len(results)} passed")
    if passed == len(results):
        print("  Network is healthy.")


def cmd_set(lab: NetworkLab, args: list[str]) -> None:
    if len(args) < 2:
        print("  Usage:")
        print("    set gateway <ip>")
        print("    set dns <ip>")
        print("    set dns-record <name> <ip>")
        return

    setting = args[0].lower()
    try:
        if setting == "gateway":
            if len(args) != 2:
                print("  Usage: set gateway <ip>")
                return
            print(f"\n  {lab.set_gateway(args[1])}")
        elif setting == "dns":
            if len(args) != 2:
                print("  Usage: set dns <ip>")
                return
            print(f"\n  {lab.set_dns(args[1])}")
        elif setting in {"dns-record", "record"}:
            if len(args) != 3:
                print("  Usage: set dns-record <name> <ip>")
                return
            print(f"\n  {lab.set_dns_record(args[1], args[2])}")
        else:
            print(f"  Unknown setting: {setting}")
            print("  Use gateway, dns, or dns-record.")
    except ValueError as exc:
        print(f"  Error: {exc}")


def cmd_ip_route(lab: NetworkLab, args: list[str]) -> None:
    if len(args) != 3:
        print("  Usage: ip route <network> <mask> <next-hop>")
        print("  Example: ip route 192.168.2.0 255.255.255.0 10.0.0.6")
        return
    try:
        print(f"\n  {lab.add_ip_route(args[0], args[1], args[2])}")
    except ValueError as exc:
        print(f"  Error: {exc}")


def cmd_show_ip_route(lab: NetworkLab, args: list[str]) -> None:
    router = args[0] if args else "R-CORE"
    try:
        print(f"\n{lab.show_ip_route(router)}")
    except ValueError as exc:
        print(f"  Error: {exc}")


def run_repl() -> int:
    lab = NetworkLab()
    print_header()
    print("\n  Type 'help' for commands. Start with 'scenarios' then 'load <id>'.")

    handlers = {
        "help": lambda _: print_menu(),
        "scenarios": lambda _: cmd_scenarios(),
        "status": lambda _: print(f"\n  {lab.show_scenario()}"),
        "ipconfig": lambda args: print(
            f"\n{lab.ipconfig(args[0] if args else 'pc-user')}"
        ),
        "arp": lambda _: print(f"\n{lab.arp()}"),
        "fix": lambda _: print(f"\n  {lab.apply_fix()}"),
        "verify": lambda _: cmd_verify(lab),
        "baseline": lambda _: (lab.reset_baseline(), print("\n  Baseline network restored."))[1],
        "quit": None,
        "exit": None,
    }

    while True:
        try:
            raw = input("\nlab> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return 0

        if not raw:
            continue

        parts = raw.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in {"quit", "exit"}:
            print("Goodbye.")
            return 0
        if cmd == "load":
            cmd_load(lab, args[0] if args else "")
        elif cmd == "ping":
            cmd_ping(lab, args[0] if args else "")
        elif cmd in {"tracert", "traceroute"}:
            cmd_tracert(lab, args[0] if args else "")
        elif cmd == "nslookup":
            cmd_nslookup(lab, args)
        elif cmd == "set":
            cmd_set(lab, args)
        elif cmd == "ip" and args and args[0].lower() == "route":
            cmd_ip_route(lab, args[1:])
        elif cmd == "show" and len(args) >= 2 and args[0].lower() == "ip" and args[1].lower() == "route":
            cmd_show_ip_route(lab, args[2:])
        elif cmd in handlers:
            handlers[cmd](args)
        else:
            print(f"  Unknown command: {cmd}. Type 'help'.")


if __name__ == "__main__":
    raise SystemExit(run_repl())
