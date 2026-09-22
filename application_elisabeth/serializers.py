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
    class Meta:
        model = Client
        fields = "__all__"


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

class ReservationServiceSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(
        source="service.name",
        read_only=True
    )

    class Meta:
        model = ReservationService
        fields = "__all__"


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
# PAIEMENT
# ============================================================

class PaymentSerializer(serializers.ModelSerializer):
    reservation_number = serializers.CharField(
        source="reservation.reservation_number",
        read_only=True
    )

    client_name = serializers.CharField(
        source="reservation.client.full_name",
        read_only=True
    )

    account_name = serializers.CharField(
        source="financial_account.name",
        read_only=True
    )

    class Meta:
        model = Payment
        fields = [
            "id",
            "reservation",
            "reservation_number",
            "client_name",
            "amount",
            "payment_date",
            "method",
            "reference",
            "operator",
            "financial_account",
            "account_name",
            "status",
            "receipt_pdf",
            "created_by",
            "created_at",
        ]

        read_only_fields = [
            "created_by",
            "receipt_pdf",
        ]

    def validate(self, attrs):
        reservation = attrs["reservation"]
        amount = attrs["amount"]

        if amount <= 0:
            raise serializers.ValidationError(
                "Le montant du paiement doit être supérieur à zéro."
            )

        if reservation.status == Reservation.Status.ANNULEE:
            raise serializers.ValidationError(
                "Impossible d'enregistrer un paiement sur une réservation annulée."
            )

        if reservation.status in [
            Reservation.Status.TERMINEE,
            Reservation.Status.CLOTUREE,
        ]:
            raise serializers.ValidationError(
                "Cette réservation est terminée ou clôturée."
            )

        current_paid = reservation.paid_amount

        if current_paid + amount > reservation.total_amount:
            raise serializers.ValidationError(
                {
                    "amount": (
                        f"Le paiement dépasse le solde restant. "
                        f"Reste à payer : {reservation.remaining_amount}"
                    )
                }
            )

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

    account_name = serializers.CharField(
        source="financial_account.name",
        read_only=True
    )

    class Meta:
        model = Expense

        fields = [
            "id",
            "category",
            "description",
            "amount",
            "expense_date",
            "financial_account",
            "account_name",
            "created_by",
            "created_at",
        ]

        read_only_fields = [
            "created_by",
        ]


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