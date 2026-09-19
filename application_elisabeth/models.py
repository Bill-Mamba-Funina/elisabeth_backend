from django.conf import settings
from django.db import models
from django.utils import timezone

class Client(models.Model):
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=60)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name


class Employee(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="employee_profile")
    role = models.CharField(max_length=80, blank=True, null=True)  # admin/manager/caissier/receptionniste/agent

    def __str__(self):
        return self.user.username


class Hall(models.Model):
    name = models.CharField(max_length=120, unique=True)
    capacity = models.IntegerField()
    daily_rate = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=30, default="DISPONIBLE")  # DISPONIBLE / OCCUPÉE

    def __str__(self):
        return self.name


class ReservationStatus(models.TextChoices):
    DEMANDE = "DEMANDE"
    EN_ATTENTE = "EN_ATTENTE"
    CONFIRMEE = "CONFIRMEE"
    EVENT_TERMINE = "EVENT_TERMINE"
    CLOTUREE = "CLOTUREE"
    ANNULEE = "ANNULEE"


class EventType(models.TextChoices):
    MARIAGE = "Mariage"
    ANNIVERSAIRE = "Anniversaire"
    BAPTEME = "Baptême"
    CONFERENCE = "Conférence"
    REUNION = "Réunion"
    DEUIL = "Deuil"
    AUTRE = "Autre"


class Reservation(models.Model):
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE, related_name="reservations")
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="reservations")

    event_type = models.CharField(max_length=80, choices=EventType.choices)
    event_title = models.CharField(max_length=200, blank=True, null=True)  # ex: “Mariage Dupont” (optionnel)

    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    guests_count = models.IntegerField(default=0)

    base_rate = models.DecimalField(max_digits=12, decimal_places=2)  # tarif
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deposit = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # acompte (optionnel, suivi via paiements aussi)

    status = models.CharField(max_length=30, choices=ReservationStatus.choices, default=ReservationStatus.DEMANDE)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_reservations")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total_price(self):
        # base_rate - discount (vous pouvez adapter si “tarif/jour” dépend de durée)
        return max(self.base_rate - self.discount, 0)

    @property
    def paid_total(self):
        agg = self.payments.aggregate_sum_amount()
        return agg or 0

    @property
    def remaining(self):
        return max(self.total_price - self.paid_total, 0)

    def __str__(self):
        return f"{self.hall.name} - {self.date} ({self.start_time})"


class PaymentQuerySet(models.QuerySet):
    def aggregate_sum_amount(self):
        v = self.aggregate(models.Sum("amount")).get("amount__sum")
        return v


class Payment(models.Model):
    PAYMENT_MODES = [
        ("ESPECES", "Espèces"),
        ("MOBILE_MONEY", "Mobile Money"),
        ("VIREMENT", "Virement bancaire"),
        ("CARTE", "Carte"),
        ("USD", "USD"),
        ("FC", "FC"),
    ]

    receipt_number = models.CharField(max_length=80, unique=True)
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name="payments")
    date = models.DateField(default=timezone.now)

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    mode = models.CharField(max_length=30, choices=PAYMENT_MODES)

    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="recorded_payments")
    created_at = models.DateTimeField(auto_now_add=True)

    receipt_pdf = models.FileField(upload_to="receipts/", null=True, blank=True)


    objects = PaymentQuerySet.as_manager()


class Service(models.Model):
    name = models.CharField(max_length=120, unique=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return self.name


class ReservationService(models.Model):
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name="services")
    service = models.ForeignKey(Service, on_delete=models.CASCADE)

    quantity = models.PositiveIntegerField(default=1)
    unit_price_snapshot = models.DecimalField(max_digits=12, decimal_places=2)

    contract_pdf = models.FileField(upload_to="contracts/", null=True, blank=True)

    @property
    def line_total(self):
        return self.quantity * self.unit_price_snapshot


class Material(models.Model):
    name = models.CharField(max_length=120, unique=True)
    total_available = models.IntegerField(default=0)

    def __str__(self):
        return self.name


class ReservationMaterialUsage(models.Model):
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name="materials_usage")
    material = models.ForeignKey(Material, on_delete=models.CASCADE)

    quantity_requested = models.IntegerField()
    quantity_used = models.IntegerField(null=True, blank=True)  # optionnel

    contract_pdf = models.FileField(upload_to="contracts/", null=True, blank=True)

    def __str__(self):
        return f"{self.reservation_id} - {self.material.name}"


class ExpenseCategory(models.Model):
    name = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return self.name


class Expense(models.Model):
    category = models.ForeignKey(ExpenseCategory, on_delete=models.SET_NULL, null=True, related_name="expenses")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField(default=timezone.now)

    note = models.TextField(blank=True, null=True)

    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="recorded_expenses")

    created_at = models.DateTimeField(auto_now_add=True)


class CashMovement(models.Model):
    class MovementType(models.TextChoices):
        IN = "IN"
        OUT = "OUT"

    movement_type = models.CharField(max_length=3, choices=MovementType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    date = models.DateField(default=timezone.now)
    note = models.CharField(max_length=240, blank=True, null=True)

    # facultatif: lien vers payment/expense
    payment = models.ForeignKey(Payment, null=True, blank=True, on_delete=models.SET_NULL, related_name="cash_movement")
    expense = models.ForeignKey(Expense, null=True, blank=True, on_delete=models.SET_NULL, related_name="cash_movement")

    created_at = models.DateTimeField(auto_now_add=True)


# Contrainte logique: réservation ne doit pas se chevaucher pour une même hall
# -> on la valide côté API (plus simple pour MVP)

