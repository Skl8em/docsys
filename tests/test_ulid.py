"""ULIDs (the documentation system's ADR-028): 26 Crockford-base32 characters, a
48-bit timestamp — or, in the ordinal mode, a controlled sort key — then 80 random
bits; sortable by the leading timestamp."""

import pytest

from docsys.ulid import is_ulid, new_ulid, timestamp_of


def test_a_new_ulid_is_valid() -> None:
    assert is_ulid(new_ulid())


def test_the_timestamp_round_trips() -> None:
    assert timestamp_of(new_ulid(ts_ms=1_760_000_000_000)) == 1_760_000_000_000


def test_the_ordinal_mode_encodes_the_order() -> None:
    assert timestamp_of(new_ulid(order=8_500_000)) == 8_500_000


def test_ulids_sort_by_timestamp() -> None:
    assert new_ulid(ts_ms=1, rand=2**80 - 1) < new_ulid(ts_ms=2, rand=0)


def test_randomness_is_explicit_when_given() -> None:
    assert new_ulid(ts_ms=0, rand=0) == "0" * 26


def test_a_timestamp_outside_48_bits_is_refused() -> None:
    with pytest.raises(ValueError, match="out of 48-bit range"):
        new_ulid(ts_ms=2**48)


@pytest.mark.parametrize(
    "candidate",
    [
        pytest.param("01M4FM6C3CASQQB5BRBN7C3BGE", id="a real ULID"),
    ],
)
def test_valid(candidate: str) -> None:
    assert is_ulid(candidate)


@pytest.mark.parametrize(
    "candidate",
    [
        pytest.param("01M4FM6C3CASQQB5BRBN7C3BG", id="too short"),
        pytest.param("01M4FM6C3CASQQB5BRBN7C3BGI", id="the excluded letter I"),
        pytest.param("01m4fm6c3casqqb5brbn7c3bge", id="lower case"),
        pytest.param("", id="empty"),
        pytest.param(None, id="None"),
    ],
)
def test_invalid(candidate: str | None) -> None:
    assert not is_ulid(candidate)
