import argparse


def _parse_print_count(value: str) -> int | None:
    if value.lower() == "all":
        return None
    count = int(value)
    if count < 0:
        raise argparse.ArgumentTypeError("print-count must be >= 0 or 'all'.")
    return count
