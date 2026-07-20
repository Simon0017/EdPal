# Career Recommendation Engine — Technical Architecture Document

**Status:** Draft for review — no implementation until approved
**Scope:** Architecture only. No code, no Django models, no Celery tasks, no services.

---

## Part 1 — What Kind of Recommendation Engine Should This Be?

**Recommendation: A weighted-graph / rules-based scoring engine as the core, wrapped in an interface designed for hybrid extension later.**

Not collaborative filtering. Not embeddings. Not ML classification. Not yet.

### Why the existing schema already answers this question

Look at what the data actually *is*:

- `CareerTag.recommendation_weight` → Careers are already weighted tag vectors.
- `QuestionnaireTag.coupling_strength` / `is_primary` → Assessments are already weighted evidence generators for tags.
- `Subject` auto-creates a `Tag` → Subjects are already tag emitters.
- `AttemptScore` (weighted_score, raw_score, percentage) → Evidence is already numeric, not categorical.

This is not "data that could become a graph." It **is** a graph: Subjects, Assessments, and Psychometrics are all *sources of tag evidence*, and Careers are *tag-weighted destinations*. The recommendation problem reduces to: aggregate evidence into a user tag-vector, compare it against career tag-vectors, rank by similarity/fit.

That is a **weighted bipartite graph scoring problem** — structurally identical to content-based filtering using an engineered feature space (tags), not raw ML. Formally this sits closest to:

- **Content-based filtering** (user profile vector vs. item profile vector), implemented as
- **Weighted graph traversal / vector similarity** over a **rules-governed weighting scheme**.

### Why not the others, right now

| Approach | Why it's not right *yet* |
|---|---|
| Collaborative filtering | No meaningful user-user or user-career interaction history yet (no "users like you chose X" signal at sufficient density). Cold-start-prone by design since most users take the assessment once. |
| Embedding-based / GNN | Requires large volumes of co-occurrence data to learn a latent space that outperforms a hand-curated, already-weighted tag space. You'd be learning what domain experts already encoded in `recommendation_weight`. |
| ML classification | No reliable label. "Recommended career" ≠ "correct career." You don't yet have outcome data (did the user pursue it, succeed, stay satisfied). Training a classifier without labels means training on your own rule engine's output — circular. |
| Pure Bayesian/probabilistic model | Overkill for the current evidence structure, though Bayesian *ideas* (shrinkage, credible intervals) are extremely useful for confidence — see Part 4. |
| Learning-to-rank | Needs historical rank-vs-outcome pairs to learn from. You don't have that data yet, but the pipeline should be shaped so this becomes a drop-in replacement later (Part 7). |

### The deciding factor: explainability is a product requirement, not a nice-to-have

A career recommendation that can't explain *why* ("Strong in Analytical Reasoning, Mathematics subject performance, and Systems-Thinking tag cluster") is a support/trust liability in this domain. Rules-based/weighted-graph scoring gives you explanations for free, because the score *is* the explanation. Black-box ML gives you a score and then makes you build a second system just to explain the first one.

---

## Part 2 — Is ML Justified, and At What Scale Does That Change?

**Current answer: No.** Not because ML is inferior in principle, but because two preconditions are missing:

1. **Labeled outcomes.** You need ground truth — did the recommended career get chosen, pursued, and validated as a good fit (via follow-up surveys, enrollment data, later psychometric consistency, etc.)? Right now `CareerRecommendation` stores *what was recommended*, not *what happened next*. Without outcome labels, no supervised model — however sophisticated — is learning anything real.
2. **Volume + density of evidence.** ML needs enough independent examples per feature combination to generalize rather than memorize. A handful of thousands of `QuestionnaireAttempt` rows spread across dozens of tags is not enough to beat a well-curated weighted rule set — it's enough to overfit.

### Rough scale thresholds (evidence-volume-driven, not just user-count-driven)

| Users | What becomes viable | Why |
|---|---|---|
| **~1k – 10k** | Nothing beyond rules/weighted graph. Focus entirely on getting the weighting scheme and tag taxonomy right. | Any model trained here overfits to noise; manual weight tuning outperforms ML. |
| **~10k – 100k** | Start collecting **outcome labels** in earnest (this is a data-collection milestone, not a modeling one). Possibly introduce a simple **logistic regression or gradient-boosted re-ranker** as a *secondary signal* layered on top of the rule engine's score — not replacing it. | Enough volume to detect systematic mis-weighting in the rule engine, not enough for deep models. |
| **~100k – 1M** | **Learning-to-rank** (e.g., gradient-boosted trees like LightGBM/XGBoost ranking objectives) becomes genuinely worthwhile, using the tag-vector as engineered features plus behavioral signals (answer timing, retake patterns). | Sufficient labeled pairs per career to learn non-linear interactions the static weights miss. |
| **~1M – 10M** | **Embeddings** for careers/tags (learned co-occurrence space) start to outperform static weights, because the relationships between tags become too numerous to hand-tune. Possible **neural ranking models**. | Enough interaction density to learn a latent space that isn't just noise. |
| **10M+** | **Graph Neural Networks** across the Subject–Assessment–Psychometric–Career graph, potentially **LLM-based reasoning** for the explanation layer (not the scoring layer). | Only at this scale does the graph have enough structure and label density to justify GNN training/serving cost. |

**Key point:** these thresholds assume you're also capturing outcome labels starting now, even before you use them. Instrument for ML today; deploy ML later. The absence of ML now is a data-maturity issue, not a permanent architectural stance — which is exactly why Part 7 exists.

---

## Part 3 — Recommendation Pipeline Design

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. INPUT SOURCES                                                      │
│    UserProfile, ProfileSubject, QuestionnaireAttempt+QuestionResponse,│
│    CareerPsychometricResponse+Answers, CareerPreference,               │
│    Historical Attempts/Recommendations                                │
└───────────────────────────────┬─────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 2. NORMALIZATION                                                       │
│    - Grades normalized to a common 0–1 scale (per SubjectRequirement)  │
│    - AttemptScore percentages normalized across questionnaire versions │
│    - Psychometric responses normalized against choice weight scale     │
│    - Timestamp/version normalization (which Questionnaire version,     │
│      which CareerPsychometricTest version, produced this evidence)     │
└───────────────────────────────┬─────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 3. FEATURE EXTRACTION                                                  │
│    Per evidence source, extract (tag_id, raw_signal_strength) pairs:  │
│    - Subject → its auto-generated Tag, weighted by grade               │
│    - QuestionResponse → Tag(s) via QuestionnaireTag.coupling_strength, │
│      scaled by AttemptScore.weighted_score                             │
│    - Psychometric responses → Tag(s) mapped via test design            │
│      (even though "no correct answer," choices still map to trait tags)│
└───────────────────────────────┬─────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 4. TAG AGGREGATION                                                     │
│    Merge all (tag_id, signal) pairs into a single UserTagVector.      │
│    Multiple sources hitting the same tag are combined                  │
│    (e.g., weighted average, not simple sum, to avoid tag inflation     │
│    when many questions map to one popular tag).                       │
└───────────────────────────────┬─────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 5. WEIGHTING                                                           │
│    Apply source-level trust weights (e.g., psychometric evidence vs.  │
│    subject-grade evidence may not deserve equal trust), recency decay │
│    for historical attempts, and QuestionnaireTag.is_primary boosting. │
└───────────────────────────────┬─────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 6. CONFIDENCE COMPUTATION  (see Part 4 — distinct from the score)     │
└───────────────────────────────┬─────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 7. CAREER RANKING                                                      │
│    Score each Career by similarity between UserTagVector and          │
│    CareerTagVector (e.g., weighted cosine or dot-product similarity), │
│    filtered/boosted by hard constraints (SubjectRequirement cutoffs,  │
│    CutoffCluster eligibility).                                        │
└───────────────────────────────┬─────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 8. EXPLANATION GENERATION                                              │
│    For each ranked career, surface the top contributing tags and      │
│    their originating evidence source ("Strong Mathematics grade +     │
│    high Analytical Reasoning assessment score"). This is generated    │
│    directly from the same vectors used for scoring — no separate      │
│    black box needed.                                                  │
└───────────────────────────────┬─────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 9. RECOMMENDATION PERSISTENCE                                          │
│    Write CareerRecommendation rows: algorithm_version, confidence_    │
│    score, recommendation_details JSON (full breakdown), processing_   │
│    status. Immutable — never overwritten, only superseded.            │
└───────────────────────────────┬─────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 10. EMAIL GENERATION                                                   │
│     Triggered off persistence completion, templated from              │
│     recommendation_details, status tracked back onto the record.      │
└───────────────────────────────┬─────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 11. HISTORICAL ANALYTICS                                               │
│     Feed CareerRecommendation history + (future) outcome data into    │
│     a reporting/labeling layer — this is the data pipeline that       │
│     eventually feeds ML training (Part 2/7).                          │
└─────────────────────────────────────────────────────────────────────┘
```

Everything from step 4 onward operates on **vectors**, not raw rows. This is the seam that makes future ML insertion possible without touching steps 1–4 (see Part 7).

---

## Part 4 — Confidence, Not Just Score

Score answers *"how good a fit is this career?"* Confidence answers *"how much should we trust this particular score?"* These must be computed and stored separately (which `CareerRecommendation.confidence_score` already anticipates).

### Confidence should be a function of:

1. **Evidence coverage** — What fraction of possible evidence sources contributed? A user with subjects + full questionnaire + full psychometric test has denser evidence than one with subjects only. Missing sources should lower confidence, not silently zero-fill the vector.

2. **Evidence agreement (cross-source consistency)** — Do independent sources point the same direction? If subject grades suggest strong analytical tags and the psychometric test also independently surfaces analytical tags, agreement is high → confidence up. If sources conflict, confidence should drop even if the *blended* score looks fine — disagreement is information, not noise to be averaged away.

3. **Sample size per tag (shrinkage)** — A tag inferred from one question response is less trustworthy than one inferred from ten. Apply Bayesian-style shrinkage: pull low-evidence tag scores toward a neutral prior rather than trusting a single data point at face value.

4. **Recency** — Older `QuestionnaireAttempt`/psychometric data should count for less unless corroborated by newer attempts. A profile update or retake should measurably shift confidence, not just the score.

5. **Career-side evidence density** — Some careers may have sparse `CareerTag` mappings (few tags, low curation effort). A well-tagged career and a thinly-tagged career shouldn't get equally confident recommendations even at the same raw score.

6. **Score separation / margin** — If the top 3 ranked careers are nearly tied, confidence in "this is *the* recommendation" is lower than if there's a clear leader. This is a ranking-stability signal, not a scoring signal.

### Suggested composable formula shape (conceptual, not code):

```
confidence = f(coverage_factor, agreement_factor, shrinkage_factor,
                recency_factor, career_data_density_factor, margin_factor)
```

Each factor normalized to [0,1] and combined multiplicatively or via a weighted geometric mean, so any single very-low factor (e.g., near-zero evidence coverage) meaningfully suppresses overall confidence rather than being averaged away.

---

## Part 5 — Versioned Recommendation Engine Design

The goal: `algorithm_version` on `CareerRecommendation` should mean something concrete and immutable — historical recommendations must remain interpretable forever, even as the engine evolves underneath.

### Design pattern: Strategy pattern + Engine Registry

- Define a stable **contract** every engine version must satisfy: given a user's evidence, return `{ranked_careers, scores, confidence_scores, explanation_payload}`.
- Each concrete engine (`V1`, `V2`, `V3`, `V4`) implements that contract independently. Nothing about the pipeline orchestration (Celery task, persistence, email) needs to know which version is running — it only depends on the contract.
- A registry maps `algorithm_version` string → engine implementation, so:
  - New jobs use the currently "active" version.
  - Historical `CareerRecommendation` rows retain the version that produced them and are **never** silently reinterpreted by a newer engine.
  - Old engine versions stay callable indefinitely (even if deprecated from new-job use) for **shadow testing** and **auditability** ("what would V3 have said about this user, compared to what V2 actually said?").

### Version progression as a concrete example

- **V1 — Deterministic rules/weighted graph** (this document's Part 1–4 design). Fully explainable, no learned parameters.
- **V2 — Tuned weighted graph** — same architecture, refined weights/shrinkage/confidence formulas based on observed outcome data. Still fully deterministic; a *parameter update*, not an architecture change.
- **V3 — Hybrid** — weighted graph score blended with a learning-to-rank re-ranker trained on accumulated outcome labels (Part 2, ~100k–1M user scale). Explanation layer still derived from the underlying tag vectors.
- **V4 — Embedding-assisted** — tag/career embeddings supplement (not replace) the tag vector for long-tail similarity the static graph misses, still emitting the same output contract.

At every step, `recommendation_details` JSON should record which sub-components (rules, LTR model, embedding model, and their respective sub-versions) contributed, so that even within one `algorithm_version`, drift is auditable.

---

## Part 6 — Should Tags Remain the Central Representation?

**Yes — tags should remain the central, canonical representation, indefinitely.** Not because they're the most powerful possible representation, but because of what they uniquely provide: a **shared, human-interpretable coordinate system** across Subjects, Assessments, Psychometrics, and Careers.

### Why not replace them

- **Explainability requirement (Part 1)** collapses without a symbolic, human-legible layer. Embeddings are opaque by nature; tags are not.
- **Cross-domain bridging** — tags are the *only* thing that currently lets a Math grade, a psychometric trait, and a Career requirement be compared at all. Removing them removes the common vocabulary.
- **Human curation and correction** — domain experts can inspect and adjust `CareerTag.recommendation_weight` directly. You cannot "correct" an embedding dimension by hand.

### Where tags fall short, and how to compensate without replacing them

- Tags are **linear and manually weighted** — they don't capture non-linear interactions (e.g., "strong in Math *and* weak in Verbal Reasoning" behaving differently than either alone). This is exactly the gap a future learning-to-rank layer (Part 5, V3) fills — *on top of* the tag vector, not instead of it.
- Tag curation is a **bottleneck** at scale — many careers, many tags, manual weight-setting doesn't scale linearly with catalog growth. Mitigate with semi-automated weight suggestion (e.g., co-occurrence statistics feeding *suggested* weights that a human approves), not by discarding tags.

**Recommendation:** treat tags as the permanent **interpretable feature space**. Any future ML sits on top of that space (tags as engineered features, or a learned embedding that's regularized to stay aligned with tag semantics) rather than replacing it outright. This is the same pattern high-integrity recommendation systems in regulated/trust-sensitive domains (career guidance, lending, health) converge on: a symbolic layer for trust and explanation, an optional statistical layer for lift.

---

## Part 7 — Designing for Future ML Without Touching Business Logic

The core design principle: **every stage of the pipeline after "tag aggregation" (step 4 in Part 3) should be swappable behind a stable interface, without changing the orchestration, persistence, or email logic around it.**

### The seams to build now

1. **A stable `UserTagVector` / `CareerTagVector` abstraction.** Whatever produces these (today: rule-based aggregation) is decoupled from whatever *consumes* them (today: weighted similarity ranking). Tomorrow's ML models consume the exact same vectors.

2. **A stable engine output contract** (Part 5) — `{ranked_careers, scores, confidence, explanation_payload}`. Celery tasks, persistence, and email generation are written against this contract, never against a specific engine's internals. This is what lets V1 → V4 evolve without touching downstream code.

3. **A feature-store mindset even before you need one.** Materializing `UserTagVector` as a first-class, cached/persisted artifact (not recomputed ad hoc inside the scoring function) means:
   - Rule-based V1/V2 read it directly.
   - Future LTR/gradient-boosted models (V3) can treat it as a feature vector with zero extra extraction work.
   - Future embedding models (V4) can be trained on the same historical vectors.

4. **Shadow-mode evaluation as a first-class capability.** New engine versions should be runnable in parallel against real traffic, writing to `recommendation_details` under a distinct version tag, *without* being shown to users or triggering email. This is how you validate an ML model against the deterministic baseline before cutover — and it requires no business-logic changes if the contract from (2) is respected.

5. **Explanation as a separate, pluggable layer.** Keep explanation generation decoupled from scoring. This is exactly where **LLM reasoning** fits best long-term: not as the ranking mechanism (too unpredictable/uncontrollable for a scoring decision), but as a natural-language rendering layer that turns the structured `explanation_payload` (top contributing tags + sources) into readable prose. The ranking stays deterministic/statistical and auditable; the *prose* can be generative.

6. **Graph-native storage awareness.** Even without adopting a GNN today, keep the Subject→Tag→Career relationships modeled so that a future GNN could be trained directly off existing tables (`CareerTag`, `QuestionnaireTag`) without a schema migration — they're already edge-weight tables in disguise.

### What this buys you

Introducing Learning-to-Rank, Gradient Boosting, Embeddings, GNNs, or LLM explanation generation later becomes a matter of **adding a new engine version behind the existing contract**, plus (for supervised approaches) having accumulated the outcome-label data described in Part 2. No rewrite of Celery orchestration, persistence schema, or email logic is required.

---

## Part 8 — Schema Critique

### Strengths

- **Tags as a shared representation** across Subjects, Assessments, Psychometrics, and Careers is the single best architectural decision in the system — it's what makes a coherent scoring engine possible at all.
- **`CareerRecommendation` is already ML-ready in spirit** — `algorithm_version`, `confidence_score`, `processing_status`, and a flexible `recommendation_details` JSON field show the schema was designed anticipating multiple algorithms and async processing.
- **Async-first design** (processing_status, presumably Celery-driven) is correct for a workload where recommendation generation is not latency-sensitive but does need reliability and retryability.
- **Weighted evidence at every layer** (`recommendation_weight`, `coupling_strength`, `weighted_score`) means the raw material for both rules-based and future ML scoring already exists — nothing needs to be re-collected.

### Weaknesses

- **Weights are static and global**, not personalized or time-aware. `CareerTag.recommendation_weight` doesn't vary by cohort, region, or time, and there's no versioning on the weights themselves (if a curator updates a weight, does it silently change how *old* recommendations would be re-scored? It shouldn't — but the schema doesn't currently protect against that).
- **No outcome/feedback table.** This is the most consequential gap. Without a `RecommendationOutcome`/`RecommendationFeedback`-style table (did the user act on it, rate it, later report the fit was accurate), you cannot compute confidence-calibration metrics, cannot evaluate engine versions against each other objectively, and cannot ever train supervised ML (Part 2). This should be added well before it's "needed."
- **No explicit tag-relationship table.** Tags currently connect *through* Subjects/Assessments/Careers, but there's no direct `TagRelationship`/`TagCooccurrence` table capturing tag-to-tag semantic proximity (e.g., "Analytical Reasoning" and "Mathematics" tags co-occurring often). This would materially improve both explanation quality and any future embedding work, and it's cheap to start logging now even before it's used.
- **No materialized `UserTagVector` / `CareerTagVector` cache.** If every recommendation job recomputes the full aggregation from raw `QuestionResponse`/`ProfileSubject`/psychometric rows, this doesn't scale — it's O(all historical evidence) per job. This should be a cached, incrementally-updated artifact, invalidated on relevant events (Part 7 point 3).

### Scalability risks

- Full-recompute aggregation per event (assessment completion, subject update, profile update) will degrade badly as historical evidence per user grows — needs to become incremental (update the vector delta, not rebuild from scratch).
- `recommendation_details` as unstructured JSON is flexible now but risks becoming a dumping ground with inconsistent shape across engine versions — enforce a versioned JSON schema per `algorithm_version` (even informally documented) so historical analytics (Part 3, step 11) doesn't have to special-case every version's blob shape.
- Email generation coupled tightly to recommendation completion could become a bottleneck/single point of failure if recommendation volume spikes (e.g., mass cron regeneration after an algorithm update) — should be decoupled into its own queue rather than inline in the same job.

### Missing tables (recommended additions)

| Table | Purpose |
|---|---|
| `RecommendationOutcome` / `RecommendationFeedback` | Captures what happened after a recommendation — essential for confidence calibration and any future ML labels. |
| `TagRelationship` | Tag-to-tag proximity/co-occurrence, feeding better explanations and future embedding work. |
| `UserTagVectorSnapshot` | Materialized, versioned cache of a user's aggregated tag vector at a point in time — avoids full recompute, and doubles as a training-data source later. |
| `CareerTagVectorSnapshot` | Same idea, career-side — useful once weights start changing over time and you need to know what vector produced a historical recommendation. |
| `RecommendationEvent` / outbox log | Explicit event log for what triggered each recommendation job (assessment completion, subject update, cron regen) — improves auditability and idempotent retry handling in Celery, which the current schema implies but doesn't make explicit. |

### Missing indexes (recommended)

- Composite index on `CareerTag(career_id, tag_id)` — this pairing is queried constantly during aggregation and ranking.
- Index on `QuestionResponse(questionnaire_attempt_id)` — needed for fast per-attempt aggregation.
- Composite index on `CareerRecommendation(user_id, algorithm_version, created_at)` — needed to efficiently fetch "latest recommendation per user per engine version" without a full table scan, which will matter a lot once historical recommendations accumulate.
- Index on `ProfileSubject(profile_id, subject_id)` if not already unique-constrained — same reasoning.

### Denormalization / caching opportunities

- Cache `UserTagVectorSnapshot` and `CareerTagVectorSnapshot` in Redis (or as the proposed DB tables) keyed by user/career + version, invalidated on the relevant upstream event, rather than recomputing per recommendation job.
- Precompute and cache career-side rankings that don't depend on user-specific data (e.g., popularity-independent career metadata) separately from the per-user scoring pass.

### Event-driven improvements

- Make the triggering events (assessment completion, psychometric completion, subject update, profile update) explicit, persisted events (the proposed `RecommendationEvent` table) rather than implicit signal handlers directly enqueuing Celery tasks — this gives you replayability, auditability, and protection against duplicate/lost job triggers, which matters once cron-based mass regeneration is introduced alongside event-triggered single-user jobs.

---

## Summary

- **Now:** weighted-graph / content-based scoring over the existing Tag representation. Fully deterministic, fully explainable.
- **Soon:** start logging outcome data and materializing tag vectors — this is invisible to users but is the actual prerequisite for everything ML-related later.
- **Later (100k+ users with labels):** learning-to-rank layered on top of the same tag vectors, behind the same engine contract.
- **Much later (1M+):** embeddings/GNNs, with tags surviving as the interpretable backbone and explanation source, not as a legacy system to be torn out.

This document proposes architecture only. No models, services, or Celery tasks have been written. Awaiting approval before implementation begins.
