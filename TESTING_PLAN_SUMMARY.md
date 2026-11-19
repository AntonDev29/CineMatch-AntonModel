# CineMatch ML Testing Plan – Quick Summary

## 📋 The Three Documents

You now have a complete testing framework:

| Document | Purpose | When to Use |
|----------|---------|------------|
| **MODEL_TESTING_PLAN.md** | Full testing methodology + phases | Week 1 planning, phase gates |
| **FEEDBACK_SYSTEM_SETUP.md** | Implementation guide | Building feedback collection system |
| **FEEDBACK_ANALYSIS_COOKBOOK.md** | Copy-paste queries + recipes | Weekly analysis & issue diagnosis |

---

## 🚀 Quick Start Timeline

### Week 1-2: Pre-Launch Testing
- [ ] Run unit tests on cinematch_model.json v2 (scoring, neighbor calculation)
- [ ] Manually validate 100 random films (check if top 10 recommendations make sense)
- [ ] Use FEEDBACK_ANALYSIS_COOKBOOK.md Query 1 to find obvious problem films

**Success Criteria:** ≥80% of manual recommendations look good

### Week 3-4: Closed Beta (50-100 testers)
- [ ] Implement feedback collection (FEEDBACK_SYSTEM_SETUP.md)
- [ ] Testers use app, thumbs-up/down recommendations
- [ ] Run weekly_checks.py every Monday
- [ ] Check dashboard: Overall precision target ≥75%

**Success Criteria:** ≥75% precision across all sources, no major issues

### Week 4-5: Deep Diagnosis (if needed)
- [ ] Use FEEDBACK_ANALYSIS_COOKBOOK.md to find problem genres/features
- [ ] Implement targeted fixes (adjust weights, add tags, etc.)
- [ ] Rebuild model: `python export_for_app.py --rebuild`
- [ ] Re-test with 50 new beta testers

**Success Criteria:** Problem areas fixed, precision back to ≥75%

### Week 6-7: Broader Beta (500 testers)
- [ ] Expand feedback collection to larger group
- [ ] A/B test any improvements (v2.0 vs v2.1)
- [ ] Generate market segment analysis

**Success Criteria:** Consistent ≥75% precision across segments

### Week 8: Production Launch
- [ ] Final checklist from MODEL_TESTING_PLAN.md
- [ ] Deploy to all App Store users
- [ ] Enable production feedback collection

---

## 📊 Key Metrics to Track

```
DAILY DASHBOARD
═══════════════════════════════════════════════════════════════
Overall Precision:      [████████░] 68% (target: ≥75%)

By Feature:
  Streaming filter:     [████████░] 72% ✅
  Home rows:            [██████░░░] 64% 🟡
  Mood scan:            [█████░░░░] 58% 🔴  ← Focus here
  Search:               [████████░] 71% ✅

By Genre (sample):
  Comedy:               [████████░] 68%
  Drama:                [████████░] 70%
  Horror:               [█████░░░░] 52% 🔴  ← Investigate
  Sci-Fi:               [█████████] 76% ✅

Problem Films:
  "Disaster Movie":     9 negative, 1 positive 🔴
  "The Room":           5 negative, 2 positive 🔴

Latest Feedback Sample:
  👍 Inception via streaming_filter
  👎 Birdemic via search
  🤷 Titanic via home_rows
```

---

## 🎯 Three Success Levels

### 🟢 GREEN (Precision ≥75%)
- Ready for Phase 3 expansion
- Deploy improvements confidently
- Maintain current feedback loops

### 🟡 YELLOW (Precision 60-74%)
- Identify 2-3 problem areas
- Implement quick fixes
- Re-test in 1 week
- Do NOT expand to more users yet

### 🔴 RED (Precision <60%)
- Stop and investigate
- May need major model review
- Consider reverting to v1
- Deep-dive analysis required

---

## 💾 Files You'll Need

1. **feedback.db** – SQLite database collecting user feedback
2. **FEEDBACK_SYSTEM_SETUP.md** – Code to create tables + insert feedback
3. **weekly_checks.py** – Automated Monday morning reports
4. **cinematch_model.json v2** – Your current model (47.9 MB)
5. **export_for_app.py** – Script to rebuild model if fixes needed

---

## 🔧 Most Common Fixes

### Problem: Low precision for Genre X
**Fix:** Increase genre-to-genre weighting in export_for_app.py
```python
WEIGHTS['genre_match'] = 0.5  # was 0.4
# Rebuild model
```

### Problem: Mood filter is too restrictive
**Fix:** Add more films to that mood category
```python
MOOD_MAPPING['Biography'] = ['think']  # Add new mapping
# Rebuild model
```

### Problem: Age rating filter cutting good films
**Fix:** Use rating + content instead of genre alone
```python
if film['rating'] > 7.0 and 'Animation' in genres:
    age_rating = 'PG'  # Most likely family-friendly
# Rebuild model
```

See FEEDBACK_ANALYSIS_COOKBOOK.md for full diagnostic recipes.

---

## 📱 In-App UI Minimal Requirement

Just add three buttons to each recommendation:

```
[ 👍 Great ] [ 🤷 Maybe ] [ 👎 Nope ]
```

That's it. Send feedback + film ID to backend. Everything else is analysis.

---

## 📞 Questions?

| Question | Answer Location |
|----------|-----------------|
| "What should I test?" | MODEL_TESTING_PLAN.md Phase 1-2 |
| "How do I collect feedback?" | FEEDBACK_SYSTEM_SETUP.md Step 1-5 |
| "Horror precision dropped—what do I check?" | FEEDBACK_ANALYSIS_COOKBOOK.md Query 3 |
| "Is 72% precision good enough?" | MODEL_TESTING_PLAN.md Phase 5.1 |
| "How do I rebuild the model?" | export_for_app.py `--rebuild` flag |
| "A/B test comparison?" | FEEDBACK_ANALYSIS_COOKBOOK.md Query 4 |

---

## 🎯 Success Criteria for Launch

**All must be YES:**

- [ ] Overall precision ≥75%
- [ ] No genre below 50%
- [ ] Streaming filter ≥70%
- [ ] Home rows ≥65%
- [ ] Mood scan ≥60%
- [ ] Watch-through rate ≥40%
- [ ] Average rating of watched films ≥3.5/5
- [ ] No critical bugs
- [ ] Performance <500ms/recommendation

If any is NO: Fix it, re-test, then launch.

---

## 🚀 Day 1 Actions

1. Read this summary (5 min)
2. Skim MODEL_TESTING_PLAN.md (20 min)
3. Copy feedback collection code from FEEDBACK_SYSTEM_SETUP.md (30 min)
4. Send to Peter: "Here's how to instrument feedback collection in the app"
5. Set up database + analytics dashboard (2-3 hours)
6. Create weekly_checks.py automation (30 min)

**Total time to ready:** ~4 hours

**Then:** Recruit 50 beta testers, deploy, collect feedback for 2-3 weeks.

---

**Next step:** Hand MODEL_TESTING_PLAN.md + FEEDBACK_SYSTEM_SETUP.md to Peter for app instrumentation.

Good luck! 🎬
