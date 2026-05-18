from django.contrib import admin
from django.utils.html import format_html

from .models import Tag


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["title", "parent", "color_swatch", "order", "slug", "child_count"]
    list_filter = ["parent"]
    search_fields = ["title", "slug", "description"]
    readonly_fields = ["slug", "color_swatch"]
    raw_id_fields = ["parent"]
    ordering = ["parent__title", "order", "title"]

    fieldsets = (
        (
            None,
            {
                "fields": ("title", "slug", "description", "parent", "order"),
            },
        ),
        (
            "UI",
            {
                "fields": ("color_hex", "color_swatch"),
                "description": "Optional colour hint used in the front-end.",
            },
        ),
    )

    # ── Custom display helpers ──────────────────

    def color_swatch(self, obj):
        if obj.color_hex:
            return format_html(
                '<span style="display:inline-block;width:20px;height:20px;'
                'border-radius:4px;background:{};border:1px solid #ccc;'
                'vertical-align:middle;"></span>&nbsp;{}',
                obj.color_hex,
                obj.color_hex,
            )
        return "—"

    color_swatch.short_description = "Colour"

    def child_count(self, obj):
        count = obj.children.count()
        return count if count else "—"

    child_count.short_description = "Children"