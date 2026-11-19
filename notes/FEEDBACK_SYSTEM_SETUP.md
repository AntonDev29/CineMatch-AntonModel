# CineMatch Feedback System Setup

Quick implementation guide for collecting and analyzing user feedback.

---

## 🚀 Quick Start (2-3 hours)

### Step 1: Create Feedback Logging (30 min)

**Add to your iOS app's Firebase or backend:**

```swift
// FeedbackManager.swift
import Foundation

class FeedbackManager {
    static let shared = FeedbackManager()
    
    struct FilmFeedback: Codable {
        let userId: String
        let recommendedFilmId: String  // Use tmdbId from model
        let feedback: String  // "positive", "negative", "neutral"
        let source: String  // "streaming_filter", "home_row", "mood_scan", "search"
        let position: Int  // 1-50 (rank in list)
        let timestamp: Date
        let sessionDurationSeconds: Int
    }
    
    func logFeedback(
        userId: String,
        filmId: String,
        feedback: String,
        source: String,
        position: Int,
        sessionDuration: Int
    ) {
        let entry = FilmFeedback(
            userId: userId,
            recommendedFilmId: filmId,
            feedback: feedback,
            source: source,
            position: position,
            timestamp: Date(),
            sessionDurationSeconds: sessionDuration
        )
        
        // Send to Firebase or your backend
        uploadFeedback(entry)
    }
    
    private func uploadFeedback(_ feedback: FilmFeedback) {
        // TODO: Implement based on your backend
        // POST /api/feedback with JSON body
    }
}

// Usage in RecommendationView:
Button(action: {
    FeedbackManager.shared.logFeedback(
        userId: currentUser.id,
        filmId: recommendation.tmdbId,
        feedback: "positive",
        source: "home_row",
        position: indexPath.row + 1,
        sessionDuration: sessionDurationSeconds
    )
}) {
    Image(systemName: "hand.thumbsup")
}
```

### Step 2: Backend Logging Endpoint (1 hour)

**Python/Flask backend:**

```python
# backend/feedback.py
from flask import Flask, request, jsonify
from datetime import datetime
import json
import sqlite3

app = Flask(__name__)

# Create feedback table
def init_db():
    conn = sqlite3.connect('feedback.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY,
            user_id TEXT,
            film_id TEXT,
            feedback TEXT,
            source TEXT,
            position INTEGER,
            timestamp TEXT,
            session_duration INTEGER
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/api/feedback', methods=['POST'])
def log_feedback():
    data = request.json
    
    conn = sqlite3.connect('feedback.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO feedback 
        (user_id, film_id, feedback, source, position, timestamp, session_duration)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['userId'],
        data['recommendedFilmId'],
        data['feedback'],
        data['source'],
        data['position'],
        data['timestamp'],
        data['sessionDurationSeconds']
    ))
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'logged'}), 200

@app.route('/api/feedback/stats', methods=['GET'])
def get_stats():
    conn = sqlite3.connect('feedback.db')
    c = conn.cursor()
    
    # Count feedback by type
    c.execute('SELECT feedback, COUNT(*) FROM feedback GROUP BY feedback')
    feedback_counts = dict(c.fetchall())
    
    # Precision by source
    c.execute('''
        SELECT source, 
               ROUND(100.0 * SUM(CASE WHEN feedback='positive' THEN 1 ELSE 0 END) / COUNT(*), 1)
        FROM feedback 
        GROUP BY source
    ''')
    source_precision = dict(c.fetchall())
    
    conn.close()
    
    return jsonify({
        'feedback_counts': feedback_counts,
        'source_precision': source_precision,
        'total_feedback': sum(feedback_counts.values())
    })

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
```

### Step 3: Analytics Dashboard (1 hour)

**Python script to generate reports:**

```python
# analytics/dashboard.py
import sqlite3
from datetime import datetime, timedelta
import json

class FeedbackAnalytics:
    def __init__(self, db_path='feedback.db'):
        self.db = db_path
    
    def get_precision_metrics(self, days=7):
        """Get precision metrics for last N days"""
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        
        since = (datetime.now() - timedelta(days=days)).isoformat()
        
        # Overall precision
        c.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN feedback='positive' THEN 1 ELSE 0 END) as positive,
                SUM(CASE WHEN feedback='neutral' THEN 1 ELSE 0 END) as neutral,
                SUM(CASE WHEN feedback='negative' THEN 1 ELSE 0 END) as negative
            FROM feedback
            WHERE timestamp > ?
        ''', (since,))
        
        total, positive, neutral, negative = c.fetchone()
        
        metrics = {
            'period': f'Last {days} days',
            'total_feedback': total,
            'positive_count': positive,
            'positive_percentage': round(100 * positive / total, 1) if total > 0 else 0,
            'neutral_percentage': round(100 * neutral / total, 1) if total > 0 else 0,
            'negative_percentage': round(100 * negative / total, 1) if total > 0 else 0,
            'timestamp': datetime.now().isoformat()
        }
        
        conn.close()
        return metrics
    
    def get_precision_by_source(self, days=7):
        """Precision breakdown by feature"""
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        
        since = (datetime.now() - timedelta(days=days)).isoformat()
        
        c.execute('''
            SELECT 
                source,
                COUNT(*) as total,
                SUM(CASE WHEN feedback='positive' THEN 1 ELSE 0 END) as positive
            FROM feedback
            WHERE timestamp > ?
            GROUP BY source
        ''', (since,))
        
        results = {}
        for source, total, positive in c.fetchall():
            results[source] = {
                'total': total,
                'positive': positive,
                'precision': round(100 * positive / total, 1) if total > 0 else 0
            }
        
        conn.close()
        return results
    
    def get_precision_by_genre(self, days=7):
        """Cross-reference feedback with cinematch_model.json to get genre precision"""
        # Load model
        import json
        with open('../cinematch_model.json') as f:
            model = json.load(f)
        
        film_genres = {f['tmdbId']: f['genres'] for f in model['films']}
        
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        
        since = (datetime.now() - timedelta(days=days)).isoformat()
        c.execute('''
            SELECT film_id, feedback FROM feedback WHERE timestamp > ?
        ''', (since,))
        
        # Aggregate by genre
        genre_stats = {}
        for film_id, feedback in c.fetchall():
            genres = film_genres.get(film_id, [])
            for genre in genres:
                if genre not in genre_stats:
                    genre_stats[genre] = {'positive': 0, 'total': 0}
                genre_stats[genre]['total'] += 1
                if feedback == 'positive':
                    genre_stats[genre]['positive'] += 1
        
        # Calculate precision
        results = {}
        for genre, stats in genre_stats.items():
            results[genre] = {
                'total': stats['total'],
                'precision': round(100 * stats['positive'] / stats['total'], 1)
            }
        
        conn.close()
        return results
    
    def generate_report(self, days=7):
        """Generate full report"""
        print(f"\n{'='*70}")
        print(f"CINEMATCH ML MODEL FEEDBACK REPORT - Last {days} days")
        print(f"{'='*70}\n")
        
        # Overall metrics
        overall = self.get_precision_metrics(days)
        print("OVERALL PRECISION")
        print(f"  Total feedback: {overall['total_feedback']}")
        print(f"  Positive: {overall['positive_count']} ({overall['positive_percentage']}%)")
        print(f"  Neutral: {overall['neutral_percentage']}%")
        print(f"  Negative: {overall['negative_percentage']}%")
        print(f"  Generated: {overall['timestamp']}\n")
        
        # By source
        print("PRECISION BY FEATURE")
        by_source = self.get_precision_by_source(days)
        for source in sorted(by_source.keys()):
            stats = by_source[source]
            bar = '█' * int(stats['precision'] / 5) + '░' * (20 - int(stats['precision'] / 5))
            print(f"  {source:20s} {bar} {stats['precision']}% ({stats['total']} feedback)")
        print()
        
        # By genre
        print("PRECISION BY GENRE")
        by_genre = self.get_precision_by_genre(days)
        for genre in sorted(by_genre.keys(), key=lambda g: by_genre[g]['precision'], reverse=True):
            stats = by_genre[genre]
            bar = '█' * int(stats['precision'] / 5) + '░' * (20 - int(stats['precision'] / 5))
            print(f"  {genre:20s} {bar} {stats['precision']}% ({stats['total']} feedback)")
        print()
        
        # Recommendations
        print("RECOMMENDATIONS")
        low_performers = {g: s for g, s in by_genre.items() if s['precision'] < 60}
        if low_performers:
            print("  ⚠️  Genres to improve (precision <60%):")
            for genre, stats in sorted(low_performers.items(), key=lambda x: x[1]['precision']):
                print(f"     - {genre}: {stats['precision']}% ({stats['total']} feedback)")
        else:
            print("  ✅ All genres performing well (≥60%)")
        
        if overall['positive_percentage'] >= 75:
            print(f"  ✅ Overall precision {overall['positive_percentage']}% - Ready for Phase 3 expansion!")
        elif overall['positive_percentage'] >= 60:
            print(f"  🟡 Overall precision {overall['positive_percentage']}% - Needs targeted improvements")
        else:
            print(f"  🔴 Overall precision {overall['positive_percentage']}% - Needs major review")
        
        print(f"\n{'='*70}\n")

# Run reports
if __name__ == '__main__':
    analytics = FeedbackAnalytics()
    
    # Generate weekly report
    analytics.generate_report(days=7)
```

---

## 📱 Step 4: Add UI for Feedback (30 min)

### SwiftUI Example:

```swift
// RecommendationCardView.swift
import SwiftUI

struct RecommendationCardView: View {
    let film: Film
    let position: Int
    @State private var showFeedbackOptions = false
    
    var body: some View {
        VStack(spacing: 12) {
            // Film poster, title, description...
            FilmPosterView(film: film)
            
            Text(film.title)
                .font(.headline)
            
            Text(film.description)
                .font(.caption)
                .lineLimit(2)
            
            // Feedback buttons
            HStack(spacing: 12) {
                Button(action: { 
                    FeedbackManager.shared.logFeedback(
                        userId: Auth.userId,
                        filmId: film.tmdbId,
                        feedback: "positive",
                        source: sourceContext,
                        position: position,
                        sessionDuration: sessionDuration
                    )
                    showConfirmation = true
                }) {
                    Label("Great!", systemImage: "hand.thumbsup.fill")
                        .font(.caption)
                }
                .buttonStyle(.bordered)
                .tint(.green)
                
                Button(action: { 
                    FeedbackManager.shared.logFeedback(
                        userId: Auth.userId,
                        filmId: film.tmdbId,
                        feedback: "neutral",
                        source: sourceContext,
                        position: position,
                        sessionDuration: sessionDuration
                    )
                }) {
                    Label("Maybe", systemImage: "hand.raised.fill")
                        .font(.caption)
                }
                .buttonStyle(.bordered)
                .tint(.gray)
                
                Button(action: { 
                    FeedbackManager.shared.logFeedback(
                        userId: Auth.userId,
                        filmId: film.tmdbId,
                        feedback: "negative",
                        source: sourceContext,
                        position: position,
                        sessionDuration: sessionDuration
                    )
                }) {
                    Label("Nope", systemImage: "hand.thumbsdown.fill")
                        .font(.caption)
                }
                .buttonStyle(.bordered)
                .tint(.red)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
    }
}
```

---

## 📊 Step 5: Weekly Review Cadence

**Every Monday morning:**

```bash
#!/bin/bash
# weekly_report.sh

cd /path/to/analytics
python dashboard.py > reports/week_$(date +%Y-%m-%d).txt

# Email to team
mail -s "CineMatch ML Feedback Report" team@example.com < reports/week_$(date +%Y-%m-%d).txt

# Push to team Slack
curl -X POST https://hooks.slack.com/services/YOUR/WEBHOOK/URL \
  -H 'Content-Type: application/json' \
  -d @- < reports/week_$(date +%Y-%m-%d).txt
```

Add to your crontab:
```
0 8 * * 1 /path/to/weekly_report.sh
```

---

## 🔄 Monthly Deep Dive (2 hours)

**First Friday of each month, run:**

```python
# monthly_analysis.py
from analytics.dashboard import FeedbackAnalytics

analytics = FeedbackAnalytics()

# Overall trend
print("\n=== MONTHLY TREND ===")
for week in range(4):
    metrics = analytics.get_precision_metrics(days=7, offset_weeks=week)
    print(f"Week {4-week}: {metrics['positive_percentage']}%")

# Problem genres
print("\n=== NEED IMPROVEMENT ===")
by_genre = analytics.get_precision_by_genre(days=30)
problem = {g: s for g, s in by_genre.items() if s['precision'] < 65}
for genre in sorted(problem, key=lambda g: by_genre[g]['precision']):
    print(f"  {genre}: {by_genre[genre]['precision']}%")

# Top performers
print("\n=== EXCELLING ===")
top = {g: s for g, s in by_genre.items() if s['precision'] > 75}
for genre in sorted(top, key=lambda g: by_genre[g]['precision'], reverse=True):
    print(f"  {genre}: {by_genre[genre]['precision']}%")

# A/B test results (if running)
print("\n=== A/B TEST (if applicable) ===")
# Compare v2.0 vs v2.1 performance
```

---

## 🎯 Success Metrics Checklist

- [ ] Feedback endpoint logging <100ms
- [ ] Dashboard generates reports in <30 sec
- [ ] Weekly reports automated + sent to team
- [ ] Can slice data by: source, genre, time period, user segment
- [ ] Overall precision tracking (target ≥75%)
- [ ] Problem areas identified within 1 week
- [ ] Easy to A/B test model changes

---

## 🚨 Troubleshooting

**"Feedback counts look low"**
- Check app is actually sending feedback
- Add test entries manually to database
- Verify backend endpoint is accessible from app

**"Precision numbers are different each day"**
- Normal variance with small sample size
- Use 7-day rolling window to smooth
- Need ~1,000 feedback entries per metric for confidence

**"One genre dropped 20% this week"**
- Could be: random variance, data error, or real problem
- Cross-check with sample of user feedback
- Look at specific films - is one bad recommendation dragging down genre?

---

## 📞 Next Steps

1. Implement FeedbackManager in Swift (today)
2. Deploy feedback endpoint (this week)
3. Set up database + analytics dashboard (this week)
4. Add feedback UI to app (next week)
5. Start collecting beta feedback (Week 3)
6. Generate first report (Week 4)

Questions? See MODEL_TESTING_PLAN.md for full context.
