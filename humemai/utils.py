"""Utility functions for the Humemai package."""

from datetime import datetime


def validate_iso_format(date_str):
    try:
        # This will raise a ValueError if the format is not correct
        datetime.fromisoformat(date_str)
        return True
    except ValueError:
        return False
