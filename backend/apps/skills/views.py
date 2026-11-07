from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework.permissions import AllowAny

from apps.analysis.serializers import SkillSerializer

from .models import Category, Skill


@extend_schema(
    tags=["Skills"],
    summary="Skill catalogue",
    description='For autocomplete. `search` matches names and aliases ("js" finds JavaScript).',
    parameters=[
        OpenApiParameter("search", str),
        OpenApiParameter("category", str, enum=Category.values),
    ],
)
class SkillListView(generics.ListAPIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    serializer_class = SkillSerializer
    filter_backends = ()

    def get_queryset(self):
        queryset = Skill.objects.all()
        if term := self.request.query_params.get("search", "").strip():
            queryset = queryset.filter(
                Q(name__icontains=term) | Q(aliases__alias__icontains=term.lower())
            ).distinct()
        if category := self.request.query_params.get("category"):
            queryset = queryset.filter(category=category)
        return queryset.order_by("name")
