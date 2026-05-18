from django import forms
from django.core.exceptions import ValidationError

from .models import Tag


class TagForm(forms.ModelForm):
    """
    Create / update a Tag node.
    Prevents a tag from being set as its own parent or any of its descendants
    (would create a cycle in the adjacency-list tree).
    """

    class Meta:
        model = Tag
        fields = ["title", "description", "parent", "order", "color_hex"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "color_hex": forms.TextInput(attrs={"type": "color", "style": "width:60px;height:36px;padding:2px;"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Exclude self and own descendants from the parent choices to prevent cycles
        if self.instance.pk:
            excluded = self._get_descendant_ids(self.instance) | {self.instance.pk}
            self.fields["parent"].queryset = Tag.objects.exclude(pk__in=excluded)

    # ── Helpers ──────────────────────────────────

    def _get_descendant_ids(self, tag):
        """Recursively collect all descendant PKs."""
        ids = set()
        for child in tag.children.all():
            ids.add(child.pk)
            ids |= self._get_descendant_ids(child)
        return ids

    # ── Validation ───────────────────────────────

    def clean_color_hex(self):
        value = self.cleaned_data.get("color_hex", "").strip()
        if value and not (value.startswith("#") and len(value) == 7):
            raise ValidationError("Enter a valid hex colour, e.g. #3a86ff.")
        return value

    def clean_parent(self):
        parent = self.cleaned_data.get("parent")
        if self.instance.pk and parent:
            if parent.pk == self.instance.pk:
                raise ValidationError("A tag cannot be its own parent.")
            if parent.pk in self._get_descendant_ids(self.instance):
                raise ValidationError(
                    "Setting a descendant as parent would create a cycle."
                )
        return parent