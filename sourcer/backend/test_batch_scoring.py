"""Test script for batch scoring functionality.

Run this to verify batch scoring works before deploying to production.

Usage:
    python test_batch_scoring.py
"""
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import settings
from app.scoring.gemini import score_candidate, score_candidates_batch

# Test job and rubric
TEST_JOB = {
    "title": "Senior Python Engineer",
    "description": "We need an experienced Python developer with Django and FastAPI experience",
    "skills": ["Python", "Django", "FastAPI", "PostgreSQL"],
    "geo": "Remote",
    "seniority": "Senior",
    "budget_min": 5000,
    "budget_max": 8000,
}

TEST_RUBRIC = {
    "skills_match": {"weight": 40, "description": "Has Python, Django, FastAPI experience"},
    "seniority_fit": {"weight": 25, "description": "Senior level (5+ years)"},
    "industry_fit": {"weight": 20, "description": "Web development background"},
    "availability": {"weight": 15, "description": "Open to work or actively searching"},
}

# Test candidates
TEST_CANDIDATES = [
    {
        "id": "1",
        "full_name": "Alice Johnson",
        "headline": "Senior Python Developer",
        "location": "San Francisco, CA",
        "skills": ["Python", "Django", "PostgreSQL", "Redis"],
        "bio": "8 years of Python development. Built scalable web applications with Django and FastAPI. Expert in database optimization.",
        "open_to_work": True,
        "source": "test",
    },
    {
        "id": "2",
        "full_name": "Bob Smith",
        "headline": "Full Stack Engineer",
        "location": "New York, NY",
        "skills": ["JavaScript", "React", "Node.js", "Python"],
        "bio": "5 years full stack development. Some Python experience but mainly focused on JavaScript ecosystem.",
        "open_to_work": False,
        "source": "test",
    },
    {
        "id": "3",
        "full_name": "Carol Davis",
        "headline": "Python Backend Engineer",
        "location": "Austin, TX",
        "skills": ["Python", "FastAPI", "Docker", "Kubernetes"],
        "bio": "6 years Python backend development. Built microservices with FastAPI. Strong DevOps skills.",
        "open_to_work": True,
        "source": "test",
    },
    {
        "id": "4",
        "full_name": "David Lee",
        "headline": "Junior Python Developer",
        "location": "Seattle, WA",
        "skills": ["Python", "Flask", "MySQL"],
        "bio": "2 years Python development. Built REST APIs with Flask. Looking to grow into senior role.",
        "open_to_work": True,
        "source": "test",
    },
    {
        "id": "5",
        "full_name": "Eve Martinez",
        "headline": "Lead Python Architect",
        "location": "Boston, MA",
        "skills": ["Python", "Django", "FastAPI", "AWS", "PostgreSQL"],
        "bio": "12 years Python development. Led teams of 10+ engineers. Expert in system architecture and scalability.",
        "open_to_work": False,
        "source": "test",
    },
]


def test_individual_scoring():
    """Test individual scoring (baseline)."""
    print("\n" + "="*80)
    print("TEST 1: Individual Scoring (Baseline)")
    print("="*80)
    
    start = time.time()
    scores = []
    
    for i, candidate in enumerate(TEST_CANDIDATES, 1):
        print(f"\nScoring candidate {i}/{len(TEST_CANDIDATES)}: {candidate['full_name']}")
        try:
            score = score_candidate(TEST_JOB, TEST_RUBRIC, candidate)
            scores.append(score)
            print(f"  Score: {score['score']}/100")
            print(f"  Reasoning: {score['reasoning'][:100]}...")
        except Exception as e:
            print(f"  ERROR: {e}")
            scores.append(None)
    
    elapsed = time.time() - start
    print(f"\n✓ Individual scoring completed in {elapsed:.1f}s")
    print(f"  Average: {elapsed/len(TEST_CANDIDATES):.1f}s per candidate")
    
    return scores, elapsed


def test_batch_scoring():
    """Test batch scoring (new implementation)."""
    print("\n" + "="*80)
    print("TEST 2: Batch Scoring (5 candidates in 1 call)")
    print("="*80)
    
    start = time.time()
    
    try:
        scores = score_candidates_batch(TEST_JOB, TEST_RUBRIC, TEST_CANDIDATES)
        elapsed = time.time() - start
        
        print(f"\n✓ Batch scoring completed in {elapsed:.1f}s")
        print(f"  Speedup: {elapsed/len(TEST_CANDIDATES):.1f}s per candidate (effective)")
        
        print("\nResults:")
        for i, (candidate, score) in enumerate(zip(TEST_CANDIDATES, scores), 1):
            print(f"\n{i}. {candidate['full_name']}")
            print(f"   Score: {score['score']}/100")
            print(f"   Reasoning: {score['reasoning'][:100]}...")
        
        return scores, elapsed
        
    except Exception as e:
        print(f"\n✗ Batch scoring failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def compare_results(individual_scores, individual_time, batch_scores, batch_time):
    """Compare individual vs batch scoring."""
    print("\n" + "="*80)
    print("COMPARISON")
    print("="*80)
    
    if not batch_scores:
        print("✗ Batch scoring failed - cannot compare")
        return
    
    print(f"\nTiming:")
    print(f"  Individual: {individual_time:.1f}s ({individual_time/len(TEST_CANDIDATES):.1f}s per candidate)")
    print(f"  Batch:      {batch_time:.1f}s ({batch_time/len(TEST_CANDIDATES):.1f}s per candidate)")
    print(f"  Speedup:    {individual_time/batch_time:.1f}x faster")
    
    print(f"\nScore Comparison:")
    for i, (ind, batch) in enumerate(zip(individual_scores, batch_scores), 1):
        if ind and batch:
            diff = abs(ind['score'] - batch['score'])
            status = "✓" if diff <= 10 else "⚠"
            print(f"  {status} Candidate {i}: Individual={ind['score']}, Batch={batch['score']}, Diff={diff}")
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    if batch_time and individual_time:
        speedup = individual_time / batch_time
        if speedup >= 3:
            print(f"✓ SUCCESS: Batch scoring is {speedup:.1f}x faster!")
        else:
            print(f"⚠ WARNING: Speedup is only {speedup:.1f}x (expected 3-5x)")
    
    # Check score quality
    if individual_scores and batch_scores:
        diffs = [abs(ind['score'] - batch['score']) for ind, batch in zip(individual_scores, batch_scores) if ind and batch]
        avg_diff = sum(diffs) / len(diffs) if diffs else 0
        
        if avg_diff <= 5:
            print(f"✓ Score quality: Excellent (avg diff: {avg_diff:.1f} points)")
        elif avg_diff <= 10:
            print(f"✓ Score quality: Good (avg diff: {avg_diff:.1f} points)")
        else:
            print(f"⚠ Score quality: Degraded (avg diff: {avg_diff:.1f} points)")


def main():
    """Run all tests."""
    print("="*80)
    print("BATCH SCORING TEST SUITE")
    print("="*80)
    print(f"\nConfiguration:")
    print(f"  AI Provider: {settings.ai_provider}")
    print(f"  Model: {settings.openrouter_model if settings.ai_provider == 'openrouter' else settings.gemini_model}")
    print(f"  Batch Scoring Enabled: {settings.batch_scoring_enabled}")
    print(f"  Batch Size: {settings.batch_scoring_size}")
    print(f"  Test Candidates: {len(TEST_CANDIDATES)}")
    
    # Test individual scoring
    individual_scores, individual_time = test_individual_scoring()
    
    # Test batch scoring
    batch_scores, batch_time = test_batch_scoring()
    
    # Compare results
    compare_results(individual_scores, individual_time, batch_scores, batch_time)
    
    print("\n✓ All tests completed!")


if __name__ == "__main__":
    main()
