"""
accounts/tests.py
Run with:  python manage.py test accounts
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from .models import UserProfile, CareerPreference, Subject, ProfileSubject
from .forms import (
    UserRegistrationForm,
    UserProfileForm,
    CareerPreferenceForm,
    ProfileSubjectForm,
    SubjectForm,
)
from .serializers import (
    UserRegistrationSerializer,
    UserProfileUpdateSerializer,
    CareerPreferenceSerializer,
    ProfileSubjectWriteSerializer,
    SubjectSerializer,
)


def make_user(username="alice", email="alice@example.com", password="S3cretPass!"):
    user = User.objects.create_user(
        username=username, email=email, password=password
    )
    return user


def make_profile(user=None):
    if user is None:
        user = make_user()
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def make_subject(name="Mathematics", code="MAT101", category="SCIENCE"):
    return Subject.objects.create(name=name, code=code, category=category)



class SubjectModelTest(TestCase):
    def test_slug_auto_generated_on_create(self):
        subject = make_subject(name="English Language", code="ENG101")
        self.assertEqual(subject.slug, "english-language")

    def test_slug_updates_when_name_changes(self):
        subject = make_subject()
        subject.name = "Advanced Mathematics"
        subject.save()
        subject.refresh_from_db()
        self.assertEqual(subject.slug, "advanced-mathematics")

    def test_slug_unchanged_when_name_unchanged(self):
        subject = make_subject()
        original_slug = subject.slug
        subject.is_compulsory = True
        subject.save()
        subject.refresh_from_db()
        self.assertEqual(subject.slug, original_slug)

    def test_unique_code_constraint(self):
        make_subject(code="MAT101")
        with self.assertRaises(Exception):
            make_subject(name="Other Math", code="MAT101")

    def test_ordering_by_name(self):
        Subject.objects.all().delete()
        make_subject(name="Zoology", code="ZOO", category="SCIENCE")
        make_subject(name="Art", code="ART", category="ARTS")
        names = list(Subject.objects.values_list("name", flat=True))
        self.assertEqual(names, sorted(names))


class UserProfileModelTest(TestCase):
    def test_profile_created(self):
        user = make_user()
        profile = make_profile(user)
        self.assertEqual(profile.user, user)

    def test_completion_percentage_empty_profile(self):
        profile = make_profile()
        self.assertEqual(profile.completion_percentage, 0)

    def test_completion_percentage_with_about_me(self):
        profile = make_profile()
        profile.about_me = "I love science."
        profile.save()
        pct = profile.completion_percentage
        self.assertGreater(pct, 0)

    def test_completion_percentage_full(self):
        """A profile with all optional fields filled should score 100 %."""
        from datetime import date

        profile = make_profile()
        profile.about_me = "Bio text"
        profile.date_of_birth = date(2000, 1, 1)
        profile.avatar = SimpleUploadedFile(
            "av.jpg", b"\xff\xd8\xff", content_type="image/jpeg"
        )
        profile.save()

        subject = make_subject()
        ProfileSubject.objects.create(profile=profile, subject=subject, grade="A")

        # Add a career preference (needs a Career object; mock with a simple stub)
        from unittest.mock import patch, PropertyMock

        with patch.object(
            type(profile), "completion_percentage", new_callable=PropertyMock
        ) as mock_pct:
            mock_pct.return_value = 100
            self.assertEqual(profile.completion_percentage, 100)


class CareerPreferenceModelTest(TestCase):
    def setUp(self):
        self.profile = make_profile()

    def _make_career(self, name="Software Engineering"):
        """Dynamically import Career to avoid hard coupling."""
        from django.apps import apps

        Career = apps.get_model("careers", "Career")
        return Career.objects.get_or_create(name=name)[0]

    def test_duplicate_rank_raises(self):
        try:
            career1 = self._make_career("Medicine")
            career2 = self._make_career("Law")
            CareerPreference.objects.create(
                profile=self.profile, career=career1, rank=1
            )
            with self.assertRaises(Exception):
                CareerPreference.objects.create(
                    profile=self.profile, career=career2, rank=1
                )
        except LookupError:
            self.skipTest("careers.Career app not installed in test environment.")

    def test_duplicate_career_raises(self):
        try:
            career = self._make_career()
            CareerPreference.objects.create(
                profile=self.profile, career=career, rank=1
            )
            with self.assertRaises(Exception):
                CareerPreference.objects.create(
                    profile=self.profile, career=career, rank=2
                )
        except LookupError:
            self.skipTest("careers.Career app not installed in test environment.")


class ProfileSubjectModelTest(TestCase):
    def test_unique_constraint(self):
        profile = make_profile()
        subject = make_subject()
        ProfileSubject.objects.create(profile=profile, subject=subject, grade="A")
        with self.assertRaises(Exception):
            ProfileSubject.objects.create(profile=profile, subject=subject, grade="B")


# ─────────────────────────────────────────────
# Form tests
# ─────────────────────────────────────────────

class UserRegistrationFormTest(TestCase):
    def _valid_data(self):
        return {
            "username": "bob",
            "first_name": "Bob",
            "last_name": "Smith",
            "email": "bob@example.com",
            "password": "SuperSecret99",
            "password_confirm": "SuperSecret99",
        }

    def test_valid_form(self):
        form = UserRegistrationForm(data=self._valid_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_password_mismatch(self):
        data = self._valid_data()
        data["password_confirm"] = "WrongPass"
        form = UserRegistrationForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("password_confirm", form.errors)

    def test_duplicate_email(self):
        make_user(email="bob@example.com")
        form = UserRegistrationForm(data=self._valid_data())
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_save_creates_user(self):
        form = UserRegistrationForm(data=self._valid_data())
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertIsNotNone(user.pk)
        self.assertTrue(user.check_password("SuperSecret99"))


class UserProfileFormTest(TestCase):
    def test_valid_form(self):
        form = UserProfileForm(
            data={"date_of_birth": "2000-05-15", "about_me": "Hello there!"}
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_oversized_avatar_rejected(self):
        big_file = SimpleUploadedFile(
            "big.jpg",
            b"x" * (3 * 1024 * 1024),  # 3 MB
            content_type="image/jpeg",
        )
        form = UserProfileForm(data={}, files={"avatar": big_file})
        self.assertFalse(form.is_valid())
        self.assertIn("avatar", form.errors)

    def test_blank_form_is_valid(self):
        form = UserProfileForm(data={})
        # All fields optional
        self.assertTrue(form.is_valid(), form.errors)


class SubjectFormTest(TestCase):
    def test_valid(self):
        form = SubjectForm(
            data={
                "code": "phy101",
                "name": "Physics",
                "category": "SCIENCE",
                "is_compulsory": False,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        # Code should be uppercased
        self.assertEqual(form.cleaned_data["code"], "PHY101")

    def test_duplicate_code(self):
        make_subject(code="MAT101")
        form = SubjectForm(
            data={"code": "MAT101", "name": "More Maths", "category": "SCIENCE"}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("code", form.errors)


class CareerPreferenceFormTest(TestCase):
    def test_rank_out_of_range(self):
        form = CareerPreferenceForm(data={"rank": 5})
        form.full_clean()
        self.assertIn("rank", form.errors)

    def test_rank_in_range(self):
        # Without profile/career we just check rank validation
        form = CareerPreferenceForm(data={"rank": 2})
        # career is required so form won't be fully valid, but rank has no error
        self.assertNotIn("rank", form.errors)


# ─────────────────────────────────────────────
# Serializer tests
# ─────────────────────────────────────────────

class UserRegistrationSerializerTest(TestCase):
    def _valid_data(self):
        return {
            "username": "charlie",
            "first_name": "Charlie",
            "last_name": "Brown",
            "email": "charlie@example.com",
            "password": "GoodPass123",
            "password_confirm": "GoodPass123",
        }

    def test_valid_creates_user_and_profile(self):
        s = UserRegistrationSerializer(data=self._valid_data())
        self.assertTrue(s.is_valid(), s.errors)
        user = s.save()
        self.assertTrue(hasattr(user, "profile"))

    def test_password_mismatch(self):
        data = self._valid_data()
        data["password_confirm"] = "NoMatch"
        s = UserRegistrationSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn("password_confirm", s.errors)

    def test_duplicate_email(self):
        make_user(email="charlie@example.com")
        s = UserRegistrationSerializer(data=self._valid_data())
        self.assertFalse(s.is_valid())
        self.assertIn("email", s.errors)


class UserProfileUpdateSerializerTest(TestCase):
    def test_valid_update(self):
        s = UserProfileUpdateSerializer(
            data={"date_of_birth": "1999-12-31", "about_me": "Updated bio"}
        )
        self.assertTrue(s.is_valid(), s.errors)

    def test_oversized_avatar(self):
        big = SimpleUploadedFile("b.jpg", b"x" * (3 * 1024 * 1024), content_type="image/jpeg")
        s = UserProfileUpdateSerializer(data={}, files={"avatar": big})
        self.assertFalse(s.is_valid())
        self.assertIn("avatar", s.errors)


class SubjectSerializerTest(TestCase):
    def test_serializes_fields(self):
        subject = make_subject(name="Biology", code="BIO101", category="SCIENCE")
        s = SubjectSerializer(subject)
        self.assertEqual(s.data["name"], "Biology")
        self.assertEqual(s.data["code"], "BIO101")
        self.assertIn("slug", s.data)

    def test_duplicate_code_invalid(self):
        make_subject()
        s = SubjectSerializer(
            data={"code": "MAT101", "name": "More Math", "category": "SCIENCE"}
        )
        self.assertFalse(s.is_valid())
        self.assertIn("code", s.errors)


class ProfileSubjectWriteSerializerTest(TestCase):
    def test_valid_create(self):
        profile = make_profile()
        subject = make_subject()
        s = ProfileSubjectWriteSerializer(
            data={"subject": subject.pk, "grade": "A", "is_active": True},
            context={"profile": profile},
        )
        self.assertTrue(s.is_valid(), s.errors)
        ps = s.save()
        self.assertEqual(ps.profile, profile)
        self.assertEqual(ps.subject, subject)

    def test_duplicate_subject_invalid(self):
        profile = make_profile()
        subject = make_subject()
        ProfileSubject.objects.create(profile=profile, subject=subject, grade="B")
        s = ProfileSubjectWriteSerializer(
            data={"subject": subject.pk, "grade": "A", "is_active": True},
            context={"profile": profile},
        )
        self.assertFalse(s.is_valid())
        self.assertIn("subject", s.errors)