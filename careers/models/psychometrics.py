# Test choices, questions, and responses
from __future__ import annotations
from django.db import models
from django.utils.text import slugify
from django.utils import timezone


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
 
 