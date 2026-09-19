from django.shortcuts import render  # (inutile mais gardé si tu l'utilises ailleurs)

# Create your views here.
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q, Sum
from django.utils import timezone
from django.db import transaction

from .models import (
    Client, Hall, Reservation, Payment, Service, ReservationService,
    Material, ReservationMaterialUsage, ExpenseCategory, Expense,
    CashMovement
)
from .serializers import (
    ClientSerializer, HallSerializer, ReservationSerializer, PaymentSerializer,
    ServiceSerializer, ReservationServiceSerializer, MaterialSerializer,
    ReservationMaterialUsageSerializer, ExpenseCategorySerializer,
    ExpenseSerializer, CashMovementSerializer
)

# ✅ PDF service
from .services.pdf_service import (
    generate_receipt_pdf,
    generate_contract_pdf,
)


class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all().order_by("-created_at")
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated]


class HallViewSet(viewsets.ModelViewSet):
    queryset = Hall.objects.all().order_by("name")
    serializer_class = HallSerializer
    permission_classes = [IsAuthenticated]


def overlaps(a_start, a_end, b_start, b_end):
    # [a_start,a_end) intersects [b_start,b_end)
    return a_start < b_end and b_start < a_end


class ReservationViewSet(viewsets.ModelViewSet):
    queryset = Reservation.objects.all().select_related("hall", "client").order_by("-date", "-created_at")
    serializer_class = ReservationSerializer
    permission_classes = [IsAuthenticated]

    def _validate_no_overlap(self, hall_id, date, start_time, end_time, exclude_reservation_id=None):
        qs = Reservation.objects.filter(hall_id=hall_id, date=date)
        if exclude_reservation_id:
            qs = qs.exclude(id=exclude_reservation_id)

        for r in qs:
            if overlaps(start_time, end_time, r.start_time, r.end_time) and r.status not in ["ANNULEE", "EVENT_TERMINE", "CLOTUREE"]:
                return False, r.id
        return True, None

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        data = request.data
        hall_id = data.get("hall")
        date = data.get("date")
        start_time = data.get("start_time")
        end_time = data.get("end_time")

        ok, conflict_id = self._validate_no_overlap(hall_id, date, start_time, end_time)
        if not ok:
            return Response(
                {"detail": f"Conflit de réservation avec reservation_id={conflict_id}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save(created_by=request.user)

        # ✅ Optionnel : si créée directement en CONFIRMEE
        if obj.status == "CONFIRMEE" and not getattr(obj, "contract_pdf", None):
            pdf_file = generate_contract_pdf(obj, request)
            obj.contract_pdf.save(f"contrat_{obj.id}.pdf", pdf_file, save=True)

        return Response(self.get_serializer(obj).data, status=status.HTTP_201_CREATED)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        reservation = self.get_object()
        data = request.data

        # ✅ IMPORTANT : capturer l'ancien status AVANT serializer.save()
        old_status = reservation.status

        hall_id = data.get("hall", reservation.hall_id)
        date = data.get("date", reservation.date)
        start_time = data.get("start_time", reservation.start_time)
        end_time = data.get("end_time", reservation.end_time)

        ok, conflict_id = self._validate_no_overlap(
            hall_id, date, start_time, end_time,
            exclude_reservation_id=reservation.id
        )
        if not ok:
            return Response(
                {"detail": f"Conflit de réservation avec reservation_id={conflict_id}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.get_serializer(reservation, data=data, partial=False)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()

        # ✅ Générer contrat seulement si passage vers CONFIRMEE
        if old_status != "CONFIRMEE" and obj.status == "CONFIRMEE":
            if not getattr(obj, "contract_pdf", None):
                pdf_file = generate_contract_pdf(obj, request)
                obj.contract_pdf.save(f"contrat_{obj.id}.pdf", pdf_file, save=True)

        return Response(self.get_serializer(obj).data)


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all().select_related("reservation", "recorded_by")
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Save payment
        obj = serializer.save(recorded_by=request.user)

        # Cash IN
        CashMovement.objects.create(
            movement_type=CashMovement.MovementType.IN,
            amount=obj.amount,
            date=obj.date,
            note=f"Paiement {obj.receipt_number}",
            payment=obj
        )

        # ✅ Générer reçu PDF après chaque paiement
        if not getattr(obj, "receipt_pdf", None):
            pdf_file = generate_receipt_pdf(obj, request)
            obj.receipt_pdf.save(
                f"recu_{obj.receipt_number}_{obj.id}.pdf",
                pdf_file,
                save=True
            )

        return Response(self.get_serializer(obj).data, status=status.HTTP_201_CREATED)


class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.all().order_by("name")
    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated]


class ReservationServiceViewSet(viewsets.ModelViewSet):
    queryset = ReservationService.objects.all().select_related("reservation", "service")
    serializer_class = ReservationServiceSerializer
    permission_classes = [IsAuthenticated]


class MaterialViewSet(viewsets.ModelViewSet):
    queryset = Material.objects.all().order_by("name")
    serializer_class = MaterialSerializer
    permission_classes = [IsAuthenticated]


class ReservationMaterialUsageViewSet(viewsets.ModelViewSet):
    queryset = ReservationMaterialUsage.objects.all().select_related("reservation", "material")
    serializer_class = ReservationMaterialUsageSerializer
    permission_classes = [IsAuthenticated]


class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    queryset = ExpenseCategory.objects.all().order_by("name")
    serializer_class = ExpenseCategorySerializer
    permission_classes = [IsAuthenticated]


class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.all().select_related("category", "recorded_by").order_by("-date", "-created_at")
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data["amount"]
        date = serializer.validated_data.get("date") or timezone.now().date()
        obj = serializer.save(recorded_by=request.user)

        CashMovement.objects.create(
            movement_type=CashMovement.MovementType.OUT,
            amount=amount,
            date=date,
            note=f"Dépense {obj.category.name if obj.category else ''}".strip(),
            expense=obj
        )
        return Response(self.get_serializer(obj).data, status=status.HTTP_201_CREATED)


class CashMovementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CashMovement.objects.all().select_related("payment", "expense").order_by("-date", "-created_at")
    serializer_class = CashMovementSerializer
    permission_classes = [IsAuthenticated]


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard(request):
    today = timezone.now().date()

    weekday = today.weekday()
    start_week = today - timezone.timedelta(days=weekday)
    end_week = start_week + timezone.timedelta(days=6)

    start_month = today.replace(day=1)
    if today.month == 12:
        start_next = today.replace(year=today.year + 1, month=1, day=1)
    else:
        start_next = today.replace(month=today.month + 1, day=1)

    res_week = Reservation.objects.filter(date__range=[start_week, end_week]).exclude(status__in=["ANNULEE"])
    paid_month = Payment.objects.filter(date__gte=start_month, date__lt=start_next)
    paid_total_month = paid_month.aggregate(Sum("amount")).get("amount__sum") or 0

    res_count = Reservation.objects.filter(
        date__gte=start_week,
        date__lte=end_week,
        status__in=["DEMANDE", "EN_ATTENTE", "CONFIRMEE"]
    ).count()

    clients_active = Client.objects.count()

    cash_in = CashMovement.objects.filter(movement_type=CashMovement.MovementType.IN).aggregate(Sum("amount")).get("amount__sum") or 0
    cash_out = CashMovement.objects.filter(movement_type=CashMovement.MovementType.OUT).aggregate(Sum("amount")).get("amount__sum") or 0
    cash_balance = cash_in - cash_out

    exp_month = Expense.objects.filter(date__gte=start_month, date__lt=start_next)
    exp_total_month = exp_month.aggregate(Sum("amount")).get("amount__sum") or 0

    open_res = Reservation.objects.filter(status__in=["DEMANDE", "EN_ATTENTE", "CONFIRMEE"])
    solde = 0
    for r in open_res:
        solde += r.remaining

    alerts = []
    overdue = Reservation.objects.filter(status__in=["DEMANDE", "EN_ATTENTE", "CONFIRMEE"], date__lt=today)
    if overdue.exists():
        alerts.append("🔴 Paiements en retard")
    pending = Reservation.objects.filter(status="EN_ATTENTE")
    if pending.exists():
        alerts.append("🟠 Réservations à confirmer")

    tomorrow = today + timezone.timedelta(days=1)
    if Reservation.objects.filter(date=tomorrow, status__in=["DEMANDE", "EN_ATTENTE", "CONFIRMEE"]).exists():
        alerts.append("🟡 Événements prévus demain")

    if open_res.exists():
        alerts.append("🔵 Contrats à signer")
    if Payment.objects.filter(date=today).exists():
        alerts.append("🟢 Paiements reçus")

    return Response({
        "reservations_week": res_count,
        "revenue_month": float(paid_total_month),
        "remaining_total": float(solde),
        "events_week_count": res_week.count(),
        "active_clients": clients_active,
        "expenses_month": float(exp_total_month),
        "cash_balance": float(cash_balance),
        "alerts": alerts
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def reservations_calendar(request, year, month):
    from calendar import monthrange

    y = int(year)
    m = int(month)
    start_day, last_day = 1, monthrange(y, m)[1]
    out = []

    for d in range(start_day, last_day + 1):
        qd = timezone.datetime(y, m, d).date()
        items = Reservation.objects.filter(date=qd).select_related("hall", "client").exclude(status="ANNULEE")

        payload = []
        for r in items:
            payload.append({
                "id": r.id,
                "event_type": r.event_type,
                "title": r.event_title or r.client.full_name,
                "hall": r.hall.name,
                "start_time": str(r.start_time),
                "end_time": str(r.end_time),
                "status": r.status
            })

        out.append({"date": str(qd), "items": payload})

    return Response({"year": year, "month": month, "days": out})
