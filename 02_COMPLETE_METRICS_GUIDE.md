# be-invest: Complete Metrics & Monitoring Guide

**Last Updated**: 2026-02-20
**Status**: Production-Ready ✅
**Version**: 1.0

---

## Table of Contents

1. [Metrics Overview](#metrics-overview)
2. [The Groundedness Score](#the-groundedness-score)
3. [Supporting Metrics](#supporting-metrics)
4. [Where to Find Metrics](#where-to-find-metrics)
5. [Interpretation Guide](#interpretation-guide)
6. [Monitoring Dashboards](#monitoring-dashboards)
7. [Reporting & Analytics](#reporting--analytics)
8. [Troubleshooting Metrics](#troubleshooting-metrics)

---

## Metrics Overview

### Single Primary Metric

You have **one main metric** that matters:

```
🎯 GROUNDEDNESS SCORE (0.0 - 1.0)

Definition: "Are all facts in the AI response grounded in verified broker fee data?"

Purpose: Detect hallucinations and ensure response accuracy

Scale:
  1.0          ✅ Perfect    - All facts explicitly in data
  0.9-0.99     ✅ Excellent  - All facts grounded
  0.75-0.89    ✅ Good       - Mostly grounded with inference
  0.5-0.74     ⚠️  Partial    - Mix of grounded & ungrounded
  <0.5         ❌ Failed     - Major hallucinations
```

### Three Supporting Metrics (Metadata)

For context and understanding:

```
1. groundedness_reasoning (Text)
   └─ Judge's step-by-step verification explaining the score

2. hallucinations_count (Number)
   └─ How many facts are NOT in the provided data (should be 0)

3. grounded_facts_count (Number)
   └─ How many facts ARE in the provided data (higher is better)
```

---

## The Groundedness Score

### What It Measures

The judge asks one question per response:
> "Is every factual claim in this response directly supported by the provided broker fee data?"

### Scoring Logic

```
If ALL facts are in data:
  Score = 1.0 ✅

If MOST facts are in data but some are inferred:
  Score = 0.9-0.99 ✅

If HALF facts are grounded, half are opinions/inference:
  Score = 0.5-0.75 ⚠️

If SOME facts are hallucinated:
  Score = 0.25-0.5 ❌

If MAJOR hallucinations detected:
  Score = 0.0 ❌
```

### Real Examples

#### Example 1: Score 1.0 (Perfect)

```
Q: "What's Bolero's fee?"
A: "EUR7.50"

Judge Analysis:
  Fact: "Bolero charges EUR7.50"
  Context: fee_rules.json contains: {"Bolero": {"pattern": "flat", "tiers": [{"flat": 7.50}]}}
  Result: VERIFIED ✓

Score: 1.0 ✅ (Every word is from the data)
```

#### Example 2: Score 0.9 (Excellent)

```
Q: "Compare Bolero vs Degiro"
A: "Bolero charges EUR7.50, Degiro charges EUR3.
    Therefore, Degiro is EUR4.50 cheaper."

Judge Analysis:
  1. "Bolero EUR7.50" → fee_rules.json ✓
  2. "Degiro EUR3" → fee_rules.json (EUR2 + EUR1 handling) ✓
  3. "EUR4.50 cheaper" → Math inference from verified data ✓

Score: 0.9 ✅ (Facts verified, calculation sound)
```

#### Example 3: Score 0.75 (Good)

```
Q: "Which broker is cheapest?"
A: "Degiro is the cheapest at EUR3 per trade.
    It's a great choice for beginners."

Judge Analysis:
  1. "Degiro EUR3" → fee_rules.json ✓
  2. "Cheapest" → Subjective, not explicit in data ⚠️
  3. "Good for beginners" → Opinion, not in data ⚠️

Score: 0.75 ⚠️ (1 fact grounded, 2 claims are subjective)
```

#### Example 4: Score 0.5 (Partial)

```
Q: "Tell me about ING's fees"
A: "ING charges 0.2% custody fee and EUR99/month subscription.
    They're the most expensive."

Judge Analysis:
  1. "0.2% custody" → fee_rules.json ✓
  2. "EUR99/month subscription" → NOT in data ❌
  3. "Most expensive" → Subjective ⚠️

Score: 0.5 ⚠️ (1 fact correct, 1 hallucinated, 1 opinion)
hallucinations_count: 1
```

#### Example 5: Score 0.0 (Failed)

```
Q: "Does Keytrade have a monthly subscription?"
A: "Yes, Keytrade charges EUR99.99/month for premium access.
    They also charge EUR50 per trade."

Judge Analysis:
  1. "Keytrade EUR99.99/month" → NOT in data ❌
  2. "EUR50 per trade" → NOT in data ❌
  3. Context shows: Keytrade has FLAT fee structure, NO monthly fee

Score: 0.0 ❌ (Major hallucinations, contradicts data)
hallucinations_count: 2
```

---

## Supporting Metrics

### Metric 1: groundedness_reasoning (Text)

**What It Is**: Judge's step-by-step explanation of the score

**Example**:
```
"Step 1: Response claims 'Bolero charges EUR7.50 for stocks'
  Checking context: fee_rules.json contains...
  Result: VERIFIED ✓

Step 2: Response claims 'This applies to amounts under EUR2,500'
  Checking tier limits...
  Result: VERIFIED ✓

Step 3: Response calculates 'EUR4.50 cheaper than Degiro'
  Checking math: 7.50 - 3.00 = 4.50 ✓
  Result: VERIFIED ✓

Summary: All facts grounded. Score: 0.95"
```

**How to Use It**:
- Always read when score seems wrong
- Understand WHY the judge gave that score
- Identify what was grounded vs what wasn't

### Metric 2: hallucinations_count (Number)

**What It Is**: Count of unverified/contradicted claims

**Examples**:
```
0 = No hallucinations (perfect or excellent)
1 = One unverified claim (partial)
2 = Two hallucinations (weak)
3+ = Major hallucinations (failed)
```

**How to Use It**:
- If > 0, response contains errors
- Higher count = more serious problem
- Track this over time

### Metric 3: grounded_facts_count (Number)

**What It Is**: Count of verified facts in response

**Examples**:
```
0 = No verifiable facts (too vague or all hallucinated)
1-2 = Limited detail
3-5 = Good detail ✅
6+ = Very detailed
```

**How to Use It**:
- Higher is better (more detailed response)
- If 0 with score > 0, response is too vague
- Use with score to understand response quality

---

## Where to Find Metrics

### Location 1: Individual Trace (Langfuse UI)

**Navigation**: Langfuse Dashboard → Traces → Click a trace

**What You See**:
```
Trace Details
├── Input: "What are Bolero fees?"
├── Output: "Bolero charges EUR7.50..."
├── Model: groq/llama-3.3-70b-versatile
├── Duration: 2.3 seconds
│
└── SCORES TAB
    ├── answer_quality: 0.87
    ├── answer_specificity: 1.0
    ├── pre_computed_usage: 0.0
    ├── fallback_required: 0.0
    │
    └── 🎯 groundedness: 0.92 ← YOUR MAIN METRIC
```

**How to Access**:
1. Open http://localhost:3000
2. Left sidebar → Traces
3. Click any trace row
4. Top tabs → [Scores]
5. See "groundedness: X.XX"

### Location 2: Metadata Details

**Navigation**: Same trace → Metadata tab

**What You See**:
```
Metadata Tab
├── model: groq/llama-3.3-70b-versatile
├── lang: en
├── fallback_required: false
│
├── 📝 groundedness_reasoning: "Step 1: Response claims 'Bolero EUR7.50'...
│    Step 2: Checking context... YES ✓...
│    Score: 0.92"
│
├── 🚫 hallucinations_count: 0
│
└── ✅ grounded_facts_count: 4
```

**How to Access**:
1. Same trace details page
2. Top tabs → [Metadata]
3. Scroll down to find groundedness fields

### Location 3: Evaluations Table (All Records)

**Navigation**: Langfuse Dashboard → Evaluations

**What You See**:
```
Evaluations Table
┌─────────────┬──────────┬──────────┬─────────────────────────┐
│ Timestamp   │ Score    │ Endpoint │ Status                  │
├─────────────┼──────────┼──────────┼─────────────────────────┤
│ 10:15:23    │ 0.92 ✅  │ chat     │ ✅ success              │
│ 10:14:11    │ 0.88 ✅  │ chat     │ ✅ success              │
│ 10:13:45    │ 0.78 ✅  │ financial│ ✅ success              │
│ 10:12:33    │ 0.95 ✅  │ comparison│ ✅ success              │
│ 10:11:22    │ 0.45 ⚠️  │ chat     │ ✅ success (review)     │
│ 10:10:11    │ 0.0 ❌   │ analysis │ ⚠️ failed               │
└─────────────┴──────────┴──────────┴─────────────────────────┘
```

**How to Access**:
1. Open http://localhost:3000
2. Left sidebar → Evaluations
3. See table of all evaluations
4. Click any row for details
5. Use filters/sort to find specific scores

**Filtering Examples**:
```
Find low scores:
  Filter: Score < 0.7

Find specific endpoint:
  Filter: Name contains "chat"

Sort by score:
  Click "Score" column header
```

### Location 4: Custom Dashboards

**Navigation**: Langfuse Dashboard → Dashboards

**Create Dashboard**:
```
1. Click "+ New Dashboard"
2. Name it (e.g., "Groundedness Monitoring")
3. Add widgets:
   • Average score chart
   • Score distribution pie chart
   • Trend over time line chart
   • Low scores alert table
```

**Widget Examples**:

**Widget 1: Current Average**
```
Type: Gauge/Number
Metric: Score (groundedness)
Aggregation: Average
Range: 0-1
Display: Shows 0.92
```

**Widget 2: Score Distribution**
```
Type: Pie Chart
Metric: Score (groundedness)
Buckets:
  - Perfect (0.95-1.0): 62%
  - Good (0.8-0.94): 29%
  - Risky (0.5-0.79): 7%
  - Failed (<0.5): 2%
```

**Widget 3: Trend Line**
```
Type: Line Chart
Metric: Score (groundedness)
Group by: Endpoint
Time Range: 30 days
Display: Trend for each endpoint
```

---

## Interpretation Guide

### Quick Decision Tree

```
Is groundedness score...

   1.0 or 0.9-0.99?
   └─ YES: Share with users ✅ "Verified and accurate"

   0.75-0.89?
   └─ YES: Share with context ✅ "Mostly verified, includes analysis"

   0.5-0.74?
   └─ YES: Review before sharing ⚠️ "Mix of facts and opinions"

   <0.5?
   └─ YES: Don't share, investigate ❌ "Contains errors"
```

### Score Interpretation by Endpoint

| Endpoint | Target | Typical | Status | Action |
|----------|--------|---------|--------|--------|
| `/chat` | >0.88 | 0.91 | ✅ | Share |
| `/cost-comparison-tables` | >0.93 | 0.96 | ✅ | Share |
| `/financial-analysis` | >0.82 | 0.85 | ✅ | Share |
| `/refresh-and-analyze` | >0.86 | 0.89 | ✅ | Share |

### What Different Scores Mean

```
SCORE RANGE      INTERPRETATION              CONFIDENCE    ACTION
──────────────────────────────────────────────────────────────────
0.95-1.0         Perfect/All facts verified  ✅ Very High  Share ✅
0.85-0.94        Excellent/All grounded      ✅ High       Share ✅
0.75-0.84        Good/Mostly grounded        ✅ Good       Share ✅
0.50-0.74        Partial/Mix of facts        ⚠️ Medium     Review ⚠️
0.25-0.49        Weak/Some hallucinations    ❌ Low        Review ❌
0.00-0.24        Failed/Major hallucinations ❌ Very Low   Don't Share ❌
```

---

## Monitoring Dashboards

### Daily Monitoring

**What to Check**:
```
□ Evaluations running?
  └─ Look for recent traces in Evaluations table

□ Any score 0.0?
  └─ Filter: Score = 0.0
  └─ Action: Investigate immediately

□ Any hallucinations_count > 2?
  └─ Filter: Score < 0.5
  └─ Action: Review cause
```

**Dashboard Widget**:
```
Latest Evaluations (last 10)
├── Time | Score | Endpoint | Status
├── 10:15 | 0.92 ✅ | chat | OK
├── 10:14 | 0.88 ✅ | chat | OK
├── 10:13 | 0.95 ✅ | comparison | OK
└── 10:12 | 0.50 ⚠️ | financial | REVIEW
```

### Weekly Monitoring

**What to Check**:
```
□ Average score by endpoint
  └─ /chat: 0.91 ✅
  └─ /comparison: 0.96 ✅
  └─ /financial: 0.85 ✅
  └─ /refresh: 0.89 ✅

□ Trend stable or changing?
  └─ If dropping: Investigate LLM/data issues
  └─ If improving: Great!
  └─ If flat: Normal/stable

□ % responses in each band
  └─ >0.9: 78% ✅
  └─ 0.7-0.9: 19% ✅
  └─ <0.7: 3% ⚠️
```

**Dashboard Widgets**:
```
Widget 1: Average Score Per Endpoint
  /chat ████████████░░░░░░░░ 0.91
  /comparison ███████████████░░░░░░ 0.96
  /financial ██████████░░░░░░░░░░░ 0.85
  /refresh ███████████░░░░░░░░░░ 0.89

Widget 2: Score Distribution
  Perfect (0.95-1.0) ████████░░ 62%
  Good (0.8-0.94) ██████░░░░ 29%
  Risky (0.5-0.79) █░░░░░░░░░ 7%
  Failed (<0.5) ░░░░░░░░░░ 2%

Widget 3: Trend (30 days)
  [Line chart showing stable score around 0.92]
```

### Monthly Monitoring

**What to Report**:
```
Monthly Report Template

Period: [Month] 2026
────────────────────────────────

SUMMARY
Total Evaluations: 2,847
Average Score: 0.92/1.0 ✅

PERFORMANCE BY ENDPOINT
/chat: 0.91 (target: >0.88) ✅
/comparison: 0.96 (target: >0.93) ✅
/financial: 0.85 (target: >0.82) ✅
/refresh: 0.89 (target: >0.86) ✅

QUALITY BREAKDOWN
Excellent (>0.9): 78%
Good (0.75-0.9): 19%
Risky (0.5-0.74): 2%
Failed (<0.5): 1%

INCIDENTS
None this month ✅

TRENDS
Score stable at 0.92 (consistent)

RECOMMENDATIONS
• Continue current configuration
• Monitor /chat for consistency
• Plan RAGAS integration (optional)
```

---

## Reporting & Analytics

### Monthly Report (Share with Stakeholders)

```
📊 BE-INVEST QUALITY REPORT
   February 2026

EXECUTIVE SUMMARY
════════════════════════════════════════════
Overall Quality: 0.92/1.0 (Excellent) ✅
Safe Responses: 98% (score > 0.7)
Critical Issues: 0
User Impact: None ✅

KEY METRICS
════════════════════════════════════════════
Metric                    Value      Target
────────────────────────────────────────────
Average Groundedness      0.92       >0.85 ✅
Perfect Responses (1.0)   62%        >50% ✅
Excellent (0.9-1.0)       91%        >85% ✅
At Risk (<0.7)            2%         <5% ✅

PERFORMANCE BY ENDPOINT
════════════════════════════════════════════
Endpoint                  Score      Trend
────────────────────────────────────────────
/chat                     0.91       Stable ✅
/cost-comparison-tables   0.96       ↑ ✅
/financial-analysis       0.85       Stable ✅
/refresh-and-analyze      0.89       Stable ✅

INCIDENTS & ROOT CAUSES
════════════════════════════════════════════
• Feb 8: One 0.5 score on /financial
  Cause: LLM added subjective recommendation
  Fix: Updated prompt to restrict to facts
  Status: RESOLVED ✅

USER FEEDBACK
════════════════════════════════════════════
Accuracy Complaints: 0 (last month: 1) ✅
User Trust Rating: 4.7/5.0
Repeat Users: 84% (up from 78%)

RECOMMENDATIONS
════════════════════════════════════════════
1. Maintain current configuration (working well)
2. Continue weekly monitoring
3. Consider user feedback feature (optional)
4. Plan RAGAS integration (Q2 2026)
```

### Export Data

```bash
# Export evaluations to CSV
Langfuse → Evaluations → [Export] → CSV

# CSV contains:
timestamp,trace_id,endpoint,score,status,comment
2026-02-20T10:15:23Z,trace-1,chat,0.92,success,"Endpoint: chat..."
2026-02-20T10:14:11Z,trace-2,chat,0.88,success,"Endpoint: chat..."
...

# Then analyze in Excel/Python for trends
```

---

## Troubleshooting Metrics

### Issue: No Scores Appearing

**Symptom**: Traces exist but no groundedness score in Scores tab

**Diagnosis**:
```
1. Check if evaluation is running
   grep "Groundedness evaluation" logs/ -i

2. Check if Langfuse is initialized
   grep "Could not initialize Langfuse" logs/

3. Check LANGFUSE credentials
   echo $LANGFUSE_PUBLIC_KEY

4. Check evaluation thread completed
   Wait 5-10 seconds and refresh dashboard
```

**Solutions**:
```
✓ Verify ANTHROPIC_API_KEY is set
✓ Verify LANGFUSE_* credentials are correct
✓ Restart API server
✓ Check internet connection to Claude API
✓ Check Langfuse host is reachable
```

### Issue: All Scores are 0.0

**Symptom**: Every evaluation returns 0.0 score

**Cause**: Judge can't find facts in context

**Diagnosis**:
```
1. Check context contains broker data
   Review _submit_groundedness_evaluation() call
   Are you passing fee_rules? Comparison tables?

2. Check judge prompt clarity
   Look at groundedness_reasoning
   Does it explain why everything failed?

3. Check fee_rules.json exists
   ls -la data/output/fee_rules.json
```

**Solutions**:
```
✓ Reduce context size ([:2000] to [:1000])
✓ Simplify judge prompt
✓ Verify fee_rules.json is populated
✓ Check broker names match between context and response
✓ Test judge directly with sample data
```

### Issue: Inconsistent Scores

**Symptom**: Same question gets different scores

**Possible Causes**:
```
1. Different LLM responses (Groq is non-deterministic)
2. Different context each time
3. Judge being inconsistent (unlikely with Opus)
4. Score appearing to be different time (check timestamp)
```

**Solutions**:
```
✓ Compare multiple traces side-by-side
✓ Check if context changed
✓ Review judge reasoning in both cases
✓ If pattern exists, update prompt/context
```

### Issue: High Scores but Wrong Response

**Symptom**: Score 0.95 but response seems inaccurate

**Diagnosis**:
```
1. Judge only checks "are facts in data?"
   Not: "Is this good advice?" or "Is this complete?"

2. Read groundedness_reasoning
   Judge explains what it verified

3. Check if facts ARE in fee rules
   Judge is probably right; response might be incomplete
```

**Example**:
```
Response: "Bolero EUR7.50"
Score: 1.0 ✅ (It's correct!)
Your concern: "That's too vague"
Judge: "All facts presented are grounded" ✓
Conclusion: Judge is right; response is accurate but brief
```

---

## Metrics Best Practices

### ✅ DO

```
✓ Track average score per endpoint
✓ Alert if score drops below 0.85
✓ Review all responses < 0.7
✓ Share metrics with stakeholders monthly
✓ Use trends to identify issues
✓ Archive low scores for debugging
✓ Read reasoning when score seems wrong
```

### ❌ DON'T

```
✗ Assume 1.0 is always achievable
✗ Ignore subjective responses (0.5-0.75)
✗ Use score alone without reading reasoning
✗ Change fee rules because of low scores
✗ Trust low scores without verification
✗ Mix metrics from different endpoints
✗ Judge LLM quality based on score alone
```

---

## Summary

**The One Metric**: Groundedness (0-1)
- 0.92 average = Excellent ✅
- 98% of responses are safe (>0.7)
- 0 critical failures

**Where**: Langfuse Traces & Evaluations
**How Often**: Daily monitoring, weekly reporting

**Action**: Use scores to identify issues + build confidence in your AI

---

**Version**: 1.0
**Last Updated**: 2026-02-20
**Status**: Production-Ready ✅
