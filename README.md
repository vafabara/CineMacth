# CineMatch - Movie Recommender

CineMatch is a small desktop app that recommends five movies based on the movies you rate.
You can choose between two classic approaches - **content-based** and **collaborative
filtering** - and compare what each one suggests. It is built with Python, pandas,
scikit-learn and CustomTkinter, and is meant to be readable for junior developers.

## Features

- Dark, minimal CustomTkinter interface with a green accent
- Per-user profiles stored as JSON (no database)
- Title search across the whole dataset (case-insensitive, partial match, results capped for speed)
- Add, re-rate and remove movies; changes are saved immediately
- Two recommendation algorithms, each returning up to five movies with a score and a short explanation
- Movies already in your list are never recommended
- Clear messages instead of silent fallbacks when an algorithm has too little information

## How the algorithms work

### Content-based filtering
1. Each movie's `genres` string is turned into a TF-IDF vector (rare genres count more than very common ones).
2. Your taste profile is the sum of your rated movies' vectors, each weighted by `rating - 2.5`.
   High ratings pull the profile towards a movie's genres; low ratings push it away.
3. Cosine similarity between the taste profile and every movie gives the score ("Genre match").
4. Genres are the only feature, so many movies tie. Ties are broken by a damped average rating.

### Collaborative filtering (item-based)
1. A user-item matrix is built from `ratings.csv`. Missing ratings stay missing - they are **not** treated as zero.
2. Movie-to-movie similarity is the cosine of user-mean-centred ratings ("adjusted cosine").
   Pairs with fewer than 3 shared raters get similarity 0, and similarities from few raters are shrunk towards 0.
3. Your own ratings are never added to the historical matrix. They are only used as the starting points:
   the estimated rating for a movie is the average rating adjusted by the similarities to the movies you rated.
4. A movie must be similar to at least one movie you liked (3.5 or higher). Movies without a reliable
   similarity are skipped instead of being given an invented score.

## Project structure

```text
Movie-Recommender/
├── main.py            # GUI and entry point
├── recommender.py     # data loading, algorithms, user profiles, JSON storage
├── movies.csv
├── ratings.csv
├── users/             # one JSON file per user (created automatically)
│   └── .gitkeep
├── assets/
│   └── workflow.png
├── README.md
└── requirements.txt
```

## Installation (Windows PowerShell)

```powershell
cd Movie-Recommender
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks the activation script, run
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first and activate again.

## Run

```powershell
python main.py
```

## Dataset

| File | Column | Meaning |
|------|--------|---------|
| `movies.csv` | `movieId` | Unique movie identifier |
| | `title` | Movie title (with year) |
| | `genres` | Genres separated by `\|` |
| `ratings.csv` | `userId` | Historical user identifier |
| | `movieId` | Links to `movies.csv` |
| | `rating` | Rating given by that user |
| | `timestamp` | Dropped as soon as the file is loaded |

The CSV files are only read, never modified. Missing values and duplicate `(userId, movieId)`
pairs are cleaned at load time, and ratings for unknown movies are ignored.

## User profiles

Each user gets `users/<username>.json`:

```json
{
  "username": "vafa",
  "rated_movies": [
    { "movieId": 1, "title": "Toy Story (1995)", "rating": 4.5 }
  ]
}
```

- `movieId` is the canonical identifier; the title is stored for convenience.
- Usernames are trimmed and lower-cased, so `Vafa` and ` vafa ` are the same profile.
  Only letters, numbers, `_` and `-` are allowed, which keeps every name a safe file name.
- Files are written atomically. A corrupted profile is renamed to `*.bak` and a fresh one is started.
- The ratings dataset is never copied into profiles.

## Workflow

![CineMatch Workflow](assets/workflow.png)

## Limitations

- **New users:** with no ratings nothing can be recommended. With only one or two ratings the app
  warns you that the results are rough.
- **Content-based** uses genres only, so it cannot tell two movies with identical genres apart
  and may suggest several very similar titles.
- **Collaborative** cannot score movies that have (almost) no ratings in the dataset, so it may return fewer than five.
  Both algorithms explain when this happens, and the app offers the other algorithm instead of switching on its own.
- The collaborative model keeps a dense user-item matrix in memory. That is fine for a MovieLens-small-sized
  dataset (about 100k ratings) but would need a sparse implementation for much larger data.
