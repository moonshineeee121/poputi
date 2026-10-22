"""Prepare the local application without creating privileged demo accounts."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.core.management import call_command

call_command("migrate", interactive=False)
call_command("seed_demo")
call_command("check")
