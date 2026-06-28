# Scenario Index

| # | File | Break Type | Key Symptom |
|---|------|------------|-------------|
| 1 | [01-wrong-gateway.md](01-wrong-gateway.md) | Wrong default gateway | Nothing beyond local subnet works |
| 2 | [02-dns-misconfiguration.md](02-dns-misconfiguration.md) | DNS client or zone error | IP works; hostname fails |
| 3 | [03-ip-conflict.md](03-ip-conflict.md) | Duplicate IP address | Intermittent / flaky connectivity |
| 4 | [04-missing-route.md](04-missing-route.md) | Missing static route | Traceroute stops mid-path |

Each scenario follows the same structure:

1. **Problem** — what the user experiences
2. **Diagnosis** — CLI commands and expected findings
3. **Fix** — configuration change
4. **Verification** — ping / traceroute / nslookup proof

Run all scenarios in the Python simulator:

```powershell
python simulator/run_lab.py
```

Or load broken configs in Packet Tracer from `configs/broken/` and follow the matching scenario guide.
