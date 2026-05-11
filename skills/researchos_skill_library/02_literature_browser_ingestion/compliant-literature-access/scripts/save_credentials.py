from __future__ import annotations

import argparse
import getpass
import sys

from credential_store import (
    CredentialStoreError,
    delete_credentials,
    get_credentials,
    list_services,
    save_credentials,
    store_path,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Save or manage local institutional credentials for compliant literature access."
    )
    parser.add_argument("--service", default="institution-access", help="Credential service name.")
    parser.add_argument("--username", help="Institution username. Prompts if omitted.")
    parser.add_argument("--password-env", help="Read password from this environment variable instead of prompting.")
    parser.add_argument("--list", action="store_true", help="List saved credential service names.")
    parser.add_argument("--delete", action="store_true", help="Delete credentials for --service.")
    parser.add_argument("--test-read", action="store_true", help="Verify that --service can be decrypted.")
    args = parser.parse_args()

    try:
        if args.list:
            rows = list_services()
            if not rows:
                print(f"No saved credentials. Store file: {store_path()}")
                return 0
            for row in rows:
                print(
                    f"{row['service']}\tusername={row['username']}\t"
                    f"storage={row['storage']}\tupdated={row['updated_utc']}"
                )
            return 0

        if args.delete:
            deleted = delete_credentials(args.service)
            print("Deleted." if deleted else "No credentials found for that service.")
            return 0

        if args.test_read:
            creds = get_credentials(args.service)
            if creds is None:
                print("No credentials found for that service.", file=sys.stderr)
                return 1
            username, password = creds
            print(f"Credential readable: service={args.service}, username={username}, password_length={len(password)}")
            return 0

        username = args.username or input("Username: ").strip()
        if args.password_env:
            import os

            password = os.environ.get(args.password_env)
            if not password:
                print(f"Environment variable {args.password_env} is empty or missing.", file=sys.stderr)
                return 1
        else:
            password = getpass.getpass("Password: ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                print("Passwords did not match.", file=sys.stderr)
                return 1
        path = save_credentials(args.service, username, password)
        print(f"Saved credentials for service={args.service}, username={username}")
        print(f"Credential metadata file: {path}")
        return 0
    except CredentialStoreError as exc:
        print(f"Credential error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
