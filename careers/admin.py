from django.contrib import admin
from django.utils.html import format_html
from django.utils.timezone import localtime
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import (
    Institution,
    Career,
    CareerTag,
    Course,
    CutoffCluster,
    SubjectRequirement,
    CareerPsychometricTest,
    CareerPsychometricQuestion,
    CareerPsychometricChoice,
    CareerPsychometricResponse,
    CareerPsychometricResponseAnswer,
    CareerRecommendation,
    ProcessingStatus,
    ResponseStatus,
    UserTagVector,
    UserInteraction,
    RecommendationFeedback,
    FeatureRegistry,
    RecommendationExplanation,
    EngineVersion,
)


# ─────────────────────────────────────────────
# Inlines
# ─────────────────────────────────────────────

class CareerTagInline(admin.TabularInline):
    model = CareerTag
    extra = 1
    autocomplete_fields = ["tag"]
    fields = ["tag", "recommendation_weight"]


class CourseInline(admin.TabularInline):
    model = Course
    extra = 0
    fields = ["code", "title", "qualification", "institution", "duration_years"]
    show_change_link = True
    raw_id_fields = ["institution"]


class CutoffClusterInline(admin.TabularInline):
    model = CutoffCluster
    extra = 1
    fields = ["cluster_number", "cutoff_points", "year"]
    ordering = ["-year", "cluster_number"]


class SubjectRequirementInline(admin.TabularInline):
    model = SubjectRequirement
    extra = 1
    autocomplete_fields = ["subject"]
    fields = ["subject", "requirement_type", "minimum_grade"]


class CareerPsychometricChoiceInline(admin.TabularInline):
    """Choices displayed inline within a question's change form."""
 
    model        = CareerPsychometricChoice
    extra        = 3
    fields       = ("order", "label", "value")
    ordering     = ("order",)
    verbose_name = "Choice"
    verbose_name_plural = "Choices"
 
 
class CareerPsychometricQuestionInline(admin.StackedInline):
    """
    Questions displayed inline within a test's change form.
    Choices are NOT shown here to keep the form manageable —
    edit choices from the question's own change form.
    """
 
    model        = CareerPsychometricQuestion
    extra        = 2
    fields       = ("order", "prompt", "question_type", "required", "is_active", "help_text", "metadata")
    ordering     = ("order",)
    show_change_link = True
    verbose_name = "Question"
    verbose_name_plural = "Questions"
 
 
class CareerPsychometricResponseAnswerInline(admin.TabularInline):
    """
    Individual answers shown read-only inside a response's change form.
    Staff should never edit raw response data — inlines are read-only.
    """
 
    model        = CareerPsychometricResponseAnswer
    extra        = 0
    readonly_fields = (
        "question_prompt", "question_type_display",
        "selected_choices_display", "text_answer", "numeric_answer", "answered_at",
    )
    fields       = (
        "question_prompt", "question_type_display",
        "selected_choices_display", "text_answer", "numeric_answer", "answered_at",
    )
    can_delete   = False
    verbose_name = "Answer"
    verbose_name_plural = "Answers"
 
    def has_add_permission(self, request, obj=None) -> bool:
        return False
 
    def has_change_permission(self, request, obj=None) -> bool:
        return False
 
    @admin.display(description="Question")
    def question_prompt(self, obj: CareerPsychometricResponseAnswer) -> str:
        return f"Q{obj.question.order}: {obj.question.prompt[:80]}"
 
    @admin.display(description="Type")
    def question_type_display(self, obj: CareerPsychometricResponseAnswer) -> str:
        return obj.question.get_question_type_display()
 
    @admin.display(description="Selected choices")
    def selected_choices_display(self, obj: CareerPsychometricResponseAnswer) -> str:
        choices = obj.selected_choices.all()
        if not choices.exists():
            return "—"
        return ", ".join(c.label for c in choices)


# ─────────────────────────────────────────────
# ModelAdmins
# ─────────────────────────────────────────────

@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "type_badge", "course_count", "website_link", "country"]
    list_filter = ["type", "country"]
    search_fields = ["name", "code", "slug", "website", "country"]
    readonly_fields = ["slug"]
    ordering = ["name"]

    fieldsets = (
        (
            None,
            {
                "fields": ("code", "name", "slug", "type", "website", "country"),
            },
        ),
    )

    # ── Custom display helpers ──────────────────

    def type_badge(self, obj):
        colours = {
            "PUBLIC_UNIVERSITY":  "#1565c0",
            "PRIVATE_UNIVERSITY": "#6a1b9a",
            "TECHNICAL":          "#2e7d32",
        }
        colour = colours.get(obj.type, "#546e7a")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:12px;font-size:12px;">{}</span>',
            colour,
            obj.get_type_display(),
        )

    type_badge.short_description = "Type"

    def website_link(self, obj):
        if obj.website:
            return format_html('<a href="{}" target="_blank">🔗 Visit</a>', obj.website)
        return "—"

    website_link.short_description = "Website"

    def course_count(self, obj):
        return obj.courses.count()

    course_count.short_description = "Courses"


@admin.register(Career)
class CareerAdmin(admin.ModelAdmin):
    list_display = ["code", "title", "sector", "course_count", "slug"]
    list_filter = ["sector"]
    search_fields = ["title", "code", "slug", "description"]
    readonly_fields = ["slug"]
    ordering = ["title"]
    inlines = [CareerTagInline, CourseInline]

    fieldsets = (
        (
            None,
            {
                "fields": ("code", "title", "slug", "sector", "description"),
            },
        ),
    )

    def course_count(self, obj):
        return obj.courses.count()

    course_count.short_description = "Courses"


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "title",
        "qualification_badge",
        "institution",
        "career",
        "duration_years",
        "slug",
    ]
    list_filter = ["qualification", "institution__type", "duration_years"]
    search_fields = ["title", "code", "slug", "institution__name", "career__title"]
    readonly_fields = ["slug"]
    raw_id_fields = ["career", "institution"]
    ordering = ["title"]
    inlines = [CutoffClusterInline, SubjectRequirementInline]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "code",
                    "title",
                    "slug",
                    "description",
                    "qualification",
                    "duration_years",
                ),
            },
        ),
        (
            "Relationships",
            {
                "fields": ("career", "institution"),
            },
        ),
    )

    def qualification_badge(self, obj):
        colours = {
            "DEGREE":      "#1565c0",
            "DIPLOMA":     "#6a1b9a",
            "CERTIFICATE": "#2e7d32",
        }
        colour = colours.get(obj.qualification, "#546e7a")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:12px;font-size:12px;">{}</span>',
            colour,
            obj.get_qualification_display(),
        )

    qualification_badge.short_description = "Qualification"


@admin.register(CutoffCluster)
class CutoffClusterAdmin(admin.ModelAdmin):
    list_display = ["course", "cluster_number", "cutoff_points", "year"]
    list_filter = ["year", "cluster_number"]
    search_fields = ["course__title", "course__code"]
    raw_id_fields = ["course"]
    ordering = ["-year", "course", "cluster_number"]


@admin.register(SubjectRequirement)
class SubjectRequirementAdmin(admin.ModelAdmin):
    list_display = ["course", "subject", "requirement_type_badge", "minimum_grade"]
    list_filter = ["requirement_type"]
    search_fields = ["course__title", "subject__name"]
    raw_id_fields = ["course"]
    autocomplete_fields = ["subject"]
    ordering = ["course", "requirement_type"]

    def requirement_type_badge(self, obj):
        colours = {
            "COMPULSORY":   "#c62828",
            "ALTERNATIVE":  "#f57f17",
            "OPTIONAL":     "#2e7d32",
        }
        colour = colours.get(obj.requirement_type, "#546e7a")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:12px;font-size:12px;">{}</span>',
            colour,
            obj.get_requirement_type_display(),
        )

    requirement_type_badge.short_description = "Requirement"


@admin.register(CareerPsychometricTest)
class CareerPsychometricTestAdmin(admin.ModelAdmin):
    """
    Main admin for psychometric tests.
    Questions can be added/edited inline or from their own change form.
    """
 
    list_display  = (
        "name", "category_badge", "estimated_duration",
        "total_questions", "is_active_icon", "is_premium_icon", "updated_at",
    )
    list_filter   = ("category", "is_active", "is_premium")
    search_fields = ("name", "description", "slug")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields     = ("created_at", "updated_at", "total_questions")
    ordering      = ("category", "name")
    inlines       = [CareerPsychometricQuestionInline]
 
    fieldsets = (
        ("Core", {
            "fields": ("name", "slug", "description", "instructions"),
        }),
        ("Settings", {
            "fields": ("category", "estimated_duration", "is_active", "is_premium"),
        }),
        ("Statistics", {
            "fields": ("total_questions", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
 
    actions = ["make_active", "make_inactive", "refresh_question_counts"]
 
    @admin.display(description="Category", ordering="category")
    def category_badge(self, obj: CareerPsychometricTest) -> str:
        colours = {
            "basic":        "#a3e635",
            "intermediate": "#38bdf8",
            "advanced":     "#facc15",
        }
        colour = colours.get(obj.category, "#aaa")
        return format_html(
            '<span style="color:{};font-weight:600;font-size:0.82em;">{}</span>',
            colour,
            obj.get_category_display(),
        )
 
    @admin.display(description="Active", boolean=False, ordering="is_active")
    def is_active_icon(self, obj: CareerPsychometricTest) -> str:
        return format_html(
            '<span style="color:{}">&#9679;</span>',
            "#a3e635" if obj.is_active else "#f87171",
        )
 
    @admin.display(description="Premium", boolean=False, ordering="is_premium")
    def is_premium_icon(self, obj: CareerPsychometricTest) -> str:
        if obj.is_premium:
            return format_html('<span style="color:#E85D04;font-weight:600;">&#9733; Premium</span>')
        return format_html('<span style="opacity:0.4;">Free</span>')
 
    @admin.action(description="Mark selected tests as active")
    def make_active(self, request, queryset) -> None:
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} test(s) marked as active.")
 
    @admin.action(description="Mark selected tests as inactive")
    def make_inactive(self, request, queryset) -> None:
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} test(s) marked as inactive.")
 
    @admin.action(description="Refresh question counts")
    def refresh_question_counts(self, request, queryset) -> None:
        for test in queryset:
            test.update_question_count()
        self.message_user(request, f"Question counts refreshed for {queryset.count()} test(s).")
 

 
@admin.register(CareerPsychometricQuestion)
class CareerPsychometricQuestionAdmin(admin.ModelAdmin):
    """
    Standalone question admin — useful for bulk management across tests.
    Choices are edited inline here.
    """
 
    list_display  = (
        "short_prompt", "questionnaire_link", "question_type",
        "order", "required", "is_active",
    )
    list_filter   = ("question_type", "required", "is_active", "questionnaire__category")
    search_fields = ("prompt", "help_text", "questionnaire__name")
    ordering      = ("questionnaire", "order")
    inlines       = [CareerPsychometricChoiceInline]
    readonly_fields = ("questionnaire",)
 
    fieldsets = (
        ("Question", {
            "fields": ("questionnaire", "order", "prompt", "help_text"),
        }),
        ("Type & Behaviour", {
            "fields": ("question_type", "required", "is_active", "metadata"),
        }),
    )
 
    @admin.display(description="Question", ordering="prompt")
    def short_prompt(self, obj: CareerPsychometricQuestion) -> str:
        return obj.prompt[:70] + ("…" if len(obj.prompt) > 70 else "")
 
    @admin.display(description="Test")
    def questionnaire_link(self, obj: CareerPsychometricQuestion) -> str:
        url = reverse("admin:careers_careerpsychometrictest_change", args=[obj.questionnaire_id])
        return format_html('<a href="{}">{}</a>', url, obj.questionnaire.name)
 

 
@admin.register(CareerPsychometricChoice)
class CareerPsychometricChoiceAdmin(admin.ModelAdmin):
    """
    Standalone choice admin — useful for bulk imports or corrections.
    Choices are also editable inline within the question admin.
    """
 
    list_display  = ("label", "value", "question_short", "order")
    search_fields = ("label", "value", "question__prompt", "question__questionnaire__name")
    ordering      = ("question", "order")
    list_select_related = ("question", "question__questionnaire")
 
    @admin.display(description="Question")
    def question_short(self, obj: CareerPsychometricChoice) -> str:
        return obj.question.prompt[:60]
 
 
@admin.register(CareerPsychometricResponse)
class CareerPsychometricResponseAdmin(admin.ModelAdmin):
    """
    Response (attempt) admin — intentionally read-only.
    Staff can view but not alter response data to preserve audit integrity.
    """
 
    list_display  = (
        "user", "questionnaire", "status_badge",
        "started_at_local", "completed_at_local", "answer_count",
    )
    list_filter   = ("status", "questionnaire__category", "questionnaire")
    search_fields = ("user__username", "user__email", "questionnaire__name")
    ordering      = ("-started_at",)
    readonly_fields = (
        "user", "questionnaire", "status", "started_at", "completed_at",
    )
    inlines = [CareerPsychometricResponseAnswerInline]
 
    # Prevent creating or deleting response records from admin
    def has_add_permission(self, request) -> bool:
        return False
 
    def has_delete_permission(self, request, obj=None) -> bool:
        return request.user.is_superuser
 
    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj: CareerPsychometricResponse) -> str:
        colours = {
            ResponseStatus.IN_PROGRESS: "#38bdf8",
            ResponseStatus.COMPLETED:   "#a3e635",
            ResponseStatus.ABANDONED:   "#f87171",
        }
        colour = colours.get(obj.status, "#aaa")
        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>',
            colour,
            obj.get_status_display(),
        )
 
    @admin.display(description="Started", ordering="started_at")
    def started_at_local(self, obj: CareerPsychometricResponse) -> str:
        return localtime(obj.started_at).strftime("%d %b %Y %H:%M")
 
    @admin.display(description="Completed")
    def completed_at_local(self, obj: CareerPsychometricResponse) -> str:
        if obj.completed_at:
            return localtime(obj.completed_at).strftime("%d %b %Y %H:%M")
        return "—"
 
    @admin.display(description="Answers")
    def answer_count(self, obj: CareerPsychometricResponse) -> int:
        return obj.answers.count()
 

 
@admin.register(CareerPsychometricResponseAnswer)
class CareerPsychometricResponseAnswerAdmin(admin.ModelAdmin):
    """
    Granular view of individual answers — useful for debugging.
    Entirely read-only.
    """
 
    list_display  = (
        "response_user", "response_test", "question_order",
        "question_type", "answer_summary", "answered_at",
    )
    list_filter   = (
        "question__question_type",
        "response__status",
        "response__questionnaire",
    )
    search_fields = (
        "response__user__username",
        "response__user__email",
        "question__prompt",
        "text_answer",
    )
    ordering      = ("-answered_at",)
    readonly_fields = (
        "response", "question", "selected_choices",
        "text_answer", "numeric_answer", "answered_at",
    )
    list_select_related = (
        "response__user", "response__questionnaire", "question",
    )
 
    def has_add_permission(self, request) -> bool:
        return False
 
    def has_change_permission(self, request, obj=None) -> bool:
        return False
 
    def has_delete_permission(self, request, obj=None) -> bool:
        return request.user.is_superuser
 
    @admin.display(description="User")
    def response_user(self, obj: CareerPsychometricResponseAnswer) -> str:
        return obj.response.user.get_full_name() or obj.response.user.username
 
    @admin.display(description="Test")
    def response_test(self, obj: CareerPsychometricResponseAnswer) -> str:
        return obj.response.questionnaire.name
 
    @admin.display(description="Q#", ordering="question__order")
    def question_order(self, obj: CareerPsychometricResponseAnswer) -> int:
        return obj.question.order
 
    @admin.display(description="Type")
    def question_type(self, obj: CareerPsychometricResponseAnswer) -> str:
        return obj.question.get_question_type_display()
 
    @admin.display(description="Answer")
    def answer_summary(self, obj: CareerPsychometricResponseAnswer) -> str:
        choices = obj.selected_choices.all()
        if choices.exists():
            labels = ", ".join(c.label for c in choices[:3])
            return labels + ("…" if choices.count() > 3 else "")
        if obj.text_answer:
            return obj.text_answer[:60] + ("…" if len(obj.text_answer) > 60 else "")
        if obj.numeric_answer is not None:
            return str(obj.numeric_answer)
        return "—"
 
 
# ─────────────────────────────────────────────────────────────────────────────
# CAREER RECOMMENDATION
# ─────────────────────────────────────────────────────────────────────────────
 
@admin.register(CareerRecommendation)
class CareerRecommendationAdmin(admin.ModelAdmin):
    """
    Recommendation records are append-only from the application side.
    Staff can inspect and manually trigger email flags but should not
    edit recommendation_details directly.
 
    Superusers may delete records if required (e.g. data correction).
    """
 
    list_display  = (
        "user", "processing_status_badge", "confidence_score",
        "algorithm_version", "email_sent_icon", "generated_at_local",
    )
    list_filter   = (
        "processing_status", "algorithm_version",
        "email_sent", "generated_at",
    )
    search_fields = ("user__username", "user__email", "recommendation_summary")
    ordering      = ("-generated_at",)
    readonly_fields = (
        "user", "response", "generated_at",
        "recommendation_details_pretty",
    )
    actions = ["mark_emails_sent", "requeue_processing"]
 
    fieldsets = (
        ("Record", {
            "fields": ("user", "response", "generated_at"),
        }),
        ("Status", {
            "fields": (
                "processing_status", "confidence_score",
                "algorithm_version", "email_sent", "email_sent_at",
            ),
        }),
        ("Content", {
            "fields": ("recommendation_summary", "recommendation_details_pretty"),
        }),
    )
 
    def has_add_permission(self, request) -> bool:
        return False
 
    def has_delete_permission(self, request, obj=None) -> bool:
        return request.user.is_superuser
 
    @admin.display(description="Status", ordering="processing_status")
    def processing_status_badge(self, obj: CareerRecommendation) -> str:
        colours = {
            ProcessingStatus.PENDING:    "#facc15",
            ProcessingStatus.PROCESSING: "#38bdf8",
            ProcessingStatus.COMPLETED:  "#a3e635",
            ProcessingStatus.FAILED:     "#f87171",
        }
        colour = colours.get(obj.processing_status, "#aaa")
        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>',
            colour,
            obj.get_processing_status_display(),
        )
 
    @admin.display(description="Email sent", boolean=False, ordering="email_sent")
    def email_sent_icon(self, obj: CareerRecommendation) -> str:
        if obj.email_sent:
            sent_at = ""
            if obj.email_sent_at:
                sent_at = localtime(obj.email_sent_at).strftime(" (%d %b %H:%M)")
            return format_html(
                '<span style="color:#a3e635;">&#10003; Sent{}</span>', sent_at
            )
        return format_html('<span style="opacity:0.4;">Not sent</span>')
 
    @admin.display(description="Generated", ordering="generated_at")
    def generated_at_local(self, obj: CareerRecommendation) -> str:
        return localtime(obj.generated_at).strftime("%d %b %Y %H:%M")
 
    @admin.display(description="Recommendation details (formatted)")
    def recommendation_details_pretty(self, obj: CareerRecommendation) -> str:
        """Render the JSONField in a readable, monospaced block."""
        import json
        try:
            formatted = json.dumps(obj.recommendation_details, indent=2, ensure_ascii=False)
        except (TypeError, ValueError):
            formatted = str(obj.recommendation_details)
        return format_html(
            '<pre style="font-size:0.82em;white-space:pre-wrap;'
            'max-height:400px;overflow-y:auto;'
            'background:rgba(0,0,0,0.04);padding:12px;border-radius:6px;">{}</pre>',
            formatted,
        )
 
    @admin.action(description="Mark selected recommendations as email sent")
    def mark_emails_sent(self, request, queryset) -> None:
        from django.utils import timezone
        updated = queryset.filter(email_sent=False).update(
            email_sent=True,
            email_sent_at=timezone.now(),
        )
        self.message_user(request, f"{updated} recommendation(s) marked as email sent.")
 
    @admin.action(description="Re-queue selected recommendations for processing")
    def requeue_processing(self, request, queryset) -> None:
        """
        Reset status to PENDING so the async recommendation engine
        will pick them up again on its next run.
        Wire this to your Celery task in the view/signal when ready.
        """
        updated = queryset.update(processing_status=ProcessingStatus.PENDING)
        self.message_user(
            request,
            f"{updated} recommendation(s) re-queued. "
            "Ensure the recommendation Celery task is running.",
        )


@admin.register(UserTagVector)
class UserTagVectorAdmin(admin.ModelAdmin):
    list_display = ("profile", "tag", "affinity_score", "confidence", "evidence_count", "algorithm_version", "last_updated")
    list_filter = ("algorithm_version",)
    search_fields = ("profile__user__username", "tag__title")
    autocomplete_fields = ("profile", "tag")
    readonly_fields = ("last_updated",)
    # This table can get large fast (users x tags) — avoid select-related
    # blowups in the changelist.
    list_select_related = ("profile", "tag")
 
 
@admin.register(UserInteraction)
class UserInteractionAdmin(admin.ModelAdmin):
    list_display = ("profile", "career", "interaction_type", "occurred_at", "duration_ms")
    list_filter = ("interaction_type", "occurred_at")
    search_fields = ("profile__user__username", "career__title", "session_id")
    autocomplete_fields = ("profile", "career", "recommendation")
    readonly_fields = ("occurred_at",)
    date_hierarchy = "occurred_at"
 
 
@admin.register(RecommendationFeedback)
class RecommendationFeedbackAdmin(admin.ModelAdmin):
    list_display = ("profile", "career", "feedback_type", "feedback_score", "submitted_at")
    list_filter = ("feedback_type", "submitted_at")
    search_fields = ("profile__user__username", "career__title")
    autocomplete_fields = ("profile", "career", "recommendation")
    readonly_fields = ("submitted_at",)
 
 
@admin.register(FeatureRegistry)
class FeatureRegistryAdmin(admin.ModelAdmin):
    list_display = ("feature_name", "feature_type", "source_table", "is_active", "version", "updated_at")
    list_filter = ("feature_type", "is_active")
    search_fields = ("feature_name", "source_table", "compute_function")
    readonly_fields = ("created_at", "updated_at")
 
 
class RecommendationExplanationInline(admin.TabularInline):
    """
    Suggested addition to your existing CareerRecommendationAdmin:
        inlines = [..., RecommendationExplanationInline]
    """
    model = RecommendationExplanation
    extra = 0
    fields = ("explanation_type", "explanation_version", "created_at")
    readonly_fields = ("created_at",)
    can_delete = False
 
 
@admin.register(RecommendationExplanation)
class RecommendationExplanationAdmin(admin.ModelAdmin):
    list_display = ("recommendation", "explanation_type", "explanation_version", "created_at")
    list_filter = ("explanation_type",)
    readonly_fields = ("created_at",)
 
 
@admin.register(EngineVersion)
class EngineVersionAdmin(admin.ModelAdmin):
    list_display = ("version_number", "engine_type", "is_active", "is_shadow", "released_at", "deprecated_at")
    list_filter = ("engine_type", "is_active", "is_shadow")
    search_fields = ("version_number", "description")
    readonly_fields = ("created_at",)
 
    # Guardrail in the UI to reinforce the "one active version" invariant
    # that's already enforced at the model level in save().
    actions = ["make_active"]
 
    @admin.action(description="Set as the active engine version")
    def make_active(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Select exactly one engine version to activate.", level="error")
            return
        engine = queryset.first()
        engine.is_active = True
        engine.is_shadow = False
        engine.save()
        self.message_user(request, f"{engine.version_number} is now the active engine.")
 