#!/usr/bin/env python3
"""Compatibility shim — the dashboard now ships as `eab dashboard`.

Prefer:  eab dashboard [--interval 300]
or:      python -m earth_agent_bench.dashboard
"""
from earth_agent_bench.dashboard import main

if __name__ == "__main__":
    main()
