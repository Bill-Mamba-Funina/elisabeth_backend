from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone


# ============================================================
# CLIENT
# ============================================================

class Client(models.Model):
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=50)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


# ============================================================
# SALLE
# ============================================================

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from rest_framework.decorators import (
    action,
    api_view,
    permission_classes,
)

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

# ============================================================
# CALENDRIER
# ============================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def calendar_view(request, year, month):
    """
    Retourne les réservations d'un mois donné.

    Exemple :
    GET /api/calendar/2026/9/
    """

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

                "guest_count": reservation.guest_count,

                "total_amount": str(
                    reservation.total_amount
                ),

                "paid_amount": str(
                    reservation.paid_amount
                ),

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


# ============================================================
# SERVICE
# ============================================================

class Service(models.Model):
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True, null=True)

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


# ============================================================
# MATERIEL
# ============================================================

class Material(models.Model):
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True, null=True)

    quantity_available = models.PositiveIntegerField(default=0)

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


# ============================================================
# RESERVATION
# ============================================================

class Reservation(models.Model):

    class Status(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente"
        CONFIRMEE = "CONFIRMEE", "Confirmée"
        EN_COURS = "EN_COURS", "En cours"
        TERMINEE = "TERMINEE", "Terminée"
        CLOTUREE = "CLOTUREE", "Clôturée"
        ANNULEE = "ANNULEE", "Annulée"

    class PaymentStatus(models.TextChoices):
        NON_PAYE = "NON_PAYE", "Non payé"
        PARTIEL = "PARTIEL", "Partiel"
        PAYE = "PAYE", "Payé"

    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,
        related_name="reservations"
    )

    hall = models.ForeignKey(
        Hall,
        on_delete=models.PROTECT,
        related_name="reservations"
    )

    reservation_number = models.CharField(
        max_length=50,
        unique=True,
        blank=True
    )

    event_type = models.CharField(max_length=150)

    event_date = models.DateField()

    start_time = models.TimeField()
    end_time = models.TimeField()

    guest_count = models.PositiveIntegerField(default=0)

    description = models.TextField(blank=True, null=True)
    observations = models.TextField(blank=True, null=True)

    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    paid_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    remaining_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.NON_PAYE
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.EN_ATTENTE
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_reservations"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-event_date", "start_time"]

    def __str__(self):
        return f"{self.reservation_number} - {self.client.full_name}"

    def calculate_payment_status(self):
        if self.paid_amount <= 0:
            return self.PaymentStatus.NON_PAYE

        if self.paid_amount >= self.total_amount:
            return self.PaymentStatus.PAYE

        return self.PaymentStatus.PARTIEL

    def recalculate_financials(self):
        confirmed_total = self.payments.filter(
            status=Payment.Status.CONFIRME
        ).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")

        self.paid_amount = confirmed_total

        self.remaining_amount = max(
            self.total_amount - self.paid_amount,
            Decimal("0.00")
        )

        self.payment_status = self.calculate_payment_status()

    def clean(self):
        if self.start_time >= self.end_time:
            raise ValidationError(
                "L'heure de fin doit être supérieure à l'heure de début."
            )

        if self.total_amount < 0:
            raise ValidationError(
                "Le montant total ne peut pas être négatif."
            )

        conflicting_reservations = Reservation.objects.filter(
            hall=self.hall,
            event_date=self.event_date,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time,
        ).exclude(pk=self.pk).exclude(
            status__in=[
                self.Status.ANNULEE,
                self.Status.TERMINEE,
                self.Status.CLOTUREE,
            ]
        )

        if conflicting_reservations.exists():
            raise ValidationError(
                "Cette salle est déjà réservée pour cette période."
            )

    def save(self, *args, **kwargs):
        if not self.reservation_number:
            year = timezone.now().year

            last_reservation = (
                Reservation.objects
                .filter(reservation_number__startswith=f"RES-{year}-")
                .order_by("-id")
                .first()
            )

            number = 1

            if last_reservation:
                try:
                    number = (
                        int(last_reservation.reservation_number.split("-")[-1])
                        + 1
                    )
                except (ValueError, IndexError):
                    number = self.__class__.objects.filter(
                        reservation_number__startswith=f"RES-{year}-"
                    ).count() + 1

            self.reservation_number = f"RES-{year}-{number:04d}"

        if self.pk:
            self.recalculate_financials()
        else:
            self.remaining_amount = self.total_amount
            self.payment_status = self.PaymentStatus.NON_PAYE

        super().save(*args, **kwargs)


# ============================================================
# SERVICES D'UNE RESERVATION
# ============================================================

class ReservationService(models.Model):
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="reservation_services"
    )

    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name="reservation_services"
    )

    quantity = models.PositiveIntegerField(default=1)

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.unit_price:
            self.unit_price = self.service.unit_price

        self.total_price = self.unit_price * self.quantity

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.service.name} - {self.reservation}"


# ============================================================
# MATERIEL D'UNE RESERVATION
# ============================================================

class ReservationMaterial(models.Model):
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="reservation_materials"
    )

    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name="reservation_materials"
    )

    quantity = models.PositiveIntegerField(default=1)

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.unit_price:
            self.unit_price = self.material.unit_price

        self.total_price = self.unit_price * self.quantity

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.material.name} - {self.reservation}"


# ============================================================
# COMPTES FINANCIERS
# ============================================================

class FinancialAccount(models.Model):

    class AccountType(models.TextChoices):
        CAISSE = "CAISSE", "Caisse"
        BANQUE = "BANQUE", "Banque"
        MOBILE_MONEY = "MOBILE_MONEY", "Mobile Money"

    name = models.CharField(max_length=150)
    account_type = models.CharField(
        max_length=30,
        choices=AccountType.choices
    )

    balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00")
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} - {self.balance}"


# ============================================================
# PAIEMENTS
# ============================================================

class Payment(models.Model):

    class Method(models.TextChoices):
        ESPECES = "ESPECES", "Espèces"
        VIREMENT = "VIREMENT_BANCAIRE", "Virement bancaire"
        MOBILE_MONEY = "MOBILE_MONEY", "Mobile Money"
        CARTE = "CARTE", "Carte"
        CHEQUE = "CHEQUE", "Chèque"
        AUTRE = "AUTRE", "Autre"

    class Status(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente"
        CONFIRME = "CONFIRME", "Confirmé"
        ANNULE = "ANNULE", "Annulé"
        REMBOURSE = "REMBOURSE", "Remboursé"

    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.PROTECT,
        related_name="payments"
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    payment_date = models.DateTimeField(default=timezone.now)

    method = models.CharField(
        max_length=30,
        choices=Method.choices
    )

    reference = models.CharField(
        max_length=150,
        blank=True,
        null=True
    )

    operator = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    financial_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="payments"
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CONFIRME
    )

    receipt_pdf = models.FileField(
        upload_to="payments/receipts/",
        blank=True,
        null=True
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_payments"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date"]

    def __str__(self):
        return f"{self.reservation.reservation_number} - {self.amount}"

    def clean(self):
        if self.amount <= 0:
            raise ValidationError(
                "Le montant du paiement doit être supérieur à zéro."
            )

        if self.financial_account.account_type == FinancialAccount.AccountType.CAISSE:
            if self.method != self.Method.ESPECES:
                raise ValidationError(
                    "La caisse physique ne peut recevoir que les paiements en espèces."
                )

        if self.financial_account.account_type == FinancialAccount.AccountType.BANQUE:
            if self.method != self.Method.VIREMENT:
                raise ValidationError(
                    "Le compte bancaire doit être associé à un virement bancaire."
                )

        if self.financial_account.account_type == FinancialAccount.AccountType.MOBILE_MONEY:
            if self.method != self.Method.MOBILE_MONEY:
                raise ValidationError(
                    "Le compte Mobile Money doit être associé à un paiement Mobile Money."
                )


# ============================================================
# MOUVEMENTS FINANCIERS
# ============================================================

class CashMovement(models.Model):

    class MovementType(models.TextChoices):
        ENTREE = "ENTREE", "Entrée"
        SORTIE = "SORTIE", "Sortie"
        TRANSFERT = "TRANSFERT", "Transfert"
        CORRECTION = "CORRECTION", "Correction"
        REMBOURSEMENT = "REMBOURSEMENT", "Remboursement"

    account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="movements"
    )

    movement_type = models.CharField(
        max_length=30,
        choices=MovementType.choices
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2
    )

    description = models.CharField(max_length=255)

    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movements"
    )

    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="financial_movements"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_movements"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.movement_type} - {self.amount}"


# ============================================================
# DEPENSES
# ============================================================

class Expense(models.Model):

    category = models.CharField(max_length=150)

    description = models.TextField()

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    expense_date = models.DateTimeField(default=timezone.now)

    financial_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="expenses"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_expenses"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.category} - {self.amount}"


# ============================================================
# CONTRAT / DOCUMENT
# ============================================================

class Contract(models.Model):
    reservation = models.OneToOneField(
        Reservation,
        on_delete=models.CASCADE,
        related_name="contract"
    )

    file = models.FileField(
        upload_to="contracts/"
    )

    signed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    def __str__(self):
        return f"Contrat - {self.reservation.reservation_number}"


# ============================================================
# NOTIFICATIONS
# ============================================================

class Notification(models.Model):

    class NotificationType(models.TextChoices):
        RESERVATION_CREATED = "RESERVATION_CREATED", "Nouvelle réservation"
        RESERVATION_CONFIRMED = "RESERVATION_CONFIRMED", "Réservation confirmée"
        RESERVATION_CANCELLED = "RESERVATION_CANCELLED", "Réservation annulée"
        PAYMENT_RECEIVED = "PAYMENT_RECEIVED", "Paiement reçu"
        PAYMENT_PARTIAL = "PAYMENT_PARTIAL", "Paiement partiel"
        PAYMENT_COMPLETED = "PAYMENT_COMPLETED", "Paiement complet"
        PAYMENT_REFUNDED = "PAYMENT_REFUNDED", "Paiement remboursé"
        EXPENSE_CREATED = "EXPENSE_CREATED", "Dépense enregistrée"
        EVENT_UPCOMING = "EVENT_UPCOMING", "Événement imminent"
        SYSTEM = "SYSTEM", "Système"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications"
    )

    notification_type = models.CharField(
        max_length=50,
        choices=NotificationType.choices
    )

    title = models.CharField(max_length=200)

    message = models.TextField()

    is_read = models.BooleanField(default=False)

    read_at = models.DateTimeField(
        null=True,
        blank=True
    )

    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications"
    )

    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title