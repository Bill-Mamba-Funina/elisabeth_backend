from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

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


# ============================================================
# CLIENT
# ============================================================

class ClientSerializer(serializers.ModelSerializer):

    reservations_count = serializers.IntegerField(
        read_only=True
    )

    class Meta:
        model = Client

        fields = [
            "id",
            "full_name",
            "phone",
            "email",
            "address",
            "notes",
            "reservations_count",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "reservations_count",
            "created_at",
            "updated_at",
        ]

    def validate_phone(self, value):
        value = (
            value.strip()
            .replace(" ", "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
        )

        if not value:
            raise serializers.ValidationError(
                "Le numéro de téléphone est obligatoire."
            )

        queryset = Client.objects.filter(
            phone=value
        )

        if self.instance:
            queryset = queryset.exclude(
                pk=self.instance.pk
            )

        if queryset.exists():
            raise serializers.ValidationError(
                "Un client existe déjà avec ce numéro de téléphone."
            )

        return value
# ============================================================
# SALLE
# ============================================================

class HallSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hall
        fields = "__all__"


# ============================================================
# SERVICE
# ============================================================

class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = "__all__"


# ============================================================
# MATERIEL
# ============================================================

class MaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Material
        fields = "__all__"


# ============================================================
# RESERVATION SERVICE
# ============================================================

class ReservationSerializer(serializers.ModelSerializer):

    client_name = serializers.CharField(
        source="client.full_name",
        read_only=True
    )

    hall_name = serializers.CharField(
        source="hall.name",
        read_only=True
    )

    paid_amount = serializers.SerializerMethodField()

    remaining_amount = serializers.SerializerMethodField()

    payment_status = serializers.SerializerMethodField()

    class Meta:
        model = Reservation

        fields = [
            "id",
            "reservation_number",

            "client",
            "client_name",

            "hall",
            "hall_name",

            "event_type",
            "event_date",
            "start_time",
            "end_time",

            "total_amount",

            "paid_amount",
            "remaining_amount",
            "payment_status",

            "status",

            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "reservation_number",
            "client_name",
            "hall_name",
            "paid_amount",
            "remaining_amount",
            "payment_status",
            "created_at",
            "updated_at",
        ]

    def get_paid_amount(self, obj):
        """
        Montant réellement payé selon les paiements
        validés de la réservation.
        """

        payments = obj.payments.filter(
            status="VALIDE"
        )

        total = sum(
            payment.amount
            for payment in payments
        )

        return total

    def get_remaining_amount(self, obj):
        paid = self.get_paid_amount(obj)

        remaining = (
            obj.total_amount - paid
        )

        return max(remaining, 0)

    def get_payment_status(self, obj):
        paid = self.get_paid_amount(obj)

        if paid <= 0:
            return "NON_PAYE"

        if paid >= obj.total_amount:
            return "PAYE"

        return "PARTIEL"

    def validate(self, attrs):

        event_date = attrs.get(
            "event_date",
            getattr(self.instance, "event_date", None)
        )

        start_time = attrs.get(
            "start_time",
            getattr(self.instance, "start_time", None)
        )

        end_time = attrs.get(
            "end_time",
            getattr(self.instance, "end_time", None)
        )

        hall = attrs.get(
            "hall",
            getattr(self.instance, "hall", None)
        )

        if (
            start_time
            and end_time
            and start_time >= end_time
        ):
            raise serializers.ValidationError({
                "end_time": (
                    "L'heure de fin doit être "
                    "postérieure à l'heure de début."
                )
            })

        # Vérification des chevauchements
        if (
            hall
            and event_date
            and start_time
            and end_time
        ):
            queryset = Reservation.objects.filter(
                hall=hall,
                event_date=event_date,
            ).exclude(
                status="ANNULEE"
            )

            # Lors d'une modification,
            # on exclut la réservation elle-même.
            if self.instance:
                queryset = queryset.exclude(
                    pk=self.instance.pk
                )

            overlapping = queryset.filter(
                start_time__lt=end_time,
                end_time__gt=start_time,
            ).exists()

            if overlapping:
                raise serializers.ValidationError({
                    "event_date": (
                        "La salle est déjà réservée "
                        "sur cette période."
                    )
                })

        # Le nouveau montant total ne peut pas être
        # inférieur à ce qui a déjà été payé.
        if self.instance and "total_amount" in attrs:

            paid = self.get_paid_amount(
                self.instance
            )

            new_total = attrs["total_amount"]

            if new_total < paid:
                raise serializers.ValidationError({
                    "total_amount": (
                        f"Le montant total ({new_total}) "
                        f"ne peut pas être inférieur au "
                        f"montant déjà payé ({paid})."
                    )
                })

        return attrs


# ============================================================
# RESERVATION MATERIAL
# ============================================================

class ReservationMaterialSerializer(serializers.ModelSerializer):
    material_name = serializers.CharField(
        source="material.name",
        read_only=True
    )

    class Meta:
        model = ReservationMaterial
        fields = "__all__"



# ============================================================
# PAYMENT SERIALIZER
# ============================================================

class PaymentSerializer(serializers.ModelSerializer):

    reservation_number = serializers.CharField(
        source="reservation.reservation_number",
        read_only=True,
    )

    financial_account_name = serializers.CharField(
        source="financial_account.name",
        read_only=True,
    )

    created_by_name = serializers.SerializerMethodField(
        read_only=True,
    )

    method_display = serializers.CharField(
        source="get_method_display",
        read_only=True,
    )

    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = Payment

        fields = [
            "id",

            # Réservation
            "reservation",
            "reservation_number",

            # Compte financier
            "financial_account",
            "financial_account_name",

            # Paiement
            "amount",
            "payment_date",
            "method",
            "method_display",
            "reference",
            "operator",

            # Statut
            "status",
            "status_display",

            # Reçu
            "receipt_pdf",

            # Création
            "created_by",
            "created_by_name",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "reservation_number",
            "financial_account_name",
            "created_by",
            "created_by_name",
            "created_at",
            "method_display",
            "status_display",
        ]

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return None

        return (
            getattr(obj.created_by, "get_full_name", lambda: "")()
            or getattr(obj.created_by, "username", None)
            or str(obj.created_by)
        )

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Le montant du paiement doit être supérieur à zéro."
            )

        return value

    def validate(self, attrs):
        instance = self.instance

        reservation = attrs.get(
            "reservation",
            instance.reservation if instance else None,
        )

        financial_account = attrs.get(
            "financial_account",
            instance.financial_account if instance else None,
        )

        method = attrs.get(
            "method",
            instance.method if instance else None,
        )

        # Le compte financier est facultatif.
        if financial_account:

            if (
                financial_account.account_type
                == FinancialAccount.AccountType.CAISSE
            ):
                if method != Payment.Method.ESPECES:
                    raise serializers.ValidationError({
                        "method": (
                            "La caisse physique ne peut recevoir "
                            "que les paiements en espèces."
                        )
                    })

            elif (
                financial_account.account_type
                == FinancialAccount.AccountType.BANQUE
            ):
                if method != Payment.Method.VIREMENT:
                    raise serializers.ValidationError({
                        "method": (
                            "Le compte bancaire doit être associé "
                            "à un virement bancaire."
                        )
                    })

            elif (
                financial_account.account_type
                == FinancialAccount.AccountType.MOBILE_MONEY
            ):
                if method != Payment.Method.MOBILE_MONEY:
                    raise serializers.ValidationError({
                        "method": (
                            "Le compte Mobile Money doit être associé "
                            "à un paiement Mobile Money."
                        )
                    })

        return attrs



# ============================================================
# RESERVATION
# ============================================================

class ReservationSerializer(serializers.ModelSerializer):

    client_name = serializers.CharField(
        source="client.full_name",
        read_only=True
    )

    hall_name = serializers.CharField(
        source="hall.name",
        read_only=True
    )

    payments = PaymentSerializer(
        many=True,
        read_only=True
    )

    services = ReservationServiceSerializer(
        source="reservation_services",
        many=True,
        read_only=True
    )

    materials = ReservationMaterialSerializer(
        source="reservation_materials",
        many=True,
        read_only=True
    )

    contract_file = serializers.FileField(
        source="contract.file",
        read_only=True
    )

    class Meta:
        model = Reservation

        fields = [
            "id",
            "reservation_number",
            "client",
            "client_name",
            "hall",
            "hall_name",
            "event_type",
            "event_date",
            "start_time",
            "end_time",
            "guest_count",
            "description",
            "observations",
            "total_amount",
            "paid_amount",
            "remaining_amount",
            "payment_status",
            "status",
            "payments",
            "services",
            "materials",
            "contract_file",
            "created_by",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "reservation_number",
            "paid_amount",
            "remaining_amount",
            "payment_status",
            "created_by",
        ]

    def validate(self, attrs):
        instance = self.instance

        reservation = Reservation(
            client=attrs.get(
                "client",
                instance.client if instance else None
            ),
            hall=attrs.get(
                "hall",
                instance.hall if instance else None
            ),
            event_date=attrs.get(
                "event_date",
                instance.event_date if instance else None
            ),
            start_time=attrs.get(
                "start_time",
                instance.start_time if instance else None
            ),
            end_time=attrs.get(
                "end_time",
                instance.end_time if instance else None
            ),
            total_amount=attrs.get(
                "total_amount",
                instance.total_amount if instance else Decimal("0.00")
            ),
        )

        if instance:
            reservation.pk = instance.pk

        reservation.clean()

        return attrs


# ============================================================
# COMPTES FINANCIERS
# ============================================================

class FinancialAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialAccount
        fields = "__all__"

        read_only_fields = [
            "balance",
        ]


# ============================================================
# MOUVEMENTS
# ============================================================

class CashMovementSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(
        source="account.name",
        read_only=True
    )

    class Meta:
        model = CashMovement
        fields = "__all__"

        read_only_fields = [
            "created_by",
        ]


# ============================================================
# DEPENSES
# ============================================================

class ExpenseSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    category_display = serializers.CharField(
        source="get_category_display",
        read_only=True,
    )

    class Meta:
        model = Expense
        fields = [
            "id",
            "title",
            "category",
            "category_display",
            "amount",
            "expense_date",
            "status",
            "status_display",
            "notes",
            "created_at",
            "created_by",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "created_by",
        ]

    def validate(self, attrs):
        category = attrs.get(
            "category",
            getattr(self.instance, "category", None),
        )

        title = attrs.get(
            "title",
            getattr(self.instance, "title", ""),
        )

        if category == Expense.Category.AUTRE:
            if not title or not title.strip():
                raise serializers.ValidationError({
                    "title": (
                        "Le titre est obligatoire "
                        "pour une dépense de type « Autre »."
                    )
                })

            attrs["title"] = title.strip()

        else:
            category_labels = {
                Expense.Category.EAU: "Eau",
                Expense.Category.ELECTRICITE: "Électricité",
                Expense.Category.SALAIRE: "Salaire",
            }

            attrs["title"] = category_labels.get(
                category,
                title,
            )

        return attrs

# ============================================================
# CONTRAT
# ============================================================

class ContractSerializer(serializers.ModelSerializer):

    reservation_number = serializers.CharField(
        source="reservation.reservation_number",
        read_only=True
    )

    class Meta:
        model = Contract

        fields = [
            "id",
            "reservation",
            "reservation_number",
            "file",
            "signed_at",
            "uploaded_at",
            "uploaded_by",
        ]

        read_only_fields = [
            "uploaded_by",
            "uploaded_at",
        ]


# ============================================================
# NOTIFICATIONS
# ============================================================

class NotificationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Notification

        fields = "__all__"

        read_only_fields = [
            "user",
            "created_at",
            "read_at",
        ]