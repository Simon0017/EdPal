from django.db import models
from django.utils.text import slugify

class Institution(models.Model):
    code    = models.CharField(max_length=20, unique=True)
    name    = models.CharField(max_length=255, db_index=True)
    slug    = models.SlugField(max_length=255, unique=True)
    type    = models.CharField(
        max_length=30,
        choices=[("PUBLIC_UNIVERSITY","Public University"),
                 ("PRIVATE_UNIVERSITY","Private University"),
                 ("TECHNICAL","Technical Institute")],
        db_index=True
    )
    website = models.URLField(blank=True,null=True)
    country = models.CharField(max_length=100, default="Kenya", db_index=True)

    class Meta:
        db_table = "careers_institution"

    def save(self,  *args, **kwargs):
        if self.pk:
            old_name = type(self).objects.get(pk=self.pk).name
            if old_name != self.name:
                self.slug = slugify(self.name)
        else:
            self.slug = slugify(self.name)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Institution: {self.name.title()}, Type: {self.type}"


class Career(models.Model):
    """
    Occupation/career path. Distinct from Course.
    A career (Medicine) can be reached via multiple courses.
    Tags connect careers to assessment dimensions.
    """
    code        = models.CharField(max_length=20, unique=True)
    title       = models.CharField(max_length=255, db_index=True)
    slug        = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    sector      = models.CharField(max_length=100, db_index=True)
    tags        = models.ManyToManyField(
        "core.Tag",
        through="careers.CareerTag",
        related_name="careers"
    )

    class Meta:
        db_table = "careers_career"
    
    def save(self,  *args, **kwargs):
        if self.pk:
            old_title = type(self).objects.get(pk=self.pk).title
            if old_title != self.title:
                self.slug = slugify(self.title)
        else:
            self.slug = slugify(self.title)

        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Career: {self.title.title()} : {self.code}"


class CareerTag(models.Model):
    """Through model — carries recommendation_weight."""
    career               = models.ForeignKey("careers.Career", on_delete=models.CASCADE)
    tag                  = models.ForeignKey("core.Tag", on_delete=models.CASCADE)
    recommendation_weight = models.DecimalField(
        max_digits=5, decimal_places=4, default=1.0,
        help_text="How strongly this tag predicts success in this career"
    )

    class Meta:
        db_table = "careers_career_tag"
        constraints = [
            models.UniqueConstraint(fields=["career","tag"], name="uq_careertag")
        ]


class Course(models.Model):
    """
    Degree/diploma programme.
    Linked to a career, offered by an institution.
    """
    code    = models.CharField(max_length=20, unique=True)
    title          = models.CharField(max_length=255, db_index=True)
    slug           = models.SlugField(max_length=255, unique=True)
    description    = models.TextField(blank=True)
    qualification  = models.CharField(
        max_length=30,
        choices=[("DEGREE","Degree"),("DIPLOMA","Diploma"),("CERTIFICATE","Certificate")]
    )
    career         = models.ForeignKey(
        "careers.Career", on_delete=models.SET_NULL,
        null=True, related_name="courses"
    )
    institution    = models.ForeignKey(
        "careers.Institution", on_delete=models.CASCADE,
        related_name="courses"
    )
    duration_years = models.PositiveSmallIntegerField(default=4)

    class Meta:
        db_table = "careers_course"

    def save(self,  *args, **kwargs):
        if self.pk:
            old_title = type(self).objects.get(pk=self.pk).title
            if old_title != self.title:
                self.slug = slugify(self.title)
        else:
            self.slug = slugify(self.title)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Course: {self.title.title()} : {self.code}"

class CutoffCluster(models.Model):
    """
    cutoff points vary by cluster (subject combination) and year.
    Separate rows per year allows trend analysis.
    """
    course         = models.ForeignKey(
        "careers.Course", on_delete=models.CASCADE,
        related_name="cutoff_clusters"
    )
    cluster_number = models.PositiveSmallIntegerField()
    cutoff_points  = models.DecimalField(max_digits=5, decimal_places=3)
    year           = models.PositiveSmallIntegerField(db_index=True)

    class Meta:
        db_table = "careers_cutoff_cluster"
        constraints = [
            models.UniqueConstraint(
                fields=["course", "cluster_number", "year"],
                name="uq_cutoff_course_cluster_year"
            )
        ]

    def __str__(self):
        return f"Course: {self.course.title}, Points: {self.cutoff_points}"

class SubjectRequirement(models.Model):
    """
    Per-course subject requirement with minimum grade.
    Normalised — no ArrayField, no JSON blob.
    """
    course         = models.ForeignKey(
        "careers.Course", on_delete=models.CASCADE,
        related_name="subject_requirements"
    )
    subject        = models.ForeignKey(
        "accounts.Subject", on_delete=models.PROTECT
    )
    requirement_type = models.CharField(
        max_length=20,
        choices=[("COMPULSORY","Compulsory"),("ALTERNATIVE","Alternative"),("OPTIONAL","Optional")]
    )
    minimum_grade  = models.CharField(max_length=5, blank=True)  # C+, B, etc.

    class Meta:
        db_table = "careers_subject_requirement"
        constraints = [
            models.UniqueConstraint(
                fields=["course","subject"],
                name="uq_subjreq_course_subject"
            )
        ]

    def __str__(self):
        return f"Course: {self.course.title}, Subject: {self.subject.code}, Min Grade {self.minimum_grade}"