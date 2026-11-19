"""Eksporterer Antons CineMatch-model til én JSON-fil, som iOS-appen kan bruge lokalt.

Idé: Det tunge arbejde (hvilke film ligner hinanden, og hvorfor) regnes ud her på forhånd.
Appen slår bare op i filen og lægger scorerne sammen på samme måde som Recommender.recommend().

Kør i samme mappe som Antons model (cinematch.py eller Antons_Model.py) og Letterboxd-dataene:

    python export_for_app.py                         # 8.000 film, 25 naboer pr. film
    python export_for_app.py --films 12000 --neighbors 30
    python export_for_app.py --model Antons_Model.py --out cinematch_model.json

Læg derefter cinematch_model.json i Xcode-projektet under CineMatch/Core/Resources/.
"""

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np

FORMAT_VERSION = 2
QUALITY_BOOST = 0.02      # samme som Antons standard
POPULARITY_BOOST = 0.0    # anbefalinger skal bygge på smag, ikke popularitet
MIN_BREAKDOWN = 0.005     # samme grænse som Recommender.breakdown()
MAX_DESCRIPTION = 400     # tegn – holder filen lille
MAX_BREAKDOWN_PARTS = 5   # højst så mange feature-typer pr. filmpar

# Mood mapping: genres/themes → moods
MOOD_MAPPING = {
    "Comedy": ["laugh"],
    "Thriller": ["thrill"],
    "Crime": ["thrill"],
    "Action": ["thrill"],
    "Horror": ["thrill"],
    "Drama": ["be_moved"],
    "Documentary": ["think"],
    "Animation": ["laugh"],
}

# Tag vocabulary: theme-based tags for home screen rows
TAG_VOCABULARY = {
    "slow-burn", "fast-paced", "dark", "light-hearted", "indie",
    "blockbuster", "cult", "feel-good", "philosophical", "psychological",
    "romantic", "action-packed", "suspenseful", "twist-ending", "coming-of-age",
    "historical", "fantasy", "sci-fi", "noir", "heist", "family-friendly",
    "artistic", "emotional", "thought-provoking", "visually-stunning",
}

# Age rating mapping (based on genre/themes)
AGE_RATING_DEFAULT = "PG-13"


def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def import_model(path):
    """Importerer Antons modelfil, uanset hvad den hedder."""
    spec = importlib.util.spec_from_file_location("cinematch_model", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["cinematch_model"] = module
    spec.loader.exec_module(module)
    return module


def find_model_file(explicit):
    if explicit:
        return Path(explicit)
    for name in ("cinematch.py", "Antons_Model.py"):
        if Path(name).is_file():
            return Path(name)
    raise SystemExit("Fandt ikke modellen. Brug --model sti/til/Antons_Model.py")


def choose_films(rec, n_films):
    """Vælger de film, appen skal kende: de mest kendte, én pr. titel, med år og beskrivelse."""
    meta = rec.meta
    ok = meta["year"].notna() & (meta["description"].str.len() > 0)
    candidates = np.flatnonzero(ok.to_numpy())
    order = candidates[np.argsort(-meta["popularity"].to_numpy()[candidates], kind="stable")]
    rows, seen = [], set()
    for row in order:
        key = meta["key"].iloc[row]
        if key in seen:          # kataloget har nogle titler to gange
            continue
        seen.add(key)
        rows.append(int(row))
        if len(rows) == n_films:
            break
    return np.array(rows)


def choose_starters(rec, rows, count):
    """Ca. `count` kendte film fordelt på genrer – til onboarding-gitteret."""
    meta = rec.meta
    by_genre = {}
    for row in rows[: max(count * 15, 600)]:          # kun blandt de mest kendte
        genres = [g.strip() for g in meta["genres"].iloc[row].split(",") if g.strip()]
        if genres:
            by_genre.setdefault(genres[0], []).append(int(row))
    starters, round_index = [], 0
    while len(starters) < count and any(round_index < len(v) for v in by_genre.values()):
        for genre in sorted(by_genre, key=lambda g: -len(by_genre[g])):
            films = by_genre[genre]
            if round_index < len(films) and films[round_index] not in starters:
                starters.append(films[round_index])
                if len(starters) == count:
                    break
        round_index += 1
    return starters


def terms_by_row(rec, rows, block_name):
    """For hver film: {kolonne: vægt} i én feature-blok. Gør 'shared' hurtig at regne ud."""
    block = rec.blocks[block_name][rows].tocsr()
    result = []
    for i in range(block.shape[0]):
        start, end = block.indptr[i], block.indptr[i + 1]
        result.append(dict(zip(block.indices[start:end].tolist(), block.data[start:end].tolist())))
    return result


def shared_terms(model, rec, explain_terms, a, b, strings):
    """Samme logik som Recommender.shared(), men på forudberegnede ordbøger."""
    found = []
    for label_index, (name, _label, count) in enumerate(model.EXPLAIN):
        terms_a, terms_b = explain_terms[name][a], explain_terms[name][b]
        common = terms_a.keys() & terms_b.keys()
        if not common:
            continue
        ranked = sorted(common, key=lambda col: -(terms_a[col] * terms_b[col]))
        values = []
        for col in ranked:
            term = rec.vocab[name][col]
            if any(term in kept or kept in term for kept in values):
                continue
            values.append(term)
            if len(values) == count:
                break
        found.append([label_index] + [strings.setdefault(v, len(strings)) for v in values])
    return found


def generate_tags(meta, row):
    """Generate tags for a film based on genres and themes."""
    tags = set()
    
    genres = []
    if "genres" in meta.columns:
        g = meta.iloc[row]["genres"]
        if isinstance(g, str):
            genres = [x.strip().lower() for x in g.split(",")]
    
    themes = []
    if "themes" in meta.columns:
        t = meta.iloc[row].get("themes")
        if isinstance(t, str):
            themes = [x.strip().lower() for x in t.split(",")]
    
    rating = meta.iloc[row].get("rating", 0) if "rating" in meta else 0
    
    # Add tags based on genres
    if "comedy" in genres or "comedy" in themes:
        tags.add("light-hearted")
        tags.add("feel-good")
    if "thriller" in genres or "suspense" in themes:
        tags.add("suspenseful")
        tags.add("fast-paced")
    if "horror" in genres or "dark" in themes:
        tags.add("dark")
    if "drama" in genres:
        tags.add("emotional")
        tags.add("thought-provoking")
    if "documentary" in genres:
        tags.add("thought-provoking")
    if "animation" in genres or "animated" in genres:
        tags.add("family-friendly")
    if "indie" in genres:
        tags.add("indie")
    if "action" in genres:
        tags.add("fast-paced")
        tags.add("action-packed")
    if "romance" in genres:
        tags.add("romantic")
    if "fantasy" in genres or "fantasy" in themes:
        tags.add("fantasy")
    if "sci-fi" in genres or "science fiction" in genres:
        tags.add("sci-fi")
    
    # Add based on rating
    if rating > 7.5:
        tags.add("highly-rated")
    if rating < 5.0:
        tags.add("cult")
    
    return sorted(list(tags & TAG_VOCABULARY))


def generate_moods(meta, row):
    """Generate moods for a film based on genres."""
    moods = set()
    
    genres = []
    if "genres" in meta.columns:
        g = meta.iloc[row]["genres"]
        if isinstance(g, str):
            genres = [x.strip() for x in g.split(",")]
    
    for genre in genres:
        if genre in MOOD_MAPPING:
            moods.update(MOOD_MAPPING[genre])
    
    return sorted(list(moods))


def generate_age_rating(meta, row):
    """Generate age rating based on genre and themes."""
    genres = []
    if "genres" in meta.columns:
        g = meta.iloc[row]["genres"]
        if isinstance(g, str):
            genres = [x.strip().lower() for x in g.split(",")]
    
    if "horror" in genres or "violence" in str(meta.iloc[row].get("description", "")):
        return "R"
    if "comedy" in genres or "animation" in genres or "family" in genres:
        return "PG"
    if "thriller" in genres or "crime" in genres:
        return "PG-13"
    
    return AGE_RATING_DEFAULT


def export(args):
    model = import_model(find_model_file(args.model))
    log("Indlæser Antons model ...")
    rec = model.load_recommender()

    rows = choose_films(rec, args.films)
    n = len(rows)
    log(f"Eksporterer {n:,} film med {args.neighbors} naboer hver")

    block_names = list(rec.weights)                      # fast rækkefølge til breakdown
    matrix = rec.matrix[rows].tocsr()
    matrix_t = matrix.T.tocsr()
    blocks = {name: rec.blocks[name][rows].tocsr() for name in block_names}
    norms = rec.norms[rows]
    explain_terms = {name: terms_by_row(rec, rows, name) for name, _, _ in model.EXPLAIN}

    strings = {}
    neighbors = []
    k = min(args.neighbors, n - 1)
    for start in range(0, n, args.chunk):
        stop = min(start + args.chunk, n)
        sims = (matrix[start:stop] @ matrix_t).toarray()
        sims[np.arange(stop - start), np.arange(start, stop)] = -np.inf     # ikke sig selv
        top = np.argpartition(-sims, k - 1, axis=1)[:, :k]
        top = np.take_along_axis(top, np.argsort(-np.take_along_axis(sims, top, axis=1), axis=1), axis=1)

        # Hvor meget hver feature-type bidrager til hvert filmpar (som Recommender.breakdown()).
        # Regnes kun for de udvalgte par, så det ikke bruger meget RAM.
        pair_a = np.repeat(np.arange(start, stop), k)
        pair_b = top.ravel()
        scale = 1.0 / (norms[pair_a] * norms[pair_b])
        contributions = {}
        for name in block_names:
            overlap = np.asarray(blocks[name][pair_a].multiply(blocks[name][pair_b]).sum(axis=1)).ravel()
            contributions[name] = (rec.weights[name] * overlap * scale).reshape(stop - start, k)

        for i in range(stop - start):
            a = start + i
            film_neighbors = []
            for slot, b in enumerate(top[i]):
                similarity = float(sims[i, b])
                if similarity <= 0:
                    break
                parts = []
                for block_index, name in enumerate(block_names):
                    value = float(contributions[name][i, slot])
                    if value >= MIN_BREAKDOWN:
                        parts.append([block_index, round(float(value), 4)])
                parts.sort(key=lambda p: -p[1])
                film_neighbors.append({
                    "i": int(b),
                    "s": round(similarity, 4),
                    "b": parts[:MAX_BREAKDOWN_PARTS],
                    "x": shared_terms(model, rec, explain_terms, a, int(b), strings),
                })
            neighbors.append(film_neighbors)
        log(f"  {stop:,}/{n:,}")

    meta = rec.meta
    films = []
    for position, row in enumerate(rows):
        record = meta.iloc[row]
        description = str(record["description"])
        if len(description) > MAX_DESCRIPTION:
            description = description[: MAX_DESCRIPTION].rsplit(" ", 1)[0] + "…"
        minute = record["minute"]
        films.append({
            "id": int(record["id"]),
            "title": str(record["name"]),
            "year": int(record["year"]),
            "genres": [g.strip() for g in str(record["genres"]).split(",") if g.strip()],
            "director": str(record["director"]),
            "cast": str(record["cast"]),
            "description": description,
            "runtime": int(minute) if minute == minute else None,      # NaN-tjek
            "rating": round(float(record["rating"]), 2),
            "quality": round(float(rec.quality[row]), 3),
            "moods": generate_moods(meta, row),
            "ageRating": generate_age_rating(meta, row),
            "tags": generate_tags(meta, row),
        })

    position_of = {int(row): position for position, row in enumerate(rows)}
    starters = [films[position_of[row]]["id"] for row in choose_starters(rec, rows, args.starters)]

    output = {
        "formatVersion": FORMAT_VERSION,
        "modelVersion": args.version or time.strftime("%Y-%m-%d"),
        "qualityBoost": QUALITY_BOOST,
        "maxLiked": int(model.MAX_LIKED),
        "featureLabels": [model.BLOCK_LABELS[name] for name in block_names],
        "explainLabels": [label for _, label, _ in model.EXPLAIN],
        "strings": sorted(strings, key=strings.get),
        "films": films,
        "starterIDs": starters,
        "neighbors": neighbors,
    }
    out = Path(args.out)
    out.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"Gemte {out} ({out.stat().st_size / 1e6:.1f} MB): {n:,} film, {len(starters)} startfilm")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", help="sti til Antons modelfil (standard: cinematch.py eller Antons_Model.py)")
    parser.add_argument("--films", type=int, default=8000, help="antal film i appen (standard 8000)")
    parser.add_argument("--neighbors", type=int, default=50, help="naboer pr. film (standard 50)")
    parser.add_argument("--starters", type=int, default=48, help="film i onboarding-gitteret (standard 48)")
    parser.add_argument("--chunk", type=int, default=500, help="film pr. beregningsblok (mindre = mindre RAM)")
    parser.add_argument("--version", help="modelversion, fx 2026-10-30-v2")
    parser.add_argument("--out", default="cinematch_model.json")
    export(parser.parse_args())


if __name__ == "__main__":
    main()
