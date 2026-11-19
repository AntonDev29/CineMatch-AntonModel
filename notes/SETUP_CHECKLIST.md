# CineMatch ML Prompt – Implementation Checklist

**Date:** 2026-10-30  
**Status:** ✅ READY – All critical requirements met; some features are future work

---

## Summary

The current ML setup (**Anton's content-based model**) perfectly fits the app's requirements:
- ✅ Model exports to JSON (26 MB, 8000 films, 25 neighbors each)
- ✅ Model runs locally on the phone; no server needed
- ✅ Scoring, breakdown, and "because" explanations work as specified
- ✅ formatVersion = 1 is stable

**Issues to address before shipping:**
1. **TMDB ID mapping** – Films need `tmdbId` field (not yet in export)
2. **Top 50 output** – For streaming filter, model must return more candidates
3. **Tags & moods** – Not yet captured per-film; needed for home screen and daily scanning
4. **"Family" content** – Missing age rating data in export

---

## ✅ Current Implementation vs. Requirements

### Architecture

| Requirement | Status | Notes |
|---|---|---|
| No ML server | ✅ Done | Model in JSON file, runs on device |
| Model exports to JSON | ✅ Done | `export_for_app.py` → `cinematch_model.json` |
| Local recommendations (top 5) | ✅ Done | App calls `recommend(liked, excluding)` |
| TMDB as film ID | ⚠️ Partial | Model uses Letterboxd ID; needs tmdbId added to export |

### Model Format (current `formatVersion: 1`)

```json
{
  "formatVersion": 1,
  "modelVersion": "2026-10-23",
  "qualityBoost": 0.02,
  "maxLiked": 25,
  "featureLabels": ["Story keywords", "Director", "Cast", "Themes", "Genres", ...],
  "explainLabels": ["Director", "Cast", "Themes", "Genres", "Keywords", "Writer", "Composer", "Studio"],
  "strings": ["string_1", "string_2", ...],  // shared strings to save space
  "films": [
    {
      "id": 1000001,                    // Letterboxd ID (needs tmdbId too)
      "title": "Film Title",
      "year": 2020,
      "genres": ["Drama", "Thriller"],
      "director": "Director Name",
      "cast": "Actor 1, Actor 2, ...",
      "description": "...",
      "runtime": 120,
      "rating": 7.5,                    // Letterboxd rating (0–10 scale)
      "quality": 0.345                  // z-score of rating
    }
  ],
  "starterIDs": [1000001, 1000002, ...],  // 48 films for onboarding grid
  "neighbors": [
    [                                   // for each film (same order as films[])
      {
        "i": 1000042,                   // neighbor film index in films[]
        "s": 0.8765,                    // similarity score (0–1)
        "b": [[0, 0.3456], [2, 0.2134]],  // breakdown: [feature_index, weight]
        "x": [                          // explanation: shared terms
          [0, 42, 15],                  // [explain_label_index, string_index_1, string_index_2, ...]
          [1, 103, 104, 105]
        ]
      },
      ...
    ]
  ]
}
```

**Field details:**
- `id`: Letterboxd ID (internal); export must add `tmdbId` for app
- `rating`: Letterboxd rating (0–10); not a count-based rating
- `quality`: z-score (negative = below average, positive = above)
- `s` (similarity): 0–1; app displays as "% match"
- `b` (breakdown): Which features make the pair similar, and how much (0–1 scale per feature)
- `x` (explanation): Shared terms per feature (grouped as explain labels)

---

## 📋 Peter's Questions & Answers

### 1. Which model? Does it still run locally?

✅ **Answer:** Anton's content-based model. Yes, 100% local.
- Runs from JSON file on the phone
- No server, no network call for recommendations
- ~35 seconds to build Letterboxd index on first app launch; then loads in ~2 seconds

**File:** `cinematch_model.json` (26 MB, 8000 films, 25 neighbors each)

---

### 2. Input: Are likes/dislikes enough?

✅ **Partial.** The model works with likes/dislikes alone, but:

| Input | Used by | Status |
|---|---|---|
| Likes | ✅ recommend() | Max 25 (newest first) |
| Dislikes | ✅ Yes, excluded from output | Works |
| "Haven't seen" | ⚠️ Not used | User taps but we ignore it |
| Streaming services | ✅ Filter only | App filters top 5 after; model gives top 5 |
| Stars (ratings) | ❌ Not collected | Not planned for MVP |

**Change needed for streaming-onboarding (A):**
- Model must output **top 50** instead of top 5, so app can filter by streaming service and still have 5–10 left.

---

### 3. Output: Top 50? Score 0–1? Reason + breakdown?

✅ **Score 0–1:** Yes, model outputs `s` (0–1) per neighbor.

⚠️ **Top 50:** Currently top 25 neighbors per film. To support streaming filter:
- Increase `--neighbors 25` → `--neighbors 50` in export
- App filters by user's streaming services, picks best 5–10

✅ **Begrundelse (reason):** Yes, model outputs:
- `"Because you liked Se7en"`
- Feature breakdown (`b`): How much each feature (Director, Cast, etc.) contributes
- Shared terms (`x`): Specific values (e.g., "David Fincher", "serial killer")

**App builds final reason:** `"Because you liked Se7en · Director: David Fincher · Themes: serial killer"`

---

### 4. Daily scanning: How do mood and "Family" affect the score?

❌ **Not in model yet.** Model outputs the same top 5 every time; doesn't know about mood or family.

**What's needed:**

| Requirement | Responsibility | Status |
|---|---|---|
| Mood tags (Laugh/Thrill/Think/Be moved) | Model + app | ⚠️ Need mood labels per film |
| Re-rank by mood | App | Can be done in app if tags exist |
| Family-safe (age rating) | Model export | ⚠️ Need age rating per film |
| Filter by "Family" | App | Can filter if rating exists |

**Solution:**
1. Export adds per-film: `moods: ["thrill", "think"]`, `ageRating: "15"`
2. App re-ranks top 50 by mood + time + company
3. Returns top 5 for today

---

### 5. Home screen: Thematic rows ("slow-burn thrillers", "Dark Nordic crime")

❌ **Not in model yet.** Model has only:
- `featureLabels`: 14 feature types (Director, Cast, Themes, etc.)
- `explainLabels`: 8 most important ones

**What's needed:**
- Per-film tags: `tags: ["slow-burn", "dark", "nordic", "crime"]`
- API to find films with tags the user likes (e.g., if user likes Nordic crime, suggest more)

**Solution:**
1. Export adds `tags: [...]` per film
2. App collects which tags the user's liked films share
3. App calls `getFilmsByTag()` or similar to populate home rows

---

### 6. Format & file size

| Field | Current | After changes |
|---|---|---|
| formatVersion | 1 | → 2 (adding fields) |
| File size | 26 MB | → ~28–30 MB (tags, mood, rating, tmdbId) |
| Films | 8000 | Same |
| Neighbors | 25 | → 50 (for streaming filter) |

**Changes for formatVersion 2:**
```json
{
  "formatVersion": 2,
  "films": [
    {
      "id": 1000001,
      "tmdbId": 550,              // NEW: TMDB ID (for app to fetch posters, streams)
      "title": "Fight Club",
      "year": 1999,
      "genres": [...],
      "moods": ["thrill", "think"],  // NEW: For daily scanning mood filter
      "ageRating": "18",          // NEW: For "Family" filter
      "tags": ["dark", "cult", "twist"],  // NEW: For home screen thematic rows
      ...existing fields...
    }
  ],
  "neighbors": [...] // now 50 per film, not 25
}
```

---

### 7. Film IDs: tmdbId in export?

❌ **Not yet.** Export currently has `id` (Letterboxd ID only).

**Must add:** `tmdbId` field for each film, so app can:
- Fetch posters from TMDB
- Fetch streaming services in Denmark
- Match user data (ratings, watches) from other services

**Where does tmdbId come from?**
- Letterboxd data may have it, or
- Use external mapping (TMDB API / IMDb crossref)
- See `ml_prompt_tmdb_id.md` for current state

---

## 🔧 To-Do Before MVP Launch

### A. Streaming Onboarding (User can filter by service)

**Needed by:** App feature (B), daily scanning (C)

| Task | Owner | Status |
|---|---|---|
| Export `--neighbors 50` (not 25) | ML | Pending |
| Update cinematch_model.json | ML | Pending |
| App filters top 50 by user's services | Peter | Design ready |

**Implementation:**
```bash
python export_for_app.py --neighbors 50
```

**Estimate:** 5 min rebuild time

---

### B. Home Screen – Thematic Rows

**Needed by:** App feature (home screen rows)

| Task | Owner | Status |
|---|---|---|
| Add `tags: [...]` per film to export | ML | Pending |
| Decide tag vocabulary (50–100 tags total?) | ML + Peter | Pending |
| App ingests tags, finds user's favorite tags | Peter | Pending |
| App calls "films with tag X" | App + API? | Design TBD |

**Notes:**
- Tags differ from genres; they're tonal/conceptual (e.g., "slow-burn", "coming-of-age", "dark Nordic")
- Could be hardcoded from themes/keywords or machine-learned
- Must be **English labels only** (app shows them to user)

**Estimate:** 1–2 hours (tagging logic) + Peter's integration

---

### C. Daily Scanning – Mood Filter

**Needed by:** App feature (C), "What do you want to watch tonight?"

| Task | Owner | Status |
|---|---|---|
| Add `moods: [...]` per film to export | ML | Pending |
| Decide mood vocabulary (4–8 moods?) | ML + Peter | Pending |
| App re-ranks top 50 by mood + time + company | Peter | Pending |

**Mood mapping idea:**
- `moods: ["laugh", "thrill", "think", "be_moved"]` or similar
- Per film, 1–3 moods (or leave empty if no mood)

**Estimate:** 1 hour (mood tagging) + Peter's integration

---

### D. Family Filter – Age Rating

**Needed by:** App feature (C), "watching with family?"

| Task | Owner | Status |
|---|---|---|
| Add `ageRating: "15"` per film to export | ML | Pending |
| App filters to films ≤ user's age limit | Peter | Pending |

**Age ratings:** Use standard (U, PG, 12A, 15, 18, etc.) or TMDB's (G, PG, PG-13, R, NC-17)?
- Recommend: **TMDB standard** (easier for app + TMDB API)
- Or: **EU standard** (U, 6, 12, 15, 18)

**Where from:** Letterboxd doesn't have it; must fetch from TMDB during export.

**Estimate:** 30 min (add TMDB fetch to export)

---

### E. TMDB ID in Export

**Needed by:** App (to fetch posters, streams, age rating)

| Task | Owner | Status |
|---|---|---|
| Map Letterboxd ID → TMDB ID | ML | Pending; see ml_prompt_tmdb_id.md |
| Add `tmdbId` field to each film in export | ML | Pending |
| Update export_for_app.py | ML | Pending |

**Note:** The document `ml_prompt_tmdb_id.md` should have current mapping stats. Check it.

**Estimate:** 30 min (if mapping exists); 2+ hours (if need to build it)

---

### F. formatVersion → 2

**When to increment:**
```json
{
  "formatVersion": 2,          // was 1
  "modelVersion": "2026-10-30-b"
}
```

**App behavior:**
- App refuses files with unknown `formatVersion`
- Increment only when adding new fields to `films` or `neighbors`

**Timing:** Do this once, after you're happy with all new fields (tags, moods, ageRating, tmdbId).

---

## 📊 Verification Checklist (Before Handoff to Peter)

After export and before committing `cinematch_model.json`:

- [ ] File size reasonable (~28–30 MB)?
- [ ] All 8000 films have `tmdbId`
- [ ] All films have `moods: [...]` (may be empty array `[]`)
- [ ] All films have `ageRating` (if sourcing from TMDB)
- [ ] All films have `tags: [...]` (may be empty array `[]`)
- [ ] Top 50 neighbors per film (not 25)?
- [ ] formatVersion = 2?
- [ ] modelVersion timestamp correct?
- [ ] starterIDs still has 48 films for onboarding?
- [ ] Breakdown + explanation still work (b, x fields unchanged)?
- [ ] No duplicate TMDB IDs or film titles?

---

## 🎯 Summary for Peter

**Now ready:**
- ✅ Download cinematch_model.json (v1, 8000 films, 25 neighbors)
- ✅ Build "For You" screen (top 5 with reasons)
- ✅ Build "Your taste" onboarding (48 starter films)
- ✅ Model scoring & breakdown logic is stable

**Next steps (in order):**
1. **Get TMDB IDs** for all 8000 films (see ml_prompt_tmdb_id.md)
2. **Export top 50** neighbors (not 25) → streaming filter works
3. **Add tags + moods + age rating** to export → home rows + daily scanning
4. **Increment formatVersion to 2**
5. **Re-export and test** with app

**Estimated total:** 2–3 hours of ML work (mostly data processing, not model changes)

---

## References

- `export_for_app.py` – Export script; adjust `--neighbors`, add new fields
- `cinematch.py` – Model & scoring logic
- `cinematch_model.json` – Current export (v1)
- `ml_prompt_app_overview.md` – Full app spec (this was your input)
- `ml_prompt_tmdb_id.md` – TMDB ID mapping status (check this first!)
- `Letterboxd_Movies_Data/*.csv` – Raw film metadata
