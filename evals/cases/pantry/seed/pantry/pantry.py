"""Ruiz Bakery's stock program. Run: python3 pantry.py <command> [arguments]; python3 pantry.py help lists them."""
import sys

from inventory.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
