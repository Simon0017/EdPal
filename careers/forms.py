from django import forms
from django.core.exceptions import ValidationError

from .models import (
    Institution,
    Career,
    CareerTag,
    Course,
    CutoffCluster,
    SubjectRequirement,
)



class InstitutionForm(forms.ModelForm):
    """
    Create / update an institution.
    slug is auto-managed by model.save() so it's excluded.
    code is uppercased and uniqueness-checked here.
    """

    class Meta:
        model = Institution
        fields = ["code", "name", "type", "website"]

    def clean_code(self):
        code = self.cleaned_data.get("code", "").strip().upper()
        qs = Institution.objects.filter(code=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("An institution with this KUCCPS code already exists.")
        return code

    def clean_website(self):
        url = self.cleaned_data.get("website", "").strip()
        if url and not (url.startswith("http://") or url.startswith("https://")):
            raise ValidationError("Website must start with http:// or https://.")
        return url




class CareerForm(forms.ModelForm):
    """
    Create / update a career path.
    slug is auto-managed by model.save().
    """

    class Meta:
        model = Career
        fields = ["code", "title", "description", "sector"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_code(self):
        code = self.cleaned_data.get("code", "").strip().upper()
        qs = Career.objects.filter(code=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("A career with this code already exists.")
        return code


class CareerTagForm(forms.ModelForm):
    """Through-model form attaching a tag to a career with a recommendation weight."""

    class Meta:
        model = CareerTag
        fields = ["career", "tag", "recommendation_weight"]

    def clean_recommendation_weight(self):
        value = self.cleaned_data.get("recommendation_weight")
        if value is not None and not (0 <= value <= 1):
            raise ValidationError("Recommendation weight must be between 0.0 and 1.0.")
        return value

    def clean(self):
        cleaned = super().clean()
        career = cleaned.get("career")
        tag = cleaned.get("tag")

        if career and tag:
            qs = CareerTag.objects.filter(career=career, tag=tag)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(
                    {"tag": "This tag is already linked to the selected career."}
                )
        return cleaned


class CourseForm(forms.ModelForm):
    """
    Create / update a KUCCPS course.
    slug is auto-managed by model.save().
    """

    class Meta:
        model = Course
        fields = [
            "kuccps_code",
            "title",
            "description",
            "qualification",
            "career",
            "institution",
            "duration_years",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_kuccps_code(self):
        code = self.cleaned_data.get("kuccps_code", "").strip().upper()
        qs = Course.objects.filter(kuccps_code=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("A course with this KUCCPS code already exists.")
        return code

    def clean_duration_years(self):
        value = self.cleaned_data.get("duration_years")
        if value is not None and not (1 <= value <= 10):
            raise ValidationError("Duration must be between 1 and 10 years.")
        return value




class CutoffClusterForm(forms.ModelForm):
    """
    Create / update a cutoff entry.
    UniqueConstraint on (course, cluster_number, year) is enforced here
    in addition to the DB constraint so the user gets a friendly message.
    """

    class Meta:
        model = CutoffCluster
        fields = ["course", "cluster_number", "cutoff_points", "year"]

    def clean_cluster_number(self):
        value = self.cleaned_data.get("cluster_number")
        if value is not None and not (1 <= value <= 4):
            raise ValidationError("Cluster number must be between 1 and 4 (KUCCPS clusters).")
        return value

    def clean_cutoff_points(self):
        value = self.cleaned_data.get("cutoff_points")
        if value is not None and not (0 <= value <= 84):
            # KUCCPS maximum is 84 points (A in 7 subjects × 12 pts each)
            raise ValidationError("Cutoff points must be between 0 and 84.")
        return value

    def clean_year(self):
        value = self.cleaned_data.get("year")
        if value is not None and not (2000 <= value <= 2100):
            raise ValidationError("Enter a valid 4-digit year.")
        return value

    def clean(self):
        cleaned = super().clean()
        course = cleaned.get("course")
        cluster_number = cleaned.get("cluster_number")
        year = cleaned.get("year")

        if course and cluster_number and year:
            qs = CutoffCluster.objects.filter(
                course=course, cluster_number=cluster_number, year=year
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(
                    f"A cutoff entry for cluster {cluster_number} in {year} "
                    "already exists for this course."
                )
        return cleaned


class BaseCutoffClusterFormSet(forms.BaseModelFormSet):
    """
    Validates a batch of cutoff entries (e.g. all 4 clusters for one year)
    to ensure no duplicate cluster numbers within the set.
    """

    def clean(self):
        if any(self.errors):
            return
        seen = []
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get("DELETE", False):
                key = (
                    form.cleaned_data.get("cluster_number"),
                    form.cleaned_data.get("year"),
                )
                if key in seen:
                    raise ValidationError(
                        f"Duplicate cluster {key[0]} for year {key[1]} in this batch."
                    )
                seen.append(key)



class SubjectRequirementForm(forms.ModelForm):
    """
    Attach a subject requirement to a course.
    Validates minimum_grade against the KCSE grade scale and
    prevents duplicate subject entries per course.
    """

    VALID_GRADES = ["A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "E"]

    class Meta:
        model = SubjectRequirement
        fields = ["course", "subject", "requirement_type", "minimum_grade"]

    def clean_minimum_grade(self):
        grade = self.cleaned_data.get("minimum_grade", "").strip()
        if grade and grade not in self.VALID_GRADES:
            raise ValidationError(
                f"Enter a valid KCSE grade. Valid grades: {', '.join(self.VALID_GRADES)}."
            )
        return grade

    def clean(self):
        cleaned = super().clean()
        course = cleaned.get("course")
        subject = cleaned.get("subject")

        if course and subject:
            qs = SubjectRequirement.objects.filter(course=course, subject=subject)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(
                    {"subject": "This subject already has a requirement for the selected course."}
                )
        return cleaned


class BaseSubjectRequirementFormSet(forms.BaseModelFormSet):
    """
    Validates a course's full subject requirement set:
    - At least one COMPULSORY requirement.
    - No duplicate subjects within the set.
    """

    def clean(self):
        if any(self.errors):
            return

        active = [
            f for f in self.forms
            if f.cleaned_data and not f.cleaned_data.get("DELETE", False)
        ]

        subjects = []
        has_compulsory = False

        for form in active:
            subject = form.cleaned_data.get("subject")
            req_type = form.cleaned_data.get("requirement_type")

            if subject in subjects:
                raise ValidationError(
                    f'Subject "{subject}" appears more than once in this requirement set.'
                )
            subjects.append(subject)

            if req_type == "COMPULSORY":
                has_compulsory = True

        if active and not has_compulsory:
            raise ValidationError(
                "At least one subject requirement must be marked as COMPULSORY."
            )