from django.http import Http404
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.enums import UserRole
from apps.accounts.models import User
from apps.support.enums import SupportTicketPriority, SupportTicketStatus
from apps.support.selectors import (
    get_admin_ticket,
    get_my_ticket,
    list_admin_tickets,
    list_my_tickets,
)
from apps.support.serializers import (
    SupportTicketAdminSerializer,
    SupportTicketAdminUpdateSerializer,
    SupportTicketCreateSerializer,
    SupportTicketSerializer,
)
from apps.support.use_cases.answer_ticket import UNSET, answer_ticket
from apps.support.use_cases.open_ticket import open_ticket
from config.pagination import DefaultPagination


class IsStudentOrTeacher(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in {UserRole.STUDENT, UserRole.TEACHER}
        )


class IsAdminRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == UserRole.ADMIN
        )


def _paginate(request, queryset, serializer_class):
    paginator = DefaultPagination()
    page = paginator.paginate_queryset(queryset, request)
    serializer = serializer_class(page, many=True)
    return paginator.get_paginated_response(serializer.data)


class MyTicketListCreateView(APIView):
    permission_classes = [IsStudentOrTeacher]

    def get(self, request):
        ticket_status = request.query_params.get("status")
        if ticket_status and ticket_status not in SupportTicketStatus.values:
            raise DRFValidationError({"status": "Status inválido."})
        qs = list_my_tickets(user=request.user, status=ticket_status)
        return _paginate(request, qs, SupportTicketSerializer)

    def post(self, request):
        serializer = SupportTicketCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = open_ticket(
            actor=request.user,
            title=serializer.validated_data["title"],
            description=serializer.validated_data["description"],
        )
        return Response(
            SupportTicketSerializer(ticket).data,
            status=status.HTTP_201_CREATED,
        )


class MyTicketDetailView(APIView):
    permission_classes = [IsStudentOrTeacher]

    def get(self, request, ticket_id):
        ticket = get_my_ticket(user=request.user, ticket_id=ticket_id)
        if ticket is None:
            raise Http404
        return Response(SupportTicketSerializer(ticket).data)


class AdminTicketListView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        ticket_status = request.query_params.get("status")
        if ticket_status and ticket_status not in SupportTicketStatus.values:
            raise DRFValidationError({"status": "Status inválido."})

        priority = request.query_params.get("priority")
        if priority and priority not in SupportTicketPriority.values:
            raise DRFValidationError({"priority": "Prioridade inválida."})

        assigned_to_raw = request.query_params.get("assigned_to")
        assigned_to = None
        if assigned_to_raw is not None and assigned_to_raw != "":
            try:
                assigned_to = int(assigned_to_raw)
            except ValueError as exc:
                raise DRFValidationError(
                    {"assigned_to": "Informe um ID numérico válido."}
                ) from exc

        search = request.query_params.get("search")
        qs = list_admin_tickets(
            status=ticket_status,
            priority=priority,
            assigned_to=assigned_to,
            search=search,
        )
        return _paginate(request, qs, SupportTicketAdminSerializer)


class AdminTicketDetailView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request, ticket_id):
        ticket = get_admin_ticket(ticket_id=ticket_id)
        if ticket is None:
            raise Http404
        return Response(SupportTicketAdminSerializer(ticket).data)

    def patch(self, request, ticket_id):
        ticket = get_admin_ticket(ticket_id=ticket_id)
        if ticket is None:
            raise Http404

        serializer = SupportTicketAdminUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        assigned_to = UNSET
        if "assigned_to" in data:
            if data["assigned_to"] is None:
                assigned_to = None
            else:
                assigned_to = User.objects.filter(pk=data["assigned_to"]).first()
                if assigned_to is None:
                    raise DRFValidationError({"assigned_to": "Usuário não encontrado."})

        updated = answer_ticket(
            actor=request.user,
            ticket=ticket,
            status=data.get("status", UNSET),
            priority=data.get("priority", UNSET),
            support_response=data.get("support_response", UNSET),
            assigned_to=assigned_to,
        )
        return Response(SupportTicketAdminSerializer(updated).data)
