"""Both algorithms and the number-of-recommendations setting."""

import pytest

import recommender as rec
from conftest import make_profile


def ids(results):
    return [r["movieId"] for r in results]


# ---------- content-based ----------
def test_content_based_recommends_similar_genres_first(data):
    results, _ = rec.recommend_content_based(data, make_profile((1, 5.0)))
    assert ids(results)[0] == 2                      # identical genres to movie 1
    assert 1 not in ids(results)                     # already rated
    assert not {4, 5, 6} & set(ids(results))         # no shared genre at all
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_content_based_needs_a_liked_movie(data):
    results, message = rec.recommend_content_based(data, make_profile((1, 1.0)))
    assert results == []
    assert "above" in message


# ---------- collaborative ----------
def test_collaborative_recommends_movies_liked_together(data):
    results, _ = rec.recommend_collaborative(data, make_profile((1, 5.0), (6, 3.0)))
    assert {2, 3} <= set(ids(results))
    assert not {1, 4, 5, 7} & set(ids(results))      # rated, opposite taste, or too little data
    assert all("score_label" in r and r["reason"] for r in results)


def test_collaborative_needs_a_liked_movie(data):
    results, message = rec.recommend_collaborative(data, make_profile((1, 2.0)))
    assert results == []
    assert "at least one movie you rated" in message


def test_collaborative_ignores_movies_without_history(data):
    results, message = rec.recommend_collaborative(data, make_profile((8, 5.0)))  # movie 8 has no ratings
    assert results == []
    assert "rating history" in message


# ---------- get_recommendations + settings ----------
def test_empty_profile_gets_a_helpful_message(data):
    result = rec.get_recommendations(data, make_profile(), rec.METHOD_CONTENT)
    assert result["recommendations"] == []
    assert "Edit My List" in result["message"]


def test_unknown_method_raises(data):
    with pytest.raises(ValueError):
        rec.get_recommendations(data, make_profile((1, 5.0)), "magic")


@pytest.mark.parametrize("method", [rec.METHOD_CONTENT, rec.METHOD_COLLABORATIVE])
def test_requested_count_is_respected(data, method):
    profile = make_profile((1, 5.0))
    assert len(rec.get_recommendations(data, profile, method, n=1)["recommendations"]) == 1


def test_count_is_clamped_to_allowed_range(data, monkeypatch):
    profile = make_profile((1, 5.0))
    assert len(rec.get_recommendations(data, profile, rec.METHOD_CONTENT, n=0)["recommendations"]) == 1
    monkeypatch.setattr(rec, "MAX_RECOMMENDATIONS", 2)
    assert len(rec.get_recommendations(data, profile, rec.METHOD_CONTENT, n=99)["recommendations"]) == 2


def test_default_and_maximum_counts():
    assert rec.NUM_RECOMMENDATIONS == 5
    assert rec.MAX_RECOMMENDATIONS == 10
