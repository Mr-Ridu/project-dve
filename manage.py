#!/usr/bin/env python
"""Django management command entry point.

Development defaults to config.settings.dev; production (cPanel Passenger)
sets DJANGO_SETTINGS_MODULE=config.settings.prod in the app environment.
"""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Is it installed and available on your PYTHONPATH? "
            "Did you forget to activate the virtual environment (.venv)?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
