from django.contrib import admin
from django.utils.html import format_html

from .models import Tag,TagRelationship, TagSourceMetadata


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


class TagRelationshipInline(admin.TabularInline):
    """
    Drop this into your existing TagAdmin as:
        inlines = [..., TagRelationshipInline]
    to let curators add relationships directly from a Tag's admin page.
    """
    model = TagRelationship
    fk_name = "from_tag"
    extra = 1
    fields = ("to_tag", "relationship_type", "strength", "is_symmetric")
    autocomplete_fields = ("to_tag",)
 
 
@admin.register(TagRelationship)
class TagRelationshipAdmin(admin.ModelAdmin):
    list_display = (
        "from_tag", "relationship_type", "to_tag",
        "strength", "is_symmetric", "is_system_generated", "updated_at",
    )
    list_filter = ("relationship_type", "is_symmetric", "is_system_generated")
    search_fields = ("from_tag__title", "to_tag__title")
    autocomplete_fields = ("from_tag", "to_tag")
    readonly_fields = ("created_at", "updated_at")
 
 
@admin.register(TagSourceMetadata)
class TagSourceMetadataAdmin(admin.ModelAdmin):
    list_display = ("tag", "source_type", "content_type", "object_id", "confidence", "created_at")
    list_filter = ("source_type", "content_type")
    search_fields = ("tag__title",)
    autocomplete_fields = ("tag",)
    readonly_fields = ("created_at",)
 