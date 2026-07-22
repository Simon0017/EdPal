# Engine output & user results

from __future__ import annotations
from django.db import models
from django.utils.text import slugify
from django.utils import timezone

class ProcessingStatus(models.TextChoices):
    PENDING    = "PENDING",    "Pending"
    PROCESSING = "PROCESSING", "Processing"
    COMPLETED  = "COMPLETED",  "Completed"
    FAILED     = "FAILED",     "Failed"


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
        "careers.CareerPsychometricResponse",
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
            models.Index(fields=["user", "algorithm_version", "generated_at"]),
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
        return self.recommendation_details.get("ranked_careers", [])
    
