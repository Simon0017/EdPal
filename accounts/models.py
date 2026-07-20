from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from core.models import Tag

class UserProfile(models.Model):
    """
    Extended profile.
    """

    user  = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile"
    )

    date_of_birth   = models.DateField(null=True, blank=True)
    about_me        = models.TextField(null=True,blank=True)
    avatar          = models.ImageField(
        upload_to="avatars/%Y/%m/",
        null=True, blank=True
    )
    notification_settings = models.JSONField(null=True,blank=True)
    remember_me = models.BooleanField(default=False,null=True,blank=True)
    updated_at = models.DateTimeField(auto_now=True,null=True)

    # Subjects via M2M 
    subjects        = models.ManyToManyField(
        "accounts.Subject",
        through="accounts.ProfileSubject",
        related_name="profiles"
    )

    class Meta:
        db_table = "accounts_profile"

        indexes = [
            models.Index(fields=["user", "updated_at"]),
        ]
    
    def __str__(self):
        return f"{self.user.username.title()}\'s Profile"

    @property
    def completion_percentage(self) -> int:
        """Computed at runtime"""
        fields = [self.date_of_birth,
                  self.about_me, self.avatar,self.remember_me,self.notification_settings]
        
        filled = sum(1 for f in fields if f)

        has_subjects = self.subjects.exists()
        has_preferences = self.career_preferences.exists()
        total = len(fields) + 2
        return int(((filled + has_subjects + has_preferences) / total) * 100)


class CareerPreference(models.Model):
    """
    Stores a FK to the user profile storing the user career preferences
    UniqueConstraint on (profile, rank) ensures no duplicate rank positions.
    UniqueConstraint on (profile, career) ensures no duplicate career choices.
    CheckConstraint on rank ensures valid range (1-4 for KUCCPS alignment).
    """
    profile = models.ForeignKey(
        "accounts.UserProfile",
        on_delete=models.CASCADE,
        related_name="career_preferences"
    )

    career  = models.ForeignKey(
        "careers.Career",
        on_delete=models.CASCADE,
        related_name="interested_profiles"
    )

    rank    = models.PositiveSmallIntegerField(
        blank=True,
        help_text="1=First choice, 4=Fourth choice (KUCCPS aligned)"
    )

    class Meta:
        db_table = "accounts_career_preference"
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "rank"],
                name="uq_profile_career_rank"
            ),
            models.UniqueConstraint(
                fields=["profile", "career"],
                name="uq_profile_career_choice"
            ),
            models.CheckConstraint(
                check=models.Q(rank__gte=1, rank__lte=4),
                name="ck_career_preference_rank_range"
            ),
        ]
        indexes = [
            models.Index(fields=["profile", "rank"]),
        ]


class Subject(models.Model):
    """
    KCSE subject catalogue..
    Used for: profile enrollment, career subject requirements, scoring weights.
    """
    code    = models.CharField(max_length=20, unique=True,blank=True)  # e.g. "MAT101"
    name    = models.CharField(max_length=150, db_index=True)
    slug    = models.SlugField(max_length=150, unique=True,blank=True)

    category = models.CharField(
        max_length=50,
        choices=[("SCIENCE","Science"),("ARTS","Arts"),
                 ("TECHNICAL","Technical"),("LANGUAGE","Language")],
        db_index=True
    )

    is_compulsory = models.BooleanField(default=False,blank=True)

    class Meta:
        db_table = "accounts_subject"
        ordering = ["name"]

    
    def save(self,  *args, **kwargs):
        if self.pk:
            old_name = type(self).objects.get(pk=self.pk).name
            if old_name != self.name:
                self.slug = slugify(self.name)
        else:
            self.slug = slugify(self.name)
        
        # small layer to create a tag
        tag,_ = Tag.objects.update_or_create(
            title=self.name
        )

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Subject: {self.name.title()}"

class ProfileSubject(models.Model):
    """
    Through model for profile<->subject. Stores current grade/level.
    Explicit through model = richer data, better queryability.
    """
    profile  = models.ForeignKey("accounts.UserProfile", on_delete=models.CASCADE)
    subject  = models.ForeignKey("accounts.Subject", on_delete=models.CASCADE)
    grade    = models.CharField(max_length=5, blank=True)  # A, B+, C, etc.

    is_active = models.BooleanField(default=True,blank=True)

    class Meta:
        db_table = "accounts_profile_subject"
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "subject"],
                name="uq_profile_subject"
            )
        ]
