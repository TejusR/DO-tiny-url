from sqlalchemy import BigInteger, DateTime, String

from app.models import ShortLink


def test_short_links_model_matches_planned_schema() -> None:
    table = ShortLink.__table__

    assert table.primary_key.columns.keys() == ["id"]
    assert isinstance(table.c.alias.type, String)
    assert table.c.alias.type.length == 32
    assert table.c.alias.nullable is False
    assert table.c.original_url.nullable is False
    assert table.c.is_custom.nullable is False
    assert isinstance(table.c.created_at.type, DateTime)
    assert table.c.created_at.type.timezone is True
    assert isinstance(table.c.click_count.type, BigInteger)
    assert table.c.last_accessed_at.nullable is True
    assert {constraint.name for constraint in table.constraints} >= {
        "pk_short_links",
        "uq_short_links_alias",
    }
