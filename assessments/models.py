from django.db import models
from django.utils.text import slugify
from django.contrib.auth.models import User

class QuestionnaireStatus(models.TextChoices):
    DRAFT     = "DRAFT",     "Draft"
    PUBLISHED = "PUBLISHED", "Published"
    ARCHIVED  = "ARCHIVED",  "Archived"


class Questionnaire(models.Model):
    """
    Versioned questionnaire. version_number + slug form natural identity.
    Soft-deleted instead of hard-deleted for audit trail.

    VERSIONING STRATEGY:
    Each edit creates a NEW Questionnaire row with incremented version_number.
    The previous version is archived (status=ARCHIVED), never mutated.
    This preserves historical response integrity — old responses always
    reference the exact questionnaire version the user actually took.
    """
    title          = models.CharField(max_length=255)
    slug           = models.SlugField(max_length=255)
    description    = models.TextField(blank=True)
    instructions   = models.TextField(blank=True)
    status         = models.CharField(
        max_length=20,
        choices=QuestionnaireStatus.choices,
        default=QuestionnaireStatus.DRAFT,
        db_index=True,
        blank=True,
    )
    version_number = models.PositiveIntegerField(default=1)
    max_score      = models.DecimalField(
        max_digits=8, decimal_places=2,
        help_text="Computed ceiling — updated when questions change"
    )
    time_limit_minutes = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="NULL = untimed. Enables future timed tests."
    )
    is_randomised  = models.BooleanField(default=False)
    tags           = models.ManyToManyField(
        "core.Tag",
        through="assessments.QuestionnaireTag",
        related_name="questionnaires"
    )

    created_by     = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="created_questionnaires",
        null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "assessments_questionnaire"
        # slug unique per version — allows same slug across versions
        constraints = [
            models.UniqueConstraint(
                fields=["slug", "version_number"],
                name="uq_questionnaire_slug_version"
            )
        ]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["slug", "version_number"]),
        ]

    def __str__(self):
        return f"{self.title}:{self.status}"


    def save(self,  *args, **kwargs):
        if self.pk:
            old_title = type(self).objects.get(pk=self.pk).title
            if old_title != self.title:
                self.slug = slugify(self.title)
        else:
            self.slug = slugify(self.title)

        super().save(*args, **kwargs)


class QuestionnaireTag(models.Model):
    """
    Through model for the M2M rel in the Questionnnare model
    """
    questionnaire    = models.ForeignKey(
        "assessments.Questionnaire", on_delete=models.CASCADE
    )
    tag              = models.ForeignKey(
        "core.Tag", on_delete=models.CASCADE
    )

    coupling_strength = models.DecimalField(
        max_digits=5, decimal_places=4,
        default=1.0,
        help_text="0.0-1.0: how strongly this Q measures this tag"
    )

    is_primary       = models.BooleanField(
        default=False,
        help_text="Primary tag drives the recommendation category"
    )

    class Meta:
        db_table = "assessments_questionnaire_tag"
        constraints = [
            models.UniqueConstraint(
                fields=["questionnaire", "tag"],
                name="uq_qtag_questionnaire_tag"
            ),
        ]
        indexes = [
            models.Index(fields=["tag", "coupling_strength"]),
        ]

    def __str__(self):
        return f"{self.tag.title}:{self.questionnaire.title}"

class QuestionType(models.TextChoices):
    MCQ          = "MCQ",       "Multiple Choice (single answer)"
    MULTI_SELECT = "MULTI",     "Multiple Select (many correct)"
    TEXT         = "TEXT",      "Free text"
    NUMERIC      = "NUMERIC",   "Numeric / Range"
    LIKERT       = "LIKERT",    "Likert Scale (psychometric)"
    RANKING      = "RANKING",   "Drag-to-rank"


class Question(models.Model):
    """
    Enterprise question model. question_text kept as TextField for
    Markdown/HTML support. Media via separate QuestionMedia FK.

    order field: deterministic ordering for non-randomised questionnaires.
    randomisation_group: questions within a group are shuffled together.
    """
    questionnaire     = models.ForeignKey(
        "assessments.Questionnaire",
        on_delete=models.CASCADE,
        related_name="questions",
        blank=True
    )

    question_type     = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        db_index=True
    )

    question_text     = models.TextField()

    explanation       = models.TextField(
        blank=True,
        help_text="Post-answer feedback shown to user"
    )

    weight            = models.DecimalField(
        max_digits=6, decimal_places=4, default=1.0,
        help_text="Multiplier for this question in total score"
    )

    max_points        = models.DecimalField(
        max_digits=6, decimal_places=2, default=1.0
    )

    order             = models.PositiveSmallIntegerField(default=0)

    randomisation_group = models.CharField(
        max_length=50, blank=True,
        help_text="Questions in same group are shuffled together"
    )

    is_required       = models.BooleanField(default=True)


    # Numeric question config (stored as JSON for extensibility)
    numeric_config    = models.JSONField(
        null=True, blank=True,
        help_text='{"min": 0, "max": 10, "step": 1, "unit": "years"}'
    )

    class Meta:
        db_table = "assessments_question"
        ordering = ["questionnaire", "order"]
        indexes = [
            models.Index(fields=["questionnaire", "order"]),
            models.Index(fields=["question_type"]),
        ]

    def __str__(self):
        return f"{self.question_text}"


class AnswerChoice(models.Model):
    """
    First-class choice row. One row per choice option.
    is_correct handles MCQ. partial_score handles partial-credit and Likert.
    choice_key is the stable identifier for response storage (e.g., "A", "B").
    """
    question      = models.ForeignKey(
        "assessments.Question",
        on_delete=models.CASCADE,
        related_name="answer_choices",
        blank=True
    )

    choice_key    = models.CharField(
        max_length=10,
        help_text="Stable key stored in responses, e.g. A/B/C/D or 1/2/3"
    )

    choice_text   = models.TextField()

    is_correct    = models.BooleanField(default=False)

    partial_score = models.DecimalField(
        max_digits=6, decimal_places=4, default=0,
        help_text="For Likert/partial credit. 0=wrong, 1=full credit",
        blank=True,
        null=True
    )

    order         = models.PositiveSmallIntegerField(default=0)

    explanation   = models.TextField(blank=True)

    class Meta:
        db_table = "assessments_answer_choice"
        constraints = [
            models.UniqueConstraint(
                fields=["question", "choice_key"],
                name="uq_choice_question_key"
            )
        ]
        ordering = ["question", "order"]

    def __str__(self):
        return f"{self.choice_text}"


class AttemptStatus(models.TextChoices):
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    COMPLETED   = "COMPLETED",   "Completed"
    ABANDONED   = "ABANDONED",   "Abandoned"
    TIMED_OUT   = "TIMED_OUT",   "Timed Out"


class QuestionnaireAttempt(models.Model):
    """
    One row per attempt. Supports unlimited retakes.
    attempt_number is auto-computed on create via service layer.

    started_at / completed_at supports accurate time-on-task analytics.
    ip_address + user_agent: optional fraud/audit signal.

    scoring  lives in scoring.AttemptScore.
    Separation of concerns: attempt tracks the event,
    score tracks the computation result.

    """
    profile        = models.ForeignKey(
        "accounts.UserProfile",
        on_delete=models.CASCADE,
        related_name="attempts"
    )
    questionnaire  = models.ForeignKey(
        "assessments.Questionnaire",
        on_delete=models.PROTECT, 
        related_name="attempts"
    )
    
    status         = models.CharField(
        max_length=20,
        choices=AttemptStatus.choices,
        default=AttemptStatus.IN_PROGRESS,
        db_index=True
    )

    attempt_number = models.PositiveIntegerField(
        help_text="1-based attempt index for this profile+questionnaire",
        null=True,blank=True
    )

    started_at     = models.DateTimeField(null=True,blank=True)
    completed_at   = models.DateTimeField(null=True, blank=True)
    ip_address     = models.GenericIPAddressField(null=True, blank=True)
    user_agent     = models.TextField(blank=True,null=True)

    class Meta:
        db_table = "responses_attempt"
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "questionnaire", "attempt_number"],
                name="uq_attempt_profile_questionnaire_number"
            )
        ]
        indexes = [
            models.Index(fields=["profile", "questionnaire", "status"]),
            models.Index(fields=["status", "started_at"]),
            models.Index(fields=["completed_at"]),
        ]

    def __str__(self):
        return f"{self.questionnaire.title}, Attempt {self.attempt_number or 0}"

class QuestionResponse(models.Model):
    """
    Immutable answer record. Once written, never mutated.
    Revisions are handled by creating a new row (for late change detection).

    answer_value stores the raw response:
      MCQ:         "A"
      MULTI:       ["A", "C"]
      TEXT:        "The mitochondria is..."
      NUMERIC:     7.5
      LIKERT:      3
      RANKING:     ["B","A","C","D"]

    Using JSONField for answer_value gives us type flexibility without
    maintaining 6 separate answer tables (EAV anti-pattern avoided).
    The trade-off: we lose DB-level type constraints on the value itself.
    This is acceptable because scoring logic validates before computing.

    """
    attempt        = models.ForeignKey(
        "assessments.QuestionnaireAttempt",
        on_delete=models.CASCADE,
        related_name="question_responses",
        null=True, blank=True
    )
    question       = models.ForeignKey(
        "assessments.Question",
        on_delete=models.PROTECT,
        related_name="responses"
    )

    answer_value   = models.JSONField()

    points_awarded = models.DecimalField(
        max_digits=8, decimal_places=4,
        null=True, blank=True,
        help_text="Populated by scoring engine after attempt completion"
    )

    is_correct     = models.BooleanField(null=True)

    responded_at   = models.DateTimeField(auto_now_add=True)

    time_taken_ms  = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Milliseconds to answer — psychometric signal"
    )

    class Meta:
        db_table = "responses_question_response"
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "question"],
                name="uq_qresponse_attempt_question"
            )
        ]
        indexes = [
            models.Index(fields=["attempt"]),
            models.Index(fields=["question", "is_correct"]),
        ]

    def __str__(self):
        return f"{self.question.question_text}: {self.is_correct}"

class AttemptScore(models.Model):
    """
    Computed aggregate score for an attempt. One row per attempt.
    Immutable once computed — revisions create new rows with is_current=False
    on old rows and is_current=True on new row.

    percentile_rank: computed asynchronously (requires population data).
    scoring_engine_version: allows tracking which engine version computed this.
    """
    attempt         = models.OneToOneField(
        "assessments.QuestionnaireAttempt",
        on_delete=models.CASCADE,
        related_name="score"
    )

    raw_score        = models.DecimalField(max_digits=10, decimal_places=4)
    weighted_score   = models.DecimalField(max_digits=10, decimal_places=4)
    percentage       = models.DecimalField(max_digits=5, decimal_places=2)

    percentile_rank  = models.DecimalField(
        max_digits=6, decimal_places=4,
        null=True, blank=True,
        help_text="Async-computed. NULL until population data available."
    )

    scoring_engine_version = models.CharField(max_length=20, default="1.0.0",blank=True)
    computed_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "scoring_attempt_score"
        indexes = [
            models.Index(fields=["percentage"]),
            models.Index(fields=["percentile_rank"]),
        ]

    def __str__(self):
        return f"{self.attempt}: {self.percentage}%"