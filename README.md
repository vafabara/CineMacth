# CineMatch - Movie Recommender

<<<<<<< HEAD
CineMatch is a Python desktop application that recommends movies based on your ratings using two machine learning approaches: **Content-Based Filtering** and **Collaborative Filtering**.

## Screenshots

<p align="center">
  <img src="assets/List.png" width="48%" alt="Movie List Interface" />
  <img src="assets/recommender.png" width="48%" alt="Movie Recommendations Interface" />
</p>

## Features

- Modern dark GUI built with CustomTkinter
- Search movies by title and browse genres
- Add, rate, update, and remove movies
- Persistent user profiles stored as JSON
- Two recommendation algorithms with scores and explanations
- Recommends up to five movies you haven't rated
- Handles missing data and limited recommendation history
=======
CineMatch is a small desktop app that recommends movies (5 by default, up to 10) based on the movies you rate.
You can choose between two classic approaches - **content-based** and **collaborative
filtering** - and compare what each one suggests. It is built with Python, pandas,
scikit-learn and CustomTkinter, and is meant to be readable for junior developers.

## Features

- Minimal CustomTkinter interface with a green accent, in dark or light mode
- Settings (gear icon): switch between light and dark mode and choose how many movies are recommended (1-10)
- How to use (`?` icon): a short step-by-step guide inside the app
- Per-user profiles stored as JSON (no database)
- Title search across the whole dataset (case-insensitive, partial match, results capped for speed)
- Add, re-rate and remove movies; changes are saved immediately
- Two recommendation algorithms, each returning up to the chosen number of movies with a score and a short explanation
- A copy icon next to every recommended movie copies its title to the clipboard
- Movies already in your list are never recommended
- Clear messages instead of silent fallbacks when an algorithm has too little information
>>>>>>> 2859e2f (setting + how to use)

## Recommendation Algorithms

**Content-Based Filtering**
- Uses TF-IDF to represent movie genres.
- Builds a user preference profile from movie ratings.
- Recommends movies based on cosine similarity.

**Collaborative Filtering**
- Uses historical ratings to calculate movie similarities.
- Predicts preferences based on similar movies and user ratings.
- Skips movies without sufficient similarity data.

<<<<<<< HEAD
## Installation
=======
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

## How to use

1. Type a username on the home page and press **Create / Load Profile**.
2. Open **Edit My List**, search for movies you know, rate them and add them to your list.
3. Open **Recommend Movies**, pick an algorithm and press **Get Recommendations**.
4. Press the copy icon next to a movie to copy its title.
5. Use the gear icon for light/dark mode and the number of recommendations, and the `?` icon for help.

Tip: rate at least 3 movies, including some you liked (3.5 or higher).

## Installation (Windows PowerShell)
>>>>>>> 2859e2f (setting + how to use)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```powershell
python main.py
```

## Requirements

- pandas
- numpy
- scikit-learn
- customtkinter

## Workflow

![CineMatch Workflow](assets/workflow.png)

## Limitations

<<<<<<< HEAD
- Users need to rate movies before receiving recommendations.
- Content-based recommendations rely on genres only.
- Collaborative filtering may return fewer than five movies when historical rating data is insufficient.
=======
- **New users:** with no ratings nothing can be recommended. With only one or two ratings the app
  warns you that the results are rough.
- **Content-based** uses genres only, so it cannot tell two movies with identical genres apart
  and may suggest several very similar titles.
- **Collaborative** cannot score movies that have (almost) no ratings in the dataset, so it may return fewer than the number you asked for.
  Both algorithms explain when this happens, and the app offers the other algorithm instead of switching on its own.
- The collaborative model keeps a dense user-item matrix in memory. That is fine for a MovieLens-small-sized
  dataset (about 100k ratings) but would need a sparse implementation for much larger data.
>>>>>>> 2859e2f (setting + how to use)
