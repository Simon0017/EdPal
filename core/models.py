from django.db import models
from django.utils.text import slugify
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError


class Tag(models.Model):
    """
    Hierarchical tag tree via self-referential FK (Adjacency List).

    Examples:	
      root: STEM
        child: Mathematics
          child: Statistics
        child: Chemistry
      root: Soft Skills
        child: Leadership
        child: Creativity
    """
    title       = models.CharField(max_length=100)
    slug        = models.SlugField(max_length=100, unique=True,blank=True)
    description = models.TextField(blank=True)
    parent      = models.ForeignKey(
        "self",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="children"
    )

    order       = models.PositiveSmallIntegerField(default=0,blank=True)
    color_hex   = models.CharField(max_length=7, blank=True)  # UI hint

    class Meta:
        db_table = "taxonomy_tag"
        ordering = ["parent__title", "order", "title"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["parent"]),
        ]
    

    def save(self,  *args, **kwargs):
        if self.pk:
            old_title = type(self).objects.get(pk=self.pk).title
            if old_title != self.title:
                self.slug = slugify(self.title)
        else:
            self.slug = slugify(self.title)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Tag: {self.title}"


class TagRelationshipType(models.TextChoices):
    RELATED       = "RELATED",       "Related To"
    PREREQUISITE  = "PREREQUISITE",  "Prerequisite Of"
    COMPLEMENTARY = "COMPLEMENTARY", "Complementary To"
    SYNONYM       = "SYNONYM",       "Synonym Of"
    CONFLICTING   = "CONFLICTING",   "Conflicts With"
 
 
class TagRelationship(models.Model):
    """
    Weighted, typed, non-hierarchical relationships between Tags.
 
    Tag.parent already models hierarchy (adjacency list) — this model
    intentionally does NOT duplicate that. It exists for relationships
    that aren't parent/child: co-occurrence, prerequisites, synonyms,
    complementary skills, etc.
 
    Symmetric relationships (RELATED, SYNONYM, COMPLEMENTARY) auto-sync
    their inverse row via a signal (see core/signals.py) — you only ever
    need to create one direction. Directional relationships
    (PREREQUISITE) are NOT auto-mirrored, since A being a prerequisite
    of B does not imply the reverse.
 
    strength is intentionally decoupled from CareerTag.recommendation_weight
    and QuestionnaireTag.coupling_strength — this is a tag-to-tag signal,
    not a source-to-tag signal, and primarily feeds explanation quality
    and (later) embedding/co-occurrence work, not scoring directly.
    """
    from_tag = models.ForeignKey(
        "core.Tag", on_delete=models.CASCADE,
        related_name="relationships_from"
    )
    
    to_tag = models.ForeignKey(
        "core.Tag", on_delete=models.CASCADE,
        related_name="relationships_to"
    )
 
    relationship_type = models.CharField(
        max_length=20,
        choices=TagRelationshipType.choices,
        db_index=True,
    )
 
    strength = models.DecimalField(
        max_digits=5, decimal_places=4, default=1.0,
        help_text="0.0-1.0: how strong/confident this relationship is"
    )
 
    is_symmetric = models.BooleanField(
        default=True,
        help_text="If True, the inverse row is auto-created/kept in sync"
    )
 
    # Provenance: was this curated by a human or computed (e.g. co-occurrence)?
    is_system_generated = models.BooleanField(default=False)
 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        db_table = "taxonomy_tag_relationship"
        constraints = [
            models.UniqueConstraint(
                fields=["from_tag", "to_tag", "relationship_type"],
                name="uq_tagrel_from_to_type"
            ),
            models.CheckConstraint(
                check=~models.Q(from_tag=models.F("to_tag")),
                name="ck_tagrel_no_self_relationship"
            ),
        ]
        indexes = [
            models.Index(fields=["from_tag", "relationship_type", "-strength"]),
            models.Index(fields=["to_tag", "relationship_type"]),
        ]
 
    def clean(self):
        if self.from_tag_id and self.to_tag_id and self.from_tag_id == self.to_tag_id:
            raise ValidationError("A tag cannot have a relationship with itself.")
 
    def __str__(self):
        return f"{self.from_tag.title} --{self.relationship_type}--> {self.to_tag.title}"
 
 
class TagSourceType(models.TextChoices):
    SUBJECT              = "SUBJECT",              "Subject"
    QUESTIONNAIRE        = "QUESTIONNAIRE",         "Questionnaire"
    QUESTION              = "QUESTION",              "Question"
    CAREER_PSYCHOMETRIC   = "CAREER_PSYCHOMETRIC",   "Career Psychometric Test"
    MANUAL                = "MANUAL",                "Manually Curated"
    SYSTEM_INFERRED       = "SYSTEM_INFERRED",       "System Inferred"
 
 
class TagSourceMetadata(models.Model):
    """
    Provenance tracking: which upstream object caused this Tag to exist
    or to be considered evidence for scoring, and how confident we are
    in that link.
 
    Uses a GenericForeignKey rather than one FK per source type, because
    the source list will keep growing (new assessment types, new
    psychometric batteries) and we don't want a schema migration every
    time a new evidence source is added.
 
    `source_type` is kept as an explicit denormalized CharField
    alongside the GenericForeignKey purely so this table stays
    queryable/filterable without joining through ContentType — it must
    always match content_type.model in practice (enforced in clean()).
    """
    tag = models.ForeignKey(
        "core.Tag", on_delete=models.CASCADE,
        related_name="source_metadata"
    )
 
    source_type = models.CharField(max_length=30, choices=TagSourceType.choices, db_index=True)
 
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    source = GenericForeignKey("content_type", "object_id")
 
    confidence = models.DecimalField(
        max_digits=5, decimal_places=4, default=1.0,
        help_text="0.0-1.0: confidence that this source genuinely evidences the tag"
    )
 
    created_at = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "taxonomy_tag_source_metadata"
        constraints = [
            models.UniqueConstraint(
                fields=["tag", "content_type", "object_id"],
                name="uq_tagsource_tag_content_object"
            )
        ]
        indexes = [
            models.Index(fields=["tag", "-confidence"]),
            models.Index(fields=["content_type", "object_id"]),
        ]
 
    def __str__(self):
        return f"{self.tag.title} <- {self.source_type} #{self.object_id}"