from django.db import models
from django.utils.text import slugify


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
