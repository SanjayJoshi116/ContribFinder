from factory.declarations import LazyAttribute, Sequence, SubFactory
from factory.django import DjangoModelFactory, Password
from factory.faker import Faker

from accounts.models import User
from github.models import GitHubAccount
from services.crypto import encrypt_token


class UserFactory(DjangoModelFactory[User]):
    class Meta:
        model = User
        django_get_or_create = ("username",)

    username = Sequence(lambda n: f"gh_{1000 + n}")
    display_name = Faker("name")
    password = Password(None)  # unusable, like GitHub-only users


class GitHubAccountFactory(DjangoModelFactory[GitHubAccount]):
    class Meta:
        model = GitHubAccount

    class Params:
        token = "gho_testtoken0000000000000000000000"

    user = SubFactory(UserFactory)
    github_id = Sequence(lambda n: 1000 + n)
    username = Sequence(lambda n: f"octocat{n}")
    avatar_url = "https://avatars.githubusercontent.com/u/1"
    access_token_encrypted = LazyAttribute(lambda o: encrypt_token(o.token))
