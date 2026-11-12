"""Small admin CLI.

    python -m app.cli hash-password

Prompts for a password and prints its bcrypt hash, the value of ADMIN_PASSWORD_HASH.
`--password VALUE` skips the prompt (the value then lands in the shell history).
"""

import argparse
import getpass
import sys

from app.core.security import hash_password


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    hash_cmd = commands.add_parser("hash-password", help="bcrypt hash for ADMIN_PASSWORD_HASH")
    hash_cmd.add_argument("--password", help="omit to be prompted")
    args = parser.parse_args(argv)

    password = args.password or getpass.getpass("Admin password: ")
    if len(password) < 8:
        print("The password must have at least 8 characters.", file=sys.stderr)
        return 1
    print(hash_password(password))
    return 0


if __name__ == "__main__":
    sys.exit(main())
