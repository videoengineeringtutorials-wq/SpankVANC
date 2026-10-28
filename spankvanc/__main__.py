from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .engine import ConfigError, doctor, plan


def main():
    parser = argparse.ArgumentParser(prog="spankvanc")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Check installed media capabilities")
    planner = commands.add_parser("plan", help="Validate a saved route")
    planner.add_argument("config", type=Path)
    server = commands.add_parser("serve", help="Open the local browser control service")
    server.add_argument("--port", type=int, default=8877)
    server.add_argument("--state-dir", type=Path, default=Path("runtime"))
    args = parser.parse_args()
    try:
        if args.command == "doctor":
            print(json.dumps(doctor(), indent=2))
        elif args.command == "plan":
            result = plan(json.loads(args.config.read_text()))
            print(json.dumps(result, indent=2))
            return 0 if result["ready"] else 2
        else:
            from .server import serve
            serve(args.port, args.state_dir)
    except (ConfigError, OSError, ValueError) as exc:
        print(f"SpankVANC: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
