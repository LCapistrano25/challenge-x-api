from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin
from apps.accounts.selectors import list_email_domains
from apps.accounts.serializers import (
    EmailDomainCreateSerializer,
    EmailDomainFilterSerializer,
    EmailDomainUpdateSerializer,
)
from apps.accounts.use_cases.create_email_domain import create_email_domain
from apps.accounts.use_cases.update_email_domain import update_email_domain


def _serialize_domain(domain) -> dict:
    return {
        "id": domain.id,
        "name": domain.name,
        "role": domain.role,
        "active": domain.active,
    }


class EmailDomainListCreateView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        filters = EmailDomainFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        domains = list_email_domains(**filters.validated_data)
        return Response(
            [_serialize_domain(domain) for domain in domains],
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = EmailDomainCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        domain = create_email_domain(actor=request.user, **serializer.validated_data)
        return Response(_serialize_domain(domain), status=status.HTTP_201_CREATED)


class EmailDomainDetailView(APIView):
    permission_classes = [IsAdmin]

    def patch(self, request, domain_id: int):
        serializer = EmailDomainUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        domain = update_email_domain(
            actor=request.user,
            domain_id=domain_id,
            **serializer.validated_data,
        )
        return Response(_serialize_domain(domain), status=status.HTTP_200_OK)
