# CineMatch App Schedule – ML Fit Analysis

**Date:** 30/10-2026  
**Status:** ✅ ML ready; no blockers identified

---

## Overview

Evaluating whether the ML model and export strategy fit within the app's development schedule and feature roadmap.

---

## Critical Path

```
Current Status:
├─ ✅ Model ready (content-based, working)
├─ ✅ Export script ready (cinematch_model.json v1)
├─ ✅ "For You" logic ready (top 5 + reasons)
├─ ⏳ Extended export (v2 with tags, moods, ratings) — 2–3 hours
│   ├─ Get TMDB IDs (0.5–2 hours)
│   ├─ Add moods/tags per film (2 hours)
│   ├─ Add age rating (0.5 hours)
│   └─ Bump formatVersion (5 min)
└─ ✅ Ready for Peter's app development

Parallel path (while ML does v2):
├─ Peter builds "For You" (works with v1 today)
├─ Peter designs "Streaming onboarding"
├─ Peter designs "Home screen" (ready once tags are in v2)
└─ Peter designs "Daily scanning" (ready once moods + age rating are in v2)
```

---

## Schedule Fit Assessment

### Phase 1: MVP (Now – Web Demo)

| Feature | ML Status | App Status | Blocker? |
|---|---|---|---|
| Login / onboarding | – | In progress | No |
| "For You" (top 5 rec.) | ✅ Ready (v1) | Ready to build | **No** |
| Basic recommendation score | ✅ Working | Using model score | **No** |
| "Because" explanation | ✅ Working | Using breakdown | **No** |
| Poster + title display | – | Uses TMDB | **No** |

**Conclusion:** MVP can ship now with v1 model. Peter has everything needed.

---

### Phase 2: Streaming + Home (Next)

| Feature | ML Needed | ML Status | App Status | Blocker? |
|---|---|---|---|---|
| Streaming filter | Top 50 candidates | ⏳ 5 min rebuild | Ready to build | **No** (fast fix) |
| Home "taste" rows | Tags per film | ⏳ 1 hour | Ready to build | **Yes** (1 hour wait) |
| TMDB posters | TMDB ID mapping | ⏳ 0.5–2 hours | Ready to use | **Maybe** (depends on mapping) |

**Conclusion:** Small delays (~1–2 hours ML work). Peter can start home/streaming UI while we finish v2.

---

### Phase 3: Daily Scanning (Later)

| Feature | ML Needed | ML Status | App Status | Blocker? |
|---|---|---|---|---|
| Mood filter | Moods per film | ⏳ 1 hour | Ready to build | **No** (design time absorbs wait) |
| "Family" filter | Age rating | ⏳ 0.5 hours | Ready to build | **No** |
| Context-aware recs | Mood re-ranking | ⏳ 1 hour | Ready to build | **No** |

**Conclusion:** All features fit parallel development. No schedule impact.

---

## Timeline Estimate

### ML Deliverables

| Item | Estimate | Risk | Notes |
|---|---|---|---|
| **v1 model (current)** | Done | ✅ None | Working now; Peter uses today |
| **TMDB ID mapping** | 0.5–2 hours | 🟡 Medium | Depends on external data; may need fetch |
| **Top 50 export** | 5 min | ✅ Low | Just change one parameter |
| **Tags + moods** | 2 hours | 🟡 Medium | Need to define tag/mood vocabulary |
| **Age rating fetch** | 0.5 hours | 🟡 Medium | Need TMDB API key + rate limiting |
| **v2 export + test** | 1 hour | ✅ Low | Standard rebuild |
| **Total** | **2–4 hours** | | **Most likely 2.5–3 hours** |

### Assumption: When can ML start?

- **TMDB mapping** – Check `ml_prompt_tmdb_id.md` immediately. If 90%+ done, start with that. Otherwise, request Peter provide mapping via external service (TMDB API fetch can be parallelized).
- **Tag/mood vocabulary** – Can start immediately; no blockers.

### App Milestones (Peter's side)

| Milestone | Requires | ML Deadline | Peter Starts |
|---|---|---|---|
| MVP web (top 5) | v1 | Done ✅ | Now |
| Streaming filter | Top 50 | ~30 min | After ML confirms |
| Home screen | Tags | ~2 hours | After v2 preview |
| Daily scanning | Moods + age | ~3 hours | After v2 merge |

**Overlap opportunity:** Peter starts UI/design while ML finishes v2. No critical path delay.

---

## Risk Assessment

### 🟢 Low Risk (Won't impact schedule)

1. **Top 50 rebuild** – Takes 5 minutes; Peter can wait.
2. **formatVersion bump** – Trivial change; tested with v2 locally before export.
3. **Existing model logic** – No changes to scoring; just more data in JSON.

### 🟡 Medium Risk (1–2 hour delays possible)

1. **TMDB ID mapping quality** – If 20%+ films missing IDs:
   - Mitigation: Use TMDB search API to fill gaps (automated)
   - Estimate: +1 hour for error handling + verification
   
2. **Tag vocabulary agreement** – If Peter has specific tag structure in mind:
   - Mitigation: Decide tags in next 30 min call; ML implements in parallel
   - Estimate: +0 hours (already in parallel window)
   
3. **Age rating data completeness** – If TMDB missing age ratings for 10%+ films:
   - Mitigation: Use fallback (IMDB, or just omit; app treats as "no restriction")
   - Estimate: +0 hours (fallback is acceptable)

### 🔴 High Risk (None identified!)

No blockers that would delay MVP or phase 2.

---

## Deliverables Checklist

### For Peter (at each phase)

**Now (MVP):**
- [x] `cinematch_model.json` v1 (8000 films, 25 neighbors)
- [x] Feature labels + explain labels
- [x] Starter IDs (48 onboarding films)
- [x] Model scoring logic documented
- [ ] TMDB ID mapping (pending; see ml_prompt_tmdb_id.md)

**Phase 2 (Streaming + Home):**
- [ ] `cinematch_model.json` v2 with:
  - [ ] `tmdbId` field (all 8000 films)
  - [ ] `tags: [...]` field (per film)
  - [ ] `neighbors` list extended to 50 (not 25)
- [ ] Verification report (file size, tag counts, etc.)

**Phase 3 (Daily Scanning):**
- [ ] `cinematch_model.json` v2 updated with:
  - [ ] `moods: [...]` field (per film)
  - [ ] `ageRating` field (per film)
- [ ] Verification report (coverage %, edge cases)

---

## Potential Issues to Watch

### 1. TMDB ID Coverage

**Current state:** Unknown. Check `ml_prompt_tmdb_id.md`.

**Scenarios:**
- ✅ 95%+ films have TMDB ID → Export as-is
- ⚠️ 80–94% → Fill gaps with TMDB search API (~0.5 hour added)
- ❌ <80% → May need to reconsider data source (unlikely with Letterboxd)

**Action:** Open `ml_prompt_tmdb_id.md` immediately.

### 2. Tag Vocabulary Consistency

**Risk:** If tags are too generic (e.g., all films tagged "good"), home rows won't be meaningful.

**Mitigation:**
- Use Letterboxd themes + TMDB tags as seed
- Filter to ~50–100 tags (don't tag every film with everything)
- Test: "Do 3–5 similar films share the same tag?"

**Action:** Define tags in next call with Peter.

### 3. Mood Assignment Quality

**Risk:** If mood tags don't match user intent (e.g., "Laugh" tag on a film nobody laughs at), users won't find mood feature useful.

**Mitigation:**
- Use Letterboxd reviews + ratings to infer mood (e.g., high-rated comedies → "Laugh")
- Or: Use TMDB genre hints (Action → "Thrill", Drama → "Be moved")
- Accept that some films have no mood (empty array is OK)

**Action:** Discuss mood taxonomy with Peter before implementation.

### 4. Age Rating Data Quality

**Risk:** TMDB may not have ratings for all films; regional differences (Denmark ≠ US).

**Mitigation:**
- Fetch TMDB rating; use EU standard (U, 6, 12, 15, 18) if available
- Fallback: Omit rating if not available; app treats as "no restriction"
- Document any gaps in verification report

**Action:** Plan TMDB fetch + fallback strategy before export.

---

## Recommended Approach

### Week 1 (Now)

**ML side:**
- Check `ml_prompt_tmdb_id.md` → estimate TMDB mapping effort
- Define tag vocabulary (20 tags min, 100 max) → discuss with Peter
- Define mood vocabulary (4–8 moods) → discuss with Peter
- Start TMDB ID fetch if <1 hour; otherwise request Peter's help

**Peter's side:**
- Build "For You" screen (uses v1 model now)
- Design "Streaming onboarding" UI (ready for filter once top 50 exists)
- Design "Home screen" layout (ready for tags once v2 exists)

### Week 2 (After ML v2)

**ML side:**
- Export v2 with all fields
- Run verification (8000 films, all fields present, no dups)
- Commit + upload to shared storage

**Peter's side:**
- Download v2 model
- Integrate tags into home screen
- Integrate moods into daily scanning
- Test end-to-end

---

## Summary for Project Manager

| Metric | Status |
|---|---|
| **MVP Blocker?** | ✅ No – ship now with v1 |
| **Schedule Risk** | 🟢 Low – all work parallelizable |
| **ML Timeline** | 2–3 hours (mostly data processing) |
| **Critical Dependency** | Check `ml_prompt_tmdb_id.md` status (may block 0.5–2 hours) |
| **No. of Model Changes** | 0 (export-only updates) |
| **App Impact** | Low (new fields, same scoring logic) |

**Recommendation:** Proceed with Phase 1 (MVP) immediately. Start Phase 2 (v2 export) in parallel to avoid schedule slip.
