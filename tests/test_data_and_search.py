"""Loading, cleaning and searching the datasets."""

import pytest

import recommender as rec


def test_split_genres():
    assert rec.split_genres("Comedy|Drama") == ["Comedy", "Drama"]
    assert rec.split_genres("(no genres listed)") == []
    assert rec.split_genres(None) == []


def test_load_data_basic_shape(data):
    assert len(data["movies"]) == 8
    assert data["movie_index"][1] == 0
    assert data["rating_scale"] == [1.0, 2.0, 3.0, 4.0, 5.0]
    assert data["tfidf"].shape[0] == 8


def test_load_data_cleans_bad_ratings(tmp_path, csv_paths):
    movies, _ = csv_paths
    ratings = tmp_path / "dirty.csv"
    ratings.write_text(
        "userId,movieId,rating,timestamp\n"
        "1,1,4.0,0\n"
        "1,1,5.0,0\n"      # duplicate pair: the last one wins
        "2,999,3.0,0\n"    # unknown movie: ignored
        "3,2,,0\n"         # missing rating: dropped
        "4,2,abc,0\n",     # not a number: dropped
        encoding="utf-8",
    )
    cleaned = rec.load_data(movies, ratings)["ratings"]
    assert len(cleaned) == 1
    assert cleaned.iloc[0]["rating"] == 5.0
    assert "timestamp" not in cleaned.columns


def test_missing_file_raises(tmp_path, csv_paths):
    with pytest.raises(FileNotFoundError):
        rec.load_data(tmp_path / "nope.csv", csv_paths[1])


def test_missing_column_raises(tmp_path, csv_paths):
    bad = tmp_path / "bad_movies.csv"
    bad.write_text("movieId,title\n1,Alpha (2000)\n", encoding="utf-8")
    with pytest.raises(ValueError, match="genres"):
        rec.load_data(bad, csv_paths[1])


def test_search_is_case_insensitive_and_partial(data):
    results, total = rec.search_movies(data, "ALP")
    assert total == 1
    assert results[0]["title"] == "Alpha (2000)"


def test_search_empty_or_unknown_query(data):
    assert rec.search_movies(data, "") == ([], 0)
    assert rec.search_movies(data, "   ") == ([], 0)
    assert rec.search_movies(data, "zzz") == ([], 0)


def test_search_limit_caps_results_but_reports_total(data):
    results, total = rec.search_movies(data, "(200", limit=3)  # matches every title
    assert len(results) == 3
    assert total == 8
