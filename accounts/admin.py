from django.contrib import admin
from django.utils.html import format_html

from .models import UserProfile, CareerPreference, Subject, ProfileSubject


class CareerPreferenceInline(admin.TabularInline):
    model = CareerPreference
    extra = 1
    autocomplete_fields = ["career"]
    fields = ["career", "rank"]
    ordering = ["rank"]


class ProfileSubjectInline(admin.TabularInline):
    model = ProfileSubject
    extra = 1
    autocomplete_fields = ["subject"]
    fields = ["subject", "grade", "is_active"]


# ─────────────────────────────────────────────
# ModelAdmins
# ─────────────────────────────────────────────

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "date_of_birth",
        "completion_badge",
        "subject_count",
        "avatar_preview",
    ]
    list_filter = ["subjects__category"]
    search_fields = ["user__username", "user__email", "about_me"]
    readonly_fields = ["avatar_preview", "completion_badge"]
    raw_id_fields = ["user"]
    inlines = [CareerPreferenceInline, ProfileSubjectInline]

    fieldsets = (
        (
            "Account",
            {
                "fields": ("user", "date_of_birth", "about_me"),
            },
        ),
        (
            "Avatar",
            {
                "fields": ("avatar", "avatar_preview"),
            },
        ),
        (
            "Progress",
            {
                "fields": ("completion_badge",),
                "description": "Read-only computed fields.",
            },
        ),
    )

    # ── Custom display helpers ──────────────────

    def avatar_preview(self, obj):
        if obj.avatar:
            return format_html(
                '<img src="{}" width="50" height="50" '
                'style="border-radius:4px;object-fit:cover;" />',
                obj.avatar.url,
            )
        return "No Avatar"

    avatar_preview.short_description = "Avatar Preview"

    def completion_badge(self, obj):
        pct = obj.completion_percentage
        colour = "#4caf50" if pct >= 75 else "#ff9800" if pct >= 40 else "#f44336"
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:12px;font-size:12px;">{} %</span>',
            colour,
            pct,
        )

    completion_badge.short_description = "Profile Completion"

    def subject_count(self, obj):
        return obj.subjects.count()

    subject_count.short_description = "Subjects"


@admin.register(CareerPreference)
class CareerPreferenceAdmin(admin.ModelAdmin):
    list_display = ["profile", "career", "rank"]
    list_filter = ["rank"]
    search_fields = [
        "profile__user__username",
        "profile__user__email",
        "career__name",
    ]
    autocomplete_fields = ["career"]
    raw_id_fields = ["profile"]
    ordering = ["profile", "rank"]


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "category", "is_compulsory", "slug"]
    list_filter = ["category", "is_compulsory"]
    search_fields = ["name", "code", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    ordering = ["name"]

    fieldsets = (
        (
            None,
            {
                "fields": ("code", "name", "slug", "category", "is_compulsory"),
            },
        ),
    )


@admin.register(ProfileSubject)
class ProfileSubjectAdmin(admin.ModelAdmin):
    list_display = ["profile", "subject", "grade", "is_active"]
    list_filter = ["is_active", "subject__category"]
    search_fields = [
        "profile__user__username",
        "profile__user__email",
        "subject__name",
    ]
    raw_id_fields = ["profile"]
    autocomplete_fields = ["subject"]