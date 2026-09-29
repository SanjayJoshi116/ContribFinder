from rest_framework import serializers

from repositories.models import Repository, RepositoryLanguage, RepositoryTopic

from .models import GitHubProfile


class GitHubProfileSerializer(serializers.ModelSerializer[GitHubProfile]):
    """Synced GitHub profile. The README body is not included here (Phase 3 analyses it)."""

    class Meta:
        model = GitHubProfile
        fields = [
            "login",
            "name",
            "bio",
            "company",
            "location",
            "blog",
            "avatar_url",
            "followers",
            "following",
            "public_repos",
            "github_created_at",
            "has_profile_readme",
            "synced_at",
        ]
        read_only_fields = fields


class RepositoryLanguageSerializer(serializers.ModelSerializer[RepositoryLanguage]):
    class Meta:
        model = RepositoryLanguage
        fields = ["language", "bytes"]
        read_only_fields = fields


class RepositorySerializer(serializers.ModelSerializer[Repository]):
    languages = RepositoryLanguageSerializer(many=True, read_only=True)
    topics: serializers.SlugRelatedField[RepositoryTopic] = serializers.SlugRelatedField(
        many=True, read_only=True, slug_field="topic"
    )

    class Meta:
        model = Repository
        fields = [
            "id",
            "full_name",
            "name",
            "owner_login",
            "description",
            "html_url",
            "default_branch",
            "stars",
            "forks",
            "open_issues",
            "primary_language",
            "license_spdx",
            "is_fork",
            "is_archived",
            "github_created_at",
            "github_updated_at",
            "pushed_at",
            "languages",
            "topics",
        ]
        read_only_fields = fields
