# CineMatch ML Testing Framework – Complete Index

## 📚 Documentation Files

Your complete testing framework consists of 5 documents:

### 1. **TESTING_OVERVIEW.txt** ⭐ START HERE
Visual guide with quick reference. Read this first for the big picture.
- Framework structure overview
- 8-week timeline at a glance
- Key metrics dashboard format
- Common fixes quick reference
- **Read time:** 10 minutes

### 2. **TESTING_PLAN_SUMMARY.md**
Executive summary and action checklist.
- Quick start timeline (weeks 1-8)
- Three success levels (🟢🟡🔴)
- Most common fixes
- Success criteria checklist
- File requirements checklist
- **Read time:** 10 minutes

### 3. **MODEL_TESTING_PLAN.md** (Comprehensive)
Full testing methodology with 5 phases.
- **Phase 1:** Pre-Release Testing (unit tests + manual validation)
- **Phase 2:** Closed Beta (50-100 testers, feedback collection)
- **Phase 3:** Analysis & Diagnosis (deep dives, iteration decisions)
- **Phase 4:** Broader Beta (500 testers, market segmentation)
- **Phase 5:** Production Launch (success criteria checklist)
- **Read time:** 30 minutes
- **Reference:** Return here for phase gates and detailed requirements

### 4. **FEEDBACK_SYSTEM_SETUP.md** (Implementation)
Step-by-step guide to build feedback infrastructure.
- Step 1: Feedback logging in Swift (FeedbackManager)
- Step 2: Backend endpoint (Python/Flask)
- Step 3: Analytics dashboard (Python queries)
- Step 4: UI for feedback (SwiftUI examples)
- Step 5: Weekly review automation
- **Implementation time:** 3-4 hours
- **Language:** Swift + Python
- **Database:** SQLite (feedback.db)

### 5. **FEEDBACK_ANALYSIS_COOKBOOK.md** (Recipes)
Copy-paste SQL queries and analysis recipes.
- **Query 1:** Find problematic films (30+ negative feedback)
- **Query 2:** Compare features by precision
- **Query 3:** Diagnose specific issues (why is mood scan low?)
- **Query 4:** A/B test model versions
- **Fixes:** Common issues + solutions
- **Weekly checklist:** Automated Monday reports
- **Use:** Weekly analysis, issue diagnosis, decision-making

---

## 🚀 Execution Roadmap

### Week 1-2: Preparation Phase
**Documents:** TESTING_OVERVIEW.txt → TESTING_PLAN_SUMMARY.md → MODEL_TESTING_PLAN.md (Phase 1)

Tasks:
- [ ] Read all overview documents (1 hour)
- [ ] Understand Phase 1 requirements
- [ ] Run unit tests on cinematch_model.json v2
- [ ] Manually validate 100 random films
- [ ] Use Query 1 (FEEDBACK_ANALYSIS_COOKBOOK.md) to find obvious problems
- [ ] Success: ≥80% of manual recommendations make sense

### Week 3-4: Closed Beta Phase
**Documents:** FEEDBACK_SYSTEM_SETUP.md → MODEL_TESTING_PLAN.md (Phase 2)

Tasks:
- [ ] Implement feedback collection (FEEDBACK_SYSTEM_SETUP.md)
- [ ] Recruit 50-100 beta testers
- [ ] Deploy v2 model to test group
- [ ] Run weekly_checks.py every Monday
- [ ] Analyze feedback using FEEDBACK_ANALYSIS_COOKBOOK.md queries
- [ ] Success: Precision ≥75%, no major issues

### Week 4-5: Diagnosis & Fix Phase
**Documents:** FEEDBACK_ANALYSIS_COOKBOOK.md → MODEL_TESTING_PLAN.md (Phase 3)

Tasks (if precision <75%):
- [ ] Identify problem areas (Query 2-3 from cookbook)
- [ ] Implement targeted fixes (see cookbook "Common Fixes" section)
- [ ] Rebuild model: `python export_for_app.py --rebuild`
- [ ] Re-test with 50 new beta testers
- [ ] Success: Problem areas fixed, precision back to ≥75%

### Week 6-7: Broader Beta Phase
**Documents:** MODEL_TESTING_PLAN.md (Phase 4)

Tasks:
- [ ] Expand feedback collection to 500 testers
- [ ] Run A/B test on any improvements (Query 4 from cookbook)
- [ ] Generate market segment analysis
- [ ] Success: Consistent ≥75% precision across all segments

### Week 8: Production Launch
**Documents:** MODEL_TESTING_PLAN.md (Phase 5)

Tasks:
- [ ] Final success criteria check (5.1 checklist)
- [ ] Deploy v2 model to App Store
- [ ] Enable production feedback collection
- [ ] Set up monthly reporting

---

## 📊 Key Sections by Task

### "I need to understand the whole plan"
1. Read: TESTING_OVERVIEW.txt (visual guide)
2. Read: TESTING_PLAN_SUMMARY.md (executive summary)
3. Skim: MODEL_TESTING_PLAN.md (detailed phases)

### "I need to build the feedback system"
1. Follow: FEEDBACK_SYSTEM_SETUP.md Step 1-5
2. Code language: Swift (app) + Python (backend)
3. Time required: 3-4 hours

### "I need to analyze feedback and find issues"
1. Use: FEEDBACK_ANALYSIS_COOKBOOK.md Query 1-4
2. SQL: Copy-paste SQLite queries
3. Time per analysis: 15-30 minutes

### "Precision is low—what do I check?"
1. Run: FEEDBACK_ANALYSIS_COOKBOOK.md Query 2 (compare features)
2. Run: FEEDBACK_ANALYSIS_COOKBOOK.md Query 3 (deep dive)
3. Find: Specific problem area (genre, feature, mood)
4. Implement: Fix from cookbook "Common Fixes" section
5. Rebuild: `python export_for_app.py --rebuild`

### "When can I launch?"
1. Check: MODEL_TESTING_PLAN.md Phase 5.1 (Success Criteria Checklist)
2. Must pass: All 10 criteria
3. If any fail: Implement fix + re-test

### "How do I A/B test improvements?"
1. Use: FEEDBACK_ANALYSIS_COOKBOOK.md Query 4
2. Split: 50/50 users between v2.0 and v2.1
3. Run: 1 week
4. Compare: Precision metrics
5. Winner: Deploy to all users

---

## 💾 Required Files & Database Schema

### Production Files (Already Have)
- `cinematch_model.json` (v2, 47.9 MB)
- `export_for_app.py` (rebuild script)

### To Create (From FEEDBACK_SYSTEM_SETUP.md)
- `FeedbackManager.swift` (app side)
- `backend/feedback.py` (server side)
- `analytics/dashboard.py` (reporting)
- `feedback.db` (SQLite database, auto-created)
- `weekly_checks.py` (automation)

### Database Schema (feedback.db)
```sql
CREATE TABLE feedback (
    id INTEGER PRIMARY KEY,
    user_id TEXT,
    film_id TEXT,  -- Use tmdbId from model
    feedback TEXT,  -- "positive" | "neutral" | "negative"
    source TEXT,    -- "streaming_filter" | "home_row" | "mood_scan" | "search"
    position INTEGER,  -- 1-50 (rank in recommendation list)
    timestamp TEXT,
    session_duration INTEGER  -- seconds
)
```

---

## 📋 Quick Reference: Common Queries

### Find films with negative feedback
Use: FEEDBACK_ANALYSIS_COOKBOOK.md → Query 1
Time: 5 minutes to run

### Compare feature performance
Use: FEEDBACK_ANALYSIS_COOKBOOK.md → Query 2
Tells you: Which feature (streaming, moods, etc) performs best

### Debug why mood_scan is low
Use: FEEDBACK_ANALYSIS_COOKBOOK.md → Query 3
Tells you: Specific problems (too few films, wrong moods, etc)

### Test if model improvement worked
Use: FEEDBACK_ANALYSIS_COOKBOOK.md → Query 4
Tells you: Whether to deploy v2.1 to all users

---

## 🎯 Success Criteria (Must All Be YES)

From MODEL_TESTING_PLAN.md Phase 5.1:

- [ ] Overall precision ≥75%
- [ ] All major genres ≥50% (most ≥60%)
- [ ] Streaming filter ≥70%
- [ ] Home rows ≥65%
- [ ] Mood scan ≥60%
- [ ] Watch-through rate ≥40%
- [ ] Average user rating ≥3.5/5
- [ ] <5% complaints in surveys
- [ ] No critical bugs
- [ ] Performance <500ms/recommendation

If any is NO → Go back to Phase 3 (fix it).

---

## 🔧 Most Common Issues & Fixes

### Issue 1: Low precision for Genre X
**Diagnosis:** FEEDBACK_ANALYSIS_COOKBOOK.md Query 2-3
**Fix:** Increase genre_match weight in export_for_app.py
**Rebuild:** `python export_for_app.py --rebuild`

### Issue 2: Mood scan underperforming
**Diagnosis:** Are there enough films in that mood? Query 3
**Fix:** Add more films to MOOD_MAPPING
**Rebuild:** `python export_for_app.py --rebuild`

### Issue 3: Age rating too restrictive
**Diagnosis:** mood + age combination = too few films? Query 3
**Fix:** Use content heuristics instead of genre alone
**Rebuild:** `python export_for_app.py --rebuild`

### Issue 4: Specific film is "bad"
**Diagnosis:** FEEDBACK_ANALYSIS_COOKBOOK.md Query 1
**Fix:** Review its neighbors, may need filtering
**Action:** Document known-bad films, skip in recommendations

---

## 📞 Document Cross-Reference

| Question | Answer Location |
|----------|-----------------|
| Where do I start? | TESTING_OVERVIEW.txt |
| What's the timeline? | TESTING_PLAN_SUMMARY.md |
| Full methodology? | MODEL_TESTING_PLAN.md |
| How to implement? | FEEDBACK_SYSTEM_SETUP.md |
| How to analyze? | FEEDBACK_ANALYSIS_COOKBOOK.md |
| How do I know when to launch? | MODEL_TESTING_PLAN.md Phase 5.1 |
| Precision dropped—what to check? | FEEDBACK_ANALYSIS_COOKBOOK.md Query 2-3 |
| Should I deploy this improvement? | FEEDBACK_ANALYSIS_COOKBOOK.md Query 4 |
| Weekly report template? | FEEDBACK_ANALYSIS_COOKBOOK.md "Weekly Checklist" |
| Common fixes? | FEEDBACK_ANALYSIS_COOKBOOK.md "Common Fixes" |

---

## 🚀 First 24 Hours Checklist

- [ ] Read TESTING_OVERVIEW.txt (10 min)
- [ ] Read TESTING_PLAN_SUMMARY.md (10 min)
- [ ] Share all docs with Peter (app developer)
- [ ] Discuss feedback collection requirements (30 min call)
- [ ] Copy code snippets from FEEDBACK_SYSTEM_SETUP.md (reference)
- [ ] Plan Week 1-2 manual validation work

**Time commitment:** 1 hour

---

## 🎓 Learning Path

**For Project Managers:**
1. TESTING_OVERVIEW.txt (timeline overview)
2. TESTING_PLAN_SUMMARY.md (success criteria)
3. Reference: Success Criteria Checklist

**For Developers:**
1. FEEDBACK_SYSTEM_SETUP.md (implementation)
2. FEEDBACK_ANALYSIS_COOKBOOK.md (queries + fixes)
3. Keep reference: Common Fixes section

**For QA/Testers:**
1. MODEL_TESTING_PLAN.md Phase 1-2 (testing procedures)
2. FEEDBACK_ANALYSIS_COOKBOOK.md (how to diagnose issues)
3. Keep reference: Weekly checklist

**For Data Analysts:**
1. FEEDBACK_ANALYSIS_COOKBOOK.md (all queries)
2. FEEDBACK_SYSTEM_SETUP.md (database setup)
3. Keep reference: A/B test comparison

---

## ✅ You're Ready

This framework covers everything needed to:
✅ Test the ML model systematically
✅ Collect user feedback efficiently
✅ Analyze results and identify issues
✅ Fix problems and iterate
✅ Know when to launch
✅ Measure success post-launch

**Next step:** Start with TESTING_OVERVIEW.txt, then follow TESTING_PLAN_SUMMARY.md checklist.

Good luck! 🎬
