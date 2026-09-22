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

class Hall(models.Model):
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True, null=True)

    capacity = models.PositiveIntegerField(default=0)

    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


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