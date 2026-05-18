from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Institution,
    Career,
    CareerTag,
    Course,
    CutoffCluster,
    SubjectRequirement,
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
    fields = ["kuccps_code", "title", "qualification", "institution", "duration_years"]
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


# ─────────────────────────────────────────────
# ModelAdmins
# ─────────────────────────────────────────────

@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "type_badge", "course_count", "website_link", "slug"]
    list_filter = ["type"]
    search_fields = ["name", "code", "slug"]
    readonly_fields = ["slug"]
    ordering = ["name"]

    fieldsets = (
        (
            None,
            {
                "fields": ("code", "name", "slug", "type", "website"),
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
        "kuccps_code",
        "title",
        "qualification_badge",
        "institution",
        "career",
        "duration_years",
        "slug",
    ]
    list_filter = ["qualification", "institution__type", "duration_years"]
    search_fields = ["title", "kuccps_code", "slug", "institution__name", "career__title"]
    readonly_fields = ["slug"]
    raw_id_fields = ["career", "institution"]
    ordering = ["title"]
    inlines = [CutoffClusterInline, SubjectRequirementInline]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "kuccps_code",
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
    search_fields = ["course__title", "course__kuccps_code"]
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