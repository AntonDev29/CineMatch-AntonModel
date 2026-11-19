# CineMatch ML Model Testing & Feedback Plan

**Objective:** Validate model precision, gather user feedback, and iterate on recommendations.

---

## 📊 Phase 1: Pre-Release Testing (Week 1-2)

### 1.1 Unit Testing – Model Logic

**What to test:**
- Recommendation scoring algorithm accuracy
- Neighbor calculation correctness
- Tag/mood generation consistency
- TMDB ID generation uniqueness

**How:**
```python
# tests/test_cinematch_model.py
def test_recommendation_scoring():
    """Verify scoring produces expected ranking"""
    film = films[0]
    recs = get_recommendations(film, top_n=50)
    assert len(recs) == 50
    assert all(r['score'] >= recs[-1]['score'] for r in recs)
    assert recs[0]['score'] > recs[-1]['score']

def test_tmdb_id_uniqueness():
    """Ensure TMDB IDs don't collide"""
    tmdb_ids = [f['tmdbId'] for f in films]
    assert len(tmdb_ids) == len(set(tmdb_ids)), "Duplicate TMDB IDs found"

def test_tags_exist():
    """Verify all films have tags"""
    assert all(len(f['tags']) > 0 for f in films)

def test_moods_valid():
    """Ensure moods are from approved list"""
    valid_moods = {'laugh', 'thrill', 'be_moved', 'think'}
    for f in films:
        assert all(m in valid_moods for m in f['moods'])
```

**Success Criteria:**
- ✅ All scoring tests pass
- ✅ No duplicate TMDB IDs
- ✅ All films have tags (>0)
- ✅ All moods are valid

---

### 1.2 Dataset Validation – Model Quality

**What to test:**
- Recommendation relevance (manual sample check)
- Edge cases (new films, controversial films, niche genres)
- Coverage (% of films with sufficient neighbors)

**How:**
```python
# Sample 100 random films and manually verify top 10 recommendations
test_films = random.sample(films, 100)

for film in test_films:
    recs = get_recommendations(film, top_n=10)
    print(f"\n{film['title']} ({film['year']})")
    print(f"  Genres: {film['genres']}")
    print("  Top 10 Recommendations:")
    for i, rec in enumerate(recs, 1):
        print(f"    {i}. {rec['title']} ({rec['year']}) - score: {rec['score']:.2f}")
    
    # Manual validation: Are these sensible?
    # Rate on 1-5 scale: 1=terrible, 5=perfect
```

**Samples to validate:**
- 20 popular mainstream films (Inception, Titanic, etc.)
- 20 indie/niche films (Mulholland Drive, Everything Everywhere All at Once)
- 20 films from underrepresented genres
- Edge cases: horror comedies, sci-fi dramas, art-house blockbusters

**Success Criteria:**
- ✅ ≥80% of recommendations are sensible (rating 3-5)
- ✅ ≥50% are excellent matches (rating 4-5)
- ✅ No weird outliers or offensive recommendations
- ✅ ≥95% films have 50 neighbors

---

## 👥 Phase 2: Closed Beta Testing (Week 3-4)

### 2.1 Beta User Recruitment

**Who:**
- 50-100 internal testers + friends + film enthusiasts
- Mix of demographics: age, genre preferences, film knowledge
- Ideally: people who use other recommendation systems (Netflix, Letterboxd)

**Duration:** 2-3 weeks of active use

**Device:** iOS app with v2 model integrated

---

### 2.2 Feedback Collection Mechanisms

#### A. **In-App Feedback (Primary)**

Add these interactions to the app:

**Thumbs Up/Down:**
```swift
// User sees recommendation, rates it immediately
Button("👍 Great recommendation") { 
    log_feedback(film_id, "positive", timestamp) 
}

Button("👎 Not relevant") { 
    log_feedback(film_id, "negative", timestamp) 
}

Button("🤷 Not sure") { 
    log_feedback(film_id, "neutral", timestamp) 
}
```

**What to capture:**
```json
{
  "user_id": "uuid",
  "recommended_film_id": "tmdbId",
  "feedback": "positive|negative|neutral",
  "context": {
    "source": "streaming_filter|home_row|mood_scan|search",
    "top_position": 1,
    "timestamp": "ISO-8601",
    "user_session_length_minutes": 5
  },
  "user_metadata": {
    "active_days": 7,
    "total_feedback_count": 42,
    "positive_ratio": 0.67
  }
}
```

#### B. **Post-View Tracking**

```python
# After user watches a recommended film
watch_feedback = {
    "recommended_film_id": "tmdbId",
    "user_actually_watched": true|false,
    "watch_completion": 0.0-1.0,  # 0.5 = watched 50%
    "rating": 1-5,
    "session_notes": "watched with family"
}
```

#### C. **Weekly Survey (Optional)**

```json
{
  "Which recommendation was most helpful this week?": "freetext",
  "Which was least helpful?": "freetext",
  "Rate overall recommendation quality": "1-5",
  "What features would improve CineMatch?": "freetext",
  "How often do you use it?": "daily|3-4x/week|1-2x/week|rarely"
}
```

---

### 2.3 Metrics Dashboard

**Build a live dashboard tracking:**

```
REAL-TIME METRICS (Refresh every 6 hours)
═══════════════════════════════════════════

Feedback Volume:
  ├─ Total feedback count: 1,247
  ├─ Positive: 823 (66%)
  ├─ Neutral: 268 (21%)
  └─ Negative: 156 (13%)

Precision by Source:
  ├─ Streaming filter: 71% positive
  ├─ Home rows: 64% positive
  ├─ Mood scan: 58% positive
  └─ Search results: 76% positive

Precision by Genre:
  ├─ Drama: 68% positive
  ├─ Comedy: 64% positive
  ├─ Sci-Fi: 71% positive
  ├─ Horror: 52% positive (← needs work)
  └─ Action: 63% positive

User Engagement:
  ├─ Active beta testers: 47/50
  ├─ Avg feedback per user: 26.5
  ├─ Watch-through rate: 42%
  └─ Avg rating (watched films): 3.8/5

Problematic Films (Most Negative Feedback):
  1. "Disaster Movie" (2008) - 9 negative, 1 positive
  2. "The Room" (2003) - 6 negative, 2 positive
  3. "Birdemic" (2010) - 5 negative, 0 positive
  └─ Action: Review neighbor calculation for cult films
```

**How to build it:**
- Create Python script to query feedback logs every 6 hours
- Push metrics to Google Sheets or Notion for visibility
- Generate weekly PDF reports

---

## 🔍 Phase 3: Analysis & Diagnosis (Week 4-5)

### 3.1 Deep Dives on Problem Areas

**If Horror precision is low (52%):**

```python
# Analyze horror film recommendations
horror_films = [f for f in films if 'Horror' in f['genres']]

for film in horror_films[:5]:
    recs = get_recommendations(film, top_n=50)
    
    # Check 1: Are we recommending too many non-horror?
    horror_ratio = sum(1 for r in recs if 'Horror' in r['genres']) / 50
    print(f"{film['title']}: {horror_ratio:.1%} of neighbors are horror")
    
    # Check 2: Are recommendations too similar or too diverse?
    scores = [r['score'] for r in recs]
    print(f"  Score range: {min(scores):.2f} - {max(scores):.2f}")
    print(f"  StdDev: {statistics.stdev(scores):.3f}")
    
    # Check 3: What do users actually say?
    feedback = load_feedback_for_film(film['tmdbId'])
    print(f"  User feedback: {feedback['positive_count']} positive, {feedback['negative_count']} negative")

# Diagnosis action:
# If horror-to-horror ratio is low: Increase horror-specific weights in scoring
# If score range is too wide: Neighbors may be too diverse
# If scores are too similar: May need better differentiation
```

**If Streaming filter is outperforming Mood scan:**

```python
# Compare source effectiveness
streaming_feedback = get_feedback_by_source("streaming_filter")
mood_feedback = get_feedback_by_source("mood_scan")

print(f"Streaming: {streaming_feedback['positive']/len(streaming_feedback['all']):.1%} positive")
print(f"Mood scan: {mood_feedback['positive']/len(mood_feedback['all']):.1%} positive")

# Root cause analysis:
# 1. Are mood-based filters too restrictive?
# 2. Are moods generating too-specific sets?
# 3. Is the age-rating filter cutting out good recommendations?

# Test hypothesis:
test_moods = get_recommendations_by_mood("laugh", age_rating="PG-13")
print(f"Available films matching 'laugh' + 'PG-13': {len(test_moods)}")
if len(test_moods) < 50:
    print("  ⚠️ Too few options! Mood + age combo too restrictive")
```

---

### 3.2 Iteration Decisions

**If precision ≥75%:** ✅ Ready for Phase 3 (broader beta)

**If precision 60-74%:** 🟡 Needs targeted fixes
- Identify 2-3 low-performing areas
- Implement fixes (see below)
- Re-test with 50 new films + 1 week of feedback

**If precision <60%:** 🔴 Needs major review
- Consider reverting to v1 model
- OR deep-dive root-cause analysis
- Likely issue: fundamental scoring weights need adjustment

---

## 🔧 Common Fixes

### Fix 1: Improve Genre Weighting

If Comedy recommendations are off:
```python
# export_for_app.py - Adjust WEIGHTS

# Current (simplified):
WEIGHTS = {
    'genre_match': 0.4,
    'rating_similarity': 0.2,
    'cast_overlap': 0.2,
    'director_match': 0.1,
    'year_proximity': 0.1
}

# New - boost genre weight for Comedy:
if film['genres'] and 'Comedy' in film['genres']:
    WEIGHTS['genre_match'] = 0.5  # was 0.4
    WEIGHTS['rating_similarity'] = 0.15  # was 0.2

# Rebuild model and re-test
```

### Fix 2: Refine Mood Mapping

If mood-based filtering isn't working:
```python
# Current simple mapping:
MOOD_MAPPING = {
    'Comedy': ['laugh'],
    'Thriller': ['thrill'],
    'Drama': ['be_moved'],
}

# Enhanced - multi-mood films:
MOOD_MAPPING = {
    'Comedy': ['laugh'],
    'Romantic Comedy': ['laugh', 'be_moved'],
    'Dark Comedy': ['laugh', 'thrill'],
    'Thriller': ['thrill'],
    'Psychological Thriller': ['thrill', 'think'],
    'Drama': ['be_moved'],
    'Documentary': ['think'],
}
```

### Fix 3: Adjust Age Rating Heuristics

If family-friendly filtering is wrong:
```python
# Current simple rules:
if 'Horror' in film['genres']: age_rating = 'R'
if 'Family' in film['genres']: age_rating = 'PG'

# Enhanced - use rating + content:
if film['imdb_rating'] < 3.5 and 'Action' in film['genres']:
    age_rating = 'R'  # Low-rated action = probably violent
if 'Animation' in film['genres'] and film['imdb_rating'] > 7.0:
    age_rating = 'PG'  # High-rated animated = likely family-friendly
```

---

## 📈 Phase 4: Broader Beta (Week 6-7)

### 4.1 Expand Testing

- Increase testers from 50 to 500 (or public App Store beta)
- Run for 2 weeks
- Collect same metrics as Phase 2

### 4.2 Market Segmentation Analysis

```python
# Analyze precision across user segments
segments = {
    'age': ['13-18', '18-25', '25-35', '35-50', '50+'],
    'film_taste': ['mainstream', 'indie', 'arthouse', 'mixed'],
    'usage_frequency': ['daily', '3-4x/week', '1-2x/week', 'rare'],
    'platform_preference': ['streaming', 'theaters', 'both']
}

for segment_type, values in segments.items():
    for value in values:
        precision = get_precision_for_segment(segment_type, value)
        confidence = get_sample_size(segment_type, value)
        print(f"{segment_type}={value}: {precision:.1%} ({confidence} samples)")
```

**Action if segments differ:**
- If indie film precision is low but mainstream is good → Indie film weighting issue
- If inactive users have higher precision → Model may be too basic (needs complexity)
- If high-frequency users rate poorly → Model may be stale/repetitive

---

## 🎯 Phase 5: Production Launch Readiness

### 5.1 Success Criteria Checklist

Before launch to all users:

- [ ] Overall precision ≥75% (positive feedback ratio)
- [ ] All major genres ≥60% precision
- [ ] No genre <50% (if yes, document known limitation)
- [ ] Streaming filter ≥70% precision
- [ ] Home rows ≥65% precision
- [ ] Mood scan ≥60% precision
- [ ] Watch-through rate ≥40% (of recommended films actually watched)
- [ ] Average user rating of watched films ≥3.5/5
- [ ] <5% complaints in weekly surveys
- [ ] No critical bugs reported
- [ ] Performance: recommendations <500ms on device

### 5.2 Fallback Plans

**If precision stays <70%:**

| Scenario | Action |
|----------|--------|
| v2 model underperforms | Compare head-to-head with v1 model on same test set |
| Specific genre fails | Disable that feature until fixed |
| Performance issues | Reduce neighbors from 50 to 25, rebuild model |
| User adoption low | Survey why; may need feature tweaks not model tweaks |

---

## 🔄 Post-Launch Continuous Improvement

### 6.1 Ongoing Feedback Loop

**Monthly review:**
```
Month 1 Metrics Report
══════════════════════
Period: Nov 13 - Dec 13, 2026

Feedback Volume: 52,400 total interactions
  ├─ Positive: 36,680 (70%)
  ├─ Neutral: 10,480 (20%)
  └─ Negative: 5,240 (10%)

By Feature:
  ├─ Streaming filter: 72% positive (8,200 feedback)
  ├─ Home rows: 68% positive (21,400 feedback)
  ├─ Mood scan: 65% positive (14,300 feedback)
  └─ Search: 71% positive (8,500 feedback)

Top Improvements:
  1. Add "Sci-Fi/Psychological" subgenre weighting (+2% precision predicted)
  2. Fix horror recommendations (currently 58%, goal 65%)
  3. Expand mood vocabulary (users asking for "relaxing", "intense")

User Satisfaction: 4.1/5 average rating
Churn (30-day inactive): 12%
```

### 6.2 A/B Testing New Model Versions

When you make improvements:

```python
# Split users 50/50: v2.0 (control) vs v2.1 (new weights)
# Run for 1 week
# Compare precision, watch-through, ratings

results = {
    'v2.0': {'positive': 0.68, 'watch_through': 0.39, 'rating': 3.7},
    'v2.1': {'positive': 0.72, 'watch_through': 0.42, 'rating': 3.9}
}

# v2.1 wins: 72% > 68% → Deploy to all users
# v2.1 ties: not better → Keep v2.0, try different fix
```

---

## 📋 Tracking Checklist

### Pre-Launch
- [ ] Unit tests written and passing
- [ ] 100 films manually validated
- [ ] Beta testers recruited (50-100 people)
- [ ] In-app feedback system implemented
- [ ] Metrics dashboard built
- [ ] Weekly review meetings scheduled

### During Beta (Weeks 3-5)
- [ ] Check dashboard 3x per week
- [ ] Collect weekly survey responses
- [ ] Identify problem areas
- [ ] Implement targeted fixes if needed
- [ ] Document changes

### Expand Beta (Weeks 6-7)
- [ ] Analyze 500-user data
- [ ] Create market segment breakdowns
- [ ] Make final model tweaks

### Launch
- [ ] Final precision check ✅
- [ ] Deploy v2 model to App Store
- [ ] Enable production feedback collection
- [ ] Set up monthly reporting

### Post-Launch
- [ ] Monthly metrics review
- [ ] A/B test improvements
- [ ] Quarterly deep-dives
- [ ] Plan v3 enhancements

---

## 📊 Sample Dashboard Query

```python
# Generate weekly report (run every Monday)
def generate_weekly_report(start_date, end_date):
    feedback = load_feedback_data(start_date, end_date)
    
    report = f"""
    WEEKLY REPORT: {start_date} to {end_date}
    ════════════════════════════════════════════
    
    OVERALL METRICS
    Feedback count: {len(feedback)}
    Positive: {feedback['positive']/len(feedback):.1%}
    Watch-through: {feedback['watched']/feedback['recommended']:.1%}
    Avg rating: {feedback['avg_rating']:.2f}/5.0
    
    BY FEATURE
    Streaming filter: {get_precision('streaming_filter'):.1%}
    Home rows: {get_precision('home_rows'):.1%}
    Mood scan: {get_precision('mood_scan'):.1%}
    
    TRENDING ISSUES
    {format_trending_issues(feedback)}
    
    RECOMMENDATIONS
    {format_recommendations(feedback)}
    """
    
    send_email_to_team(report)
    save_report(report, f"reports/week_{start_date}.txt")
```

---

## 🎬 Next Steps

1. **This Week:** Set up feedback collection in app
2. **Next Week:** Recruit beta testers, build dashboard
3. **Week 3:** Launch closed beta
4. **Weeks 4-5:** Analyze + fix issues
5. **Weeks 6-7:** Expand beta + final validation
6. **Week 8:** Launch to production

---

**Contact:** Questions about testing approach? Review this plan with Peter before starting Phase 1.
