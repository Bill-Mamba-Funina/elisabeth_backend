from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from rest_framework import serializers



from .utils import normalize_phone


from django.db import transaction

from .models import (
    Client,
    Hall,
    Material,
    Reservation,
    FinancialAccount,
    Payment,
    CashMovement,
    Expense,
    Contract,
    Personnel,
    Refund,Hall, 
    HallImage, 
    HallVideo,
    Tarif,
)

# ============================================================
# CLIENT
# ============================================================

class ClientSerializer(serializers.ModelSerializer):

    reservations_count = serializers.IntegerField(
        read_only=True
    )

    reservations_history = serializers.SerializerMethodField()

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
            "reservations_history",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "reservations_count",
            "reservations_history",
            "created_at",
            "updated_at",
        ]

    def get_reservations_history(self, obj):

        reservations = (
            obj.reservations
            .select_related("hall", "tarif")
            .prefetch_related("payments", "refunds")
            .all()
        )

        return [
            {
                "id": reservation.id,
                "reservation_number": (
                    reservation.reservation_number
                ),
                "event_type": reservation.event_type,
                "event_date": reservation.event_date,
                "start_time": reservation.start_time,
                "end_time": reservation.end_time,
                "hall": (
                    reservation.hall.name
                    if reservation.hall
                    else None
                ),
                "status": reservation.status,
                "payment_status": (
                    reservation.payment_status
                ),
                "total_amount": (
                    reservation.total_amount
                ),
                "paid_amount": (
                    reservation.paid_amount
                ),
                "remaining_amount": (
                    reservation.remaining_amount
                ),
                "payments": [
                    {
                        "id": payment.id,
                        "amount": payment.amount,
                        "payment_date": payment.payment_date,
                        "method": payment.method,
                        "status": payment.status,
                        "reference": payment.reference,
                    }
                    for payment in reservation.payments.all()
                ],
                "refunds": [
                    {
                        "id": refund.id,
                        "amount": refund.amount,
                        "refund_date": refund.refund_date,
                        "method": refund.method,
                        "status": refund.status,
                        "reason": refund.reason,
                        "reference": refund.reference,
                    }
                    for refund in reservation.refunds.all()
                ],
                "created_at": reservation.created_at,
            }
            for reservation in reservations
        ]




class ClientHistorySerializer(serializers.ModelSerializer):

    class Meta:
        model = Reservation

        fields = [
            "id",
            "reservation_number",
            "event_type",
            "event_date",
            "start_time",
            "end_time",
            "status",
            "payment_status",
            "total_amount",
            "paid_amount",
            "remaining_amount",
            "created_at",
        ]



# ============================================================
# HALL
# ============================================================

class HallImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = HallImage
        fields = [
            "id",
            "image",
            "url",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "url",
            "created_at",
        ]

    def get_url(self, obj):
        if not obj.image:
            return None

        request = self.context.get("request")
        url = obj.image.url

        if request:
            return request.build_absolute_uri(url)

        return url


class HallVideoSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = HallVideo
        fields = [
            "id",
            "video",
            "url",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "url",
            "created_at",
        ]

    def get_url(self, obj):
        if not obj.video:
            return None

        request = self.context.get("request")
        url = obj.video.url

        if request:
            return request.build_absolute_uri(url)

        return url



class HallSerializer(serializers.ModelSerializer):
    images = serializers.SerializerMethodField()
    videos = serializers.SerializerMethodField()

    class Meta:
        model = Hall
        fields = [
            "id",
            "name",
            "description",
            "capacity",
            "price",
            "is_active",
            "images",
            "videos",
        ]

    def get_images(self, obj):
        request = self.context.get("request")

        result = []

        for image in obj.images.all():
            if not image.image:
                continue

            url = image.image.url

            if request:
                url = request.build_absolute_uri(url)

            result.append({
                "id": image.id,
                "url": url,
                "name": image.image.name,
            })

        return result

    def get_videos(self, obj):
        request = self.context.get("request")

        result = []

        for video in obj.videos.all():
            if not video.video:
                continue

            url = video.video.url

            if request:
                url = request.build_absolute_uri(url)

            result.append({
                "id": video.id,
                "url": url,
                "name": video.video.name,
            })

        return result


# ============================================================
# MATERIEL
# ============================================================

class MaterialSerializer(serializers.ModelSerializer):

    etat_label = serializers.CharField(
        source="get_etat_display",
        read_only=True
    )

    class Meta:
        model = Material

        fields = [
            "id",
            "name",
            "description",
            "quantity_available",
            "unit_price",
            "etat",
            "etat_label",
            "is_active",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "etat_label",
            "created_at",
            "updated_at",
        ]


# ============================================================
# PERSONNEL
# ============================================================

class PersonnelSerializer(serializers.ModelSerializer):

    class Meta:
        model = Personnel
        fields = "__all__"

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]




# ============================================================
# RESERVATION
# ============================================================





class ReservationSerializer(serializers.ModelSerializer):

    # =========================================================
    # INFORMATIONS CLIENT ENTRANTES
    # =========================================================

    client_full_name = serializers.CharField(
        write_only=True,
        required=True,
    )

    client_phone = serializers.CharField(
        write_only=True,
        required=True,
    )

    client_email = serializers.EmailField(
        write_only=True,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    client_address = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    # =========================================================
    # INFORMATIONS CLIENT SORTANTES
    # =========================================================

    client_name = serializers.CharField(
        source="client.full_name",
        read_only=True,
    )

    client_phone_display = serializers.SerializerMethodField(
        read_only=True,
    )

    client_email_display = serializers.SerializerMethodField(
        read_only=True,
    )

    client_address_display = serializers.SerializerMethodField(
        read_only=True,
    )

    # =========================================================
    # SALLE
    # =========================================================

    hall_name = serializers.CharField(
        source="hall.name",
        read_only=True,
    )

    # =========================================================
    # TARIF
    # =========================================================

    tarif_name = serializers.CharField(
        source="tarif.name",
        read_only=True,
    )

    tarif_amount = serializers.DecimalField(
        source="tarif.amount",
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

    # =========================================================
    # FINANCES
    # =========================================================

    total_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

    paid_amount = serializers.DecimalField(
        source="net_paid_amount",
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

    remaining_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

    # =========================================================
    # STATUTS
    # =========================================================

    payment_status_display = serializers.CharField(
        source="get_payment_status_display",
        read_only=True,
    )

    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    # =========================================================
    # META
    # =========================================================

    class Meta:
        model = Reservation

        fields = [
            "id",
            "reservation_number",

            # -------------------------------------------------
            # CLIENT
            # -------------------------------------------------
            "client",
            "client_name",
            "client_phone_display",
            "client_email_display",
            "client_address_display",

            # -------------------------------------------------
            # INFORMATIONS CLIENT ENTRANTES
            # -------------------------------------------------
            "client_full_name",
            "client_phone",
            "client_email",
            "client_address",

            # -------------------------------------------------
            # SALLE
            # -------------------------------------------------
            "hall",
            "hall_name",

            # -------------------------------------------------
            # TARIF
            # -------------------------------------------------
            "tarif",
            "tarif_name",
            "tarif_amount",

            # -------------------------------------------------
            # ÉVÉNEMENT
            # -------------------------------------------------
            "event_type",
            "event_date",
            "start_time",
            "end_time",
            "guest_count",

            # -------------------------------------------------
            # STATUTS
            # -------------------------------------------------
            "status",
            "status_display",
            "payment_status",
            "payment_status_display",

            # -------------------------------------------------
            # FINANCES
            # -------------------------------------------------
            "total_amount",
            "paid_amount",
            "remaining_amount",

            # -------------------------------------------------
            # DATES
            # -------------------------------------------------
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "reservation_number",
            "client",
            "event_type",
            "payment_status",
            "total_amount",
            "paid_amount",
            "remaining_amount",
            "created_at",
            "updated_at",
        ]

    # =========================================================
    # CLIENT - INFORMATIONS SORTANTES
    # =========================================================

    def get_client_phone_display(self, obj):
        """
        Retourne le téléphone réel enregistré dans Client.
        """

        if not obj.client:
            return ""

        return str(
            obj.client.phone or ""
        ).strip()

    def get_client_email_display(self, obj):
        """
        Retourne l'email réel enregistré dans Client.
        """

        if not obj.client:
            return ""

        return str(
            obj.client.email or ""
        ).strip()

    def get_client_address_display(self, obj):
        """
        Retourne l'adresse réelle enregistrée dans Client.
        """

        if not obj.client:
            return ""

        return str(
            obj.client.address or ""
        ).strip()

    # =========================================================
    # NORMALISATION TELEPHONE
    # =========================================================

    def validate_client_phone(self, value):

        value = normalize_phone(value)

        if not value:
            raise serializers.ValidationError(
                "Le numéro de téléphone est obligatoire."
            )

        return value

    # =========================================================
    # VALIDATION RESERVATION
    # =========================================================

    def validate(self, attrs):

        start_time = attrs.get("start_time")
        end_time = attrs.get("end_time")

        # -----------------------------------------------------
        # Vérification des heures
        # -----------------------------------------------------

        if (
            start_time
            and end_time
            and start_time >= end_time
        ):
            raise serializers.ValidationError({
                "end_time": (
                    "L'heure de fin doit être supérieure "
                    "à l'heure de début."
                )
            })

        hall = attrs.get("hall")
        event_date = attrs.get("event_date")

        # -----------------------------------------------------
        # Vérification chevauchement salle
        # -----------------------------------------------------

        if (
            hall
            and event_date
            and start_time
            and end_time
        ):

            reservation_id = (
                self.instance.pk
                if self.instance
                else None
            )

            conflicts = Reservation.objects.filter(
                hall=hall,
                event_date=event_date,
                start_time__lt=end_time,
                end_time__gt=start_time,
            ).exclude(
                status__in=[
                    Reservation.Status.ANNULEE,
                    Reservation.Status.TERMINEE,
                    Reservation.Status.CLOTUREE,
                ]
            )

            if reservation_id:
                conflicts = conflicts.exclude(
                    pk=reservation_id
                )

            if conflicts.exists():
                raise serializers.ValidationError({
                    "hall": (
                        "Cette salle est déjà réservée "
                        "pour cette période."
                    )
                })

        return attrs

    # =========================================================
    # CREATION
    # =========================================================

    @transaction.atomic
    def create(self, validated_data):

        # -----------------------------------------------------
        # Récupération des informations client
        # -----------------------------------------------------

        full_name = validated_data.pop(
            "client_full_name"
        ).strip()

        phone = normalize_phone(
            validated_data.pop("client_phone")
        )

        if not phone:
            raise serializers.ValidationError({
                "client_phone": (
                    "Le numéro de téléphone est obligatoire."
                )
            })

        email = validated_data.pop(
            "client_email",
            None,
        )

        address = validated_data.pop(
            "client_address",
            None,
        )

        # -----------------------------------------------------
        # Nettoyage email
        # -----------------------------------------------------

        if email is not None:
            email = email.strip()

            if not email:
                email = None

        # -----------------------------------------------------
        # Nettoyage adresse
        # -----------------------------------------------------

        if address is not None:
            address = address.strip()

            if not address:
                address = None

        # =====================================================
        # RECHERCHE CLIENT PAR TELEPHONE
        # =====================================================

        client = (
            Client.objects
            .select_for_update()
            .filter(phone=phone)
            .first()
        )

        # =====================================================
        # CLIENT EXISTANT
        # =====================================================

        if client:

            client.full_name = full_name

            if email is not None:
                client.email = email

            if address is not None:
                client.address = address

            client.save(
                update_fields=[
                    "full_name",
                    "email",
                    "address",
                    "updated_at",
                ]
            )

        # =====================================================
        # NOUVEAU CLIENT
        # =====================================================

        else:

            client = Client.objects.create(
                full_name=full_name,
                phone=phone,
                email=email,
                address=address,
            )

        # =====================================================
        # CREATION RESERVATION
        # =====================================================

        reservation = Reservation.objects.create(
            client=client,
            **validated_data,
        )

        return reservation

    # =========================================================
    # MODIFICATION
    # =========================================================

    @transaction.atomic
    def update(self, instance, validated_data):

        client_full_name = validated_data.pop(
            "client_full_name",
            None,
        )

        client_phone = validated_data.pop(
            "client_phone",
            None,
        )

        client_email = validated_data.pop(
            "client_email",
            None,
        )

        client_address = validated_data.pop(
            "client_address",
            None,
        )

        client = instance.client

        # =====================================================
        # CLIENT
        # =====================================================

        if client:

            # -------------------------------------------------
            # NOM
            # -------------------------------------------------

            if client_full_name is not None:

                client.full_name = (
                    client_full_name.strip()
                )

            # -------------------------------------------------
            # TELEPHONE
            # -------------------------------------------------

            if client_phone is not None:

                new_phone = normalize_phone(
                    client_phone
                )

                if not new_phone:
                    raise serializers.ValidationError({
                        "client_phone": (
                            "Le numéro de téléphone "
                            "est obligatoire."
                        )
                    })

                duplicate = (
                    Client.objects
                    .filter(phone=new_phone)
                    .exclude(pk=client.pk)
                    .exists()
                )

                if duplicate:
                    raise serializers.ValidationError({
                        "client_phone": (
                            "Un autre client utilise déjà "
                            "ce numéro de téléphone."
                        )
                    })

                client.phone = new_phone

            # -------------------------------------------------
            # EMAIL
            # -------------------------------------------------

            if client_email is not None:

                client.email = (
                    client_email.strip()
                    if client_email
                    else None
                )

            # -------------------------------------------------
            # ADRESSE
            # -------------------------------------------------

            if client_address is not None:

                client.address = (
                    client_address.strip()
                    if client_address
                    else None
                )

            client.save()

        # =====================================================
        # RESERVATION
        # =====================================================

        for field, value in validated_data.items():
            setattr(
                instance,
                field,
                value,
            )

        instance.save()

        return instance




class TarifSerializer(serializers.ModelSerializer):

    class Meta:

        model = Tarif

        fields = [
            "id",
            "name",
            "description",
            "amount",
            "is_active",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]


# ============================================================
# FINANCIAL ACCOUNT
# ============================================================

class FinancialAccountSerializer(serializers.ModelSerializer):

    class Meta:
        model = FinancialAccount
        fields = "__all__"



# ============================================================
# PAYMENT
# ============================================================

class PaymentSerializer(serializers.ModelSerializer):

    reservation_number = serializers.CharField(
        source="reservation.reservation_number",
        read_only=True,
    )

    client = ClientSerializer(
        source="reservation.client",
        read_only=True,
    )

    class Meta:
        model = Payment

        fields = [
            "id",
            "reservation",
            "reservation_number",
            "client",
            "financial_account",
            "amount",
            "payment_date",
            "method",
            "reference",
            "operator",
            "status",
            "receipt_pdf",
            "created_by",
            "created_at",
            "idempotency_key",
        ]

        read_only_fields = [
            "id",
            "reservation_number",
            "client",
            "created_by",
            "created_at",
        ]

        extra_kwargs = {
            "idempotency_key": {
                "required": False,
                "allow_null": True,
            },
            "reference": {
                "required": False,
                "allow_blank": True,
                "allow_null": True,
            },
        }

    def validate_reference(self, value):

        if value is None:
            return None

        value = value.strip()

        if not value:
            return None

        return value

    def validate(self, attrs):

        reservation = attrs.get("reservation")

        amount = attrs.get("amount")

        status_value = attrs.get(
            "status",
            Payment.Status.EN_ATTENTE,
        )

        if amount is not None and amount <= Decimal("0.00"):
            raise serializers.ValidationError({
                "amount": (
                    "Le montant doit être supérieur à zéro."
                )
            })

        if (
            reservation
            and amount
            and status_value != Payment.Status.ANNULE
        ):

            # On ne fait ici qu'une vérification informative.
            # Le verrouillage réel sera fait dans le ViewSet.
            remaining = reservation.remaining_amount

            if amount > remaining:
                raise serializers.ValidationError({
                    "amount": (
                        f"Le montant maximum autorisé est "
                        f"{remaining} $."
                    )
                })

        return attrs

    def create(self, validated_data):

        request = self.context.get("request")

        if (
            request
            and request.user
            and request.user.is_authenticated
        ):
            validated_data["created_by"] = request.user

        return super().create(validated_data)



# ============================================================
# CASH MOVEMENT
# ============================================================

class CashMovementSerializer(serializers.ModelSerializer):

    class Meta:
        model = CashMovement
        fields = "__all__"

        read_only_fields = [
            "id",
            "created_at",
        ]



class ExpenseSerializer(serializers.ModelSerializer):

    category_display = serializers.CharField(
        source="get_category_display",
        read_only=True,
    )

    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    created_by_name = serializers.SerializerMethodField(
        read_only=True
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
            "created_by_name",
        ]

        read_only_fields = [
            "id",
            "category_display",
            "status_display",
            "created_at",
            "created_by",
            "created_by_name",
        ]

    def get_created_by_name(self, obj):

        if not obj.created_by:
            return ""

        full_name = obj.created_by.get_full_name()

        if full_name:
            return full_name

        return obj.created_by.username
# ============================================================
# CONTRACT
# ============================================================

class ContractSerializer(serializers.ModelSerializer):

    class Meta:
        model = Contract
        fields = "__all__"

        read_only_fields = [
            "id",
            "uploaded_at",
        ]





class RefundSerializer(serializers.ModelSerializer):
    financial_account_name = serializers.ReadOnlyField(
        source="financial_account.name"
    )

    payment_amount = serializers.ReadOnlyField(
        source="payment.amount"
    )

    reservation_number = serializers.ReadOnlyField(
        source="reservation.reservation_number"
    )

    client_name = serializers.SerializerMethodField()

    already_refunded = serializers.SerializerMethodField()

    refundable_amount = serializers.SerializerMethodField()

    class Meta:
        model = Refund

        fields = [
            "id",
            "payment",
            "payment_amount",
            "reservation",
            "reservation_number",
            "client_name",
            "financial_account",
            "financial_account_name",
            "amount",
            "already_refunded",
            "refundable_amount",
            "method",
            "reason",
            "reference",
            "status",
            "refund_date",
            "receipt_pdf",
            "created_at",
            "created_by",
        ]

        read_only_fields = [
            "id",
            "payment_amount",
            "reservation_number",
            "client_name",
            "already_refunded",
            "refundable_amount",
            "created_at",
            "created_by",
        ]

    def get_client_name(self, obj):
        if not obj.reservation_id:
            return None

        client = obj.reservation.client

        if not client:
            return None

        return client.full_name

    def get_already_refunded(self, obj):
        return (
            Refund.objects
            .filter(
                payment=obj.payment,
                status=Refund.Status.VALIDE,
            )
            .exclude(pk=obj.pk)
            .aggregate(
                total=Coalesce(
                    Sum("amount"),
                    Decimal("0.00"),
                )
            )["total"]
        )

    def get_refundable_amount(self, obj):
        already_refunded = self.get_already_refunded(obj)

        remaining = (
            obj.payment.amount
            - already_refunded
        )

        if remaining < Decimal("0.00"):
            return Decimal("0.00")

        return remaining

    def validate(self, attrs):
        payment = attrs.get("payment")

        if not payment:
            raise serializers.ValidationError({
                "payment": (
                    "Le paiement d'origine est obligatoire."
                )
            })

        if payment.status != Payment.Status.VALIDE:
            raise serializers.ValidationError({
                "payment": (
                    "Seul un paiement validé peut être remboursé."
                )
            })

        reservation = attrs.get("reservation")

        if reservation and reservation.pk != payment.reservation_id:
            raise serializers.ValidationError({
                "reservation": (
                    "La réservation ne correspond pas "
                    "au paiement sélectionné."
                )
            })

        attrs["reservation"] = payment.reservation

        amount = attrs.get("amount")

        if amount is None:
            raise serializers.ValidationError({
                "amount": (
                    "Le montant du remboursement est obligatoire."
                )
            })

        if amount <= Decimal("0.00"):
            raise serializers.ValidationError({
                "amount": (
                    "Le montant du remboursement doit "
                    "être supérieur à 0."
                )
            })

        already_refunded = (
            Refund.objects
            .filter(
                payment=payment,
                status=Refund.Status.VALIDE,
            )
            .aggregate(
                total=Coalesce(
                    Sum("amount"),
                    Decimal("0.00"),
                )
            )["total"]
        )

        refundable_amount = (
            payment.amount
            - already_refunded
        )

        if amount > refundable_amount:
            raise serializers.ValidationError({
                "amount": (
                    "Le montant du remboursement dépasse "
                    f"le montant encore remboursable "
                    f"({refundable_amount} $)."
                )
            })

        return attrs

    def validate_refund_date(self, value):
        if not value:
            raise serializers.ValidationError(
                "La date du remboursement est obligatoire."
            )

        return value

