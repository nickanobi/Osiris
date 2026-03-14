#!/usr/bin/env python3
"""
Osiris — User Management Script
================================
Run this directly on the Pi via SSH to create, list, or remove Osiris accounts.
Never expose this script to the web — it is for admin use only.

Usage:
  python3 add_user.py add <username> "<Display Name>" <password>
  python3 add_user.py list
  python3 add_user.py delete <username>
  python3 add_user.py password <username> <new_password>

Examples:
  python3 add_user.py add nick "Nick" mysecretpassword
  python3 add_user.py add emily "Emily" herown password
  python3 add_user.py list
  python3 add_user.py password nick newpassword123
  python3 add_user.py delete emily
"""

import json
import os
import sys
from werkzeug.security import generate_password_hash

USERS_FILE = os.path.expanduser("~/agent/users.json")


def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE) as f:
            return json.load(f)
    return {}


def save_users(users):
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)
    print(f"Saved to {USERS_FILE}")


def cmd_add(username, display_name, password):
    username = username.lower().strip()
    users = load_users()
    if username in users:
        print(f"User '{username}' already exists. Use 'password' to change their password.")
        return
    users[username] = {
        "display_name": display_name,
        "password_hash": generate_password_hash(password),
        "created": __import__("datetime").date.today().isoformat()
    }
    save_users(users)
    print(f"✓ User '{username}' ({display_name}) created successfully.")
    memory_file = os.path.expanduser(f"~/agent/memory_{username}.json")
    if not os.path.exists(memory_file):
        with open(memory_file, "w") as f:
            json.dump({"facts": []}, f)
        print(f"✓ Memory file created: {memory_file}")


def cmd_list():
    users = load_users()
    if not users:
        print("No users configured. Run: python3 add_user.py add <username> \"<Name>\" <password>")
        return
    print(f"\n{'USERNAME':<16} {'DISPLAY NAME':<20} {'CREATED'}")
    print("-" * 50)
    for u, data in users.items():
        print(f"{u:<16} {data.get('display_name', ''):<20} {data.get('created', '—')}")
    print()


def cmd_delete(username):
    username = username.lower().strip()
    users = load_users()
    if username not in users:
        print(f"User '{username}' not found.")
        return
    confirm = input(f"Delete user '{username}' ({users[username].get('display_name', '')})? "
                    f"Their memory file will NOT be deleted. Type yes to confirm: ")
    if confirm.strip().lower() != "yes":
        print("Cancelled.")
        return
    del users[username]
    save_users(users)
    print(f"✓ User '{username}' removed.")


def cmd_password(username, new_password):
    username = username.lower().strip()
    users = load_users()
    if username not in users:
        print(f"User '{username}' not found.")
        return
    users[username]["password_hash"] = generate_password_hash(new_password)
    save_users(users)
    print(f"✓ Password updated for '{username}'.")


def print_usage():
    print(__doc__)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "add" and len(sys.argv) == 5:
        cmd_add(sys.argv[2], sys.argv[3], sys.argv[4])

    elif cmd == "list":
        cmd_list()

    elif cmd == "delete" and len(sys.argv) == 3:
        cmd_delete(sys.argv[2])

    elif cmd == "password" and len(sys.argv) == 4:
        cmd_password(sys.argv[2], sys.argv[3])

    else:
        print_usage()
        sys.exit(1)
