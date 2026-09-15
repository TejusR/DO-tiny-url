from app.aliases import ALIAS_ALPHABET, ALIAS_LENGTH, generate_alias


def test_generated_alias_has_expected_shape() -> None:
    alias = generate_alias()

    assert len(alias) == ALIAS_LENGTH
    assert set(alias) <= set(ALIAS_ALPHABET)
