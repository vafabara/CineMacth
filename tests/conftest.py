"""Shared fixtures: a tiny, fully predictable dataset so every test is deterministic."""

import sys
from pathlib import Path

import pytest

# make `import recommender` work when pytest is started from any folder
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import recommender as rec  # noqa: E402

MOVIES_CSV = """movieId,title,genres
1,Alpha (2000),Action|Sci-Fi
2,Beta (2001),Action|Sci-Fi
3,Gamma (2002),Action
4,Delta (2003),Comedy
5,Epsilon (2004),Comedy|Romance
6,Zeta (2005),Drama
7,Eta (2006),Sci-Fi
8,Theta (2007),(no genres listed)
"""


def _ratings_csv():
    """Users 1-6 love movies 1-3 and dislike 4-5; users 7-12 are the opposite.

    So movies 1, 2 and 3 are "liked together", and 4 and 5 are their opposite.
    Movie 7 is rated by one user only (too little data for collaborative filtering).
    """
    lines = ["userId,movieId,rating,timestamp"]
    for user in range(1, 13):
        group_a = user <= 6
        for movie in (1, 2, 3):
            lines.append(f"{user},{movie},{5.0 if group_a else 1.0},0")
        for movie in (4, 5):
            lines.append(f"{user},{movie},{1.0 if group_a else 5.0},0")
        lines.append(f"{user},6,3.0,0")
    lines.append("1,7,4.0,0")
    return "\n".join(lines) + "\n"


@pytest.fixture
def csv_paths(tmp_path):
    movies, ratings = tmp_path / "movies.csv", tmp_path / "ratings.csv"
    movies.write_text(MOVIES_CSV, encoding="utf-8")
    ratings.write_text(_ratings_csv(), encoding="utf-8")
    return movies, ratings


@pytest.fixture
def data(csv_paths):
    return rec.load_data(*csv_paths)


@pytest.fixture(autouse=True)
def users_dir(tmp_path, monkeypatch):
    """Profiles are written to a temporary folder, never to the real users/ folder."""
    folder = tmp_path / "users"
    monkeypatch.setattr(rec, "USERS_DIR", folder)
    return folder


def make_profile(*pairs, username="tester"):
    """make_profile((1, 5.0), (2, 4.0)) -> an in-memory profile (not saved)."""
    return {
        "username": username,
        "rated_movies": [{"movieId": m, "title": f"movie {m}", "rating": r} for m, r in pairs],
    }
