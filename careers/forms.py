from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import (
    Institution,
    Career,
    CareerTag,
    Course,
    CutoffCluster,
    SubjectRequirement,
    CareerPsychometricTest,
    CareerPsychometricQuestion,
    CareerPsychometricChoice,
    CareerPsychometricResponse,
    CareerPsychometricResponseAnswer,
    CareerRecommendation,
    QuestionType,
)



class InstitutionForm(forms.ModelForm):
    """
    Create / update an institution.
    slug is auto-managed by model.save() so it's excluded.
    code is uppercased and uniqueness-checked here.
    """

    class Meta:
        model = Institution
        fields = ["code", "name", "type", "website", "country"]

    def clean_code(self):
        code = self.cleaned_data.get("code", "").strip().upper()
        qs = Institution.objects.filter(code=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("An institution with this code already exists.")
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
    Create / update a course.
    slug is auto-managed by model.save().
    """

    class Meta:
        model = Course
        fields = [
            "code",
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

    def clean_code(self):
        code = self.cleaned_data.get("code", "").strip().upper()
        qs = Course.objects.filter(code=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("A course with this code already exists.")
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
        if value is None:
            raise ValidationError("Cluster number is required.")
        return value

    def clean_cutoff_points(self):
        value = self.cleaned_data.get("cutoff_points")
        if value is None:
            raise ValidationError("Cutoff points are required.")
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

    # TODO consider adding more robust grade validation (e.g. using a mapping of grades to numeric values)
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

     
class CareerPsychometricTestForm(forms.ModelForm):
    """
    Create / update a psychometric test.
    slug is auto-managed by model.save() so it's excluded from fields.
    total_questions is updated programmatically, so it is also excluded.
    """

    class Meta:
        model = CareerPsychometricTest
        fields = [
            "name",
            "description",
            "instructions",
            "category",
            "estimated_duration",
            "is_active",
            "is_premium",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "instructions": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_estimated_duration(self):
        value = self.cleaned_data.get("estimated_duration")
        if value is not None and value <= 0:
            raise ValidationError("Estimated duration must be greater than 0 minutes.")
        return value


class CareerPsychometricQuestionForm(forms.ModelForm):
    """
    Create / update a psychometric question.
    Validates the structure of type-specific metadata configurations.
    """

    class Meta:
        model = CareerPsychometricQuestion
        fields = [
            "questionnaire",
            "order",
            "prompt",
            "help_text",
            "question_type",
            "required",
            "is_active",
            "metadata",
        ]
        widgets = {
            "prompt": forms.Textarea(attrs={"rows": 3}),
            "help_text": forms.Textarea(attrs={"rows": 2}),
        }

    def clean_metadata(self):
        metadata = self.cleaned_data.get("metadata")
        question_type = self.cleaned_data.get("question_type")

        # If metadata is not a dictionary, raise an error
        if not isinstance(metadata, dict):
            raise ValidationError("Metadata must be a valid JSON object.")

        # Optional schema-level checks depending on the question_type
        if question_type == QuestionType.NUMERIC:
            required_keys = {"min", "max"}
            if not required_keys.issubset(metadata.keys()):
                raise ValidationError(
                    "Numeric metadata must contain at least 'min' and 'max' constraints."
                )
            try:
                float(metadata["min"])
                float(metadata["max"])
            except (ValueError, TypeError):
                raise ValidationError("'min' and 'max' values in metadata must be numbers.")
                
        elif question_type in [QuestionType.SHORT_TEXT, QuestionType.LONG_TEXT]:
            if "max_length" in metadata:
                try:
                    int(metadata["max_length"])
                except (ValueError, TypeError):
                    raise ValidationError("'max_length' in metadata must be an integer.")

        return metadata


class BaseCareerPsychometricQuestionFormSet(forms.BaseModelFormSet):
    """
    Validates a batch of questions for a questionnaire
    to ensure no duplicate question order coordinates within the batch.
    """

    def clean(self):
        if any(self.errors):
            return
        
        seen_orders = []
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get("DELETE", False):
                order = form.cleaned_data.get("order")
                if order in seen_orders:
                    raise ValidationError(
                        f"Duplicate display order '{order}' detected in this batch of questions."
                    )
                seen_orders.append(order)


class CareerPsychometricChoiceForm(forms.ModelForm):
    """
    Create / update a psychometric choice option.
    Ensures choices are only added to eligible question types.
    """

    class Meta:
        model = CareerPsychometricChoice
        fields = ["question", "label", "value", "order"]

    def clean(self):
        cleaned = super().clean()
        question = cleaned.get("question")
        value = cleaned.get("value")

        if question:
            # Prevent adding choices to text or numeric questions
            choice_types = [
                QuestionType.SINGLE_CHOICE,
                QuestionType.MULTIPLE_CHOICE,
                QuestionType.MULTI_SELECT,
            ]
            if question.question_type not in choice_types:
                raise ValidationError(
                    f"Choices can only be added to questions of type: "
                    f"{', '.join(choice_types)}."
                )

            # Check value uniqueness within the same question
            qs = CareerPsychometricChoice.objects.filter(question=question, value=value)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(
                    {"value": f"The option value '{value}' already exists for this question."}
                )

        return cleaned


class CareerPsychometricResponseForm(forms.ModelForm):
    """
    Create / update a test attempt response record.
    Forces completed_at timestamps to match up with COMPLETED status.
    """

    class Meta:
        model = CareerPsychometricResponse
        fields = ["user", "questionnaire", "status", "completed_at"]

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("status")
        completed_at = cleaned.get("completed_at")

        # Automatically manage completed_at coherence
        if status == "COMPLETED" and not completed_at:
            cleaned["completed_at"] = timezone.now()
        elif status != "COMPLETED":
            cleaned["completed_at"] = None

        return cleaned


class CareerPsychometricResponseAnswerForm(forms.ModelForm):
    """
    Enforces application-layer rule:
    Only one of (selected_choices, text_answer, numeric_answer) should be populated.
    Also validates that input values match the specified question type constraints.
    """

    class Meta:
        model = CareerPsychometricResponseAnswer
        fields = ["response", "question", "selected_choices", "text_answer", "numeric_answer"]

    def clean(self):
        cleaned = super().clean()
        question = cleaned.get("question")
        selected_choices = cleaned.get("selected_choices")
        text_answer = cleaned.get("text_answer", "").strip()
        numeric_answer = cleaned.get("numeric_answer")

        if question:
            q_type = question.question_type

            # Rule 1: Validate ONLY relevant fields are filled
            has_choices = bool(selected_choices)
            has_text = bool(text_answer)
            has_numeric = numeric_answer is not None

            # Count how many answer storage types were filled out
            provided_types_count = sum([has_choices, has_text, has_numeric])

            if question.required and provided_types_count == 0:
                raise ValidationError("This question is required and must have an answer.")

            if provided_types_count > 1:
                raise ValidationError(
                    "An answer can only populate one output type "
                    "(selected choices, text answer, or numeric answer)."
                )

            # Rule 2: Type matching validations
            if q_type in [QuestionType.SINGLE_CHOICE, QuestionType.MULTIPLE_CHOICE, QuestionType.MULTI_SELECT]:
                if not has_choices and question.required:
                    raise ValidationError({"selected_choices": "You must select at least one choice."})

            elif q_type in [QuestionType.SHORT_TEXT, QuestionType.LONG_TEXT]:
                if not has_text and question.required:
                    raise ValidationError({"text_answer": "This text field cannot be left blank."})
                
                # Check optional max length limits stored inside the metadata
                max_len = question.metadata.get("max_length")
                if max_len and len(text_answer) > int(max_len):
                    raise ValidationError(
                        {"text_answer": f"Answer exceeds the maximum length of {max_len} characters."}
                    )

            elif q_type == QuestionType.NUMERIC:
                if not has_numeric and question.required:
                    raise ValidationError({"numeric_answer": "You must provide a numeric answer."})
                
                if has_numeric:
                    # Check metadata ranges if defined
                    q_min = question.metadata.get("min")
                    q_max = question.metadata.get("max")
                    if q_min is not None and numeric_answer < q_min:
                        raise ValidationError(
                            {"numeric_answer": f"Value cannot be lower than {q_min}."}
                        )
                    if q_max is not None and numeric_answer > q_max:
                        raise ValidationError(
                            {"numeric_answer": f"Value cannot be higher than {q_max}."}
                        )

        return cleaned


class CareerRecommendationForm(forms.ModelForm):
    """
    Admin-facing form to validate or manually review recommendation records.
    """

    class Meta:
        model = CareerRecommendation
        fields = [
            "user",
            "response",
            "processing_status",
            "recommendation_summary",
            "recommendation_details",
            "confidence_score",
            "algorithm_version",
            "email_sent",
            "email_sent_at",
        ]
        widgets = {
            "recommendation_summary": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_confidence_score(self):
        score = self.cleaned_data.get("confidence_score")
        if score is not None and not (0 <= score <= 100):
            raise ValidationError("Confidence score must be between 0.00 and 100.00.")
        return score

    def clean_recommendation_details(self):
        details = self.cleaned_data.get("recommendation_details")
        if not isinstance(details, dict):
            raise ValidationError("Recommendation details must be a valid JSON object.")
        return details  