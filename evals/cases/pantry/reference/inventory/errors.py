class PantryError(Exception):
    """A mistake in what the user typed or asked for: cli prints the message to stderr and exits with code 1."""
