"""Usernames and the JSON profile files."""

import json

import pytest

import recommender as rec


@pytest.mark.parametrize("raw, expected", [("Vafa", "vafa"), ("  vafa  ", "vafa"), ("a_b-1", "a_b-1")])
def test_normalize_username_valid(raw, expected):
    assert rec.normalize_username(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", None, "../evil", "a b", "a/b", "x" * 33, "con", "LPT1"])
def test_normalize_username_invalid(raw):
    with pytest.raises(ValueError):
        rec.normalize_username(raw)


def test_new_profile_is_created_and_saved(data, users_dir):
    profile, created, warning = rec.load_profile(data, "Vafa")
    assert created and warning is None
    assert profile == {"username": "vafa", "rated_movies": []}
    assert (users_dir / "vafa.json").exists()


def test_same_user_different_spelling_loads_same_file(data):
    profile, _, _ = rec.load_profile(data, "vafa")
    rec.set_rating(data, profile, 1, 4.0)
    again, created, _ = rec.load_profile(data, " VAFA ")
    assert not created
    assert again["rated_movies"][0]["movieId"] == 1


def test_set_rating_adds_then_updates_without_duplicates(data):
    profile, _, _ = rec.load_profile(data, "vafa")
    rec.set_rating(data, profile, 1, 4.0)
    rec.set_rating(data, profile, 1, 2.0)
    assert len(profile["rated_movies"]) == 1
    assert rec.get_rating(profile, 1) == 2.0
    assert rec.get_rating(profile, 2) is None


def test_set_rating_rejects_bad_input(data):
    profile, _, _ = rec.load_profile(data, "vafa")
    with pytest.raises(ValueError):
        rec.set_rating(data, profile, 999, 3.0)   # unknown movie
    with pytest.raises(ValueError):
        rec.set_rating(data, profile, 1, 3.3)     # not on the rating scale
    assert profile["rated_movies"] == []          # nothing changed


def test_remove_movie_is_saved(data):
    profile, _, _ = rec.load_profile(data, "vafa")
    rec.set_rating(data, profile, 1, 4.0)
    rec.set_rating(data, profile, 2, 5.0)
    rec.remove_movie(profile, 1)
    reloaded, _, _ = rec.load_profile(data, "vafa")
    assert [e["movieId"] for e in reloaded["rated_movies"]] == [2]


def test_corrupted_profile_is_backed_up_and_reset(data, users_dir):
    users_dir.mkdir(parents=True)
    (users_dir / "vafa.json").write_text("{ not json", encoding="utf-8")
    profile, created, warning = rec.load_profile(data, "vafa")
    assert created and profile["rated_movies"] == []
    assert "unreadable" in warning
    assert list(users_dir.glob("vafa.corrupt-*.bak"))


def test_invalid_entries_are_skipped_with_a_warning(data, users_dir):
    users_dir.mkdir(parents=True)
    stored = {"username": "vafa", "rated_movies": [
        {"movieId": 1, "rating": 4.0},
        {"movieId": 999, "rating": 4.0},   # unknown movie
        {"movieId": 2, "rating": 9.9},     # rating not on the scale
        {"title": "no id"},                # missing keys
    ]}
    (users_dir / "vafa.json").write_text(json.dumps(stored), encoding="utf-8")
    profile, created, warning = rec.load_profile(data, "vafa")
    assert not created
    assert [e["movieId"] for e in profile["rated_movies"]] == [1]
    assert "3 invalid entries" in warning
