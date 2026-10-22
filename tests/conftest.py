import pytest


@pytest.fixture(autouse=True)
def fast_password_hashing(settings):
    # Only the test environment uses a fast hasher; the application keeps Django's defaults.
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
