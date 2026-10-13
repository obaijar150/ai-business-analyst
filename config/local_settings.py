"""Local-only settings for running the demo without PostgreSQL or Docker."""

from .settings import *  # noqa: F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "local-demo.sqlite3",  # noqa: F405
    }
}
