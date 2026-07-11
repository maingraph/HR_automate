# Quick Start: Performance Features

## Real-time Updates

### Backend - Sending WebSocket Notifications

```python
from app.api.websocket import notify_job_update

# Notify about job status change
await notify_job_update(job_id, {
    "type": "job_update",
    "data": {"status": "running", "progress": 50}
})

# Notify about pipeline progress
await notify_job_update(job_id, {
    "type": "pipeline_log",
    "data": {"stage": "scraping", "count": 100}
})
```

### Frontend - Receiving Updates

```typescript
import { useWebSocket } from "@/lib/hooks/useWebSocket";

function JobPage({ jobId }: { jobId: string }) {
  const { lastMessage, isConnected } = useWebSocket(`job:${jobId}`);
  
  useEffect(() => {
    if (!lastMessage) return;
    
    const { type, data } = lastMessage;
    
    if (type === 'job_update') {
      // Update job state
      setJob(prev => ({ ...prev, ...data }));
    }
  }, [lastMessage]);
  
  return <div>Connected: {isConnected ? '✓' : '✗'}</div>;
}
```

## Performance Monitoring

### Track Operations

```python
from app.core.monitoring import track_performance, log_performance_summary

# Track a single operation
with track_performance("my_operation"):
    # ... your code ...
    pass

# Log summary at end of task
log_performance_summary()
```

### Get Statistics

```python
from app.core.monitoring import get_monitor

monitor = get_monitor()
stats = monitor.get_stats("scrape_telegram")
print(f"Average: {stats['avg']:.2f}s")
print(f"Total calls: {stats['count']}")
```

## Optimized Components

### Use Memoized Candidate Card

```typescript
import { CandidateCard } from "@/components/CandidateCard";

function CandidateList({ candidates }: { candidates: Candidate[] }) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  
  return (
    <div>
      {candidates.map(candidate => (
        <CandidateCard
          key={candidate.id}
          candidate={candidate}
          isExpanded={expandedId === candidate.id}
          onToggle={() => setExpandedId(
            expandedId === candidate.id ? null : candidate.id
          )}
        />
      ))}
    </div>
  );
}
```

### Use Virtualized List (for 500+ items)

```typescript
import { VirtualizedCandidateList } from "@/components/VirtualizedCandidateList";

function LargeCandidateList({ candidates }: { candidates: Candidate[] }) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  
  return (
    <VirtualizedCandidateList
      candidates={candidates}
      expandedId={expandedId}
      onToggleExpand={setExpandedId}
      height={800} // viewport height in pixels
    />
  );
}
```

## Database Queries

### Optimized Candidate Queries

```python
# Use indexed columns for filtering
candidates = (
    sb.table("candidates")
    .select("*")
    .eq("job_id", job_id)
    .eq("status", "scored")  # Uses candidates_status_idx
    .gte("gemini_score", 70)  # Uses candidates_job_status_score_idx
    .order("gemini_score", desc=True)
    .limit(100)
    .execute()
)

# Filter by open_to_work (uses partial index)
otw_candidates = (
    sb.table("candidates")
    .select("*")
    .eq("job_id", job_id)
    .eq("open_to_work", True)  # Uses candidates_otw_idx
    .execute()
)

# Filter by scan depth
phase1_candidates = (
    sb.table("candidates")
    .select("*")
    .eq("job_id", job_id)
    .eq("scan_depth", 1)  # Uses candidates_scan_depth_idx
    .execute()
)
```

## Batch Processing

### Process Large Lists

```python
from app.scoring.gemini import embed_texts
from app.scoring.pipeline import stage2_gemini_score

# Embeddings with progress logging
texts = [candidate_blob(c) for c in candidates]
embeddings = embed_texts(texts, batch_size=100)  # Logs every 100

# Scoring with progress logging
scored = stage2_gemini_score(
    job, 
    rubric, 
    candidates,
    batch_size=10  # Logs every 10 candidates
)
```

## Monitoring Dashboard (Future)

### Check Performance Metrics

```bash
# View recent performance logs
tail -f backend/logs/app.log | grep "⏱️"

# Example output:
# ⏱️  scrape_telegram: 12.45s
# ⏱️  stage1_embed_filter: 23.67s
# ⏱️  persist_candidates: 3.12s
```

### Database Performance

```sql
-- Check index usage
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan as scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
    AND tablename IN ('candidates', 'jobs', 'pipeline_runs')
ORDER BY idx_scan DESC;

-- Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

## Troubleshooting

### WebSocket Not Connecting

```typescript
// Check connection status
const { isConnected, error } = useWebSocket(`job:${jobId}`);

if (error) {
  console.error("WebSocket error:", error);
}

// Manually reconnect
useEffect(() => {
  if (!isConnected) {
    // Hook will auto-reconnect with exponential backoff
    console.log("Waiting for reconnection...");
  }
}, [isConnected]);
```

### Slow Queries

```sql
-- Find missing indexes
SELECT 
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation
FROM pg_stats
WHERE schemaname = 'public'
    AND tablename = 'candidates'
    AND n_distinct > 100
ORDER BY abs(correlation) DESC;
```

### High Memory Usage

```python
# Process in smaller batches
BATCH_SIZE = 100  # Reduce if memory issues

for i in range(0, len(candidates), BATCH_SIZE):
    batch = candidates[i:i + BATCH_SIZE]
    process_batch(batch)
    # Memory is freed between batches
```

## Best Practices

1. **Always use indexed columns** in WHERE clauses
2. **Limit result sets** - use `.limit()` for large queries
3. **Use WebSocket for real-time updates** - avoid polling
4. **Track performance** for new operations
5. **Virtualize large lists** (500+ items)
6. **Memoize expensive components**
7. **Batch process** large datasets

## Performance Targets

- **WebSocket latency**: < 100ms
- **Database queries**: < 500ms for 10k rows
- **Candidate list render**: < 100ms for 2000 items
- **Pipeline stage**: Log progress every 10-100 items
- **Embedding generation**: ~1s per 10 texts
- **LLM scoring**: ~13s per candidate (Gemini free tier)

---

**Last Updated**: 2026-04-27
