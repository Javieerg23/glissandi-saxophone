#!/usr/bin/env python
"""Utilidad de línea de comandos de Django, solo para desarrollo.

Django command-line utility, for development only.
"""

import os
import sys


def main() -> None:
    """Ejecuta la tarea administrativa indicada. / Runs the given administrative task."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
