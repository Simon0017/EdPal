from __future__ import annotations
from django.db import models
from django.utils.text import slugify
from django.conf import settings
from django.utils import timezone

class Institution(models.Model):
    code    = models.CharField(max_length=20, unique=True)
    name    = models.CharField(max_length=255, db_index=True)
    slug    = models.SlugField(max_length=255, unique=True)
    type    = models.CharField(
        max_length=30,
        choices=[("PUBLIC_UNIVERSITY","Public University"),
                 ("PRIVATE_UNIVERSITY","Private University"),
                 ("TECHNICAL","Technical Institute")],
        db_index=True
    )
    website = models.URLField(blank=True,null=True)
    country = models.CharField(max_length=100, default="Kenya", db_index=True)

    class Meta:
        db_table = "careers_institution"

    def save(self,  *args, **kwargs):
        if self.pk:
            old_name = type(self).objects.get(pk=self.pk).name
            if old_name != self.name:
                self.slug = slugify(self.name)
        else:
            self.slug = slugify(self.name)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Institution: {self.name.title()}, Type: {self.type}"


class Career(models.Model):
    """
    Occupation/career path. Distinct from Course.
    A career (Medicine) can be reached via multiple courses.
    Tags connect careers to assessment dimensions.
    """
    code        = models.CharField(max_length=20, unique=True)
    title       = models.CharField(max_length=255, db_index=True)
    slug        = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    sector      = models.CharField(max_length=100, db_index=True)
    tags        = models.ManyToManyField(
        "core.Tag",
        through="careers.CareerTag",
        related_name="careers"
    )

    class Meta:
        db_table = "careers_career"
    
    def save(self,  *args, **kwargs):
        if self.pk:
            old_title = type(self).objects.get(pk=self.pk).title
            if old_title != self.title:
                self.slug = slugify(self.title)
        else:
            self.slug = slugify(self.title)

        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Career: {self.title.title()} : {self.code}"


class CareerTag(models.Model):
    """Through model — carries recommendation_weight."""
    career               = models.ForeignKey("careers.Career", on_delete=models.CASCADE)
    tag                  = models.ForeignKey("core.Tag", on_delete=models.CASCADE)
    recommendation_weight = models.DecimalField(
        max_digits=5, decimal_places=4, default=1.0,
        help_text="How strongly this tag predicts success in this career"
    )

    class Meta:
        db_table = "careers_career_tag"
        constraints = [
            models.UniqueConstraint(fields=["career","tag"], name="uq_careertag")
        ]


class Course(models.Model):
    """
    Degree/diploma programme.
    Linked to a career, offered by an institution.
    """
    code    = models.CharField(max_length=20, unique=True)
    title          = models.CharField(max_length=255, db_index=True)
    slug           = models.SlugField(max_length=255)
    description    = models.TextField(blank=True)
    qualification  = models.CharField(
        max_length=30,
        choices=[("DEGREE","Degree"),("DIPLOMA","Diploma"),("CERTIFICATE","Certificate")]
    )
    career         = models.ForeignKey(
        "careers.Career", on_delete=models.SET_NULL,
        null=True, related_name="courses"
    )
    institution    = models.ForeignKey(
        "careers.Institution", on_delete=models.CASCADE,
        related_name="courses"
    )
    duration_years = models.PositiveSmallIntegerField(default=4)

    class Meta:
        db_table = "careers_course"

    def save(self,  *args, **kwargs):
        if self.pk:
            old_title = type(self).objects.get(pk=self.pk).title
            if old_title != self.title:
                self.slug = slugify(self.title)
        else:
            self.slug = slugify(self.title)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Course: {self.title.title()} : {self.code}"

class CutoffCluster(models.Model):
    """
    cutoff points vary by cluster (subject combination) and year.
    Separate rows per year allows trend analysis.
    """
    course         = models.ForeignKey(
        "careers.Course", on_delete=models.CASCADE,
        related_name="cutoff_clusters"
    )
    institution = models.ForeignKey(
        "careers.Institution",on_delete=models.CASCADE,
        related_name="cutoff_clusters",null=True
    )
    cluster_number = models.PositiveSmallIntegerField()
    cutoff_points  = models.DecimalField(max_digits=5, decimal_places=3)
    year           = models.PositiveSmallIntegerField(db_index=True)

    class Meta:
        db_table = "careers_cutoff_cluster"
        constraints = [
            models.UniqueConstraint(
                fields=["course", "cluster_number", "year","institution"],
                name="uq_cutoff_course_cluster_year_institution"
            )
        ]

    def __str__(self):
        return f"Course: {self.course.title}, Points: {self.cutoff_points}"

class SubjectRequirement(models.Model):
    """
    Per-course subject requirement with minimum grade.
    Normalised — no ArrayField, no JSON blob.
    """
    course         = models.ForeignKey(
        "careers.Course", on_delete=models.CASCADE,
        related_name="subject_requirements"
    )
    subject        = models.ForeignKey(
        "accounts.Subject", on_delete=models.PROTECT
    )
    requirement_type = models.CharField(
        max_length=20,
        choices=[("COMPULSORY","Compulsory"),("ALTERNATIVE","Alternative"),("OPTIONAL","Optional")]
    )
    minimum_grade  = models.CharField(max_length=5, blank=True)  # C+, B, etc.

    class Meta:
        db_table = "careers_subject_requirement"
        constraints = [
            models.UniqueConstraint(
                fields=["course","subject"],
                name="uq_subjreq_course_subject"
            )
        ]

    def __str__(self):
        return f"Course: {self.course.title}, Subject: {self.subject.code}, Min Grade {self.minimum_grade}"

 
class TestCategory(models.TextChoices):
    BASIC        = "basic",        "Basic"
    INTERMEDIATE = "intermediate", "Intermediate"
    ADVANCED     = "advanced",     "Advanced"
 
 
class QuestionType(models.TextChoices):
    SINGLE_CHOICE   = "SINGLE_CHOICE",   "Single Choice"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE", "Multiple Choice"
    MULTI_SELECT    = "MULTI_SELECT",    "Multiple Selection"
    NUMERIC         = "NUMERIC",         "Numeric"
    SHORT_TEXT      = "SHORT_TEXT",      "Short Text"
    LONG_TEXT       = "LONG_TEXT",       "Long Text"
 
 
class ResponseStatus(models.TextChoices):
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    COMPLETED   = "COMPLETED",   "Completed"
    ABANDONED   = "ABANDONED",   "Abandoned"
 
 
class ProcessingStatus(models.TextChoices):
    PENDING    = "PENDING",    "Pending"
    PROCESSING = "PROCESSING", "Processing"
    COMPLETED  = "COMPLETED",  "Completed"
    FAILED     = "FAILED",     "Failed"
 
 
 
class CareerPsychometricTest(models.Model):
    """
    Represents a single psychometric assessment.
 
    Assessments have no right or wrong answers. They are designed to surface
    personality traits, aptitudes, and interests that map to career recommendations.
 
    Premium tests (is_premium=True) will be gated behind a subscription
    when payment integration is added. The UI already accommodates this.
    """
 
    name: str = models.CharField(max_length=255, verbose_name="Test name")
    slug: str = models.SlugField(
        max_length=255, unique=True, verbose_name="URL slug",
        help_text="Auto-generated from name. Used in URLs.",
    )
    description: str = models.TextField(
        verbose_name="Short description",
        help_text="Shown on the test selection card. Keep concise (2-3 sentences).",
    )
    instructions: str = models.TextField(
        blank=True,
        verbose_name="Instructions",
        help_text="Displayed to the user before they begin. Can include guidance on approach.",
    )
    category: str = models.CharField(
        max_length=20,
        choices=TestCategory.choices,
        default=TestCategory.BASIC,
        verbose_name="Difficulty category",
    )
    estimated_duration: int = models.PositiveSmallIntegerField(
        verbose_name="Estimated duration (minutes)",
        help_text="Shown on the card. Should reflect median completion time.",
    )
    total_questions: int = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Total questions",
        help_text="Denormalised count. Updated automatically via signal or save().",
    )
    is_active: bool = models.BooleanField(
        default=True,
        verbose_name="Active",
        help_text="Only active tests are shown to users.",
    )
    is_premium: bool = models.BooleanField(
        default=False,
        verbose_name="Premium only",
        help_text="If True, requires a paid subscription to attempt. UI placeholder is in place.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        verbose_name        = "Career Psychometric Test"
        verbose_name_plural = "Career Psychometric Tests"
        ordering            = ["category", "name"]
        indexes             = [
            models.Index(fields=["is_active", "category"]),
            models.Index(fields=["slug"]),
        ]
 
    def __str__(self) -> str:
        return self.name
 
    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
 
    def update_question_count(self) -> None:
        """Refresh the denormalised total_questions field."""
        self.total_questions = self.questions.filter(is_active=True).count()
        self.save(update_fields=["total_questions"])
 
 
class CareerPsychometricQuestion(models.Model):
    """
    A single question within a CareerPsychometricTest.
 
    Supports all required question types via question_type.
    For NUMERIC questions, use metadata to store min/max/step/unit as a JSONField.
    For text questions, use metadata for max_length and placeholder.
 
    There are deliberately no scoring fields — these are psychometric questions.
    """
 
    questionnaire = models.ForeignKey(
        CareerPsychometricTest,
        on_delete=models.CASCADE,
        related_name="questions",
        verbose_name="Test",
    )
    order: int = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Display order",
        help_text="Questions are presented in ascending order.",
    )
    prompt: str = models.TextField(verbose_name="Question text")
    help_text: str = models.TextField(
        blank=True,
        verbose_name="Help text",
        help_text="Optional clarification shown below the question prompt.",
    )
    question_type: str = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        default=QuestionType.SINGLE_CHOICE,
        verbose_name="Question type",
    )
    required: bool = models.BooleanField(
        default=True,
        verbose_name="Required",
        help_text="If True, the user cannot advance without answering.",
    )
    is_active: bool = models.BooleanField(default=True, verbose_name="Active")
    metadata: dict = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Metadata",
        help_text=(
            "Type-specific configuration. Examples:\n"
            "  NUMERIC:    {\"min\": 0, \"max\": 10, \"step\": 1, \"unit\": \"years\"}\n"
            "  SHORT_TEXT: {\"max_length\": 255, \"placeholder\": \"Your answer…\"}\n"
            "  LONG_TEXT:  {\"max_length\": 2000}"
        ),
    )
 
    class Meta:
        verbose_name        = "Career Psychometric Question"
        verbose_name_plural = "Career Psychometric Questions"
        ordering            = ["questionnaire", "order"]
        indexes             = [
            models.Index(fields=["questionnaire", "order"]),
            models.Index(fields=["questionnaire", "is_active"]),
        ]
 
    def __str__(self) -> str:
        return f"[{self.questionnaire.name}] Q{self.order}: {self.prompt[:60]}"
 
 

 
class CareerPsychometricChoice(models.Model):
    """
    An individual selectable option for SINGLE_CHOICE, MULTIPLE_CHOICE,
    or MULTI_SELECT question types.
 
    value is stored in responses (not label) so labels can be updated without
    invalidating historical response data.
    """
 
    question = models.ForeignKey(
        CareerPsychometricQuestion,
        on_delete=models.CASCADE,
        related_name="choices",
        verbose_name="Question",
    )
    label: str = models.CharField(
        max_length=512,
        verbose_name="Display label",
        help_text="What the user sees.",
    )
    value: str = models.CharField(
        max_length=100,
        verbose_name="Stored value",
        help_text="What is saved in the response. Should be stable (e.g. a slug or key).",
    )
    order: int = models.PositiveSmallIntegerField(default=0, verbose_name="Display order")
 
    class Meta:
        verbose_name        = "Career Psychometric Choice"
        verbose_name_plural = "Career Psychometric Choices"
        ordering            = ["question", "order"]
        indexes             = [models.Index(fields=["question", "order"])]
 
    def __str__(self) -> str:
        return f"{self.question_id} → {self.label}"
 
 
 
class CareerPsychometricResponse(models.Model):
    """
    Records one attempt by a user at a CareerPsychometricTest.
 
    A user may have multiple responses for the same test (retakes).
    Each response is linked to individual CareerPsychometricResponseAnswer records.
 
    The status field allows the frontend to resume IN_PROGRESS attempts.
    """
 
    user = models.ForeignKey(
        "accounts.UserProfile",
        on_delete=models.CASCADE,
        related_name="psychometric_responses",
        verbose_name="User",
    )
    questionnaire = models.ForeignKey(
        CareerPsychometricTest,
        on_delete=models.CASCADE,
        related_name="responses",
        verbose_name="Test",
    )
    started_at  = models.DateTimeField(auto_now_add=True, verbose_name="Started at")
    completed_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Completed at"
    )
    status: str = models.CharField(
        max_length=20,
        choices=ResponseStatus.choices,
        default=ResponseStatus.IN_PROGRESS,
        verbose_name="Status",
    )
 
    class Meta:
        verbose_name        = "Career Psychometric Response"
        verbose_name_plural = "Career Psychometric Responses"
        ordering            = ["-started_at"]
        indexes             = [
            models.Index(fields=["user", "questionnaire", "status"]),
            models.Index(fields=["user", "status"]),
        ]
 
    def __str__(self) -> str:
        return f"{self.user} — {self.questionnaire.name} ({self.status})"
 
    def complete(self) -> None:
        """Mark this response as completed and record the timestamp."""
        self.status       = ResponseStatus.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at"])
 
 
class CareerPsychometricResponseAnswer(models.Model):
    """
    Stores the answer to a single question within a CareerPsychometricResponse.
 
    Accommodates all question types:
      - SINGLE_CHOICE / MULTIPLE_CHOICE: use selected_choices (M2M)
      - MULTI_SELECT:                    use selected_choices (M2M, multiple entries)
      - NUMERIC:                         use numeric_answer
      - SHORT_TEXT / LONG_TEXT:          use text_answer
 
    Only one of (selected_choices, text_answer, numeric_answer) should be
    populated per record — enforced at the application layer.
    """
 
    response = models.ForeignKey(
        CareerPsychometricResponse,
        on_delete=models.CASCADE,
        related_name="answers",
        verbose_name="Response",
    )
    question = models.ForeignKey(
        CareerPsychometricQuestion,
        on_delete=models.CASCADE,
        related_name="response_answers",
        verbose_name="Question",
    )
    selected_choices = models.ManyToManyField(
        CareerPsychometricChoice,
        blank=True,
        related_name="response_answers",
        verbose_name="Selected choices",
        help_text="Used for SINGLE_CHOICE, MULTIPLE_CHOICE, and MULTI_SELECT.",
    )
    text_answer: str = models.TextField(
        blank=True,
        default="",
        verbose_name="Text answer",
        help_text="Used for SHORT_TEXT and LONG_TEXT questions.",
    )
    numeric_answer = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Numeric answer",
        help_text="Used for NUMERIC questions.",
    )
    answered_at = models.DateTimeField(auto_now=True, verbose_name="Last updated at")
 
    class Meta:
        verbose_name        = "Career Psychometric Response Answer"
        verbose_name_plural = "Career Psychometric Response Answers"
        ordering            = ["response", "question__order"]
        # Enforce one answer per question per response
        unique_together     = [("response", "question")]
        indexes             = [
            models.Index(fields=["response"]),
            models.Index(fields=["question"]),
        ]
 
    def __str__(self) -> str:
        return f"Answer: {self.response_id} — Q{self.question.order}"
 
 

class CareerRecommendation(models.Model):
    """
    Stores a generated career recommendation for a user, tied to a specific
    psychometric response.
 
    Design for extensibility:
      - processing_status supports async generation (e.g. Celery task).
      - recommendation_details (JSONField) holds the full structured output
        so the schema can evolve without migrations.
      - Records are never overwritten — regeneration creates a new row,
        allowing full recommendation history and A/B comparison of algorithms.
      - confidence_score supports multiple algorithms with varying confidence.
      - algorithm_version tracks which recommendation engine produced the result.
    """
 
    user = models.ForeignKey(
        "accounts.UserProfile",
        on_delete=models.CASCADE,
        related_name="career_recommendations",
        verbose_name="User",
    )
    
    response = models.ForeignKey(
        CareerPsychometricResponse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recommendations",
        verbose_name="Source response",
        help_text="The psychometric response that triggered this recommendation. "
                  "Nullable so recommendations can be regenerated independently.",
    )
    generated_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Generated at",
    )
    processing_status: str = models.CharField(
        max_length=20,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING,
        verbose_name="Processing status",
        help_text="Tracks async recommendation generation pipeline state.",
    )
    recommendation_summary: str = models.TextField(
        blank=True,
        verbose_name="Summary",
        help_text="Human-readable summary of the top recommendation. Suitable for email.",
    )
    recommendation_details: dict = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Recommendation details",
        help_text=(
            "Full structured recommendation output. Schema example:\n"
            "{\n"
            "  \"careers\": [{\"slug\": \"software-engineer\", \"match_pct\": 88, \"rank\": 1, \"reason\": \"…\"}],\n"
            "  \"insights\": [{\"title\": \"…\", \"body\": \"…\", \"score\": 78}]\n"
            "}"
        ),
    )
    confidence_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Confidence score (0–100)",
        help_text="Algorithm confidence in this recommendation set.",
    )
    algorithm_version: str = models.CharField(
        max_length=50,
        blank=True,
        default="v1",
        verbose_name="Algorithm version",
        help_text="Tracks which recommendation algorithm produced this result. "
                  "Enables later A/B comparison or version filtering.",
    )
    email_sent: bool = models.BooleanField(
        default=False,
        verbose_name="Email sent",
        help_text="True once the recommendation email has been dispatched to the user.",
    )
    email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Email sent at",
    )
 
    class Meta:
        verbose_name        = "Career Recommendation"
        verbose_name_plural = "Career Recommendations"
        ordering            = ["-generated_at"]
        indexes             = [
            models.Index(fields=["user", "processing_status"]),
            models.Index(fields=["user", "-generated_at"]),
            models.Index(fields=["response"]),
        ]
 
    def __str__(self) -> str:
        return f"Recommendation for {self.user} ({self.processing_status}) — {self.generated_at:%Y-%m-%d}"
 
    def mark_email_sent(self) -> None:
        """Record that the recommendation email has been dispatched."""
        self.email_sent    = True
        self.email_sent_at = timezone.now()
        self.save(update_fields=["email_sent", "email_sent_at"])
 
    @property
    def is_ready(self) -> bool:
        """True when the recommendation has been fully processed."""
        return self.processing_status == ProcessingStatus.COMPLETED
 
    def get_top_careers(self) -> list:
        """
        Convenience accessor for the structured careers list inside recommendation_details.
        Returns an empty list if details are not yet populated.
        """
        return self.recommendation_details.get("careers", [])