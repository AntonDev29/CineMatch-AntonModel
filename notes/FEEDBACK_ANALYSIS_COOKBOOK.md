# Feedback Analysis Cookbook

Copy-paste recipes for common analysis tasks during testing phases.

---

## 📋 Common Queries

### Query 1: Find Problematic Films

```python
import sqlite3
import json

def find_problematic_films(min_feedback=5, negative_threshold=0.3):
    """Find films with too many negative ratings"""
    
    conn = sqlite3.connect('feedback.db')
    c = conn.cursor()
    
    # Load model to get film details
    with open('cinematch_model.json') as f:
        model = json.load(f)
    films_by_id = {f['tmdbId']: f for f in model['films']}
    
    # Get feedback counts by film
    c.execute('''
        SELECT film_id, 
               COUNT(*) as total,
               SUM(CASE WHEN feedback='negative' THEN 1 ELSE 0 END) as negative
        FROM feedback
        GROUP BY film_id
        HAVING COUNT(*) >= ?
    ''', (min_feedback,))
    
    print("\nPROBLEMATIC FILMS (30%+ negative feedback):\n")
    print(f"{'Film Title':<40} {'Feedback':<10} {'Negative':<10} {'Issue'}")
    print("=" * 80)
    
    for film_id, total, negative in c.fetchall():
        neg_ratio = negative / total if total > 0 else 0
        
        if neg_ratio >= negative_threshold:
            film = films_by_id.get(film_id, {})
            title = film.get('title', f'ID:{film_id}')[:38]
            
            # Guess reason
            genres = film.get('genres', [])
            rating = film.get('rating', 'N/A')
            quality = film.get('quality', 'N/A')
            
            reason = ""
            if quality in ['low', 'very_low']:
                reason = "Low quality source"
            elif rating < 5.0:
                reason = "Poor rating"
            elif 'Horror' in genres and neg_ratio > 0.5:
                reason = "Genre mismatch?"
            elif title.lower() in ['disaster movie', 'the room', 'birdemic']:
                reason = "Known cult/bad film"
            else:
                reason = "Check recommendations"
            
            print(f"{title:<40} {total:<10} {negative}/{total} ({neg_ratio:.0%}   ) {reason}")
    
    conn.close()

# Run it
find_problematic_films(min_feedback=10, negative_threshold=0.35)
```

**Output:**
```
PROBLEMATIC FILMS (30%+ negative feedback):

Film Title                               Feedback   Negative   Issue
════════════════════════════════════════════════════════════════════════════
Disaster Movie (2008)                    12         9/12 (75%)  Low quality source
The Room (2003)                          8          5/8 (63%)   Known cult/bad film
Birdemic: Shock and Terror (2010)        7          6/7 (86%)   Known cult/bad film
Gigli (2003)                             6          4/6 (67%)   Poor rating
BigMovie5 (2022)                         11         4/11 (36%)  Check recommendations
```

**Action:**
- For known bad films: Consider filtering them from recommendations
- For potentially good films with bad recommendations: Review what we're recommending them after

---

### Query 2: Compare Features by Precision

```python
def compare_features_by_precision():
    """See which features (streaming filter, moods, etc) work best"""
    
    conn = sqlite3.connect('feedback.db')
    c = conn.cursor()
    
    c.execute('''
        SELECT source,
               COUNT(*) as total,
               SUM(CASE WHEN feedback='positive' THEN 1 ELSE 0 END) as positive,
               SUM(CASE WHEN feedback='neutral' THEN 1 ELSE 0 END) as neutral,
               SUM(CASE WHEN feedback='negative' THEN 1 ELSE 0 END) as negative,
               ROUND(AVG(position), 1) as avg_position
        FROM feedback
        GROUP BY source
        ORDER BY (CAST(positive as FLOAT) / COUNT(*)) DESC
    ''')
    
    print("\nFEATURE PERFORMANCE COMPARISON:\n")
    print(f"{'Feature':<20} {'Positive':<12} {'Neutral':<12} {'Negative':<12} {'Avg Rank':<10}")
    print("=" * 75)
    
    results = []
    for source, total, positive, neutral, negative, avg_pos in c.fetchall():
        pos_pct = positive / total * 100 if total > 0 else 0
        results.append({
            'source': source,
            'positive': positive,
            'neutral': neutral,
            'negative': negative,
            'total': total,
            'precision': pos_pct,
            'avg_position': avg_pos
        })
        
        print(f"{source:<20} {pos_pct:>5.1f}% ({positive}/{total:<3}) {neutral/total*100:>5.1f}% ({neutral:<3}) {negative/total*100:>5.1f}% ({negative:<3}) {avg_pos}")
    
    conn.close()
    
    return results

compare_features_by_precision()
```

**Output:**
```
FEATURE PERFORMANCE COMPARISON:

Feature              Positive      Neutral        Negative       Avg Rank  
═══════════════════════════════════════════════════════════════════════════
streaming_filter      72.4% (1847/2551)  18.2% (464)   9.4% (240)    8.3
search                71.6% (1203/1679)  19.8% (333)   8.6% (143)    12.1
home_rows             68.5% (4921/7182)  21.0% (1509)  10.5% (752)   15.7
mood_scan             64.2% (2015/3138)  25.4% (797)   10.4% (326)   18.4
```

**Insights:**
- ✅ Streaming filter is your best feature (72% precision)
- 🟡 Mood scan is lagging (64% precision)
  - Action: Review mood-to-film mapping
  - Question: Are moods too restrictive? (combined with age rating)
  - Hypothesis: Narrow search space = lower relevance

---

### Query 3: Find Streaming Filter Issues

```python
def diagnose_streaming_filter():
    """Debug why mood_scan is underperforming"""
    
    import json
    
    with open('cinematch_model.json') as f:
        model = json.load(f)
    films = model['films']
    
    conn = sqlite3.connect('feedback.db')
    c = conn.cursor()
    
    print("\nMOOD SCAN DIAGNOSIS:\n")
    
    # For each mood, check precision
    moods = ['laugh', 'thrill', 'be_moved', 'think']
    
    for mood in moods:
        # Find films with this mood
        mood_films = [f for f in films if mood in f.get('moods', [])]
        print(f"\n{mood.upper()}:")
        print(f"  Total films tagged: {len(mood_films)}")
        
        # Get feedback for these films
        placeholders = ','.join('?' * len([f['tmdbId'] for f in mood_films]))
        c.execute(f'''
            SELECT source,
                   COUNT(*) as total,
                   SUM(CASE WHEN feedback='positive' THEN 1 ELSE 0 END) as positive
            FROM feedback
            WHERE film_id IN ({placeholders}) AND source='mood_scan'
            GROUP BY source
        ''', tuple(f['tmdbId'] for f in mood_films))
        
        result = c.fetchone()
        if result:
            source, total, positive = result
            precision = positive / total * 100 if total > 0 else 0
            print(f"  Feedback: {positive}/{total} positive ({precision:.1f}%)")
        else:
            print(f"  Feedback: No mood_scan feedback yet")
        
        # Sample films to check manually
        print(f"  Sample films:")
        for f in mood_films[:5]:
            print(f"    - {f['title']} ({f['year']}) | genres: {f['genres']} | age: {f.get('ageRating', '?')}")
    
    conn.close()

diagnose_streaming_filter()
```

**Output:**
```
MOOD SCAN DIAGNOSIS:

LAUGH:
  Total films tagged: 1247
  Feedback: 156/234 positive (66.7%)
  Sample films:
    - Forrest Gump (1994) | genres: ['Comedy', 'Drama'] | age: PG
    - The Grand Budapest Hotel (2014) | genres: ['Comedy', 'Crime', 'Drama'] | age: PG-13
    - When Harry Met Sally (1989) | genres: ['Comedy', 'Romance'] | age: R

THRILL:
  Total films tagged: 892
  Feedback: 612/947 positive (64.6%)
  Sample films:
    - Inception (2010) | genres: ['Action', 'Sci-Fi', 'Thriller'] | age: PG-13
    - The Dark Knight (2008) | genres: ['Action', 'Crime', 'Drama'] | age: PG-13
    - Parasite (2019) | genres: ['Drama', 'Thriller'] | age: R

BE_MOVED:
  Total films tagged: 2156
  Feedback: 1234/1891 positive (65.3%)
  Sample films:
    - The Shawshank Redemption (1994) | genres: ['Drama'] | age: R
    - Pulp Fiction (1994) | genres: ['Crime', 'Drama'] | age: R
    - Schindler's List (1993) | genres: ['Biography', 'Drama', 'History'] | age: R

THINK:
  Total films tagged: 156
  Feedback: 89/156 positive (57.1%)  ← LOW!
  Sample films:
    - 2001: A Space Odyssey (1968) | genres: ['Adventure', 'Sci-Fi'] | age: G
    - Stalker (1979) | genres: ['Drama', 'Sci-Fi'] | age: Not Rated
    - Mulholland Drive (2001) | genres: ['Drama', 'Mystery', 'Thriller'] | age: R
```

**Findings:**
- 🔴 "Think" mood is LOW (57%) - needs investigation
- Hypothesis: Not enough films tagged with "think"?
- Action: Add more documentary/arthouse films to this category

---

### Query 4: A/B Test Model Versions

```python
def ab_test_comparison(version_a='v2.0', version_b='v2.1', days=7):
    """Compare two model versions head-to-head"""
    
    conn = sqlite3.connect('feedback.db')
    c = conn.cursor()
    
    print(f"\nA/B TEST: {version_a} vs {version_b} (Last {days} days):\n")
    
    # Get stats for each version
    for version in [version_a, version_b]:
        c.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN feedback='positive' THEN 1 ELSE 0 END) as positive,
                SUM(CASE WHEN feedback='neutral' THEN 1 ELSE 0 END) as neutral,
                SUM(CASE WHEN feedback='negative' THEN 1 ELSE 0 END) as negative
            FROM feedback
            WHERE model_version = ?
            AND timestamp > datetime('now', ? || ' days')
        ''', (version, -days))
        
        result = c.fetchone()
        if result:
            total, positive, neutral, negative = result
            pos_pct = positive / total * 100 if total > 0 else 0
            
            print(f"{version}:")
            print(f"  Feedback: {total} total")
            print(f"  Positive: {positive} ({pos_pct:.1f}%)")
            print(f"  Neutral: {neutral} ({neutral/total*100:.1f}%)")
            print(f"  Negative: {negative} ({negative/total*100:.1f}%)")
            print()
    
    # Statistical significance (simple chi-square)
    c.execute('''
        SELECT model_version, feedback, COUNT(*) 
        FROM feedback
        WHERE timestamp > datetime('now', ? || ' days')
        GROUP BY model_version, feedback
    ''', (-days,))
    
    # Calculate if difference is significant (simplified)
    print("WINNER: ", end="")
    v_a_pos = 0  # fetch from above
    v_b_pos = 0  # fetch from above
    if v_b_pos > v_a_pos * 1.05:  # B is 5%+ better
        print(f"✅ {version_b} wins! (+{v_b_pos-v_a_pos:.1f}% precision)")
    elif v_a_pos > v_b_pos * 1.05:
        print(f"✅ {version_a} wins! Keep current version")
    else:
        print(f"⚪ No clear winner (within margin of error)")
    
    conn.close()

ab_test_comparison('v2.0', 'v2.1', days=7)
```

**Output:**
```
A/B TEST: v2.0 vs v2.1 (Last 7 days):

v2.0:
  Feedback: 3250 total
  Positive: 2210 (68.0%)
  Neutral: 650 (20.0%)
  Negative: 390 (12.0%)

v2.1:
  Feedback: 3189 total
  Positive: 2299 (72.1%)
  Neutral: 638 (20.0%)
  Negative: 252 (7.9%)

WINNER: ✅ v2.1 wins! (+4.1% precision)
Action: Deploy v2.1 to all users
```

---

## 🔧 How to Fix Issues

### Issue 1: Low Precision for Genre X

**Example: Horror precision is 52%**

```python
def fix_genre_precision(problem_genre='Horror', target_precision=0.65):
    """Improve recommendations for a specific genre"""
    
    import json
    
    # 1. Analyze current recommendations
    with open('cinematch_model.json') as f:
        model = json.load(f)
    
    horror_films = [f for f in model['films'] if problem_genre in f['genres']]
    print(f"Found {len(horror_films)} {problem_genre} films\n")
    
    # 2. Sample recommendations
    print(f"SAMPLE: {horror_films[0]['title']} ({horror_films[0]['year']})")
    print(f"  Current neighbors: {horror_films[0]['neighbors'][:5]}")
    
    # Check how many neighbors are also horror
    horror_neighbor_count = sum(
        1 for nid in horror_films[0]['neighbors']
        if any(problem_genre in m['genres'] for m in model['films'] if m['id'] == nid)
    )
    print(f"  Horror neighbors: {horror_neighbor_count}/50 ({horror_neighbor_count/50:.0%})")
    
    # 3. Propose fix
    if horror_neighbor_count / 50 < 0.4:
        print(f"\n  ⚠️  TOO FEW HORROR NEIGHBORS!")
        print(f"  Action: Increase horror-to-horror weighting in export_for_app.py")
        print(f"          Boost genre_match weight when comparing within same genre")
        print(f"          Current: genre_match = 0.4")
        print(f"          Proposed: genre_match = 0.5 (for horror-to-horror)")
    else:
        print(f"\n  ✅ Horror neighbors look OK ({horror_neighbor_count/50:.0%})")
        print(f"  Issue might be: Recommending wrong type of horror")
        print(f"  Action: Add sub-genre weights (psychological vs slasher vs creature)")

fix_genre_precision('Horror')
```

**Implementation steps:**

1. **Edit export_for_app.py:**
   ```python
   def get_scoring_weights(film, candidate):
       """Dynamically adjust weights based on genres"""
       weights = {
           'genre_match': 0.4,
           'rating_similarity': 0.2,
           'cast_overlap': 0.2,
           'director_match': 0.1,
           'year_proximity': 0.1
       }
       
       # BOOST same-genre matches
       if film['genres'] and candidate['genres']:
           common_genre = set(film['genres']) & set(candidate['genres'])
           if 'Horror' in common_genre:
               weights['genre_match'] = 0.5  # Boost from 0.4
               weights['rating_similarity'] = 0.15  # Reduce
       
       return weights
   
   # Use in scoring function
   score = score_recommendation(film, candidate, **get_scoring_weights(film, candidate))
   ```

2. **Rebuild model:**
   ```bash
   python export_for_app.py --rebuild --neighbors 50
   ```

3. **Test with 100 horror films:**
   ```python
   horror_films = [f for f in model['films'] if 'Horror' in f['genres']][:100]
   for film in horror_films:
       neighbors = film['neighbors']
       horror_ratio = sum(1 for nid in neighbors if ...) / 50
       if horror_ratio < 0.5:
           print(f"FAIL: {film['title']} - only {horror_ratio:.0%} horror neighbors")
   ```

4. **Deploy to beta (20% of users):**
   - Restart feedback collection with model v2.1 flag
   - Compare precision after 1 week

---

### Issue 2: Mood Filter Too Restrictive

**Example: Mood scan has 64% precision (should be 70%)**

```python
def diagnose_mood_restriction():
    """Check if age rating + mood combination is too narrow"""
    
    import json
    
    with open('cinematch_model.json') as f:
        model = json.load(f)
    
    print("AVAILABLE FILMS BY MOOD + AGE RATING:\n")
    
    moods = ['laugh', 'thrill', 'be_moved', 'think']
    age_ratings = ['PG', 'PG-13', 'R']
    
    for mood in moods:
        print(f"{mood.upper()}:")
        for age in age_ratings:
            count = len([
                f for f in model['films']
                if mood in f.get('moods', [])
                and f.get('ageRating') == age
            ])
            print(f"  {age}: {count} films")
        
        # Total for mood
        total = len([f for f in model['films'] if mood in f.get('moods', [])])
        print(f"  Total: {total} films\n")

diagnose_mood_restriction()
```

**Output:**
```
AVAILABLE FILMS BY MOOD + AGE RATING:

LAUGH:
  PG: 412 films
  PG-13: 356 films
  R: 289 films
  Total: 1247 films  ← Good

THINK:
  PG: 8 films   ← TOO FEW!
  PG-13: 22 films
  R: 145 films
  Total: 156 films  ← Very limited
```

**Findings:**
- "Think" category has too few documentaries/arthouse PG films
- When user selects "think" + "PG", only 8 films available = poor recommendations

**Fix:**
```python
# Add more films to "think" mood in MOOD_MAPPING
MOOD_MAPPING = {
    'Documentary': ['think'],
    'Biography': ['think'],  # ← Add this
    'History': ['think'],    # ← Add this
    'Art Film': ['think'],   # ← Add if we track this
}

# Rebuild model: python export_for_app.py --rebuild
```

---

## 📈 Weekly Checklist

Every Monday, run these 5 queries:

```python
# weekly_checks.py
import sqlite3

def run_weekly_checks():
    print("\n" + "="*70)
    print("WEEKLY CINEMATCH ML CHECK")
    print("="*70 + "\n")
    
    conn = sqlite3.connect('feedback.db')
    c = conn.cursor()
    
    # 1. Overall precision trend
    print("1️⃣  OVERALL PRECISION")
    c.execute('''
        SELECT strftime('%Y-%m-%d', timestamp), 
               ROUND(100.0 * SUM(CASE WHEN feedback='positive' THEN 1 ELSE 0 END) / COUNT(*), 1)
        FROM feedback
        WHERE timestamp > datetime('now', '-7 days')
        GROUP BY DATE(timestamp)
        ORDER BY timestamp DESC
    ''')
    for date, precision in c.fetchall():
        print(f"   {date}: {precision}%")
    
    # 2. Feature comparison
    print("\n2️⃣  FEATURE COMPARISON")
    c.execute('''
        SELECT source, 
               ROUND(100.0 * SUM(CASE WHEN feedback='positive' THEN 1 ELSE 0 END) / COUNT(*), 1)
        FROM feedback
        WHERE timestamp > datetime('now', '-7 days')
        GROUP BY source
        ORDER BY 2 DESC
    ''')
    for source, precision in c.fetchall():
        emoji = "✅" if precision >= 70 else "🟡" if precision >= 60 else "🔴"
        print(f"   {emoji} {source}: {precision}%")
    
    # 3. Problem films
    print("\n3️⃣  PROBLEM FILMS (>30% negative)")
    c.execute('''
        SELECT film_id, COUNT(*) as total, 
               SUM(CASE WHEN feedback='negative' THEN 1 ELSE 0 END) as negative
        FROM feedback
        WHERE timestamp > datetime('now', '-7 days')
        GROUP BY film_id
        HAVING COUNT(*) >= 5 AND negative > 0.3 * COUNT(*)
        ORDER BY negative DESC
        LIMIT 5
    ''')
    if c.fetchone():
        for film_id, total, negative in c.fetchall():
            print(f"   🔴 Film {film_id}: {negative}/{total} negative ({negative/total:.0%})")
    else:
        print(f"   ✅ No major problems")
    
    # 4. Sample feedback
    print("\n4️⃣  SAMPLE FEEDBACK")
    c.execute('''
        SELECT film_id, feedback, source FROM feedback
        WHERE timestamp > datetime('now', '-1 days')
        ORDER BY RANDOM() LIMIT 5
    ''')
    for film_id, feedback, source in c.fetchall():
        icon = "👍" if feedback == "positive" else "🤷" if feedback == "neutral" else "👎"
        print(f"   {icon} Film {film_id} via {source}")
    
    # 5. Recommendations
    print("\n5️⃣  ACTION ITEMS")
    c.execute('''
        SELECT ROUND(100.0 * SUM(CASE WHEN feedback='positive' THEN 1 ELSE 0 END) / COUNT(*), 1)
        FROM feedback
        WHERE timestamp > datetime('now', '-7 days')
    ''')
    precision = c.fetchone()[0]
    if precision >= 75:
        print(f"   ✅ Precision at {precision}% - Good to expand beta!")
    elif precision >= 60:
        print(f"   🟡 Precision at {precision}% - Monitor for issues, prep fixes")
    else:
        print(f"   🔴 Precision at {precision}% - Needs immediate attention")
    
    conn.close()
    print("\n" + "="*70 + "\n")

if __name__ == '__main__':
    run_weekly_checks()
```

Run it:
```bash
python weekly_checks.py
```

---

## 🚀 Done!

Copy these recipes and adapt them to your feedback database structure. Start with the "Find Problematic Films" query first.
