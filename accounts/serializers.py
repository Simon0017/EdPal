from django.contrib.auth.models import User
from rest_framework import serializers

from .models import UserProfile, CareerPreference, Subject, ProfileSubject


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ["id", "code", "name", "slug", "category", "is_compulsory"]
        read_only_fields = ["slug"]

    def validate_code(self, value):
        value = value.strip().upper()
        qs = Subject.objects.filter(code=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "A subject with this code already exists."
            )
        return value


class ProfileSubjectSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    subject_id = serializers.PrimaryKeyRelatedField(
        queryset=Subject.objects.all(), source="subject", write_only=True
    )

    class Meta:
        model = ProfileSubject
        fields = ["id", "subject", "subject_id", "grade", "is_active"]


class ProfileSubjectWriteSerializer(serializers.ModelSerializer):
    """Used when creating/updating a ProfileSubject for a given profile."""

    class Meta:
        model = ProfileSubject
        fields = ["id", "subject", "grade", "is_active"]

    def validate(self, attrs):
        profile = self.context.get("profile")
        subject = attrs.get("subject")

        if profile and subject:
            qs = ProfileSubject.objects.filter(profile=profile, subject=subject)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"subject": "This subject is already on your profile."}
                )
        return attrs

    def create(self, validated_data):
        profile = self.context["profile"]
        return ProfileSubject.objects.create(profile=profile, **validated_data)



class CareerPreferenceSerializer(serializers.ModelSerializer):
    # Nested read; write via career_id
    career_id = serializers.IntegerField(write_only=True)
    career_name = serializers.CharField(source="career.name", read_only=True)

    class Meta:
        model = CareerPreference
        fields = ["id", "career_id", "career_name", "rank"]

    def validate_rank(self, value):
        if not (1 <= value <= 4):
            raise serializers.ValidationError(
                "Rank must be between 1 and 4 (KUCCPS aligned)."
            )
        return value

    def validate(self, attrs):
        profile = self.context.get("profile")
        rank = attrs.get("rank")
        career_id = attrs.get("career_id")

        if profile:
            qs = CareerPreference.objects.filter(profile=profile)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.filter(rank=rank).exists():
                raise serializers.ValidationError(
                    {"rank": f"You already have a career at rank {rank}."}
                )
            if qs.filter(career_id=career_id).exists():
                raise serializers.ValidationError(
                    {"career_id": "This career is already in your preferences."}
                )
        return attrs

    def create(self, validated_data):
        profile = self.context["profile"]
        return CareerPreference.objects.create(profile=profile, **validated_data)


class UserProfileSerializer(serializers.ModelSerializer):
    """Full read serializer — used for retrieve / list."""

    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    full_name = serializers.SerializerMethodField()
    completion_percentage = serializers.IntegerField(read_only=True)
    subjects = ProfileSubjectSerializer(
        source="profilesubject_set", many=True, read_only=True
    )
    career_preferences = CareerPreferenceSerializer(many=True, read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "username",
            "email",
            "full_name",
            "date_of_birth",
            "about_me",
            "avatar_url",
            "completion_percentage",
            "subjects",
            "career_preferences",
        ]

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    def get_avatar_url(self, obj):
        request = self.context.get("request")
        if obj.avatar and request:
            return request.build_absolute_uri(obj.avatar.url)
        return None


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """Write serializer — only mutable profile fields."""

    class Meta:
        model = UserProfile
        fields = ["date_of_birth", "about_me", "avatar"]

    def validate_avatar(self, value):
        if value:
            max_mb = 2
            if value.size > max_mb * 1024 * 1024:
                raise serializers.ValidationError(
                    f"Avatar must be smaller than {max_mb} MB."
                )
            allowed = ["image/jpeg", "image/png", "image/webp"]
            if hasattr(value, "content_type") and value.content_type not in allowed:
                raise serializers.ValidationError(
                    "Only JPEG, PNG, and WebP images are accepted."
                )
        return value


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "password", "password_confirm"]

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        UserProfile.objects.create(user=user)
        return user