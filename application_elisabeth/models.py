from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone


# ============================================================
# CLIENT
# ============================================================
class Client(models.Model):
    full_name = models.CharField(max_length=200)
    phone = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
    )
    email = models.EmailField(
        blank=True,
        null=True,
    )
    address = models.TextField(
        blank=True,
        null=True,
    )
    notes = models.TextField(
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]
        verbose_name = "Client"
        verbose_name_plural = "Clients"

    def __str__(self):
        return f"{self.full_name} - {self.phone}"


# ============================================================
# SALLE
# ============================================================
class Hall(models.Model):
    name = models.CharField(
        max_length=150,
        unique=True,
    )
    description = models.TextField(
        blank=True,
        null=True,
    )
    capacity = models.PositiveIntegerField(
        default=0,
    )
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    is_active = models.BooleanField(
        default=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Salle"
        verbose_name_plural = "Salles"

    def __str__(self):
        return self.name


class HallImage(models.Model):
    hall = models.ForeignKey(
        Hall,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(
        upload_to="halls/images/",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return f"Image - {self.hall.name}"


class HallVideo(models.Model):
    hall = models.ForeignKey(
        Hall,
        on_delete=models.CASCADE,
        related_name="videos",
    )
    video = models.FileField(
        upload_to="halls/videos/",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return f"Vidéo - {self.hall.name}"


# ============================================================
# DEMANDE DE DEVIS
# ============================================================
class QuoteRequest(models.Model):
    class Status(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente"
        TRAITE = "TRAITE", "Traité"
        REJETE = "REJETE", "Rejeté"

    hall = models.ForeignKey(
        Hall,
        on_delete=models.CASCADE,
        related_name="quote_requests",
    )
    client_name = models.CharField(
        max_length=200,
    )
    client_email = models.EmailField()
    client_phone = models.CharField(
        max_length=50,
    )
    event_date = models.DateField()
    message = models.TextField(
        blank=True,
        null=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.EN_ATTENTE,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Demande de devis"
        verbose_name_plural = "Demandes de devis"

    def __str__(self):
        return f"Devis {self.hall.name} - {self.client_name}"


# ============================================================
# MATERIEL
# ============================================================
class Material(models.Model):
    class Etat(models.TextChoices):
        ACTIF = "ACTIF", "Actif"
        EN_REPARATION = "EN_REPARATION", "En réparation"
        ABIME = "ABIME", "Abîmé"

    name = models.CharField(
        max_length=150,
        unique=True,
    )
    description = models.TextField(
        blank=True,
        null=True,
    )
    quantity_available = models.PositiveIntegerField(
        default=0,
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    etat = models.CharField(
        max_length=30,
        choices=Etat.choices,
        default=Etat.ACTIF,
    )
    is_active = models.BooleanField(
        default=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Matériel"
        verbose_name_plural = "Matériel"

    def __str__(self):
        return self.name


# ============================================================
# PERSONNEL
# ============================================================
class Personnel(models.Model):
    class Fonction(models.TextChoices):
        GERANTE = "GERANTE", "Gérante"
        AGENT_SECURITE = "AGENT_SECURITE", "Agent de sécurité"
        DECORATEUR = "DECORATEUR", "Décorateur"
        TECHNICIEN = "TECHNICIEN", "Technicien"
        NETTOYEUR = "NETTOYEUR", "Nettoyeur"
        SERVEUR = "SERVEUR", "Serveur"
        RECEPTIONNISTE = "RECEPTIONNISTE", "Réceptionniste"
        AUTRE = "AUTRE", "Autre"

    class Statut(models.TextChoices):
        ACTIF = "ACTIF", "Actif"
        INACTIF = "INACTIF", "Inactif"

    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    telephone = models.CharField(
        max_length=30,
        blank=True,
        null=True,
    )
    email = models.EmailField(
        blank=True,
        null=True,
    )
    fonction = models.CharField(
        max_length=50,
        choices=Fonction.choices,
        default=Fonction.AUTRE,
    )
    statut = models.CharField(
        max_length=20,
        choices=Statut.choices,
        default=Statut.ACTIF,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nom", "prenom"]
        verbose_name = "Personnel"
        verbose_name_plural = "Personnel"

    def __str__(self):
        return f"{self.prenom} {self.nom}"


# ============================================================
# TARIFICATION
# ============================================================
class Tarif(models.Model):
    name = models.CharField(
        max_length=150,
        unique=True,
        verbose_name="Nom",
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Description",
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Montant",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Actif",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Tarif"
        verbose_name_plural = "Tarifs"

    def __str__(self):
        return f"{self.name} - {self.amount} $"

    def clean(self):
        super().clean()
        if self.amount is not None and self.amount < Decimal("0.00"):
            raise ValidationError("Le montant du tarif ne peut pas être négatif.")


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
        REMBOURSE = "REMBOURSE", "Remboursé"

    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    hall = models.ForeignKey(
        Hall,
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    tarif = models.ForeignKey(
        Tarif,
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    reservation_number = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
    )
    event_type = models.CharField(
        max_length=150,
    )
    event_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    guest_count = models.PositiveIntegerField(
        default=0,
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.NON_PAYE,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.EN_ATTENTE,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_reservations",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-event_date", "start_time"]
        verbose_name = "Réservation"
        verbose_name_plural = "Réservations"

    def __str__(self):
        return f"{self.reservation_number} - {self.client.full_name}"

    @property
    def total_amount(self):
        if self.tarif_id:
            return self.tarif.amount or Decimal("0.00")
        return Decimal("0.00")

    @property
    def paid_amount(self):
        total = (
            self.payments.filter(status=Payment.Status.VALIDE)
            .aggregate(total=Sum("amount"))
            .get("total")
            or Decimal("0.00")
        )
        return total

    @property
    def refunded_amount(self):
        total = (
            self.refunds.aggregate(total=Sum("amount")).get("total")
            or Decimal("0.00")
        )
        return total

    @property
    def net_paid_amount(self):
        value = self.paid_amount - self.refunded_amount
        return max(value, Decimal("0.00"))

    @property
    def remaining_amount(self):
        remaining = self.total_amount - self.net_paid_amount
        return max(remaining, Decimal("0.00"))

    def calculate_payment_status(self):
        total = self.total_amount
        paid = self.paid_amount
        refunded = self.refunded_amount

        if refunded > Decimal("0.00") and paid <= refunded:
            return self.PaymentStatus.REMBOURSE
        if paid <= Decimal("0.00"):
            return self.PaymentStatus.NON_PAYE
        if paid >= total and refunded <= Decimal("0.00"):
            return self.PaymentStatus.PAYE
        if refunded > Decimal("0.00"):
            if self.net_paid_amount <= Decimal("0.00"):
                return self.PaymentStatus.REMBOURSE
            return self.PaymentStatus.PARTIEL
        return self.PaymentStatus.PARTIEL

    def recalculate_financials(self):
        new_status = self.calculate_payment_status()
        if self.payment_status != new_status:
            self.payment_status = new_status
            Reservation.objects.filter(pk=self.pk).update(
                payment_status=new_status,
                updated_at=timezone.now(),
            )
        return {
            "total_amount": self.total_amount,
            "paid_amount": self.paid_amount,
            "refunded_amount": self.refunded_amount,
            "remaining_amount": self.remaining_amount,
            "payment_status": self.payment_status,
        }

    def clean(self):
        super().clean()
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError(
                "L'heure de fin doit être supérieure à l'heure de début."
            )
        if self.tarif_id and self.tarif.amount < Decimal("0.00"):
            raise ValidationError("Le montant du tarif ne peut pas être négatif.")

        if self.hall_id and self.event_date:
            conflicting_reservations = (
                Reservation.objects.filter(
                    hall=self.hall,
                    event_date=self.event_date,
                    start_time__lt=self.end_time,
                    end_time__gt=self.start_time,
                )
                .exclude(pk=self.pk)
                .exclude(
                    status__in=[
                        self.Status.ANNULEE,
                        self.Status.TERMINEE,
                        self.Status.CLOTUREE,
                    ]
                )
            )
            if conflicting_reservations.exists():
                raise ValidationError("Cette salle est déjà réservée pour cette période.")

    def save(self, *args, **kwargs):
        if self.tarif_id:
            self.event_type = self.tarif.name

        if not self.reservation_number:
            year = timezone.now().year
            last_reservation = (
                Reservation.objects.filter(
                    reservation_number__startswith=f"RES-{year}-"
                )
                .order_by("-id")
                .first()
            )
            number = 1
            if last_reservation:
                try:
                    number = (
                        int(last_reservation.reservation_number.split("-")[-1]) + 1
                    )
                except (ValueError, IndexError):
                    number = (
                        Reservation.objects.filter(
                            reservation_number__startswith=f"RES-{year}-"
                        ).count()
                        + 1
                    )
            self.reservation_number = f"RES-{year}-{number:04d}"

        self.full_clean()
        super().save(*args, **kwargs)

        new_status = self.calculate_payment_status()
        if self.payment_status != new_status:
            Reservation.objects.filter(pk=self.pk).update(
                payment_status=new_status,
                updated_at=timezone.now(),
            )
            self.payment_status = new_status


# ============================================================
# COMPTES FINANCIERS
# ============================================================
class FinancialAccount(models.Model):
    class AccountType(models.TextChoices):
        CAISSE = "CAISSE", "Caisse"
        BANQUE = "BANQUE", "Banque"
        MOBILE_MONEY = "MOBILE_MONEY", "Mobile Money"

    name = models.CharField(
        max_length=150,
    )
    account_type = models.CharField(
        max_length=30,
        choices=AccountType.choices,
    )
    balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    is_active = models.BooleanField(
        default=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Compte financier"
        verbose_name_plural = "Comptes financiers"

    def __str__(self):
        return f"{self.name} - {self.balance} $"



# ============================================================
# PAIEMENT
# ============================================================

class Payment(models.Model):

    class Method(models.TextChoices):
        ESPECES = "ESPECES", "Espèces"
        VIREMENT = "VIREMENT", "Virement bancaire"
        MOBILE_MONEY = "MOBILE_MONEY", "Mobile Money"

    class Status(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente"
        VALIDE = "VALIDE", "Validé"
        ANNULE = "ANNULE", "Annulé"

    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="payments",
        blank=True,
        null=True,
    )

    financial_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.SET_NULL,
        related_name="payments",
        blank=True,
        null=True,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    payment_date = models.DateTimeField(
        default=timezone.now,
    )

    method = models.CharField(
        max_length=30,
        choices=Method.choices,
        default=Method.ESPECES,
    )

    reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    operator = models.CharField(
        max_length=150,
        blank=True,
        null=True,
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.EN_ATTENTE,
    )

    receipt_pdf = models.FileField(
        upload_to="payments/receipts/",
        blank=True,
        null=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_payments",
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    # ========================================================
    # CLÉ D'IDEMPOTENCE
    # ========================================================
    #
    # Cette clé identifie UNE opération de paiement.
    #
    # Si le frontend envoie deux fois exactement la même
    # opération, Django retrouvera le premier paiement
    # au lieu d'en créer un deuxième.
    #
    idempotency_key = models.UUIDField(
        unique=True,
        db_index=True,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]

        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"

    def clean(self):
        super().clean()

        # ----------------------------------------------------
        # MONTANT
        # ----------------------------------------------------

        if self.amount is None:
            raise ValidationError(
                "Le montant du paiement est obligatoire."
            )

        if self.amount <= Decimal("0.00"):
            raise ValidationError(
                "Le montant du paiement doit être supérieur à zéro."
            )

        # ----------------------------------------------------
        # VALIDATION DU COMPTE FINANCIER
        # ----------------------------------------------------

        if self.financial_account:

            if (
                self.financial_account.account_type
                == FinancialAccount.AccountType.CAISSE
                and self.method != self.Method.ESPECES
            ):
                raise ValidationError(
                    "La caisse physique ne peut recevoir "
                    "que les paiements en espèces."
                )

            if (
                self.financial_account.account_type
                == FinancialAccount.AccountType.BANQUE
                and self.method != self.Method.VIREMENT
            ):
                raise ValidationError(
                    "Le compte bancaire doit être associé "
                    "à un virement bancaire."
                )

            if (
                self.financial_account.account_type
                == FinancialAccount.AccountType.MOBILE_MONEY
                and self.method != self.Method.MOBILE_MONEY
            ):
                raise ValidationError(
                    "Le compte Mobile Money doit être associé "
                    "à un paiement Mobile Money."
                )

        # ----------------------------------------------------
        # VÉRIFICATION DU RESTE À PAYER
        # ----------------------------------------------------
        #
        # IMPORTANT :
        # cette vérification ne modifie aucun compte.
        #
        # Le verrouillage réel de la réservation est fait
        # dans PaymentViewSet.perform_create().
        #

        if self.reservation_id and self.status != self.Status.ANNULE:

            remaining = self.reservation.remaining_amount

            # Modification d'un paiement existant
            if self.pk:

                old_payment = (
                    Payment.objects
                    .filter(pk=self.pk)
                    .first()
                )

                if (
                    old_payment
                    and old_payment.status == self.Status.VALIDE
                ):
                    remaining += old_payment.amount

            if remaining <= Decimal("0.00"):
                raise ValidationError(
                    "Cette réservation est déjà entièrement payée."
                )

            if self.amount > remaining:
                raise ValidationError(
                    (
                        f"Le montant du paiement ({self.amount} $) "
                        f"dépasse le solde restant à payer "
                        f"({remaining} $)."
                    )
                )

    # ========================================================
    # SAVE
    # ========================================================
    #
    # IMPORTANT :
    #
    # NE PAS créer CashMovement ici.
    #
    # Le mouvement financier est créé UNIQUEMENT dans
    # PaymentViewSet.valider().
    #
    # Cela supprime le double enregistrement.
    #

    def save(self, *args, **kwargs):

        self.full_clean()

        super().save(*args, **kwargs)

        if self.reservation_id:
            self.reservation.recalculate_financials()

    def __str__(self):

        if self.reservation:
            return (
                f"Paiement #{self.id} - "
                f"{self.reservation.reservation_number}"
            )

        return f"Paiement #{self.id}"


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
        related_name="movements",
    )
    movement_type = models.CharField(
        max_length=30,
        choices=MovementType.choices,
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )
    description = models.CharField(
        max_length=255,
    )
    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movements",
    )
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="financial_movements",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_movements",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Mouvement de caisse"
        verbose_name_plural = "Mouvements de caisse"

    def __str__(self):
        return f"{self.movement_type} - {self.amount} $"


# ============================================================
# DEPENSES
# ============================================================
class Expense(models.Model):
    class ExpenseType(models.TextChoices):
        EAU = "EAU", "Eau"
        ELECTRICITE = "ELECTRICITE", "Électricité"
        SALAIRE = "SALAIRE", "Salaire"
        AUTRE = "AUTRE", "Autre"

    category = models.CharField(
        max_length=150,
        choices=ExpenseType.choices,
        default=ExpenseType.AUTRE,
    )
    description = models.TextField()
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    expense_date = models.DateTimeField(
        default=timezone.now,
    )
    financial_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="expenses",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_expenses",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-expense_date"]
        verbose_name = "Dépense"
        verbose_name_plural = "Dépenses"

    def clean(self):
        super().clean()

        if self.amount is not None and self.amount <= Decimal("0.00"):
            raise ValidationError(
                "Le montant de la dépense doit être supérieur à zéro."
            )

        # Récupération automatique de la caisse principale si le compte n'est pas spécifié
        if not self.financial_account:
            caisse_account = FinancialAccount.objects.filter(
                account_type=FinancialAccount.AccountType.CAISSE,
                is_active=True,
            ).first()

            if not caisse_account:
                raise ValidationError(
                    "Aucun compte de Caisse actif n'a été trouvé dans le système."
                )
            self.financial_account = caisse_account

        # Récupération du total/solde de la caisse et validation du montant
        caisse_balance = self.financial_account.balance
        if self.amount and caisse_balance < self.amount:
            raise ValidationError(
                f"Opération impossible : Le montant de la dépense ({self.amount} $) "
                f"est supérieur au solde disponible en Caisse ({caisse_balance} $)."
            )

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        self.full_clean()
        super().save(*args, **kwargs)

        if is_new and self.financial_account:
            self.financial_account.balance -= self.amount
            self.financial_account.save(update_fields=["balance"])

            CashMovement.objects.create(
                account=self.financial_account,
                movement_type=CashMovement.MovementType.SORTIE,
                amount=self.amount,
                description=(
                    f"Dépense [{self.get_category_display()}] : "
                    f"{self.description[:100]}"
                ),
                created_by=self.created_by,
            )

    def __str__(self):
        return f"{self.category} - {self.amount} $"


# ============================================================
# CONTRAT
# ============================================================
class Contract(models.Model):
    reservation = models.OneToOneField(
        Reservation,
        on_delete=models.CASCADE,
        related_name="contract",
    )
    file = models.FileField(
        upload_to="contracts/",
    )
    signed_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Contrat"
        verbose_name_plural = "Contrats"

    def __str__(self):
        return f"Contrat - {self.reservation.reservation_number}"


# ============================================================
# REMBOURSEMENTS
# ============================================================

class Refund(models.Model):

    class Method(models.TextChoices):
        ESPECES = "ESPECES", "Espèces"
        VIREMENT = "VIREMENT", "Virement bancaire"
        MOBILE_MONEY = "MOBILE_MONEY", "Mobile Money"

    class Status(models.TextChoices):
        VALIDE = "VALIDE", "Validé"
        ANNULE = "ANNULE", "Annulé"

    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        related_name="refunds",
    )

    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.PROTECT,
        related_name="refunds",
    )

    financial_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="refunds",
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    refund_date = models.DateTimeField(
        default=timezone.now,
    )

    method = models.CharField(
        max_length=30,
        choices=Method.choices,
    )

    reason = models.TextField(
        blank=True,
        null=True,
    )

    reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.VALIDE,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_refunds",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Remboursement"
        verbose_name_plural = "Remboursements"

    def clean(self):
        super().clean()

        if self.amount is None or self.amount <= Decimal("0.00"):
            raise ValidationError(
                "Le montant du remboursement doit être supérieur à zéro."
            )

        if not self.payment_id:
            raise ValidationError(
                "Le paiement à rembourser est obligatoire."
            )

        if not self.reservation_id:
            raise ValidationError(
                "La réservation est obligatoire."
            )

        if self.payment.reservation_id != self.reservation_id:
            raise ValidationError(
                "Le paiement ne correspond pas à cette réservation."
            )

        if self.payment.status != Payment.Status.VALIDE:
            raise ValidationError(
                "Seul un paiement validé peut être remboursé."
            )

        if self.financial_account_id != self.payment.financial_account_id:
            raise ValidationError(
                "Le compte financier du remboursement doit "
                "correspondre au compte du paiement."
            )

        # ----------------------------------------------------
        # TOTAL DÉJÀ REMBOURSÉ SUR CE PAIEMENT
        # ----------------------------------------------------

        already_refunded = (
            Refund.objects
            .filter(
                payment=self.payment,
                status=Refund.Status.VALIDE,
            )
            .exclude(pk=self.pk)
            .aggregate(total=Sum("amount"))
            .get("total")
            or Decimal("0.00")
        )

        refundable_amount = self.payment.amount - already_refunded

        if refundable_amount <= Decimal("0.00"):
            raise ValidationError(
                "Ce paiement a déjà été entièrement remboursé."
            )

        if self.amount > refundable_amount:
            raise ValidationError(
                (
                    f"Le montant du remboursement ({self.amount} $) "
                    f"dépasse le montant encore remboursable "
                    f"({refundable_amount} $)."
                )
            )

        # ----------------------------------------------------
        # LE COMPTE DOIT AVOIR SUFFISAMMENT DE FONDS
        # ----------------------------------------------------

        if self.financial_account.balance < self.amount:
            raise ValidationError(
                (
                    f"Solde insuffisant sur le compte "
                    f"{self.financial_account.name}. "
                    f"Solde disponible : "
                    f"{self.financial_account.balance} $."
                )
            )

    @property
    def refundable_amount(self):
        already_refunded = (
            Refund.objects
            .filter(
                payment=self.payment,
                status=Refund.Status.VALIDE,
            )
            .exclude(pk=self.pk)
            .aggregate(total=Sum("amount"))
            .get("total")
            or Decimal("0.00")
        )

        return max(
            self.payment.amount - already_refunded,
            Decimal("0.00"),
        )

    @transaction.atomic
    def save(self, *args, **kwargs):

        is_new = self.pk is None

        self.full_clean()

        super().save(*args, **kwargs)

        # ----------------------------------------------------
        # SORTIE FINANCIÈRE
        # ----------------------------------------------------

        if (
            is_new
            and self.status == self.Status.VALIDE
        ):
            account = FinancialAccount.objects.select_for_update().get(
                pk=self.financial_account_id
            )

            if account.balance < self.amount:
                raise ValidationError(
                    "Le solde du compte est insuffisant."
                )

            account.balance -= self.amount

            account.save(
                update_fields=["balance"]
            )

            CashMovement.objects.create(
                account=account,
                movement_type=CashMovement.MovementType.REMBOURSEMENT,
                amount=self.amount,
                description=(
                    f"Remboursement paiement #{self.payment_id} "
                    f"de la réservation "
                    f"{self.reservation.reservation_number}"
                ),
                payment=self.payment,
                reservation=self.reservation,
                created_by=self.created_by,
            )

            self.reservation.recalculate_financials()

    def __str__(self):
        return (
            f"Remboursement #{self.id} - "
            f"{self.amount} $ - "
            f"{self.reservation.reservation_number}"
        )