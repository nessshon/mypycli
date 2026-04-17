from __future__ import annotations

import argparse
import sys

from mypycli.cli.commands.locales import cmd_check, cmd_init, cmd_sync


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``mypycli`` dev-tooling CLI."""
    parser = argparse.ArgumentParser(prog="mypycli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    locales = subparsers.add_parser("locales", help="Manage locale files")
    locales_sub = locales.add_subparsers(dest="subcommand", required=True)
    locales_sub.add_parser("init", help="Scaffold locales/ with bundled defaults")
    locales_sub.add_parser("sync", help="Update mypycli: section in locales/*.yml")
    locales_sub.add_parser("check", help="Validate locales/ consistency")

    args = parser.parse_args(argv)

    if args.command == "locales":
        if args.subcommand == "init":
            return cmd_init()
        if args.subcommand == "sync":
            return cmd_sync()
        if args.subcommand == "check":
            return cmd_check()

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
