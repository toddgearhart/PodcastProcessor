from __future__ import annotations

import getpass

from app.auth import password_hash


def main() -> None:
    first = getpass.getpass("Administrator password: ")
    second = getpass.getpass("Confirm password: ")
    if not first or first != second:
        raise SystemExit("Passwords were empty or did not match")
    print(password_hash.hash(first))


if __name__ == "__main__":
    main()

