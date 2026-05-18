from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import UserProfile, CareerPreference, Subject, ProfileSubject


class UserRegistrationForm(forms.ModelForm):
    """Handles core User creation alongside profile bootstrap."""

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Password"}),
        min_length=8,
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Confirm password"}),
        label="Confirm Password",
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email"]

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        pw = cleaned.get("password")
        pw_confirm = cleaned.get("password_confirm")
        if pw and pw_confirm and pw != pw_confirm:
            self.add_error("password_confirm", "Passwords do not match.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class UserProfileForm(forms.ModelForm):
    """Edit the extended UserProfile fields."""

    class Meta:
        model = UserProfile
        fields = ["date_of_birth", "about_me", "avatar"]
        widgets = {
            "date_of_birth": forms.DateInput(
                attrs={"type": "date"}, format="%Y-%m-%d"
            ),
            "about_me": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar:
            max_size_mb = 2
            if avatar.size > max_size_mb * 1024 * 1024:
                raise ValidationError(
                    f"Avatar file size must be under {max_size_mb} MB."
                )
            allowed_types = ["image/jpeg", "image/png", "image/webp"]
            if hasattr(avatar, "content_type") and avatar.content_type not in allowed_types:
                raise ValidationError(
                    "Only JPEG, PNG, and WebP images are accepted."
                )
        return avatar




class CareerPreferenceForm(forms.ModelForm):
    """Single career preference entry; rank uniqueness is validated here."""

    class Meta:
        model = CareerPreference
        fields = ["career", "rank"]

    def __init__(self, *args, profile=None, **kwargs):
        self.profile = profile
        super().__init__(*args, **kwargs)

    def clean_rank(self):
        rank = self.cleaned_data.get("rank")
        if rank is not None and not (1 <= rank <= 4):
            raise ValidationError("Rank must be between 1 and 4 (KUCCPS aligned).")
        return rank

    def clean(self):
        cleaned = super().clean()
        career = cleaned.get("career")
        rank = cleaned.get("rank")

        if self.profile and career and rank:
            qs = CareerPreference.objects.filter(profile=self.profile)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.filter(rank=rank).exists():
                raise ValidationError(
                    {"rank": f"You already have a career at rank {rank}."}
                )
            if qs.filter(career=career).exists():
                raise ValidationError(
                    {"career": "This career is already in your preferences."}
                )
        return cleaned


class CareerPreferenceFormSet(forms.BaseModelFormSet):
    """Validates that a profile's full set of preferences has no rank collisions."""

    def clean(self):
        if any(self.errors):
            return
        ranks = []
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get("DELETE", False):
                rank = form.cleaned_data.get("rank")
                if rank in ranks:
                    raise ValidationError(
                        "Each career choice must have a unique rank."
                    )
                ranks.append(rank)


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ["code", "name", "category", "is_compulsory"]

    def clean_code(self):
        code = self.cleaned_data.get("code", "").strip().upper()
        qs = Subject.objects.filter(code=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("A subject with this code already exists.")
        return code


class ProfileSubjectForm(forms.ModelForm):
    """Allows a student to add/update a subject with their current grade."""

    GRADE_CHOICES = [
        ("", "— Select grade —"),
        ("A", "A"),
        ("A-", "A-"),
        ("B+", "B+"),
        ("B", "B"),
        ("B-", "B-"),
        ("C+", "C+"),
        ("C", "C"),
        ("C-", "C-"),
        ("D+", "D+"),
        ("D", "D"),
        ("D-", "D-"),
        ("E", "E"),
    ]

    grade = forms.ChoiceField(choices=GRADE_CHOICES, required=False)

    class Meta:
        model = ProfileSubject
        fields = ["subject", "grade", "is_active"]

    def __init__(self, *args, profile=None, **kwargs):
        self.profile = profile
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        subject = cleaned.get("subject")

        if self.profile and subject:
            qs = ProfileSubject.objects.filter(
                profile=self.profile, subject=subject
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(
                    {"subject": "This subject is already on your profile."}
                )
        return cleaned