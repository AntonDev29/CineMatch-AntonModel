# 📋 Peter's Action Checklist – Start Here

**Status:** All ML work complete. Model v2 ready for download.  
**Your next:** Read, download, integrate, and build.

---

## 1️⃣ READ (Next 15 minutes)

### Essential Reading (In Order)

| # | File | Time | Why |
|---|---|---|---|
| 1 | **ANSWER_TO_PETER.md** | 10 min | What's in v2 model + integration example |
| 2 | **IMPLEMENTATION_COMPLETE.md** | 5 min | Technical details + testing checklist |

### Optional Reading (Reference Later)

- **FIXES_COMPLETE.md** – Full list of changes + verification results
- **export_for_app.py** – If you need to rebuild the model

---

## 2️⃣ DOWNLOAD (Next 2 minutes)

| File | Size | Location | Action |
|---|---|---|---|
| **cinematch_model.json** | 47.9 MB | C:\Users\anton\Desktop\CineMatch\ | Download to your Xcode project |

**Place in Xcode:**
```
CineMatch/Core/Resources/cinematch_model.json
```

---

## 3️⃣ UPDATE APP CODE (Next 1–2 hours)

### Task A: Model Loader Update

**Current (v1):**
```swift
let modelData = try JSONDecoder().decode([String: Any].self, from: modelFile)
// Directly load films, neighbors
```

**New (v2):**
```swift
guard let modelDict = try JSONSerialization.jsonObject(with: modelFile) as? [String: Any] else {
    fatalError("Invalid JSON")
}

// Check format version
guard let version = modelDict["formatVersion"] as? Int, version == 2 else {
    fatalError("Model format version not supported. Expected 2, got \(version ?? -1)")
}

// Parse films with new fields
if let filmsArray = modelDict["films"] as? [[String: Any]] {
    for filmDict in filmsArray {
        let tmdbId = filmDict["tmdbId"] as? Int ?? 0
        let moods = filmDict["moods"] as? [String] ?? []
        let ageRating = filmDict["ageRating"] as? String ?? "PG"
        let tags = filmDict["tags"] as? [String] ?? []
        // ... store in your model
    }
}
```

### Task B: Data Model Update

**Add to your Film struct:**
```swift
struct Film: Codable {
    let id: Int
    let tmdbId: Int              // NEW
    let title: String
    let year: Int
    let genres: [String]
    let director: String
    let cast: String
    let description: String
    let runtime: Int?
    let rating: Double
    let quality: Double
    let moods: [String]           // NEW
    let ageRating: String         // NEW
    let tags: [String]            // NEW
    // ... rest of fields
}
```

---

## 4️⃣ BUILD 3 FEATURES (Next 7–12 hours, spread over 1–2 weeks)

### Feature A: Streaming Filter (2–4 hours)

**What's ready from ML:**
- ✅ `tmdbId` for all films (for TMDB API calls)
- ✅ Top 50 candidates (app filters down to 5)

**What you need to build:**
1. Let user choose streaming services (Netflix, HBO Max, etc.)
2. For each recommended film, call TMDB watch/providers API
3. Check if film is available in user's region (Denmark)
4. Show "✓ Netflix available" or "Not available"
5. Filter top 50 → top 5 based on what's available

**Pseudocode:**
```swift
let top50 = recommend(likes)  // Get 50 candidates

for film in top50 {
    let providers = fetchTMDB(film.tmdbId).watchProviders
    if providers.contains(where: { user.services.contains($0) }) {
        available.append(film)
    }
}

return available.prefix(5)  // Top 5 with streaming available
```

### Feature B: Home Screen Thematic Rows (3–5 hours)

**What's ready from ML:**
- ✅ `tags` for all films (dark, indie, romantic, etc.)

**What you need to build:**
1. Get user's liked films from Supabase
2. Aggregate all their tags (e.g., 5 films with "dark" tag)
3. Sort by frequency (most common tags first)
4. Create rows: "Because you like dark films", "Your indie taste", etc.
5. Populate each row with films matching that tag

**Pseudocode:**
```swift
let likedFilms = supabase.getLikedFilms()  // User's likes
var tagCounts: [String: Int] = [:]

for film in likedFilms {
    for tag in film.tags {
        tagCounts[tag, default: 0] += 1
    }
}

let topTags = tagCounts.sorted { $0.value > $1.value }.prefix(5)

for (tag, count) in topTags {
    let filmsWithTag = allFilms.filter { $0.tags.contains(tag) }
    addRow(title: "Because you like \(tag) films", films: filmsWithTag)
}
```

### Feature C: Daily Mood Scanning (2–3 hours)

**What's ready from ML:**
- ✅ `moods` for all films (laugh, thrill, be_moved, think)
- ✅ `ageRating` for all films (PG, PG-13, R)

**What you need to build:**
1. Add UI: "What's your mood?" (4 buttons)
2. Add UI: "Time available?" (3 options)
3. Add UI: "Watching with?" (4 options)
4. Combine filters: mood + runtime + ageRating + streaming
5. Show top 5 with reason mentioning mood

**Pseudocode:**
```swift
let userMood = "thrill"            // User selected
let timeMinutes = 120              // User selected
let company = "family"             // User selected

let top50 = recommend(likes)       // 50 candidates

var results = top50
    .filter { $0.moods.contains(userMood) }
    .filter { ($0.runtime ?? 0) <= timeMinutes }
    .filter { company != "family" || $0.ageRating != "R" }
    .filter { isAvailableOnUserServices($0) }

return results.prefix(5)  // Top 5 matching all criteria
```

---

## 5️⃣ TEST (Next 1–2 hours)

### Before Submitting to App Store

Use the checklist in **IMPLEMENTATION_COMPLETE.md**:

- [ ] Model loads without errors
- [ ] `formatVersion` check passes
- [ ] All 8000 films parse correctly
- [ ] `tmdbId` present (non-zero)
- [ ] Recommendation scoring works
- [ ] Top 5 recommendations match v1 output
- [ ] New features work end-to-end

---

## 📞 If You Have Questions

| Question | Answer | Where |
|---|---|---|
| "What's in the model?" | JSON file with 8000 films + 50 neighbors each | ANSWER_TO_PETER.md § Filformat |
| "How do I parse new fields?" | Example in IMPLEMENTATION_COMPLETE.md | Integration section |
| "How does mood filtering work?" | Example pseudocode above (Feature C) | This checklist |
| "Can I rebuild the model?" | Yes, use export_for_app.py | export_for_app.py § main() |
| "What if a field is missing?" | Use safe defaults (empty array, "PG", etc.) | IMPLEMENTATION_COMPLETE.md § Fallbacks |

---

## 📊 Progress Tracker

| Task | Time Est. | Status | Notes |
|---|---|---|---|
| Read documentation | 15 min | → Start here | ANSWER_TO_PETER.md |
| Download model | 2 min | → Then this | cinematch_model.json |
| Update model loader | 1–2 hours | → Then this | Handle formatVersion 2 |
| Build streaming filter | 2–4 hours | → Do this | Use tmdbId |
| Build home screen rows | 3–5 hours | → Do this | Use tags |
| Build daily mood scanning | 2–3 hours | → Do this | Use moods + ageRating |
| Test end-to-end | 1–2 hours | → Final step | Use checklist |
| **Total** | **7–12 hours** | | Spread over 1–2 weeks |

---

## ✅ You're Ready!

All ML work is complete. No waiting. No blockers.

**Start with:** Read ANSWER_TO_PETER.md (10 minutes)  
**Then:** Download cinematch_model.json (2 minutes)  
**Then:** Start coding Feature A (2–4 hours)  

🚀 **Good luck!**
