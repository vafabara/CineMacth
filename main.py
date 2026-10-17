"""CineMatch - desktop GUI built with CustomTkinter.

This file only handles the interface. All data loading, recommendation logic and
profile storage live in recommender.py.
"""

import queue
import threading

import customtkinter as ctk

import recommender as rec

# --------------------------------------------------------------------------
# Theme: near-black background, one green accent
# --------------------------------------------------------------------------
BG = "#0b0b0b"
CARD = "#141414"
CARD_ALT = "#1b1b1b"
BORDER = "#2a2a2a"
ACCENT = "#22c55e"
ACCENT_HOVER = "#16a34a"
ACCENT_TEXT = "#04130a"        # dark text on green buttons
SELECTED = "#13301d"
TEXT = "#ededed"
MUTED = "#9a9a9a"
DISABLED = "#5c5c5c"
ERROR = "#f87171"
WARNING = "#fbbf24"


# --------------------------------------------------------------------------
# Small widget helpers (keep the page code below short and readable)
# --------------------------------------------------------------------------
def make_label(parent, text="", size=14, weight="normal", color=TEXT, **kwargs):
    return ctk.CTkLabel(
        parent, text=text, text_color=color,
        font=ctk.CTkFont(size=size, weight=weight), **kwargs,
    )


def make_card(parent, **kwargs):
    return ctk.CTkFrame(
        parent, fg_color=CARD, corner_radius=16,
        border_width=1, border_color=BORDER, **kwargs,
    )


def make_entry(parent, placeholder):
    return ctk.CTkEntry(
        parent, placeholder_text=placeholder, height=40, corner_radius=10,
        fg_color=CARD_ALT, border_color=BORDER, text_color=TEXT,
        placeholder_text_color="#6b6b6b",
    )


def make_button(parent, text, command, primary=True, **kwargs):
    kwargs.setdefault("height", 40)
    if primary:
        colors = dict(fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=ACCENT_TEXT,
                      border_width=0)
    else:
        colors = dict(fg_color="transparent", hover_color=CARD_ALT, text_color=TEXT,
                      border_width=1, border_color=BORDER)
    return ctk.CTkButton(
        parent, text=text, command=command, corner_radius=10,
        text_color_disabled=DISABLED, font=ctk.CTkFont(size=14, weight="bold"),
        **colors, **kwargs,
    )


def make_option_menu(parent, values, variable=None, command=None, width=90):
    return ctk.CTkOptionMenu(
        parent, values=values, variable=variable, command=command, width=width, height=32,
        corner_radius=8, fg_color=CARD_ALT, button_color=ACCENT_HOVER, button_hover_color=ACCENT,
        text_color=TEXT, dropdown_fg_color=CARD_ALT, dropdown_hover_color=SELECTED,
        dropdown_text_color=TEXT,
    )


def make_scroll_frame(parent):
    return ctk.CTkScrollableFrame(
        parent, fg_color="transparent",
        scrollbar_button_color=BORDER, scrollbar_button_hover_color="#3a3a3a",
    )


def bind_click(widgets, callback):
    """Make a custom 'row' (frame + labels) clickable."""
    for widget in widgets:
        widget.bind("<Button-1>", lambda event: callback())


def header_bar(parent, app, title):
    """Back button + page title + active user. Returns (bar, user_label)."""
    bar = ctk.CTkFrame(parent, fg_color="transparent")
    bar.grid_columnconfigure(1, weight=1)
    make_button(bar, "< Home", lambda: app.show_page("home"), primary=False, width=90).grid(
        row=0, column=0, padx=(0, 16))
    make_label(bar, title, size=24, weight="bold").grid(row=0, column=1, sticky="w")
    user_label = make_label(bar, "", size=13, color=MUTED)
    user_label.grid(row=0, column=2, sticky="e")
    return bar, user_label


# --------------------------------------------------------------------------
# Application window
# --------------------------------------------------------------------------
class App(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode("dark")
        super().__init__()
        self.title("CineMatch")
        self.geometry("1060x740")
        self.minsize(880, 640)
        self.configure(fg_color=BG)

        self.data = None      # datasets + cached models, loaded once at startup
        self.profile = None   # the active user's profile (None until a username is entered)

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=28, pady=22)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.pages = {
            "loading": LoadingPage(container, self),
            "home": HomePage(container, self),
            "edit": EditPage(container, self),
            "recommend": RecommendPage(container, self),
        }
        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")

        self.show_page("loading")
        self.load_dataset()

    def show_page(self, name):
        page = self.pages[name]
        page.tkraise()
        if hasattr(page, "on_show"):
            page.on_show()

    def run_in_background(self, work, on_success, on_error):
        """Run slow work in a thread so the window never freezes.

        Tkinter widgets may only be touched from the main thread, so the worker puts its
        result in a queue and the main thread polls that queue with after().
        """
        results = queue.Queue()

        def worker():
            try:
                results.put(("ok", work()))
            except Exception as exc:  # shown to the user, not swallowed
                results.put(("error", exc))

        def poll():
            try:
                status, value = results.get_nowait()
            except queue.Empty:
                self.after(80, poll)
                return
            (on_success if status == "ok" else on_error)(value)

        threading.Thread(target=worker, daemon=True).start()
        poll()

    def load_dataset(self):
        self.pages["loading"].show_loading()
        self.run_in_background(rec.load_data, self._data_loaded, self._data_failed)

    def _data_loaded(self, data):
        self.data = data
        rec.ensure_users_dir()
        self.show_page("home")

    def _data_failed(self, error):
        self.pages["loading"].show_error(str(error))


# --------------------------------------------------------------------------
# Loading page
# --------------------------------------------------------------------------
class LoadingPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        box = ctk.CTkFrame(self, fg_color="transparent")
        box.grid(row=0, column=0)
        make_label(box, "CineMatch", size=44, weight="bold", color=ACCENT).pack(pady=(0, 18))
        self.progress = ctk.CTkProgressBar(
            box, mode="indeterminate", width=320, progress_color=ACCENT, fg_color=BORDER)
        self.progress.pack()
        self.status = make_label(box, "", size=14, color=MUTED, wraplength=560, justify="center")
        self.status.pack(pady=14)
        self.retry = make_button(box, "Try Again", app.load_dataset, width=140)

    def show_loading(self):
        self.retry.pack_forget()
        self.status.configure(text="Loading movies and ratings...", text_color=MUTED)
        self.progress.pack()
        self.progress.start()

    def show_error(self, message):
        self.progress.stop()
        self.progress.pack_forget()
        self.status.configure(text=f"Could not load the datasets.\n\n{message}", text_color=ERROR)
        self.retry.pack(pady=(4, 0))


# --------------------------------------------------------------------------
# Home page
# --------------------------------------------------------------------------
class HomePage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=0, column=0)
        content.grid_columnconfigure(0, minsize=640)

        make_label(content, "CineMatch", size=48, weight="bold", color=ACCENT).grid(row=0, column=0)
        make_label(
            content,
            "Rate movies you know and get five recommendations, using either genre-based "
            "(content-based) or crowd-based (collaborative) filtering.",
            size=14, color=MUTED, wraplength=600, justify="center",
        ).grid(row=1, column=0, pady=(6, 0))

        # --- username card ---
        user_card = make_card(content)
        user_card.grid(row=2, column=0, sticky="ew", pady=(28, 12))
        user_card.grid_columnconfigure(0, weight=1)
        make_label(user_card, "Username", size=13, weight="bold", color=MUTED).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(16, 4))
        self.username_entry = make_entry(user_card, "Enter your username")
        self.username_entry.grid(row=1, column=0, sticky="ew", padx=(20, 10))
        self.username_entry.bind("<Return>", lambda event: self.submit_username())
        make_button(user_card, "Create / Load Profile", self.submit_username, width=200).grid(
            row=1, column=1, padx=(0, 20))
        self.message = make_label(user_card, "", size=12, wraplength=590, justify="left")
        self.message.grid(row=2, column=0, columnspan=2, sticky="w", padx=20, pady=(8, 14))
        self.set_message("Not case-sensitive. Letters, numbers, _ and - only.", MUTED)

        # --- status card ---
        status_card = make_card(content)
        status_card.grid(row=3, column=0, sticky="ew", pady=(0, 18))
        status_card.grid_columnconfigure((0, 1), weight=1, uniform="status")
        make_label(status_card, "ACTIVE USER", size=11, weight="bold", color=MUTED).grid(
            row=0, column=0, sticky="w", padx=20, pady=(14, 0))
        make_label(status_card, "RATED MOVIES", size=11, weight="bold", color=MUTED).grid(
            row=0, column=1, sticky="w", padx=20, pady=(14, 0))
        self.active_user = make_label(status_card, "", size=20, weight="bold")
        self.active_user.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 14))
        self.rated_count = make_label(status_card, "", size=20, weight="bold", color=ACCENT)
        self.rated_count.grid(row=1, column=1, sticky="w", padx=20, pady=(0, 14))

        # --- actions ---
        actions = ctk.CTkFrame(content, fg_color="transparent")
        actions.grid(row=4, column=0, sticky="ew")
        actions.grid_columnconfigure((0, 1), weight=1, uniform="actions")
        self.edit_button = make_button(
            actions, "Edit My List", lambda: app.show_page("edit"), primary=False, height=50)
        self.edit_button.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.recommend_button = make_button(
            actions, "Recommend Movies", lambda: app.show_page("recommend"), height=50)
        self.recommend_button.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        self.refresh()

    def set_message(self, text, color):
        self.message.configure(text=text, text_color=color)

    def submit_username(self):
        try:
            profile, created, warning = rec.load_profile(self.app.data, self.username_entry.get())
        except ValueError as exc:  # invalid username
            self.set_message(str(exc), ERROR)
            return
        except OSError as exc:     # file system problem
            self.set_message(f"Could not read or write the profile file: {exc}", ERROR)
            return

        self.app.profile = profile
        self.username_entry.delete(0, "end")
        self.username_entry.insert(0, profile["username"])
        if warning:
            self.set_message(warning, WARNING)
        else:
            self.set_message("New profile created." if created else "Profile loaded.", ACCENT)
        self.refresh()

    def refresh(self):
        profile = self.app.profile
        if profile is None:
            self.active_user.configure(text="Not signed in", text_color=MUTED)
            self.rated_count.configure(text="-", text_color=MUTED)
        else:
            self.active_user.configure(text=profile["username"], text_color=TEXT)
            self.rated_count.configure(text=str(len(profile["rated_movies"])), text_color=ACCENT)

        enabled = profile is not None
        self.edit_button.configure(state="normal" if enabled else "disabled")
        self.recommend_button.configure(state="normal" if enabled else "disabled")
        # the primary button turns grey while disabled
        self.recommend_button.configure(fg_color=ACCENT if enabled else CARD_ALT)

    def on_show(self):
        self.refresh()


# --------------------------------------------------------------------------
# Edit My List page
# --------------------------------------------------------------------------
class EditPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.selected = None          # the search result currently selected
        self.search_job = None        # pending after() id, used to debounce typing
        self.result_rows = {}         # movieId -> row frame
        self.wrap_labels = []         # labels whose wraplength follows the window width
        self.wrap = 330

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure((0, 1), weight=1, uniform="columns")

        bar, self.user_label = header_bar(self, app, "Edit My List")
        bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 16))

        # ---------- left: search ----------
        left = make_card(self)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        left.grid_rowconfigure(2, weight=1)
        left.grid_columnconfigure(0, weight=1)
        make_label(left, "Find a movie", size=16, weight="bold").grid(
            row=0, column=0, sticky="w", padx=18, pady=(16, 8))
        self.search_entry = make_entry(left, "Search by title, e.g. matrix")
        self.search_entry.grid(row=1, column=0, sticky="ew", padx=18)
        self.search_entry.bind("<KeyRelease>", self.schedule_search)

        self.results_frame = make_scroll_frame(left)
        self.results_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(8, 0))
        self.results_frame.grid_columnconfigure(0, weight=1)
        self.search_info = make_label(left, "", size=12, color=MUTED)
        self.search_info.grid(row=3, column=0, sticky="w", padx=18, pady=(4, 0))

        panel = ctk.CTkFrame(left, fg_color=CARD_ALT, corner_radius=12)
        panel.grid(row=4, column=0, sticky="ew", padx=14, pady=14)
        panel.grid_columnconfigure(0, weight=1)
        self.selected_label = make_label(
            panel, "", size=14, weight="bold", wraplength=self.wrap, justify="left")
        self.selected_label.grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(12, 4))
        make_label(panel, "Your rating", size=13, color=MUTED).grid(
            row=1, column=0, sticky="w", padx=14, pady=(0, 12))
        self.rating_var = ctk.StringVar(value="3.0")
        self.rating_menu = make_option_menu(
            panel, [f"{v:.1f}" for v in app.data["rating_scale"]] if app.data else ["3.0"],
            variable=self.rating_var)
        self.rating_menu.grid(row=1, column=1, padx=8, pady=(0, 12))
        self.add_button = make_button(panel, "Add to My List", self.save_selected, width=150)
        self.add_button.grid(row=1, column=2, padx=(0, 14), pady=(0, 12))
        self.panel_message = make_label(panel, "", size=12, color=MUTED, wraplength=self.wrap,
                                        justify="left")
        self.panel_message.grid(row=2, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 10))
        self.clear_selection()

        # ---------- right: my list ----------
        right = make_card(self)
        right.grid(row=1, column=1, sticky="nsew", padx=(8, 0))
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)
        self.list_title = make_label(right, "My List", size=16, weight="bold")
        self.list_title.grid(row=0, column=0, sticky="w", padx=18, pady=(16, 8))
        self.list_frame = make_scroll_frame(right)
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.list_frame.grid_columnconfigure(0, weight=1)
        self.list_message = make_label(right, "", size=12, color=ERROR, wraplength=self.wrap,
                                       justify="left")
        self.list_message.grid(row=2, column=0, sticky="w", padx=18, pady=(0, 12))

        self.bind("<Configure>", self.on_resize)

    # ----- page lifecycle -----
    def on_show(self):
        username = self.app.profile["username"] if self.app.profile else ""
        self.user_label.configure(text=f"Signed in as {username}")
        values = [f"{v:.1f}" for v in self.app.data["rating_scale"]]
        self.rating_menu.configure(values=values)
        self.list_message.configure(text="")
        self.clear_selection()
        self.render_list()
        self.run_search()

    def on_resize(self, event):
        if event.widget is not self:
            return
        wrap = max(220, event.width // 2 - 120)
        if abs(wrap - self.wrap) < 8:
            return
        self.wrap = wrap
        for label in self.wrap_labels:
            try:
                label.configure(wraplength=wrap)
            except Exception:  # label was already destroyed by a re-render
                pass
        for label in (self.selected_label, self.panel_message, self.list_message):
            label.configure(wraplength=wrap)

    # ----- searching -----
    def schedule_search(self, event=None):
        if self.search_job is not None:
            self.after_cancel(self.search_job)
        self.search_job = self.after(250, self.run_search)  # wait until typing pauses

    def run_search(self):
        self.search_job = None
        results, total = rec.search_movies(self.app.data, self.search_entry.get())
        self.render_results(results, total)

    def render_results(self, results, total):
        for child in self.results_frame.winfo_children():
            child.destroy()
        self.result_rows = {}
        self.wrap_labels = [l for l in self.wrap_labels if l.winfo_exists()]

        query = self.search_entry.get().strip()
        if not query:
            self.search_info.configure(text="Type part of a title to search the whole dataset.")
            return
        if not results:
            self.search_info.configure(text="No movies found. Try a different spelling.")
            return
        shown = f"Showing {len(results)} of {total} matches" if total > len(results) else f"{total} match{'es' if total != 1 else ''}"
        self.search_info.configure(text=shown + (" - refine your search to narrow it down." if total > len(results) else "."))

        for index, movie in enumerate(results):
            row = ctk.CTkFrame(self.results_frame, fg_color=CARD_ALT, corner_radius=10)
            row.grid(row=index, column=0, sticky="ew", pady=3, padx=(0, 4))
            row.grid_columnconfigure(0, weight=1)
            title = make_label(row, movie["title"], size=14, weight="bold", anchor="w",
                               justify="left", wraplength=self.wrap)
            title.grid(row=0, column=0, sticky="w", padx=12, pady=(8, 0))
            genres = make_label(row, movie["genres"], size=12, color=MUTED, anchor="w",
                                justify="left", wraplength=self.wrap)
            genres.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 8))
            self.wrap_labels += [title, genres]
            self.result_rows[movie["movieId"]] = row
            bind_click([row, title, genres], lambda m=movie: self.select_movie(m))
        if self.selected and self.selected["movieId"] in self.result_rows:
            self.result_rows[self.selected["movieId"]].configure(fg_color=SELECTED)

    # ----- selecting and saving -----
    def clear_selection(self):
        self.selected = None
        self.selected_label.configure(text="Select a movie from the results", text_color=MUTED)
        self.panel_message.configure(text="")
        self.add_button.configure(state="disabled", text="Add to My List")

    def select_movie(self, movie):
        if self.selected and self.selected["movieId"] in self.result_rows:
            self.result_rows[self.selected["movieId"]].configure(fg_color=CARD_ALT)
        self.selected = movie
        self.result_rows[movie["movieId"]].configure(fg_color=SELECTED)
        self.selected_label.configure(text=movie["title"], text_color=TEXT)
        self.panel_message.configure(text="")

        existing = rec.get_rating(self.app.profile, movie["movieId"])
        if existing is None:
            scale = self.app.data["rating_scale"]
            self.rating_var.set(f"{min(scale, key=lambda v: abs(v - 3.0)):.1f}")  # neutral default
            self.add_button.configure(state="normal", text="Add to My List")
        else:
            self.rating_var.set(f"{existing:.1f}")
            self.add_button.configure(state="normal", text="Update Rating")
            self.panel_message.configure(text="Already in your list - saving updates its rating.",
                                         text_color=MUTED)

    def save_selected(self):
        if not self.selected:
            return
        try:
            rec.set_rating(self.app.data, self.app.profile,
                           self.selected["movieId"], float(self.rating_var.get()))
        except (ValueError, OSError) as exc:
            self.panel_message.configure(text=f"Could not save: {exc}", text_color=ERROR)
            return
        self.add_button.configure(text="Update Rating")
        self.panel_message.configure(text="Saved to your list.", text_color=ACCENT)
        self.render_list()

    # ----- the user's list -----
    def render_list(self):
        for child in self.list_frame.winfo_children():
            child.destroy()
        self.wrap_labels = [l for l in self.wrap_labels if l.winfo_exists()]

        movies = self.app.profile["rated_movies"] if self.app.profile else []
        self.list_title.configure(text=f"My List ({len(movies)})")
        if not movies:
            make_label(self.list_frame, "Your list is empty.\nSearch for a movie on the left to add it.",
                       size=13, color=MUTED, justify="left").grid(row=0, column=0, sticky="w", padx=8, pady=8)
            return

        values = [f"{v:.1f}" for v in self.app.data["rating_scale"]]
        for index, entry in enumerate(reversed(movies)):  # newest first
            row = ctk.CTkFrame(self.list_frame, fg_color=CARD_ALT, corner_radius=10)
            row.grid(row=index, column=0, sticky="ew", pady=3, padx=(0, 4))
            row.grid_columnconfigure(0, weight=1)
            title = make_label(row, entry["title"], size=13, weight="bold", anchor="w",
                               justify="left", wraplength=self.wrap)
            title.grid(row=0, column=0, sticky="w", padx=12, pady=10)
            self.wrap_labels.append(title)
            menu = make_option_menu(
                row, values, width=80,
                command=lambda value, movie_id=entry["movieId"]: self.change_rating(movie_id, value))
            menu.set(f"{entry['rating']:.1f}")
            menu.grid(row=0, column=1, padx=6)
            ctk.CTkButton(
                row, text="Remove", width=70, height=32, corner_radius=8, fg_color="transparent",
                border_width=1, border_color=BORDER, text_color=MUTED, hover_color="#3a1515",
                command=lambda movie_id=entry["movieId"]: self.remove(movie_id),
            ).grid(row=0, column=2, padx=(0, 10))

    def change_rating(self, movie_id, value):
        try:
            rec.set_rating(self.app.data, self.app.profile, movie_id, float(value))
            self.list_message.configure(text="")
        except (ValueError, OSError) as exc:
            self.list_message.configure(text=f"Could not save: {exc}")
            self.render_list()  # show the real stored values again
        if self.selected and self.selected["movieId"] == movie_id:
            self.rating_var.set(f"{float(value):.1f}")

    def remove(self, movie_id):
        try:
            rec.remove_movie(self.app.profile, movie_id)
            self.list_message.configure(text="")
        except OSError as exc:
            self.list_message.configure(text=f"Could not save: {exc}")
        if self.selected and self.selected["movieId"] == movie_id:
            self.add_button.configure(text="Add to My List")
            self.panel_message.configure(text="")
        self.render_list()


# --------------------------------------------------------------------------
# Recommend Movies page
# --------------------------------------------------------------------------
METHOD_INFO = {
    rec.METHOD_CONTENT: (
        "Content-Based Filtering",
        "Looks at the genres of the movies you rated and finds movies with a similar "
        "genre profile. Higher ratings count more.",
    ),
    rec.METHOD_COLLABORATIVE: (
        "Collaborative Filtering",
        "Uses the ratings of hundreds of other viewers to find movies that people who "
        "liked your movies also liked.",
    ),
}


class RecommendPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.busy = False
        self.wrap_labels = []
        self.grid_rowconfigure(4, weight=1)
        self.grid_columnconfigure(0, weight=1)

        bar, self.user_label = header_bar(self, app, "Recommend Movies")
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 16))

        # --- algorithm choice: two clearly separated cards ---
        choice = ctk.CTkFrame(self, fg_color="transparent")
        choice.grid(row=1, column=0, sticky="ew")
        choice.grid_columnconfigure((0, 1), weight=1, uniform="algo")
        self.method_var = ctk.StringVar(value=rec.METHOD_CONTENT)
        self.method_cards = {}
        for column, (method, (name, description)) in enumerate(METHOD_INFO.items()):
            card = ctk.CTkFrame(choice, fg_color=CARD, corner_radius=16, border_width=2,
                                border_color=BORDER)
            card.grid(row=0, column=column, sticky="nsew", padx=(0, 8) if column == 0 else (8, 0))
            radio = ctk.CTkRadioButton(
                card, text=name, variable=self.method_var, value=method,
                font=ctk.CTkFont(size=15, weight="bold"), text_color=TEXT,
                fg_color=ACCENT, hover_color=ACCENT_HOVER, border_color=MUTED)
            radio.grid(row=0, column=0, sticky="w", padx=18, pady=(16, 4))
            text = make_label(card, description, size=12, color=MUTED, wraplength=380,
                              justify="left", anchor="w")
            text.grid(row=1, column=0, sticky="w", padx=18, pady=(0, 16))
            bind_click([card, text], lambda m=method: self.method_var.set(m))
            self.method_cards[method] = card
        self.method_var.trace_add("write", lambda *args: self.highlight_choice())
        self.highlight_choice()

        # --- action row ---
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", pady=14)
        self.go_button = make_button(actions, "Get Recommendations", self.get_recommendations,
                                     width=220, height=44)
        self.go_button.grid(row=0, column=0)
        self.progress = ctk.CTkProgressBar(actions, mode="indeterminate", width=160,
                                           progress_color=ACCENT, fg_color=BORDER)
        self.status = make_label(actions, "", size=13, color=MUTED)
        self.status.grid(row=0, column=2, padx=14)

        # --- message banner (+ optional "try the other algorithm" button) ---
        self.banner = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12, border_width=1,
                                   border_color=BORDER)
        self.banner.grid_columnconfigure(0, weight=1)
        self.banner_text = make_label(self.banner, "", size=13, justify="left", anchor="w",
                                      wraplength=800)
        self.banner_text.grid(row=0, column=0, sticky="w", padx=16, pady=12)
        self.alternative_button = make_button(self.banner, "", self.try_other_algorithm,
                                              primary=False, height=34)
        self.wrap_labels.append(self.banner_text)

        # --- results ---
        self.results = make_scroll_frame(self)
        self.results.grid(row=4, column=0, sticky="nsew", pady=(8, 0))
        self.results.grid_columnconfigure(0, weight=1)
        self.bind("<Configure>", self.on_resize)

    def on_show(self):
        username = self.app.profile["username"] if self.app.profile else ""
        self.user_label.configure(text=f"Signed in as {username}")
        self.hide_banner()
        self.show_placeholder()

    def on_resize(self, event):
        if event.widget is not self:
            return
        wrap = max(300, event.width - 120)
        for label in self.wrap_labels:
            try:
                label.configure(wraplength=wrap)
            except Exception:
                pass

    def highlight_choice(self):
        for method, card in self.method_cards.items():
            card.configure(border_color=ACCENT if self.method_var.get() == method else BORDER)

    # ----- helpers for the results area -----
    def clear_results(self):
        for child in self.results.winfo_children():
            child.destroy()
        self.wrap_labels = [self.banner_text]

    def show_placeholder(self):
        self.clear_results()
        make_label(self.results, "Choose an algorithm and press \"Get Recommendations\".",
                   size=13, color=MUTED).grid(row=0, column=0, pady=30)

    def show_banner(self, text, color=TEXT, offer_other=False):
        self.banner_text.configure(text=text, text_color=color)
        self.banner.grid(row=3, column=0, sticky="ew")
        if offer_other:
            other = self.other_method()
            self.alternative_button.configure(text=f"Try {METHOD_INFO[other][0]} instead")
            self.alternative_button.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 12))
        else:
            self.alternative_button.grid_remove()

    def hide_banner(self):
        self.banner.grid_remove()

    def other_method(self):
        return (rec.METHOD_COLLABORATIVE if self.method_var.get() == rec.METHOD_CONTENT
                else rec.METHOD_CONTENT)

    def set_busy(self, busy):
        self.busy = busy
        self.go_button.configure(state="disabled" if busy else "normal")
        if busy:
            self.progress.grid(row=0, column=1, padx=(14, 0))
            self.progress.start()
            self.status.configure(text="Calculating recommendations...")
        else:
            self.progress.stop()
            self.progress.grid_remove()
            self.status.configure(text="")

    # ----- running an algorithm -----
    def get_recommendations(self):
        if self.busy:
            return
        method = self.method_var.get()
        data, profile = self.app.data, self.app.profile
        self.set_busy(True)
        self.hide_banner()
        self.app.run_in_background(
            lambda: rec.get_recommendations(data, profile, method),
            self.show_results, self.show_error)

    def try_other_algorithm(self):
        self.method_var.set(self.other_method())  # explicit user choice, never automatic
        self.get_recommendations()

    def show_error(self, error):
        self.set_busy(False)
        self.show_banner(f"Something went wrong while calculating recommendations: {error}", ERROR)

    def show_results(self, result):
        self.set_busy(False)
        self.clear_results()
        recommendations, message = result["recommendations"], result["message"]

        if message:
            self.show_banner(message, MUTED if recommendations else WARNING,
                             offer_other=not recommendations and bool(self.app.profile["rated_movies"]))
        else:
            self.hide_banner()

        for index, movie in enumerate(recommendations):
            card = make_card(self.results)
            card.grid(row=index, column=0, sticky="ew", pady=5, padx=(0, 4))
            card.grid_columnconfigure(1, weight=1)
            make_label(card, str(index + 1), size=22, weight="bold", color=ACCENT, width=44).grid(
                row=0, column=0, rowspan=3, padx=(10, 0), pady=14)
            make_label(card, movie["title"], size=16, weight="bold", anchor="w",
                       justify="left", wraplength=560).grid(
                row=0, column=1, sticky="w", padx=8, pady=(12, 0))
            make_label(card, movie["genres"], size=12, color=MUTED, anchor="w",
                       justify="left", wraplength=560).grid(row=1, column=1, sticky="w", padx=8)
            reason = make_label(card, movie["reason"], size=12, anchor="w", justify="left",
                                wraplength=560)
            reason.grid(row=2, column=1, sticky="w", padx=8, pady=(4, 12))
            ctk.CTkLabel(
                card, text=movie["score_label"], fg_color=SELECTED, text_color=ACCENT,
                corner_radius=8, font=ctk.CTkFont(size=12, weight="bold"), width=170, height=30,
            ).grid(row=0, column=2, rowspan=3, padx=16)


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
