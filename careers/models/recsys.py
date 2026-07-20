# Recommendation engine infrastructure & metrics

from __future__ import annotations
from django.db import models
from django.utils.text import slugify
from django.core.exceptions import ValidationError


# ─────────────────────────────────────────────────────────────────────────
# 1. UserTagVector — materialized, current tag affinity per user.
#    This is the artifact Part 3 / Part 7 of the architecture doc calls
#    the "UserTagVector" — computed by the aggregation stage, read by the
#    scoring stage, and reused as-is by any future ML engine version.
# ─────────────────────────────────────────────────────────────────────────
class UserTagVector(models.Model):
    """
    One row per (profile, tag): the CURRENT aggregated affinity for that
    tag across all evidence sources (subjects, assessments, psychometrics).
 
    This table is written by the tag-aggregation stage of the pipeline and
    read by every downstream stage (ranking, explanation). It is NOT an
    event log — it's a live cache, recomputed incrementally as new
    evidence arrives. last_updated + source_event (optional future field)
    lets you reason about staleness.
 
    evidence_count and confidence are separate from affinity_score
    deliberately — see Part 4 of the architecture doc: score and
    confidence must never be conflated into one number.
    """
    profile = models.ForeignKey(
        "accounts.UserProfile", on_delete=models.CASCADE,
        related_name="tag_vector_entries"
    )
    tag = models.ForeignKey(
        "core.Tag", on_delete=models.CASCADE,
        related_name="user_vector_entries"
    )
 
    affinity_score = models.DecimalField(
        max_digits=6, decimal_places=4, default=0,
        help_text="0.0-1.0 aggregated affinity for this tag"
    )
    confidence = models.DecimalField(
        max_digits=5, decimal_places=4, default=0,
        help_text="0.0-1.0 confidence in affinity_score (see Part 4 methodology)"
    )
    evidence_count = models.PositiveIntegerField(
        default=0,
        help_text="How many distinct evidence sources contributed to this score"
    )
 
    algorithm_version = models.CharField(
        max_length=20, blank=True,
        help_text="Which engine version last computed this row"
    )
 
    last_updated = models.DateTimeField(auto_now=True)
 
    class Meta:
        db_table = "recsys_user_tag_vector"
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "tag"], name="uq_usertagvector_profile_tag"
            )
        ]
        indexes = [
            models.Index(fields=["profile", "-affinity_score"]),
            models.Index(fields=["tag", "-affinity_score"]),
            models.Index(fields=["profile", "last_updated"]),
        ]
 
    def __str__(self):
        return f"{self.profile}: {self.tag.title} = {self.affinity_score}"
 
 
# ─────────────────────────────────────────────────────────────────────────
# 2. UserInteraction — implicit feedback. Raw event log, append-only.
# ─────────────────────────────────────────────────────────────────────────
class InteractionType(models.TextChoices):
    VIEW    = "VIEW",    "View"
    CLICK   = "CLICK",   "Click"
    SAVE    = "SAVE",    "Save"
    SHARE   = "SHARE",   "Share"
    DISMISS = "DISMISS", "Dismiss"
    APPLY   = "APPLY",   "Apply / Follow Through"
 
 
class UserInteraction(models.Model):
    """
    Append-only implicit feedback log. Never updated after creation.
 
    This is the raw material for future learning-to-rank training data
    (Part 2/7 of the architecture doc) — do not aggregate into this table,
    aggregate FROM it into UserTagVector / analytics tables instead.
    """
    profile = models.ForeignKey(
        "accounts.UserProfile", on_delete=models.CASCADE,
        related_name="career_interactions"
    )
    career = models.ForeignKey(
        "careers.Career", on_delete=models.CASCADE,
        related_name="user_interactions"
    )
    recommendation = models.ForeignKey(
        "careers.CareerRecommendation", on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="interactions",
        help_text="If this interaction happened in the context of a specific recommendation"
    )
 
    interaction_type = models.CharField(
        max_length=10, choices=InteractionType.choices, db_index=True
    )
 
    session_id = models.CharField(max_length=64, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
 
    occurred_at = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "recsys_user_interaction"
        indexes = [
            models.Index(fields=["profile", "career", "interaction_type"]),
            models.Index(fields=["career", "interaction_type", "occurred_at"]),
            models.Index(fields=["session_id"]),
        ]
 
    def __str__(self):
        return f"{self.profile}: {self.interaction_type} on {self.career}"
 
 
# ─────────────────────────────────────────────────────────────────────────
# 3. RecommendationFeedback — explicit feedback (subsumes "outcome" data)
# ─────────────────────────────────────────────────────────────────────────
class FeedbackType(models.TextChoices):
    INTERESTED       = "INTERESTED",       "Interested"
    NOT_INTERESTED   = "NOT_INTERESTED",   "Not Interested"
    ALREADY_PURSUING = "ALREADY_PURSUING", "Already Pursuing"
    NOT_RELEVANT     = "NOT_RELEVANT",     "Not Relevant To Me"
    INACCURATE       = "INACCURATE",       "Inaccurate Match"
 
 
class RecommendationFeedback(models.Model):
    """
    Explicit, user-provided signal on a career/recommendation. This is the
    single most important table for future ML: it's the closest thing to
    a ground-truth label this system can collect (see Part 2 of the
    architecture doc — ML is not justified until this table has volume).
    """
    profile = models.ForeignKey(
        "accounts.UserProfile", on_delete=models.CASCADE,
        related_name="recommendation_feedback"
    )
    career = models.ForeignKey(
        "careers.Career", on_delete=models.CASCADE,
        related_name="feedback_entries"
    )
    recommendation = models.ForeignKey(
        "careers.CareerRecommendation", on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="feedback"
    )
 
    feedback_type = models.CharField(
        max_length=20, choices=FeedbackType.choices, db_index=True
    )
    feedback_score = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True,
        help_text="Optional explicit rating, e.g. -1.0 to 1.0 or 1-5"
    )
    context = models.JSONField(
        null=True, blank=True,
        help_text="Free-form context, e.g. which UI surface this was collected from"
    )
 
    submitted_at = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "recsys_recommendation_feedback"
        indexes = [
            models.Index(fields=["profile", "career"]),
            models.Index(fields=["career", "feedback_type"]),
            models.Index(fields=["recommendation"]),
        ]
 
    def __str__(self):
        return f"{self.profile}: {self.feedback_type} on {self.career}"
 
 
# ─────────────────────────────────────────────────────────────────────────
# 4. FeatureRegistry — metadata registry, not feature values.
#    Lets a future ML engine version introspect what features exist
#    without a schema change (Part 7 of the architecture doc).
# ─────────────────────────────────────────────────────────────────────────
class FeatureType(models.TextChoices):
    NUMERIC     = "NUMERIC",     "Numeric"
    CATEGORICAL = "CATEGORICAL", "Categorical"
    BOOLEAN     = "BOOLEAN",     "Boolean"
    VECTOR      = "VECTOR",      "Vector"
    TEXT        = "TEXT",        "Text"
 
 
class FeatureRegistry(models.Model):
    """
    Documents what features EXIST and how to compute them — does not store
    feature values (those live in UserTagVector / are computed on demand).
 
    This is deliberately a thin metadata table. Its job is to let a future
    engine version (V3 learning-to-rank, V4 embeddings) discover available
    features programmatically via compute_function, rather than the
    feature set being hardcoded into engine code.
    """
    feature_name = models.CharField(max_length=100, unique=True)
    feature_type = models.CharField(max_length=20, choices=FeatureType.choices)
 
    source_table = models.CharField(
        max_length=100,
        help_text="Primary table this feature is derived from, e.g. 'UserTagVector'"
    )
    compute_function = models.CharField(
        max_length=255,
        help_text="Dotted path, e.g. 'careers.services.features.subject_affinity'"
    )
 
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    version = models.CharField(max_length=20, default="1.0.0")
 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        db_table = "recsys_feature_registry"
        indexes = [
            models.Index(fields=["feature_type", "is_active"]),
        ]
 
    def __str__(self):
        return f"{self.feature_name} ({self.feature_type})"
 
 
# ─────────────────────────────────────────────────────────────────────────
# 5. RecommendationExplanation — structured explanation, split out of
#    CareerRecommendation.recommendation_details for queryability.
# ─────────────────────────────────────────────────────────────────────────
class ExplanationType(models.TextChoices):
    TAG_CONTRIBUTION    = "TAG_CONTRIBUTION",    "Tag Contribution Breakdown"
    SUBJECT_MATCH       = "SUBJECT_MATCH",       "Subject Match"
    PSYCHOMETRIC_MATCH  = "PSYCHOMETRIC_MATCH",  "Psychometric Match"
    PEER_COMPARISON     = "PEER_COMPARISON",     "Peer Comparison"
    NARRATIVE           = "NARRATIVE",           "Natural-Language Narrative"
 
 
class RecommendationExplanation(models.Model):
    """
    Structured, queryable explanation records for a CareerRecommendation.
 
    Kept separate from CareerRecommendation.recommendation_details (which
    remains as the full raw dump) so that:
      - explanation_type can be filtered/queried without JSON path lookups
      - a future LLM-based narrative layer (Part 7) can be added as a new
        explanation_type without touching scoring code or the parent row
      - explanation_version lets you regenerate narrative text without
        recomputing the underlying recommendation
    """
    recommendation = models.ForeignKey(
        "careers.CareerRecommendation", on_delete=models.CASCADE,
        related_name="explanations"
    )
 
    explanation_type = models.CharField(max_length=20, choices=ExplanationType.choices)
    explanation_data = models.JSONField()
    explanation_version = models.CharField(max_length=20, default="1.0.0")
 
    created_at = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "recsys_recommendation_explanation"
        indexes = [
            models.Index(fields=["recommendation", "explanation_type"]),
        ]
 
    def __str__(self):
        return f"{self.recommendation}: {self.explanation_type}"
 
 
# ─────────────────────────────────────────────────────────────────────────
# 6. EngineVersion — registry backing the versioned engine design (Part 5)
# ─────────────────────────────────────────────────────────────────────────
class EngineType(models.TextChoices):
    RULE_BASED         = "RULE_BASED",         "Rule-Based / Weighted Graph"
    HYBRID             = "HYBRID",             "Hybrid"
    LEARNING_TO_RANK   = "LEARNING_TO_RANK",   "Learning To Rank"
    EMBEDDING          = "EMBEDDING",          "Embedding-Based"
    GRAPH_NEURAL_NET   = "GRAPH_NEURAL_NET",   "Graph Neural Network"
 
 
class EngineVersion(models.Model):
    """
    Registry of recommendation engine versions. `version_number` is the
    exact string persisted onto CareerRecommendation.algorithm_version —
    this table is metadata ABOUT that string, not a replacement for it.
 
    is_active: exactly one row is active at a time (enforced in save());
    this is the version new recommendation jobs use.
 
    is_shadow: any number of rows may be shadow-enabled simultaneously —
    shadow engines run in parallel on real traffic, writing results, but
    are never surfaced to users or used to trigger emails (Part 7,
    shadow-mode evaluation).
    """
    version_number = models.CharField(max_length=20, unique=True)
    engine_type = models.CharField(max_length=20, choices=EngineType.choices)
 
    parameters = models.JSONField(
        null=True, blank=True,
        help_text="Snapshot of weights/config this version was released with"
    )
 
    is_active = models.BooleanField(
        default=False,
        help_text="Exactly one engine version is active for new jobs at a time"
    )
    is_shadow = models.BooleanField(
        default=False,
        help_text="Runs in parallel for evaluation; never user-facing"
    )
 
    description = models.TextField(blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    deprecated_at = models.DateTimeField(null=True, blank=True)
 
    created_at = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "recsys_engine_version"
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["engine_type", "is_active"]),
        ]
 
    def clean(self):
        if self.is_active and self.is_shadow:
            raise ValidationError("An engine version cannot be both active and shadow.")
 
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_active:
            # Global single-active-version invariant. Uses .update() to
            # avoid recursive save()/signal calls.
            EngineVersion.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
 
    def __str__(self):
        flag = "ACTIVE" if self.is_active else ("SHADOW" if self.is_shadow else "inactive")
        return f"{self.version_number} ({self.engine_type}) [{flag}]"