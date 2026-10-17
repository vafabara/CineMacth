"""CineMatch - data loading, recommendation algorithms and user profiles.

This module contains NO GUI code. main.py calls the public functions below:

    load_data()                         read + clean the CSVs, build cached models
    search_movies()                     title search for the GUI
    load_profile() / set_rating() /     user profiles stored as JSON in users/
    remove_movie()
    get_recommendations()               content-based or collaborative filtering
"""

import json
import os
import re
import tempfile
import unicodedata
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
MOVIES_PATH = BASE_DIR / "movies.csv"
RATINGS_PATH = BASE_DIR / "ratings.csv"
USERS_DIR = BASE_DIR / "users"

METHOD_CONTENT = "content"
METHOD_COLLABORATIVE = "collaborative"

NUM_RECOMMENDATIONS = 5
MAX_SEARCH_RESULTS = 50

# Collaborative filtering
MIN_COMMON_RATERS = 3   # two movies need >= 3 shared raters, otherwise similarity = 0
SHRINKAGE = 10          # pulls similarities based on few shared raters towards 0
DAMPING = 1.0           # pulls predictions with weak evidence towards the average rating

# Popularity prior used only to break ties between equally good candidates
POPULARITY_PRIOR_VOTES = 10

NO_GENRES = "(no genres listed)"
USERNAME_PATTERN = re.compile(r"[\w-]{1,32}")
WINDOWS_RESERVED_NAMES = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


# --------------------------------------------------------------------------
# Loading and preprocessing
# --------------------------------------------------------------------------
def split_genres(text):
    """'Comedy|Drama' -> ['Comedy', 'Drama']. Missing/'(no genres listed)' -> []."""
    if not isinstance(text, str):
        return []
    genres = [g.strip() for g in text.split("|")]
    return [g for g in genres if g and g.lower() != NO_GENRES]


def _read_csv(path, required_columns):
    if not path.exists():
        raise FileNotFoundError(
            f"Could not find '{path.name}'. Place it in the project folder: {path.parent}"
        )
    try:
        frame = pd.read_csv(path)
    except Exception as exc:  # unreadable / not a CSV
        raise ValueError(f"'{path.name}' could not be read as a CSV file ({exc}).") from exc
    missing = [c for c in required_columns if c not in frame.columns]
    if missing:
        raise ValueError(f"'{path.name}' is missing required column(s): {', '.join(missing)}.")
    return frame


def _load_movies(path):
    movies = _read_csv(path, ["movieId", "title", "genres"])[["movieId", "title", "genres"]]
    movies["movieId"] = pd.to_numeric(movies["movieId"], errors="coerce")
    movies = movies.dropna(subset=["movieId", "title"])
    movies["movieId"] = movies["movieId"].astype(int)
    movies = movies.drop_duplicates(subset="movieId", keep="first")  # movieId must be unique
    movies["title"] = movies["title"].astype(str).str.strip()
    movies = movies[movies["title"] != ""]
    movies["genres"] = movies["genres"].fillna("").astype(str)
    movies = movies.reset_index(drop=True)

    movies["genre_list"] = movies["genres"].apply(split_genres)
    movies["genres_text"] = movies["genre_list"].apply(
        lambda genres: ", ".join(genres) if genres else "No genres listed"
    )
    movies["title_lower"] = movies["title"].str.lower()
    return movies


def _load_ratings(path, valid_movie_ids):
    ratings = _read_csv(path, ["userId", "movieId", "rating"])
    ratings = ratings.drop(columns=["timestamp"], errors="ignore")  # never needed

    for column in ["userId", "movieId", "rating"]:
        ratings[column] = pd.to_numeric(ratings[column], errors="coerce")
    ratings = ratings.dropna()
    ratings = ratings[np.isfinite(ratings["rating"]) & (ratings["rating"] > 0)]
    ratings = ratings.astype({"userId": int, "movieId": int, "rating": float})
    ratings = ratings[ratings["movieId"].isin(valid_movie_ids)]
    # one rating per (user, movie): keep the last one if a pair appears twice
    ratings = ratings.drop_duplicates(subset=["userId", "movieId"], keep="last")
    return ratings.reset_index(drop=True)


def _detect_rating_scale(ratings):
    """Rating choices offered in the GUI, taken from the data (normally 0.5 ... 5.0)."""
    values = np.sort(ratings["rating"].unique())
    step = float(np.diff(values).min()) if len(values) > 1 else 0.5
    scale = [round(float(v), 2) for v in np.arange(values.min(), values.max() + step / 2, step)]
    if len(scale) > 20 or len(scale) < 2:  # unusual data: fall back to the MovieLens scale
        scale = [x / 2 for x in range(1, 11)]
    return scale


def _build_collaborative_model(ratings, movie_index):
    """Item-based CF model: a user x movie matrix built only from historical ratings."""
    # Missing ratings stay NaN here - they are NOT treated as zero ratings.
    matrix = ratings.pivot(index="userId", columns="movieId", values="rating")

    # Adjusted cosine: subtract each user's own average so that "generous" and "harsh"
    # raters become comparable. After centering, "not rated" becomes 0 = "no opinion".
    user_means = matrix.mean(axis=1)
    centered = matrix.sub(user_means, axis=0).fillna(0.0).to_numpy(dtype=np.float32)
    mask = matrix.notna().to_numpy(dtype=np.float32)  # 1 where a rating exists

    item_ids = matrix.columns.to_numpy()
    return {
        "centered": centered,
        "mask": mask,
        "norms": np.sqrt((centered ** 2).sum(axis=0)),
        "column_of": {int(movie_id): col for col, movie_id in enumerate(item_ids)},
        "movie_rows": np.array([movie_index[int(m)] for m in item_ids]),
        "cache": {},  # column -> similarity row, filled lazily and reused
    }


def load_data(movies_path=MOVIES_PATH, ratings_path=RATINGS_PATH):
    """Load, clean and index the datasets once. Returns one dict used by everything else.

    The original CSV files are only read, never modified.
    """
    movies = _load_movies(Path(movies_path))
    ratings = _load_ratings(Path(ratings_path), set(movies["movieId"]))
    if movies.empty:
        raise ValueError("movies.csv contains no usable movies.")
    if ratings.empty:
        raise ValueError("ratings.csv contains no usable ratings.")

    # Per-movie statistics. 'popularity' is a damped average rating, used only as a tie-breaker.
    stats = ratings.groupby("movieId")["rating"].agg(["count", "mean"])
    global_mean = float(ratings["rating"].mean())
    movies["n_ratings"] = movies["movieId"].map(stats["count"]).fillna(0).astype(int)
    avg = movies["movieId"].map(stats["mean"]).fillna(global_mean)
    votes = movies["n_ratings"]
    movies["popularity"] = (votes * avg + POPULARITY_PRIOR_VOTES * global_mean) / (
        votes + POPULARITY_PRIOR_VOTES
    )

    movie_index = {int(m): i for i, m in enumerate(movies["movieId"])}

    # Content-based model: one TF-IDF vector per movie, built from its genres.
    try:
        vectorizer = TfidfVectorizer(tokenizer=split_genres, token_pattern=None, lowercase=False)
        tfidf = vectorizer.fit_transform(movies["genres"])
    except ValueError:  # no movie has any genre
        vectorizer, tfidf = None, None

    scale = _detect_rating_scale(ratings)
    return {
        "movies": movies,
        "movie_index": movie_index,
        "ratings": ratings,
        "vectorizer": vectorizer,
        "tfidf": tfidf,
        "collab": _build_collaborative_model(ratings, movie_index),
        "global_mean": global_mean,
        "rating_scale": scale,
        # thresholds relative to the scale (for 0.5-5.0: neutral = 2.5, liked >= 3.5)
        "neutral_rating": max(scale) * 0.5,
        "liked_rating": max(scale) * 0.7,
    }


# --------------------------------------------------------------------------
# Searching
# --------------------------------------------------------------------------
def search_movies(data, query, limit=MAX_SEARCH_RESULTS):
    """Case-insensitive partial title search. Returns (results, total_matches)."""
    query = (query or "").strip().lower()
    if not query:
        return [], 0

    movies = data["movies"]
    hits = movies[movies["title_lower"].str.contains(query, regex=False, na=False)]
    total = len(hits)
    # Titles that start with the query first, then the most-rated movies.
    hits = hits.assign(starts=hits["title_lower"].str.startswith(query))
    hits = hits.sort_values(["starts", "n_ratings"], ascending=[False, False]).head(limit)
    results = [
        {"movieId": int(row.movieId), "title": row.title, "genres": row.genres_text}
        for row in hits.itertuples()
    ]
    return results, total


# --------------------------------------------------------------------------
# User profiles (one JSON file per user in users/)
# --------------------------------------------------------------------------
def ensure_users_dir():
    USERS_DIR.mkdir(parents=True, exist_ok=True)


def normalize_username(raw):
    """Same person -> same string: trim, normalise unicode, lower-case.

    Only letters, digits, '_' and '-' are accepted. That makes every valid name a safe
    filename: no slashes, dots or spaces (no path traversal) and no two different names
    can end up sharing one file.
    """
    name = unicodedata.normalize("NFKC", raw or "").strip().casefold()
    if not name:
        raise ValueError("Please enter a username.")
    if not USERNAME_PATTERN.fullmatch(name):
        raise ValueError(
            "Usernames may only contain letters, numbers, '_' and '-' "
            "(1-32 characters, no spaces)."
        )
    if name in WINDOWS_RESERVED_NAMES:
        raise ValueError(f"'{name}' is a reserved name on Windows. Please choose another one.")
    return name


def _profile_path(username):
    path = (USERS_DIR / f"{username}.json").resolve()
    if path.parent != USERS_DIR.resolve():  # defence in depth against path tricks
        raise ValueError("Invalid username.")
    return path


def save_profile(profile):
    """Write the profile atomically: a crash mid-write can never leave a broken file."""
    ensure_users_dir()
    path = _profile_path(profile["username"])
    payload = {
        "username": profile["username"],
        "rated_movies": [
            {"movieId": int(e["movieId"]), "title": e["title"], "rating": float(e["rating"])}
            for e in profile["rated_movies"]
        ],
    }
    fd, tmp_name = tempfile.mkstemp(dir=USERS_DIR, prefix="tmp_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2, ensure_ascii=False)
        os.replace(tmp_name, path)
    except Exception:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise


def _clean_entries(data, entries):
    """Keep only valid, unique entries. Returns (clean_list, number_skipped)."""
    clean, skipped = {}, 0
    if not isinstance(entries, list):
        return [], 0
    for entry in entries:
        try:
            movie_id = int(entry["movieId"])
            rating = float(entry["rating"])
        except (KeyError, TypeError, ValueError):
            skipped += 1
            continue
        if movie_id not in data["movie_index"] or rating not in data["rating_scale"]:
            skipped += 1
            continue
        title = data["movies"].at[data["movie_index"][movie_id], "title"]
        clean[movie_id] = {"movieId": movie_id, "title": title, "rating": rating}  # no duplicates
    return list(clean.values()), skipped


def load_profile(data, raw_username):
    """Load the user's profile or create it. Returns (profile, created, warning_or_None)."""
    username = normalize_username(raw_username)
    path = _profile_path(username)
    ensure_users_dir()

    new_profile = {"username": username, "rated_movies": []}
    if not path.exists():
        save_profile(new_profile)
        return new_profile, True, None

    try:
        with open(path, encoding="utf-8") as file:
            stored = json.load(file)
        if not isinstance(stored, dict):
            raise ValueError("profile is not a JSON object")
    except (OSError, ValueError):  # JSONDecodeError and UnicodeDecodeError are ValueErrors
        # Keep the damaged file for inspection instead of silently destroying it.
        backup = path.with_name(f"{username}.corrupt-{datetime.now():%Y%m%d-%H%M%S}.bak")
        try:
            os.replace(path, backup)
        except OSError:
            backup = None
        save_profile(new_profile)
        note = f" The damaged file was kept as '{backup.name}'." if backup else ""
        return new_profile, True, "Your profile file was unreadable, so a fresh one was created." + note

    entries, skipped = _clean_entries(data, stored.get("rated_movies", []))
    profile = {"username": username, "rated_movies": entries}
    warning = None
    if skipped:
        warning = (
            f"{skipped} invalid entr{'y' if skipped == 1 else 'ies'} in your profile "
            "were ignored (they are dropped the next time the profile is saved)."
        )
    return profile, False, warning


def get_rating(profile, movie_id):
    for entry in profile["rated_movies"]:
        if entry["movieId"] == movie_id:
            return entry["rating"]
    return None


def set_rating(data, profile, movie_id, rating):
    """Add a movie, or update its rating if it is already in the list. Saves immediately."""
    movie_id, rating = int(movie_id), float(rating)
    if movie_id not in data["movie_index"]:
        raise ValueError("That movie is not in the dataset.")
    if rating not in data["rating_scale"]:
        raise ValueError(f"Rating must be one of: {data['rating_scale']}")

    title = data["movies"].at[data["movie_index"][movie_id], "title"]
    updated = [dict(e) for e in profile["rated_movies"]]
    for entry in updated:
        if entry["movieId"] == movie_id:  # same movie -> update, never duplicate
            entry["rating"] = rating
            break
    else:
        updated.append({"movieId": movie_id, "title": title, "rating": rating})

    # Save first; only change the in-memory profile if saving worked.
    save_profile({"username": profile["username"], "rated_movies": updated})
    profile["rated_movies"] = updated


def remove_movie(profile, movie_id):
    updated = [dict(e) for e in profile["rated_movies"] if e["movieId"] != int(movie_id)]
    save_profile({"username": profile["username"], "rated_movies": updated})
    profile["rated_movies"] = updated


# --------------------------------------------------------------------------
# Recommendations
# --------------------------------------------------------------------------
def _make_result(data, row, score, score_label, reason):
    movies = data["movies"]
    return {
        "movieId": int(movies.at[row, "movieId"]),
        "title": movies.at[row, "title"],
        "genres": movies.at[row, "genres_text"],
        "score": float(score),
        "score_label": score_label,
        "reason": reason,
    }


def _few_ratings_note(profile):
    count = len(profile["rated_movies"])
    if count < 3:
        return (
            f"You have rated only {count} movie{'s' if count != 1 else ''}, so these "
            "suggestions rest on very little information. Rate more movies for better results."
        )
    return None


def recommend_content_based(data, profile, n=NUM_RECOMMENDATIONS):
    """Content-based filtering on genres. Returns (recommendations, message_or_None).

    How it works:
      1. Every movie is a TF-IDF vector over genres (rare genres weigh more than 'Drama').
      2. The user's taste vector = sum over rated movies of (rating - neutral) * movie vector.
         Rating 5.0 pulls the taste strongly towards a movie's genres, 2.5 does nothing,
         1.0 pushes the taste away from them.
      3. Cosine similarity between the taste vector and every movie gives the score.
      4. Already-rated movies and movies with no positive match are dropped.
      5. Ties (many movies share identical genres) are broken by damped average rating.
    """
    tfidf, vectorizer = data["tfidf"], data["vectorizer"]
    if tfidf is None:
        return [], "The movie dataset has no genre information, so content-based filtering is not possible."

    rated_rows = [data["movie_index"][e["movieId"]] for e in profile["rated_movies"]]
    weights = np.array([e["rating"] - data["neutral_rating"] for e in profile["rated_movies"]])
    if not (weights > 0).any():
        return [], (
            f"None of your ratings are above {data['neutral_rating']:g}, so there is no sign of what "
            "you like yet. Rate at least one movie you enjoyed highly."
        )

    taste = np.asarray(tfidf[rated_rows].T.dot(weights)).reshape(1, -1)
    if not (taste > 0).any():
        return [], "The movies you liked have no genre information, so no taste profile could be built."

    scores = cosine_similarity(taste, tfidf).ravel()
    eligible = scores > 1e-6
    eligible[rated_rows] = False
    candidates = np.flatnonzero(eligible)

    # primary key: score (rounded to ignore float noise), secondary key: popularity
    order = np.lexsort((-data["movies"]["popularity"].to_numpy()[candidates],
                        -np.round(scores[candidates], 6)))
    top = candidates[order][:n]

    taste_by_genre = dict(zip(vectorizer.get_feature_names_out(), taste[0]))
    genre_lists = data["movies"]["genre_list"]
    results = []
    for row in top:
        matching = sorted(
            (g for g in genre_lists.iat[row] if taste_by_genre.get(g, 0) > 0),
            key=lambda g: -taste_by_genre[g],
        )[:3]
        reason = f"Matches your taste for {', '.join(matching)}." if matching else "Similar genres to movies you liked."
        results.append(_make_result(data, row, scores[row], f"Genre match: {scores[row] * 100:.0f}%", reason))

    notes = []
    if len(results) < n:
        notes.append(
            f"Only {len(results)} unrated movie{'s' if len(results) != 1 else ''} share genres with your "
            f"taste profile, so fewer than {n} could be recommended."
        )
    few = _few_ratings_note(profile)
    if few:
        notes.append(few)
    return results, "\n".join(notes) or None


def _item_similarities(collab, column):
    """Similarity of one movie to every other movie (computed once, then cached)."""
    cache = collab["cache"]
    if column in cache:
        return cache[column]

    centered, mask, norms = collab["centered"], collab["mask"], collab["norms"]
    dot = centered[:, column] @ centered                      # sum over users of a_u * b_u
    denominator = norms * norms[column]
    similarity = np.divide(dot, denominator, out=np.zeros_like(dot), where=denominator > 0)

    common = mask[:, column] @ mask                           # how many users rated both movies
    similarity = similarity * common / (common + SHRINKAGE)   # shrink: few shared raters = less trust
    similarity[common < MIN_COMMON_RATERS] = 0.0              # too little overlap: no similarity
    similarity[similarity < 0] = 0.0                          # only "liked together" counts
    similarity[column] = 0.0
    cache[column] = similarity
    return similarity


def recommend_collaborative(data, profile, n=NUM_RECOMMENDATIONS):
    """Item-based collaborative filtering. Returns (recommendations, message_or_None).

    How it works:
      1. Item-item similarity comes ONLY from the historical user-item matrix
         (adjusted cosine on user-mean-centred ratings; missing ratings are not zeros).
      2. The new user is never added to that matrix; their ratings are only used as the
         "anchors" - the movies we look for neighbours of.
      3. Predicted rating for a candidate = average rating + sum(sim * (rating - average))
         / (sum(sim) + damping), over the user's rated movies. Movies similar to ones the user
         rated high are pulled up, movies similar to disliked ones are pushed down.
      4. A candidate must be similar to at least one movie the user liked. If a movie has no
         reliable similarity to anything the user rated, it is skipped, not given a made-up score.
    """
    collab = data["collab"]
    anchors = [
        (collab["column_of"][e["movieId"]], e["rating"], e["title"])
        for e in profile["rated_movies"] if e["movieId"] in collab["column_of"]
    ]
    if not anchors:
        return [], (
            "None of the movies you rated have rating history in the dataset, so collaborative "
            "filtering has nothing to compare against."
        )

    ratings = np.array([a[1] for a in anchors])
    liked = ratings >= data["liked_rating"]
    if not liked.any():
        return [], (
            f"Collaborative filtering needs at least one movie you rated {data['liked_rating']:g} "
            "or higher to find similar movies."
        )

    similarities = np.vstack([_item_similarities(collab, a[0]) for a in anchors]).astype(np.float64)
    mean = data["global_mean"]
    predicted = mean + ((ratings - mean) @ similarities) / (similarities.sum(axis=0) + DAMPING)
    evidence = similarities[liked].sum(axis=0)   # similarity to movies the user liked

    eligible = (evidence > 0) & (predicted > mean)
    eligible[[a[0] for a in anchors]] = False    # never recommend what is already in the list
    candidates = np.flatnonzero(eligible)

    popularity = data["movies"]["popularity"].to_numpy()[collab["movie_rows"]]
    order = np.lexsort((-popularity[candidates], -np.round(predicted[candidates], 4)))
    top = candidates[order][:n]

    liked_positions = np.flatnonzero(liked)
    scale_max = max(data["rating_scale"])
    results = []
    for column in top:
        # the liked movies that contributed most to this recommendation
        strongest = liked_positions[np.argsort(-similarities[liked_positions, column])][:2]
        names = " and ".join(f"\"{anchors[i][2]}\"" for i in strongest if similarities[i, column] > 0)
        score = min(predicted[column], scale_max)
        results.append(_make_result(
            data, collab["movie_rows"][column], score,
            f"Estimated rating: {score:.1f} / {scale_max:g}",
            f"People who rated {names} highly also tended to like this movie.",
        ))

    notes = []
    skipped = len(profile["rated_movies"]) - len(anchors)
    if skipped:
        notes.append(f"{skipped} of your movies have no rating history in the dataset and were not used.")
    if not results:
        notes.append(
            "No movie could be scored reliably. A movie needs at least "
            f"{MIN_COMMON_RATERS} users in the dataset who rated both it and one of your movies."
        )
    elif len(results) < n:
        notes.append(
            f"Only {len(results)} movie{'s' if len(results) != 1 else ''} could be scored reliably "
            f"(movies need at least {MIN_COMMON_RATERS} shared raters with your rated movies), "
            f"so fewer than {n} are shown."
        )
    few = _few_ratings_note(profile)
    if few:
        notes.append(few)
    return results, "\n".join(notes) or None


def get_recommendations(data, profile, method, n=NUM_RECOMMENDATIONS):
    """Run the chosen algorithm. Returns {'recommendations': [...], 'message': str | None}.

    The chosen algorithm is never swapped silently: if it cannot produce results, the message
    explains why and the GUI offers the other algorithm as a choice.
    """
    if not profile["rated_movies"]:
        return {
            "recommendations": [],
            "message": "You haven't rated any movies yet. Open 'Edit My List', add some movies "
                       "you know and rate them, then come back for recommendations.",
        }
    if method == METHOD_CONTENT:
        recommendations, message = recommend_content_based(data, profile, n)
    elif method == METHOD_COLLABORATIVE:
        recommendations, message = recommend_collaborative(data, profile, n)
    else:
        raise ValueError(f"Unknown recommendation method: {method}")
    return {"recommendations": recommendations, "message": message}
