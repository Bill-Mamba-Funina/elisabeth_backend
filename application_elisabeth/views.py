from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from .models import (
    Client,
    Hall,
    Service,
    Material,
    Reservation,
    ReservationService,
    ReservationMaterial,
    FinancialAccount,
    Payment,
    CashMovement,
    Expense,
    Contract,
    Notification,
)

from .serializers import (
    ClientSerializer,
    HallSerializer,
    ServiceSerializer,
    MaterialSerializer,
    ReservationSerializer,
    ReservationServiceSerializer,
    ReservationMaterialSerializer,
    FinancialAccountSerializer,
    PaymentSerializer,
    CashMovementSerializer,
    ExpenseSerializer,
    ContractSerializer,
    NotificationSerializer,
)

from .services.pdf_service import generate_payment_receipt_pdf


# ============================================================
# CLIENTS
# ============================================================

class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all().order_by("full_name")
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated]


# ============================================================
# SALLES
# ============================================================

class HallViewSet(viewsets.ModelViewSet):
    queryset = Hall.objects.all().order_by("name")
    serializer_class = HallSerializer
    permission_classes = [IsAuthenticated]


# ============================================================
# SERVICES
# ============================================================

class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.all().order_by("name")
    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated]


# ============================================================
# MATERIEL
# ============================================================

class MaterialViewSet(viewsets.ModelViewSet):
    queryset = Material.objects.all().order_by("name")
    serializer_class = MaterialSerializer
    permission_classes = [IsAuthenticated]


# ============================================================
# RESERVATIONS
# ============================================================

class ReservationViewSet(viewsets.ModelViewSet):
    queryset = (
        Reservation.objects
        .select_related("client", "hall")
        .prefetch_related("payments")
        .order_by("-event_date")
    )

    serializer_class = ReservationSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        reservation = serializer.save(
            created_by=self.request.user
        )

        Notification.objects.create(
            user=self.request.user,
            notification_type=Notification.NotificationType.RESERVATION_CREATED,
            title="Nouvelle réservation",
            message=(
                f"La réservation {reservation.reservation_number} "
                f"a été créée."
            ),
            reservation=reservation,
        )

    def perform_update(self, serializer):
        reservation = serializer.save()

        if reservation.status == Reservation.Status.CONFIRMEE:
            Notification.objects.create(
                user=self.request.user,
                notification_type=(
                    Notification.NotificationType.RESERVATION_CONFIRMED
                ),
                title="Réservation confirmée",
                message=(
                    f"La réservation {reservation.reservation_number} "
                    f"a été confirmée."
                ),
                reservation=reservation,
            )

    @action(
        detail=True,
        methods=["post"],
        url_path="confirmer"
    )
    def confirmer(self, request, pk=None):
        reservation = self.get_object()

        if reservation.status == Reservation.Status.ANNULEE:
            return Response(
                {
                    "detail": (
                        "Une réservation annulée ne peut pas être confirmée."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        reservation.status = Reservation.Status.CONFIRMEE
        reservation.save()

        Notification.objects.create(
            user=request.user,
            notification_type=(
                Notification.NotificationType.RESERVATION_CONFIRMED
            ),
            title="Réservation confirmée",
            message=(
                f"La réservation {reservation.reservation_number} "
                f"est maintenant confirmée."
            ),
            reservation=reservation,
        )

        return Response(
            ReservationSerializer(
                reservation,
                context={"request": request}
            ).data
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="annuler"
    )
    def annuler(self, request, pk=None):
        reservation = self.get_object()

        reservation.status = Reservation.Status.ANNULEE
        reservation.save()

        Notification.objects.create(
            user=request.user,
            notification_type=(
                Notification.NotificationType.RESERVATION_CANCELLED
            ),
            title="Réservation annulée",
            message=(
                f"La réservation {reservation.reservation_number} "
                f"a été annulée."
            ),
            reservation=reservation,
        )

        return Response(
            ReservationSerializer(reservation).data
        )


# ============================================================
# RESERVATION SERVICES
# ============================================================

class ReservationServiceViewSet(viewsets.ModelViewSet):
    queryset = ReservationService.objects.select_related(
        "reservation",
        "service"
    ).all()

    serializer_class = ReservationServiceSerializer
    permission_classes = [IsAuthenticated]


# ============================================================
# RESERVATION MATERIEL
# ============================================================

class ReservationMaterialViewSet(viewsets.ModelViewSet):
    queryset = ReservationMaterial.objects.select_related(
        "reservation",
        "material"
    ).all()

    serializer_class = ReservationMaterialSerializer
    permission_classes = [IsAuthenticated]


# ============================================================
# COMPTES FINANCIERS
# ============================================================

class FinancialAccountViewSet(viewsets.ModelViewSet):
    queryset = FinancialAccount.objects.all()
    serializer_class = FinancialAccountSerializer
    permission_classes = [IsAuthenticated]

    @action(
        detail=True,
        methods=["get"],
        url_path="solde"
    )
    def solde(self, request, pk=None):
        account = self.get_object()

        return Response(
            {
                "id": account.id,
                "name": account.name,
                "account_type": account.account_type,
                "balance": account.balance,
            }
        )


# ============================================================
# PAIEMENTS
# ============================================================

class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.select_related(
        "reservation",
        "reservation__client",
        "financial_account",
        "created_by",
    ).all()

    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def perform_create(self, serializer):

        payment = serializer.save(
            created_by=self.request.user
        )

        reservation = payment.reservation
        account = payment.financial_account

        # ----------------------------------------------------
        # 1. RECALCUL DE LA RESERVATION
        # ----------------------------------------------------

        reservation.recalculate_financials()
        reservation.save(
            update_fields=[
                "paid_amount",
                "remaining_amount",
                "payment_status",
                "updated_at",
            ]
        )

        # ----------------------------------------------------
        # 2. MOUVEMENT FINANCIER
        # ----------------------------------------------------

        CashMovement.objects.create(
            account=account,
            movement_type=CashMovement.MovementType.ENTREE,
            amount=payment.amount,
            description=(
                f"Paiement {reservation.reservation_number} "
                f"- {payment.amount}"
            ),
            payment=payment,
            reservation=reservation,
            created_by=self.request.user,
        )

        # ----------------------------------------------------
        # 3. MISE A JOUR DU COMPTE
        # ----------------------------------------------------

        account.balance += payment.amount
        account.save(update_fields=["balance"])

        # ----------------------------------------------------
        # 4. NOTIFICATION
        # ----------------------------------------------------

        if reservation.payment_status == Reservation.PaymentStatus.PAYE:
            notification_type = (
                Notification.NotificationType.PAYMENT_COMPLETED
            )

            title = "Paiement complet"

            message = (
                f"Le paiement de la réservation "
                f"{reservation.reservation_number} "
                f"est maintenant complet."
            )

        else:
            notification_type = (
                Notification.NotificationType.PAYMENT_PARTIAL
            )

            title = "Paiement reçu"

            message = (
                f"Un paiement de {payment.amount} a été reçu "
                f"pour la réservation "
                f"{reservation.reservation_number}. "
                f"Reste à payer : {reservation.remaining_amount}."
            )

        Notification.objects.create(
            user=self.request.user,
            notification_type=notification_type,
            title=title,
            message=message,
            reservation=reservation,
            payment=payment,
        )

        # ----------------------------------------------------
        # 5. GENERATION DU PDF DU PAIEMENT
        # ----------------------------------------------------

        try:
            pdf_file = generate_payment_receipt_pdf(payment)

            if pdf_file:
                payment.receipt_pdf.save(
                    f"recu-{payment.id}.pdf",
                    pdf_file,
                    save=True,
                )

        except Exception as error:
            # Le paiement reste enregistré même si
            # la génération du PDF échoue.
            print(
                f"Erreur génération reçu PDF : {error}"
            )

    @action(
        detail=True,
        methods=["get"],
        url_path="recu"
    )
    def recu(self, request, pk=None):
        payment = self.get_object()

        if not payment.receipt_pdf:
            return Response(
                {
                    "detail": "Aucun reçu PDF n'est disponible."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "payment_id": payment.id,
                "receipt_pdf": request.build_absolute_uri(
                    payment.receipt_pdf.url
                ),
            }
        )


# ============================================================
# DEPENSES
# ============================================================

class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.select_related(
        "financial_account",
        "created_by",
    ).all()

    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def perform_create(self, serializer):

        expense = serializer.save(
            created_by=self.request.user
        )

        account = expense.financial_account

        if account.balance < expense.amount:
            raise ValueError(
                "Solde insuffisant pour effectuer cette dépense."
            )

        account.balance -= expense.amount
        account.save(update_fields=["balance"])

        CashMovement.objects.create(
            account=account,
            movement_type=CashMovement.MovementType.SORTIE,
            amount=expense.amount,
            description=expense.description,
            created_by=self.request.user,
        )

        Notification.objects.create(
            user=self.request.user,
            notification_type=(
                Notification.NotificationType.EXPENSE_CREATED
            ),
            title="Dépense enregistrée",
            message=(
                f"Une dépense de {expense.amount} "
                f"a été enregistrée."
            ),
        )


# ============================================================
# MOUVEMENTS FINANCIERS
# ============================================================

class CashMovementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CashMovement.objects.select_related(
        "account",
        "payment",
        "reservation",
        "created_by",
    ).all()

    serializer_class = CashMovementSerializer
    permission_classes = [IsAuthenticated]


# ============================================================
# CONTRATS
# ============================================================

class ContractViewSet(viewsets.ModelViewSet):
    queryset = Contract.objects.select_related(
        "reservation",
        "reservation__client",
    ).all()

    serializer_class = ContractSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(
            uploaded_by=self.request.user
        )


# ============================================================
# NOTIFICATIONS
# ============================================================

class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(
            user=self.request.user
        ).select_related(
            "reservation",
            "payment",
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="lire"
    )
    def lire(self, request, pk=None):
        notification = self.get_object()

        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(
            update_fields=[
                "is_read",
                "read_at",
            ]
        )

        return Response(
            NotificationSerializer(notification).data
        )



# ============================================================
# CALENDRIER
# ============================================================

def calendar_view(request, year, month):
    """
    Retourne les réservations d'un mois donné.

    Exemple :
    GET /api/calendar/2026/9/
    """

    if request.method != "GET":
        return JsonResponse(
            {
                "detail": "Méthode non autorisée."
            },
            status=405,
        )

    # Vérification du mois
    if month < 1 or month > 12:
        return JsonResponse(
            {
                "detail": "Le mois doit être compris entre 1 et 12."
            },
            status=400,
        )

    reservations = (
        Reservation.objects
        .filter(
            event_date__year=year,
            event_date__month=month,
        )
        .select_related(
            "client",
            "hall",
        )
        .order_by(
            "event_date",
            "start_time",
        )
    )

    data = []

    for reservation in reservations:
        data.append(
            {
                "id": reservation.id,
                "reservation_number": reservation.reservation_number,
                "client": (
                    reservation.client.full_name
                    if reservation.client
                    else None
                ),
                "hall": (
                    reservation.hall.name
                    if reservation.hall
                    else None
                ),
                "event_type": reservation.event_type,
                "date": (
                    reservation.event_date.isoformat()
                    if reservation.event_date
                    else None
                ),
                "start_time": (
                    reservation.start_time.strftime("%H:%M")
                    if reservation.start_time
                    else None
                ),
                "end_time": (
                    reservation.end_time.strftime("%H:%M")
                    if reservation.end_time
                    else None
                ),
                "guests_count": reservation.guests_count,
                "total_amount": str(reservation.total_amount),
                "paid_amount": str(reservation.paid_amount),
                "remaining_amount": str(
                    reservation.remaining_amount
                ),
                "payment_status": reservation.payment_status,
                "status": reservation.status,
            }
        )

    return JsonResponse(
        {
            "year": year,
            "month": month,
            "count": len(data),
            "results": data,
        }
    )