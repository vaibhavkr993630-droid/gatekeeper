"""Settings normalization that matters for deployment."""
import pytest

from app.core.config import Settings


@pytest.mark.parametrize(
    "given",
    [
        "postgres://u:p@host:5432/db",  # Heroku/Render-style
        "postgresql://u:p@host:5432/db",  # bare libpq URL
        "postgresql+asyncpg://u:p@host:5432/db",  # already correct
    ],
)
def test_database_url_gets_the_async_driver(given):
    s = Settings(database_url=given, _env_file=None)
    assert s.database_url == "postgresql+asyncpg://u:p@host:5432/db"


def test_allowed_host_list_parsing():
    assert Settings(allowed_hosts="*", _env_file=None).allowed_host_list == ["*"]
    assert Settings(allowed_hosts="a.com, b.com", _env_file=None).allowed_host_list == [
        "a.com",
        "b.com",
    ]
    assert Settings(allowed_hosts="", _env_file=None).allowed_host_list == ["*"]
