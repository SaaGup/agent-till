"""A production deployment must not run on the development signing key: a guessable JWT secret
lets anyone mint a merchant session and approve their own orders, which silently disables the
human-in-the-loop gate rather than visibly breaking it."""

import pytest

from app.config import settings
from app.main import DEV_JWT_SECRET, _check_production_secrets


@pytest.fixture
def restore_settings():
    original = (settings.environment, settings.jwt_secret, settings.demo_key)
    yield
    settings.environment, settings.jwt_secret, settings.demo_key = original


def test_development_boots_with_defaults(restore_settings):
    settings.environment = "development"
    settings.jwt_secret = DEV_JWT_SECRET
    settings.demo_key = "change-me"
    _check_production_secrets()  # must not raise


def test_production_refuses_the_development_secret(restore_settings):
    settings.environment = "production"
    settings.jwt_secret = DEV_JWT_SECRET
    settings.demo_key = "a-real-demo-key"
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        _check_production_secrets()


def test_production_refuses_a_short_secret(restore_settings):
    settings.environment = "production"
    settings.jwt_secret = "too-short"
    settings.demo_key = "a-real-demo-key"
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        _check_production_secrets()


def test_production_refuses_the_default_demo_key(restore_settings):
    settings.environment = "production"
    settings.jwt_secret = "x" * 48
    settings.demo_key = "change-me"
    with pytest.raises(RuntimeError, match="DEMO_KEY"):
        _check_production_secrets()


def test_production_boots_when_secrets_are_set(restore_settings):
    settings.environment = "production"
    settings.jwt_secret = "x" * 48
    settings.demo_key = "a-real-demo-key"
    _check_production_secrets()  # must not raise
