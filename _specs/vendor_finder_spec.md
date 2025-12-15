# Vendor Finder Workflow Spec

## The Problem

User needs to find a service provider (e.g., endodontist, contractor, accountant). This requires:
1. Understanding what they're looking for
2. Finding candidates
3. Researching each candidate
4. Analyzing and comparing options
5. Making a decision

**Current state:** The workflow searches, builds a list, fetches websites, finds reviews, but:
- The final output is unclear - just a list with scattered data
- No clear analysis or recommendation
- Information is fragmented, not synthesized
- No comparison view to help decide
- Reviews are superficial (search snippets, not actual reviews)
- No clear "here's what I found, here's what I recommend"

---

## User Story

> "I need an endodontist in Cambridge. Find me good options, tell me what people say about them, and help me decide who to call."

The workflow should act like a smart assistant who:
1. Understands the search (location, specialty, any constraints)
2. Finds real candidates (not aggregator sites)
3. Researches each one properly (not just scraping snippets)
4. Synthesizes findings into a useful report
5. Gives a clear recommendation with reasoning

---

## Proposed Workflow Stages

### Stage 1: Understand Requirements
**Goal:** Clarify exactly what we're looking for

**Input:**
- Query: "endodontist"
- Location: "Cambridge, MA"
- Requirements: "weekend hours, takes Delta Dental"

**Output:**
- Structured criteria with search strategy
- Clear confirmation of what we're searching for

**Checkpoint:** User confirms criteria before we start searching

---

### Stage 2: Find Candidates
**Goal:** Build a list of real, specific vendors (not directories)

**Method:**
1. Multiple targeted searches
2. Filter out aggregators, directories, irrelevant results
3. Dedupe by actual business

**Output:**
- 5-15 real vendor candidates
- For each: name, website, brief description, location

**Checkpoint:** User reviews list, can remove any they don't want researched

---

### Stage 3: Deep Research (per vendor)
**Goal:** Get real information about each vendor

**For each vendor, gather:**
1. **From their website:**
   - Services offered
   - Location/hours
   - Insurance accepted
   - Staff/credentials
   - Any specialties

2. **From Yelp (if applicable):**
   - Star rating
   - Review count
   - Key positive themes
   - Key negative themes
   - 2-3 representative quotes

3. **From Google Reviews:**
   - Star rating
   - Review count
   - Key themes

4. **From Reddit/forums (if found):**
   - Community sentiment
   - Any red flags or strong endorsements

**Output per vendor:**
```
Dr. Smith Endodontics
━━━━━━━━━━━━━━━━━━━━
📍 123 Main St, Cambridge
🕐 Mon-Fri 8-5, Sat 9-1
💰 Accepts: Delta Dental, Aetna, BCBS

⭐ 4.7/5 (127 reviews on Yelp)
⭐ 4.5/5 (89 reviews on Google)

✅ Strengths:
   • "Painless procedure" (mentioned 15x)
   • "Great with anxious patients"
   • Modern equipment

⚠️ Concerns:
   • "Long wait times" (mentioned 8x)
   • "Parking is difficult"

💬 Sample Reviews:
   "Had a root canal here and barely felt anything..."
```

---

### Stage 4: Analysis & Recommendation
**Goal:** Synthesize findings and help user decide

**Output:**

```
## Summary

I researched 8 endodontists in Cambridge, MA.

### Top Recommendation: Dr. Smith Endodontics
Why: Highest ratings, accepts your insurance, has Saturday hours.
Only caveat: Parking is limited - plan to arrive early.

### Strong Alternative: Cambridge Dental Specialists
Why: Slightly lower ratings but never mentioned wait times.
Good if: You prioritize efficiency over ambiance.

### Avoid: QuickRoot Dental
Why: Multiple recent reviews mention billing issues.

## Quick Comparison

| Name           | Rating | Accepts Delta | Sat Hours | Wait Time |
|----------------|--------|---------------|-----------|-----------|
| Dr. Smith      | 4.7    | ✓             | ✓         | Long      |
| Cambridge DS   | 4.3    | ✓             | ✗         | Short     |
| EndoExperts    | 4.5    | ✗             | ✓         | Medium    |
```

**Checkpoint:** User reviews final report

---

## What Gets Saved as Asset

### Option A: Full Research Report (Document)
A complete markdown document with:
- Search criteria
- All vendor profiles
- Analysis and recommendations
- Comparison table

### Option B: Vendor Comparison Table (Table)
Interactive table with:
- All vendors as rows
- Key attributes as columns
- Sortable/filterable in table view

### Option C: Both
- Report saved as document asset
- Table saved as data asset

**Recommendation:** Save both. User can reference the detailed report or quickly scan the table.

---

## Key Improvements Needed

### 1. Better Review Collection
**Current:** Searches for "Company yelp reviews" and parses snippets
**Better:**
- Use Yelp API if available
- Actually visit Yelp/Google pages and extract review data
- Get real review counts and ratings, not guesses from snippets

### 2. Real Analysis
**Current:** Lists vendors with their data, no synthesis
**Better:**
- Dedicated analysis step that:
  - Identifies patterns across vendors
  - Makes specific recommendations
  - Explains trade-offs
  - Highlights red flags

### 3. Better UI
**Current:** Card view showing raw data
**Better:**
- Clear visual hierarchy (recommendation at top)
- Comparison table
- Expandable detail sections
- Color-coded ratings/sentiment

### 4. Smarter Filtering
**Current:** All vendors go through all steps
**Better:**
- Let user exclude vendors at checkpoint
- Don't waste time researching vendors user isn't interested in

### 5. Clear Deliverable
**Current:** "Here's some vendors with data"
**Better:** "Here's my recommendation and why, here's the full research"

---

## Revised Graph Structure

```
[understand_requirements]
        ↓
[requirements_checkpoint] ← user confirms
        ↓
[find_candidates]
        ↓
[candidates_checkpoint] ← user can exclude vendors
        ↓
[deep_research] ← researches remaining vendors in parallel
        ↓
[analyze_and_recommend] ← NEW: LLM synthesizes findings
        ↓
[final_checkpoint] ← user reviews report, can save
```

---

## Adaptive Behavior: Handling Different Result Sizes

The number of vendors we find varies wildly by search. The workflow should adapt:

### Bucket A: Very Few Results (0-3 vendors)

**Situation:** Niche service, small market, or overly restrictive search.

**Behavior:**
1. Research ALL found vendors thoroughly
2. Investigate WHY results are sparse:
   - Is the search too narrow? (suggest broadening)
   - Is this a niche market? (explain to user)
   - Are we missing vendors? (try alternative search terms)
3. Consider expanding search:
   - Widen geographic radius
   - Try related service types
   - Search without location constraint to show what exists elsewhere
4. Report transparently: "Only found 2 endodontists in Cambridge. Here's why..."

**Checkpoint message:** "I only found 2 candidates. Should I expand the search radius or continue with these?"

### Bucket B: Moderate Results (4-12 vendors)

**Situation:** Healthy market with a manageable number of options.

**Behavior:**
1. Research ALL vendors - this is the ideal scenario
2. Full deep-dive on each
3. Provide complete comparison

**Checkpoint message:** "Found 8 candidates. Ready to research all of them."

### Bucket C: Many Results (13-25 vendors)

**Situation:** Competitive market, lots of options.

**Behavior:**
1. At checkpoint, present the full list with basic info
2. Let user SELECT which ones to research (checkboxes)
3. Suggest a strategy: "I can research all 18, or you can select your top picks"
4. If user says "just do it", use heuristics to prioritize:
   - Vendors with existing reviews visible in search
   - Vendors whose websites look established
   - Geographic proximity to user's specified location

**Checkpoint message:** "Found 18 candidates. Select which ones to research deeply, or I can prioritize based on initial signals."

### Bucket D: Too Many Results (25+ vendors)

**Situation:** Very broad search, or common service type.

**Behavior:**
1. Acknowledge the volume
2. Suggest narrowing criteria:
   - More specific location?
   - Specific specialty within the field?
   - Specific requirement that would filter?
3. Or offer to take top N by some heuristic (proximity, review visibility)

**Checkpoint message:** "Found 40+ candidates - that's too many to research thoroughly. Can you narrow it down? Or I can focus on the top 15 closest to [location]."

---

## Handling Sparse Data

### Vendors with no reviews
- Still include them in the list
- Note: "No reviews found on Yelp/Google"
- Research their website more thoroughly to compensate
- Flag this in the analysis: "Limited review data - recommend calling to ask for references"

### Vendors with minimal web presence
- Include with caveat
- May indicate: new business, word-of-mouth only, or low quality
- Note in analysis: "Minimal online presence - could be new or established through referrals"

### Conflicting information
- Present both sides
- Note the conflict explicitly
- Let user decide what matters

---

## Implementation Priority

1. **Add analysis step** - This is the biggest gap. Even with current data, we should synthesize it.

2. **Fix review collection** - Actually visit review sites instead of parsing search snippets.

3. **Implement adaptive bucket logic** - Different behavior for different result sizes.

4. **Improve checkpoint UX** - Let user select/deselect vendors, show bucket-appropriate options.

5. **Better final output** - Clear recommendation, comparison table, proper formatting.

6. **Asset saving** - Save both report and table.

---

## Deferred (Not Now)

- **Pricing info** - Often unavailable, skip for now
- **Parallel research** - Keep sequential for simpler progress display

---

## Future: Review Collection Strategy (v2)

Reviews deserve their own adaptive logic, similar to vendor counts. This is complex and deferred, but noting the considerations here:

### The Problem with Reviews

1. **Groomed reviews** - Many businesses actively manage their reviews (incentivized positive reviews, fake reviews, burying negative ones)
2. **Recency bias** - Recent reviews may not reflect long-term quality
3. **Volume varies wildly** - Local endodontist might have 20 reviews; chain restaurant has 2,000
4. **Platform differences** - Yelp crowd differs from Google crowd differs from Reddit

### Review Bucket Logic (Future)

| Bucket | Count | Strategy |
|--------|-------|----------|
| **None** | 0 | Note "no reviews found", flag as unknown quantity |
| **Few** | 1-10 | Read ALL of them, every one matters |
| **Moderate** | 11-50 | Sample strategy: best, worst, and recent |
| **Many** | 50+ | Statistical approach: distribution, trends, outlier analysis |

### What to Look For (Future)

**Don't just average the stars.** A smart review analysis should:

1. **Look at distribution**
   - All 5-stars? Suspicious.
   - Bimodal (lots of 5s and 1s)? Polarizing - dig into why.
   - Normal distribution around 4? Probably legitimate.

2. **Sample strategically**
   - Sort by BEST: What do happy customers love?
   - Sort by WORST: What makes people angry? (Often more informative)
   - Sort by RECENT: Has quality changed?
   - Sort by OLDEST: What was the original reputation?

3. **Detect manipulation signals**
   - Many reviews posted in short time window
   - Generic/vague language ("Great service!")
   - Reviewer has only reviewed this one business
   - Sudden spike in positive reviews (reputation repair campaign?)

4. **Weight appropriately**
   - Detailed reviews > short reviews
   - Verified purchase/visit > anonymous
   - Consistent themes across platforms > single-platform praise

5. **Look for patterns**
   - Same complaint repeated = real issue
   - One-off complaint = maybe a bad day
   - "Used to be great, now terrible" = ownership/staff change?

### For Now (v1)

Current implementation just searches for reviews and summarizes snippets. That's a start, but we know it's superficial. The analysis step should caveat: "Review data is limited to search snippets - recommend checking Yelp/Google directly for full picture."
