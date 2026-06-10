from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Questionnaire,
    QuestionnaireTag,
    Question,
    AnswerChoice,
    QuestionnaireAttempt,
    QuestionResponse,
    AttemptScore,
)


# ─────────────────────────────────────────────
# Inlines
# ─────────────────────────────────────────────

class QuestionnaireTagInline(admin.TabularInline):
    model = QuestionnaireTag
    extra = 1
    autocomplete_fields = ["tag"]
    fields = ["tag", "coupling_strength", "is_primary"]


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    fields = ["order", "question_type", "question_text", "max_points", "weight", "is_required"]
    ordering = ["order"]
    show_change_link = True


class AnswerChoiceInline(admin.TabularInline):
    model = AnswerChoice
    extra = 2
    fields = ["order", "choice_key", "choice_text", "is_correct", "partial_score"]
    ordering = ["order"]


class QuestionResponseInline(admin.TabularInline):
    model = QuestionResponse
    extra = 0
    readonly_fields = ["question", "answer_value", "points_awarded", "is_correct", "responded_at", "time_taken_ms"]
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


# ─────────────────────────────────────────────
# ModelAdmins
# ─────────────────────────────────────────────

@admin.register(Questionnaire)
class QuestionnaireAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "version_number",
        "status_badge",
        "max_score",
        "time_limit_minutes",
        "is_randomised",
        "question_count",
        "created_at",
        "created_by",
    ]
    list_filter = ["status", "is_randomised"]
    search_fields = ["title", "slug", "description"]
    readonly_fields = ["slug", "created_at", "modified_at"]
    ordering = ["-version_number", "title"]
    date_hierarchy = "created_at"
    inlines = [QuestionnaireTagInline, QuestionInline]

    fieldsets = (
        (
            "Identity",
            {
                "fields": ("title", "slug", "version_number", "status", "created_by"),
            },
        ),
        (
            "Content",
            {
                "fields": ("description", "instructions"),
            },
        ),
        (
            "Scoring & Behaviour",
            {
                "fields": ("max_score", "time_limit_minutes", "is_randomised"),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "modified_at"),
                "classes": ("collapse",),
            },
        ),
    )

    # ── Custom display helpers ──────────────────

    def status_badge(self, obj):
        colours = {
            "DRAFT":     "#ff9800",
            "PUBLISHED": "#4caf50",
            "ARCHIVED":  "#9e9e9e",
        }
        colour = colours.get(obj.status, "#607d8b")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;'
            'border-radius:12px;font-size:12px;">{}</span>',
            colour,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def question_count(self, obj):
        return obj.questions.count()

    question_count.short_description = "Questions"


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = [
        "short_text",
        "questionnaire",
        "question_type",
        "order",
        "max_points",
        "weight",
        "is_required",
    ]
    list_filter = ["question_type", "is_required", "questionnaire__status"]
    search_fields = ["question_text", "questionnaire__title"]
    raw_id_fields = ["questionnaire"]
    ordering = ["questionnaire", "order"]
    inlines = [AnswerChoiceInline]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "questionnaire",
                    "question_type",
                    "question_text",
                    "explanation",
                    "is_required",
                ),
            },
        ),
        (
            "Ordering & Grouping",
            {
                "fields": ("order", "randomisation_group"),
            },
        ),
        (
            "Scoring",
            {
                "fields": ("max_points", "weight"),
            },
        ),
        (
            "Numeric Config",
            {
                "fields": ("numeric_config",),
                "classes": ("collapse",),
                "description": 'JSON: {"min": 0, "max": 10, "step": 1, "unit": "years"}',
            },
        ),
    )

    def short_text(self, obj):
        return (obj.question_text[:80] + "…") if len(obj.question_text) > 80 else obj.question_text

    short_text.short_description = "Question"


@admin.register(AnswerChoice)
class AnswerChoiceAdmin(admin.ModelAdmin):
    list_display = [
        "choice_key",
        "short_text",
        "question",
        "is_correct",
        "partial_score",
        "order",
    ]
    list_filter = ["is_correct"]
    search_fields = ["choice_text", "question__question_text"]
    raw_id_fields = ["question"]
    ordering = ["question", "order"]

    def short_text(self, obj):
        return (obj.choice_text[:80] + "…") if len(obj.choice_text) > 80 else obj.choice_text

    short_text.short_description = "Choice Text"


@admin.register(QuestionnaireAttempt)
class QuestionnaireAttemptAdmin(admin.ModelAdmin):
    list_display = [
        "profile",
        "questionnaire",
        "attempt_number",
        "status_badge",
        "started_at",
        "completed_at",
        "duration_display",
    ]
    list_filter = ["status", "questionnaire"]
    search_fields = [
        "profile__user__username",
        "profile__user__email",
        "questionnaire__title",
    ]
    readonly_fields = [
        "started_at",
        "completed_at",
        "ip_address",
        "user_agent",
        "attempt_number",
    ]
    raw_id_fields = ["profile", "questionnaire"]
    date_hierarchy = "started_at"
    inlines = [QuestionResponseInline]

    fieldsets = (
        (
            "Attempt",
            {
                "fields": (
                    "profile",
                    "questionnaire",
                    "attempt_number",
                    "status",
                ),
            },
        ),
        (
            "Timing",
            {
                "fields": ("started_at", "completed_at"),
            },
        ),
        (
            "Audit",
            {
                "fields": ("ip_address", "user_agent"),
                "classes": ("collapse",),
            },
        ),
    )

    def status_badge(self, obj):
        colours = {
            "IN_PROGRESS": "#2196f3",
            "COMPLETED":   "#4caf50",
            "ABANDONED":   "#f44336",
            "TIMED_OUT":   "#ff9800",
        }
        colour = colours.get(obj.status, "#607d8b")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;'
            'border-radius:12px;font-size:12px;">{}</span>',
            colour,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def duration_display(self, obj):
        if obj.started_at and obj.completed_at:
            delta = obj.completed_at - obj.started_at
            minutes, seconds = divmod(int(delta.total_seconds()), 60)
            return f"{minutes}m {seconds}s"
        return "—"

    duration_display.short_description = "Duration"


@admin.register(QuestionResponse)
class QuestionResponseAdmin(admin.ModelAdmin):
    list_display = [
        "attempt",
        "question",
        "answer_value",
        "is_correct",
        "points_awarded",
        "responded_at",
        "time_taken_ms",
    ]
    list_filter = ["is_correct"]
    search_fields = [
        "attempt__profile__user__username",
        "question__question_text",
    ]
    readonly_fields = [
        "attempt",
        "question",
        "answer_value",
        "points_awarded",
        "is_correct",
        "responded_at",
        "time_taken_ms",
    ]
    raw_id_fields = []

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # Immutable — no edits allowed
        return False


@admin.register(AttemptScore)
class AttemptScoreAdmin(admin.ModelAdmin):
    list_display = [
        "attempt",
        "raw_score",
        "weighted_score",
        "percentage_display",
        "percentile_rank",
        "scoring_engine_version",
        "computed_at",
    ]
    search_fields = ["attempt__profile__user__username"]
    readonly_fields = [
        "attempt",
        "raw_score",
        "weighted_score",
        "percentage",
        "percentile_rank",
        "scoring_engine_version",
        "computed_at",
    ]
    ordering = ["-computed_at"]
    date_hierarchy = "computed_at"

    def percentage_display(self, obj):
        pct = float(obj.percentage)
        colour = "#4caf50" if pct >= 75 else "#ff9800" if pct >= 50 else "#f44336"
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}%</span>',
            colour,
            pct,
        )

    percentage_display.short_description = "Percentage"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False