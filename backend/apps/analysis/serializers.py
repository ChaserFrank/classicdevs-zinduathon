from rest_framework import serializers

from apps.skills.models import Skill

from .models import ClaimedSkill

# --- Skill card (brief 7.1). Documentation only: the card is built by cards.build_card(). ---
# Field names are already camelCase here so the schema matches the JSON exactly (incl. hasCI).


class CardProfileSerializer(serializers.Serializer):
    username = serializers.CharField()
    name = serializers.CharField(allow_null=True)
    avatarUrl = serializers.URLField()
    verifiedOwner = serializers.BooleanField()


class SubScoreValueSerializer(serializers.Serializer):
    value = serializers.IntegerField(min_value=0, max_value=20)
    reason = serializers.CharField()


class CardSubScoresSerializer(serializers.Serializer):
    consistency = SubScoreValueSerializer()
    iteration = SubScoreValueSerializer()
    quality = SubScoreValueSerializer()
    breadth = SubScoreValueSerializer()
    ownership = SubScoreValueSerializer()


class CardRepoSerializer(serializers.Serializer):
    name = serializers.CharField()
    url = serializers.URLField()
    commits = serializers.IntegerField()
    firstCommit = serializers.DateTimeField()
    lastCommit = serializers.DateTimeField()
    hasTests = serializers.BooleanField()
    hasCI = serializers.BooleanField()


class CardSkillSerializer(serializers.Serializer):
    name = serializers.CharField()
    category = serializers.ChoiceField(choices=["Language", "Framework", "Practice", "Tool"])
    label = serializers.ChoiceField(choices=["Strong", "Moderate", "Emerging", "Unverified"])
    evidence = serializers.FloatField()
    repos = CardRepoSerializer(many=True)


class CardClaimSerializer(serializers.Serializer):
    skill = serializers.CharField()
    status = serializers.ChoiceField(choices=["Verified", "Partly", "Unverified"])


class CardFlagSerializer(serializers.Serializer):
    type = serializers.ChoiceField(
        choices=["one_shot_dump", "unexplained_bulk", "tutorial_clone", "unverified_claim"]
    )
    repo = serializers.CharField(required=False)
    reason = serializers.CharField()


class CardSerializer(serializers.Serializer):
    username = serializers.CharField()
    profile = CardProfileSerializer()
    signalScore = serializers.IntegerField(min_value=0, max_value=100)
    subScores = CardSubScoresSerializer()
    skills = CardSkillSerializer(many=True)
    claims = CardClaimSerializer(many=True)
    flags = CardFlagSerializer(many=True)
    aiSummary = serializers.CharField()
    reposAnalysed = serializers.IntegerField()
    commitsAnalysed = serializers.IntegerField()
    analysedAt = serializers.DateTimeField()


# --- Analyses ---


class AnalysisCreateSerializer(serializers.Serializer):
    github_login = serializers.RegexField(
        r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$",
        required=False,
        help_text="Admins only: the GitHub login to analyse. Job seekers always analyse their own.",
    )
    force = serializers.BooleanField(default=False, help_text="Ignore a result under 24 h old.")


class AnalysisStartedSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()


class AnalysisDetailSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    github_login = serializers.CharField()
    status = serializers.ChoiceField(choices=["queued", "running", "completed", "failed"])
    progress_step = serializers.IntegerField(
        help_text="1 reading repos · 2 reading commits · 3 finding skills · 4 scoring"
    )
    error_code = serializers.CharField(allow_blank=True)
    error_message = serializers.CharField(allow_blank=True)
    signal_score = serializers.IntegerField(allow_null=True)
    created_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField(allow_null=True)
    card = CardSerializer(allow_null=True)
    tips = serializers.ListField(
        child=serializers.CharField(), help_text="Owner and admins only; empty for others."
    )


class AnalysisListItemSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="public_id")
    github_login = serializers.CharField()
    status = serializers.CharField()
    signal_score = serializers.IntegerField(allow_null=True)
    sub_scores = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField(allow_null=True)

    def get_sub_scores(self, obj) -> dict[str, int]:
        return {s.key: s.value for s in obj.subscores.all()}


# --- Claimed skills and catalogue ---


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ("name", "slug", "category")


class ClaimedSkillSerializer(serializers.ModelSerializer):
    skill = SkillSerializer(allow_null=True)

    class Meta:
        model = ClaimedSkill
        fields = ("raw_text", "skill", "position")


class ClaimedSkillsSerializer(serializers.Serializer):
    skills = ClaimedSkillSerializer(many=True, read_only=True)


class ClaimedSkillsUpdateSerializer(serializers.Serializer):
    skills = serializers.ListField(
        child=serializers.CharField(max_length=80, trim_whitespace=True),
        max_length=ClaimedSkill.MAX_PER_USER,
        allow_empty=True,
        help_text="What you list on your CV, in order (max 12). Replaces the current list.",
    )

    def validate_skills(self, value):
        seen, unique = set(), []
        for text in value:
            text = " ".join(text.split())
            if text and text.lower() not in seen:
                seen.add(text.lower())
                unique.append(text)
        return unique
