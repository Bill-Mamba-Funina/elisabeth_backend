from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .services.notification_service import send_notification

from rest_framework import status, viewsets
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response

from .models import Hall, HallImage, HallVideo

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from rest_framework import serializers, status, viewsets
from rest_framework.decorators import (
    action,
    api_view,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

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
    Refund,
    Tarif,
)

from .serializers import (
    ClientSerializer,
    HallSerializer,
    MaterialSerializer,
    ReservationSerializer,
    FinancialAccountSerializer,
    PaymentSerializer,
    CashMovementSerializer,
    ExpenseSerializer,
    ContractSerializer,
    PersonnelSerializer,
    HallSerializer,
    HallImageSerializer,
    HallVideoSerializer,
    TarifSerializer,
    RefundSerializer,
)

from .services.pdf_service import generate_payment_receipt_pdf












# ============================================================
# CLIENTS
# ============================================================

class ClientViewSet(viewsets.ModelViewSet):

    queryset = Client.objects.all().order_by("full_name")
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):

        client = serializer.save()

        send_notification(
            subject="Nouveau client",
            message=(
                f"Un nouveau client a été créé.\n\n"
                f"Nom : {client.full_name}\n"
                f"Téléphone : {client.phone}"
            ),
        )

# ============================================================
# SALLES
# ============================================================


class HallViewSet(viewsets.ModelViewSet):
    queryset = Hall.objects.prefetch_related(
        "images",
        "videos",
    ).all()

    serializer_class = HallSerializer

    parser_classes = [
        MultiPartParser, 
        FormParser,
        JSONParser,
    ]

    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        hall = serializer.save()

        # =====================================================
        # IMAGES
        # =====================================================

        images = request.FILES.getlist("images")

        for image in images:
            HallImage.objects.create(
                hall=hall,
                image=image,
            )

        # =====================================================
        # VIDEOS
        # =====================================================

        videos = request.FILES.getlist("videos")

        for video in videos:
            HallVideo.objects.create(
                hall=hall,
                video=video,
            )

        # =====================================================
        # REPONSE
        # =====================================================

        response_serializer = self.get_serializer(
            hall
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop(
            "partial",
            False,
        )

        instance = self.get_object()

        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )

        serializer.is_valid(
            raise_exception=True
        )

        hall = serializer.save()

        # =====================================================
        # NOUVELLES IMAGES
        # =====================================================

        images = request.FILES.getlist(
            "images"
        )

        for image in images:
            HallImage.objects.create(
                hall=hall,
                image=image,
            )

        # =====================================================
        # NOUVELLES VIDEOS
        # =====================================================

        videos = request.FILES.getlist(
            "videos"
        )

        for video in videos:
            HallVideo.objects.create(
                hall=hall,
                video=video,
            )

        response_serializer = self.get_serializer(
            hall
        )

        return Response(
            response_serializer.data
        )



class HallImageViewSet(viewsets.ModelViewSet):
    queryset = HallImage.objects.all().select_related("hall")
    serializer_class = HallImageSerializer

    parser_classes = [
        MultiPartParser,
        FormParser,
        JSONParser,
    ]


class HallVideoViewSet(viewsets.ModelViewSet):
    queryset = HallVideo.objects.all().select_related("hall")
    serializer_class = HallVideoSerializer

    parser_classes = [
        MultiPartParser,
        FormParser,
        JSONParser,
    ]



# ============================================================
# MATERIEL
# ============================================================

class MaterialViewSet(viewsets.ModelViewSet):
    queryset = Material.objects.all().order_by("name")
    serializer_class = MaterialSerializer
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



class TarifViewSet(viewsets.ModelViewSet):
    queryset = Tarif.objects.all()
    serializer_class = TarifSerializer
    permission_classes = [IsAuthenticated]




# ============================================================
# PAIEMENTS
# ============================================================

class PaymentViewSet(viewsets.ModelViewSet):

    queryset = (
        Payment.objects
        .select_related(
            "reservation",
            "reservation__client",
            "financial_account",
            "created_by",
        )
        .all()
        .order_by("-payment_date", "-id")
    )

    serializer_class = PaymentSerializer

    permission_classes = [IsAuthenticated]

    # ========================================================
    # CREATION
    # ========================================================

    @transaction.atomic
    def perform_create(self, serializer):

        validated_data = serializer.validated_data

        reservation = validated_data.get("reservation")

        idempotency_key = validated_data.get(
            "idempotency_key"
        )

        # ----------------------------------------------------
        # PROTECTION CONTRE LE DOUBLE POST
        # ----------------------------------------------------

        if idempotency_key:

            existing_payment = (
                Payment.objects
                .select_for_update()
                .filter(
                    idempotency_key=idempotency_key
                )
                .first()
            )

            if existing_payment:

                raise serializers.ValidationError({
                    "detail": (
                        "Ce paiement a déjà été enregistré."
                    ),
                    "payment_id": existing_payment.id,
                })

        # ----------------------------------------------------
        # VERROUILLAGE DE LA RESERVATION
        # ----------------------------------------------------
        #
        # Très important :
        #
        # Deux requêtes simultanées ne peuvent pas calculer
        # le même reste à payer et créer deux paiements.
        #

        locked_reservation = None

        if reservation:

            locked_reservation = (
                Reservation.objects
                .select_for_update()
                .select_related("tarif")
                .get(pk=reservation.pk)
            )

            # ------------------------------------------------
            # RESTE A PAYER ACTUEL
            # ------------------------------------------------

            total = (
                locked_reservation.total_amount
                or Decimal("0.00")
            )

            already_paid = (
                Payment.objects
                .filter(
                    reservation=locked_reservation,
                    status=Payment.Status.VALIDE,
                )
                .aggregate(
                    total=Sum("amount")
                )
                .get("total")
                or Decimal("0.00")
            )

            refunded = (
                locked_reservation.refunded_amount
            )

            remaining = (
                total
                - already_paid
                + refunded
            )

            if remaining < Decimal("0.00"):
                remaining = Decimal("0.00")

            amount = validated_data.get("amount")

            status_value = validated_data.get(
                "status",
                Payment.Status.EN_ATTENTE,
            )

            # ------------------------------------------------
            # PAIEMENT ANNULE
            # ------------------------------------------------

            if status_value == Payment.Status.ANNULE:

                raise serializers.ValidationError({
                    "status": (
                        "Un paiement ne peut pas être "
                        "créé directement avec le statut "
                        "ANNULÉ."
                    )
                })

            # ------------------------------------------------
            # RESERVATION DEJA PAYEE
            # ------------------------------------------------

            if remaining <= Decimal("0.00"):

                raise serializers.ValidationError({
                    "amount": (
                        "Cette réservation est déjà "
                        "entièrement payée."
                    )
                })

            # ------------------------------------------------
            # DEPASSEMENT
            # ------------------------------------------------

            if amount > remaining:

                raise serializers.ValidationError({
                    "amount": (
                        f"Le montant maximum autorisé est "
                        f"{remaining} $."
                    )
                })

            # On remplace l'objet reservation du serializer
            # par l'objet verrouillé.
            validated_data["reservation"] = (
                locked_reservation
            )

        # ----------------------------------------------------
        # REFERENCE UNIQUE SI FOURNIE
        # ----------------------------------------------------

        reference = validated_data.get("reference")

        if reference:

            existing_reference = (
                Payment.objects
                .select_for_update()
                .filter(reference=reference)
                .first()
            )

            if existing_reference:

                raise serializers.ValidationError({
                    "reference": (
                        "Cette référence de paiement "
                        "est déjà utilisée."
                    ),
                    "payment_id": existing_reference.id,
                })

        # ----------------------------------------------------
        # CREATION UNIQUE
        # ----------------------------------------------------

        serializer.save(
            created_by=self.request.user
        )

    # ========================================================
    # VALIDER
    # ========================================================

    @action(
        detail=True,
        methods=["post"],
        url_path="valider",
    )
    @transaction.atomic
    def valider(self, request, pk=None):

        # ----------------------------------------------------
        # VERROUILLER LE PAIEMENT
        # ----------------------------------------------------

        payment = (
            Payment.objects
            .select_for_update()
            .select_related(
                "reservation",
                "reservation__client",
                "financial_account",
            )
            .get(pk=pk)
        )

        # ----------------------------------------------------
        # DEJA VALIDE
        # ----------------------------------------------------

        if payment.status == Payment.Status.VALIDE:

            return Response(
                {
                    "detail": (
                        "Ce paiement est déjà validé."
                    ),
                    "payment": PaymentSerializer(
                        payment,
                        context={
                            "request": request,
                        },
                    ).data,
                },
                status=status.HTTP_200_OK,
            )

        # ----------------------------------------------------
        # ANNULE
        # ----------------------------------------------------

        if payment.status == Payment.Status.ANNULE:

            return Response(
                {
                    "detail": (
                        "Un paiement annulé ne peut pas "
                        "être validé."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ----------------------------------------------------
        # VERROUILLER LA RESERVATION
        # ----------------------------------------------------

        reservation = None

        if payment.reservation_id:

            reservation = (
                Reservation.objects
                .select_for_update()
                .select_related("tarif")
                .get(
                    pk=payment.reservation_id
                )
            )

            # ------------------------------------------------
            # CALCUL DU RESTE
            # ------------------------------------------------

            total = (
                reservation.total_amount
                or Decimal("0.00")
            )

            other_paid = (
                Payment.objects
                .filter(
                    reservation=reservation,
                    status=Payment.Status.VALIDE,
                )
                .exclude(pk=payment.pk)
                .aggregate(
                    total=Sum("amount")
                )
                .get("total")
                or Decimal("0.00")
            )

            refunded = (
                reservation.refunded_amount
            )

            remaining = (
                total
                - other_paid
                + refunded
            )

            if remaining < Decimal("0.00"):
                remaining = Decimal("0.00")

            # ------------------------------------------------
            # PAIEMENT DEJA COUVERT
            # ------------------------------------------------

            if remaining <= Decimal("0.00"):

                return Response(
                    {
                        "detail": (
                            "Cette réservation est déjà "
                            "entièrement payée."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # ------------------------------------------------
            # DEPASSEMENT
            # ------------------------------------------------

            if payment.amount > remaining:

                return Response(
                    {
                        "detail": (
                            f"Le montant du paiement "
                            f"({payment.amount} $) dépasse "
                            f"le reste à payer "
                            f"({remaining} $)."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # ====================================================
        # VALIDATION DU PAIEMENT
        # ====================================================

        payment.status = Payment.Status.VALIDE

        payment.save(
            update_fields=["status"]
        )

        # ====================================================
        # MOUVEMENT FINANCIER UNIQUE
        # ====================================================

        if payment.financial_account:

            # -----------------------------------------------
            # VERROUILLAGE DU COMPTE
            # -----------------------------------------------

            account = (
                FinancialAccount.objects
                .select_for_update()
                .get(
                    pk=payment.financial_account_id
                )
            )

            # -----------------------------------------------
            # VERIFICATION EXISTENCE MOUVEMENT
            # -----------------------------------------------

            mouvement_existe = (
                CashMovement.objects
                .filter(
                    payment=payment,
                    movement_type=(
                        CashMovement.MovementType.ENTREE
                    ),
                )
                .exists()
            )

            # -----------------------------------------------
            # CREATION UNIQUE
            # -----------------------------------------------

            if not mouvement_existe:

                account.balance += payment.amount

                account.save(
                    update_fields=["balance"]
                )

                CashMovement.objects.create(
                    account=account,
                    payment=payment,
                    reservation=payment.reservation,
                    movement_type=(
                        CashMovement.MovementType.ENTREE
                    ),
                    amount=payment.amount,
                    description=(
                        f"Paiement validé "
                        f"#{payment.id}"
                    ),
                    created_by=request.user,
                )

        # ====================================================
        # MISE A JOUR RESERVATION
        # ====================================================

        if reservation:

            reservation.recalculate_financials()

        # ====================================================
        # RECU PDF
        # ====================================================

        try:

            generate_payment_receipt_pdf(
                payment
            )

        except Exception as exc:

            print(
                "Erreur génération reçu PDF :",
                exc,
            )

        # ====================================================
        # REPONSE
        # ====================================================

        return Response(
            PaymentSerializer(
                payment,
                context={
                    "request": request,
                },
            ).data,
            status=status.HTTP_200_OK,
        )

    # ========================================================
    # ANNULER
    # ========================================================

    @action(
        detail=True,
        methods=["post"],
        url_path="annuler",
    )
    @transaction.atomic
    def annuler(self, request, pk=None):

        payment = (
            Payment.objects
            .select_for_update()
            .get(pk=pk)
        )

        if payment.status == Payment.Status.VALIDE:

            return Response(
                {
                    "detail": (
                        "Un paiement déjà validé ne peut "
                        "pas être annulé directement. "
                        "Utilisez une procédure de "
                        "remboursement ou de correction."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if payment.status == Payment.Status.ANNULE:

            return Response(
                {
                    "detail": (
                        "Ce paiement est déjà annulé."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment.status = Payment.Status.ANNULE

        payment.save(
            update_fields=["status"]
        )

        return Response(
            PaymentSerializer(
                payment,
                context={
                    "request": request,
                },
            ).data
        )

    # ========================================================
    # RECU PDF
    # ========================================================

    @action(
        detail=True,
        methods=["get"],
        url_path="recu",
    )
    def recu(self, request, pk=None):

        payment = self.get_object()

        if payment.status != Payment.Status.VALIDE:

            return Response(
                {
                    "detail": (
                        "Le reçu ne peut être généré "
                        "que pour un paiement validé."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        pdf = generate_payment_receipt_pdf(
            payment
        )

        return pdf


# ============================================================
# RESERVATIONS
# ============================================================

class ReservationViewSet(viewsets.ModelViewSet):

    queryset = (
        Reservation.objects
        .select_related(
            "client",
            "hall",
            "tarif",
        )
        .prefetch_related(
            "payments",
            "refunds",
        )
        .order_by("-event_date")
    )

    serializer_class = ReservationSerializer

    permission_classes = [IsAuthenticated]

    # --------------------------------------------------------
    # CREATION
    # --------------------------------------------------------

    def perform_create(self, serializer):

        reservation = serializer.save(
            created_by=self.request.user
        )

        Notification.objects.create(
            user=self.request.user,

            notification_type=(
                Notification.NotificationType.RESERVATION_CREATED
            ),

            title="Nouvelle réservation",

            message=(
                f"La réservation "
                f"{reservation.reservation_number} "
                f"a été créée."
            ),

            reservation=reservation,
        )

    # --------------------------------------------------------
    # MODIFICATION
    # --------------------------------------------------------

    def perform_update(self, serializer):

        old_status = serializer.instance.status

        reservation = serializer.save()

        if (
            old_status != Reservation.Status.CONFIRMEE
            and reservation.status
            == Reservation.Status.CONFIRMEE
        ):

            Notification.objects.create(
                user=self.request.user,

                notification_type=(
                    Notification.NotificationType.RESERVATION_CONFIRMED
                ),

                title="Réservation confirmée",

                message=(
                    f"La réservation "
                    f"{reservation.reservation_number} "
                    f"a été confirmée."
                ),

                reservation=reservation,
            )

    # --------------------------------------------------------
    # CONFIRMER
    # --------------------------------------------------------

    @action(
        detail=True,
        methods=["post"],
        url_path="confirmer",
    )
    def confirmer(self, request, pk=None):

        reservation = self.get_object()

        if (
            reservation.status
            == Reservation.Status.ANNULEE
        ):
            return Response(
                {
                    "detail": (
                        "Une réservation annulée "
                        "ne peut pas être confirmée."
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
                f"La réservation "
                f"{reservation.reservation_number} "
                f"est maintenant confirmée."
            ),

            reservation=reservation,
        )

        return Response(
            ReservationSerializer(
                reservation,
                context={
                    "request": request,
                },
            ).data
        )

    # --------------------------------------------------------
    # ANNULER
    # --------------------------------------------------------

    @action(
        detail=True,
        methods=["post"],
        url_path="annuler",
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
                f"La réservation "
                f"{reservation.reservation_number} "
                f"a été annulée."
            ),

            reservation=reservation,
        )

        return Response(
            ReservationSerializer(
                reservation,
                context={
                    "request": request,
                },
            ).data
        )




# ============================================================
# DEPENSES
# ============================================================

class ExpenseViewSet(viewsets.ModelViewSet):

    queryset = (
        Expense.objects
        .select_related("created_by")
        .all()
        .order_by("-expense_date", "-id")
    )

    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated]

    # ========================================================
    # CREATION
    # ========================================================

    @transaction.atomic
    def perform_create(self, serializer):

        serializer.save(
            created_by=self.request.user
        )

        expense = serializer.instance

        send_notification(
            subject="Nouvelle dépense",
            message=(
                f"Une nouvelle dépense a été enregistrée.\n\n"
                f"Titre : {expense.title}\n"
                f"Catégorie : "
                f"{expense.get_category_display()}\n"
                f"Montant : {expense.amount} $\n"
                f"Statut : "
                f"{expense.get_status_display()}"
            ),
        )

    # ========================================================
    # MODIFICATION
    # ========================================================

    @transaction.atomic
    def perform_update(self, serializer):

        serializer.save()

    # ========================================================
    # PAYER UNE DEPENSE
    # ========================================================

    @action(
        detail=True,
        methods=["post"],
        url_path="payer",
    )
    @transaction.atomic
    def payer(self, request, pk=None):

        expense = (
            Expense.objects
            .select_for_update()
            .select_related("created_by")
            .get(pk=pk)
        )

        # ----------------------------------------------------
        # DEJA PAYEE
        # ----------------------------------------------------

        if expense.status == Expense.Status.PAYEE:

            return Response(
                {
                    "detail": (
                        "Cette dépense est déjà payée."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ----------------------------------------------------
        # ANNULEE
        # ----------------------------------------------------

        if expense.status == Expense.Status.ANNULEE:

            return Response(
                {
                    "detail": (
                        "Une dépense annulée "
                        "ne peut pas être payée."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ----------------------------------------------------
        # PASSAGE A PAYEE
        # ----------------------------------------------------
        #
        # Le modèle Expense.save() s'occupe automatiquement :
        #
        # - de trouver la caisse active ;
        # - vérifier le solde ;
        # - diminuer la caisse ;
        # - créer CashMovement SORTIE.
        #

        expense.status = Expense.Status.PAYEE

        expense.save(
            update_fields=[
                "status",
            ]
        )

        send_notification(
            subject="Dépense payée",
            message=(
                f"La dépense #{expense.id} a été payée.\n\n"
                f"Titre : {expense.title}\n"
                f"Montant : {expense.amount} $"
            ),
        )

        return Response(
            ExpenseSerializer(
                expense,
                context={
                    "request": request,
                },
            ).data,
            status=status.HTTP_200_OK,
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
# CALENDRIER
# ============================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def calendar_view(request, year, month):
    """
    Retourne les réservations du mois demandé
    pour alimenter le calendrier frontend.
    """

    reservations = (
        Reservation.objects
        .filter(
            event_date__year=year,
            event_date__month=month,
        )
        .select_related("client", "hall")
        .order_by("event_date", "start_time")
    )

    results = []

    for reservation in reservations:
        results.append({
            "id": reservation.id,
            "reservation_number": reservation.reservation_number,

            "client": (
                str(reservation.client)
                if reservation.client
                else None
            ),

            "hall": (
                str(reservation.hall)
                if reservation.hall
                else None
            ),

            "event_type": reservation.event_type or "",

            "date": (
                reservation.event_date.isoformat()
                if reservation.event_date
                else None
            ),

            "start_time": (
                reservation.start_time.strftime("%H:%M")
                if reservation.start_time
                else ""
            ),

            "end_time": (
                reservation.end_time.strftime("%H:%M")
                if reservation.end_time
                else ""
            ),

            "status": reservation.status,

            "payment_status": getattr(
                reservation,
                "payment_status",
                ""
            ),
        })

    return JsonResponse({
        "year": year,
        "month": month,
        "count": len(results),
        "results": results,
    })




class PersonnelViewSet(viewsets.ModelViewSet):

    queryset = Personnel.objects.all().order_by(
        "nom",
        "prenom",
    )

    serializer_class = PersonnelSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):

        personnel = serializer.save()

        send_notification(
            subject="Nouveau personnel",
            message=(
                f"Un nouveau membre du personnel "
                f"a été ajouté.\n\n"
                f"Nom : "
                f"{personnel.nom} "
                f"{personnel.prenom}"
            ),
        )



# ============================================================
# TABLEAU DE BORD / RAPPORTS
# ============================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_report(request):
    """
    Tableau de bord global de l'application.

    Sources financières :
    - chiffre d'affaires théorique : tarifs des réservations non annulées
    - encaissements : paiements VALIDES
    - dépenses : Expense
    - remboursements : Refund
    - soldes : FinancialAccount
    - mouvements : CashMovement
    """

    # ========================================================
    # QUERYSETS
    # ========================================================

    reservations = (
        Reservation.objects
        .select_related(
            "client",
            "hall",
            "tarif",
        )
        .prefetch_related("payments", "refunds")
        .all()
    )

    payments = Payment.objects.filter(
        status=Payment.Status.VALIDE
    )

    expenses = Expense.objects.all()

    refunds = Refund.objects.all()

    accounts = FinancialAccount.objects.filter(
        is_active=True
    )

    movements = CashMovement.objects.all()

    # ========================================================
    # RESERVATIONS
    # ========================================================

    total_reservations = reservations.count()

    reservations_annulees = reservations.filter(
        status=Reservation.Status.ANNULEE
    ).count()

    reservations_actives = reservations.exclude(
        status=Reservation.Status.ANNULEE
    ).count()

    reservations_terminees = reservations.filter(
        status__in=[
            Reservation.Status.TERMINEE,
            Reservation.Status.CLOTUREE,
        ]
    ).count()

    # ========================================================
    # CHIFFRE D'AFFAIRES THEORIQUE
    # ========================================================

    chiffre_affaires = Decimal("0.00")

    for reservation in reservations:

        if reservation.status == Reservation.Status.ANNULEE:
            continue

        if reservation.tarif_id:
            chiffre_affaires += (
                reservation.tarif.amount
                or Decimal("0.00")
            )

    # ========================================================
    # ENCAISSEMENTS
    # ========================================================

    total_encaisse = (
        payments
        .aggregate(
            total=Sum("amount")
        )
        .get("total")
        or Decimal("0.00")
    )

    # ========================================================
    # DEPENSES
    # ========================================================

    total_depenses = (
        expenses
        .exclude(
            status=Expense.Status.ANNULEE
        )
        .aggregate(
            total=Sum("amount")
        )
        .get("total")
        or Decimal("0.00")
    )

    # ========================================================
    # REMBOURSEMENTS VALIDES
    # ========================================================

    total_rembourse = (
        refunds
        .filter(
            status=Refund.Status.VALIDE
        )
        .aggregate(
            total=Sum("amount")
        )
        .get("total")
        or Decimal("0.00")
    )

    # ========================================================
    # RESTE A RECOUVRER
    # ========================================================

    reste_a_recouvrer = Decimal("0.00")

    for reservation in reservations:

        if reservation.status == Reservation.Status.ANNULEE:
            continue

        montant_reservation = Decimal("0.00")

        if reservation.tarif_id:
            montant_reservation = (
                reservation.tarif.amount
                or Decimal("0.00")
            )

        montant_paye = (
            payments
            .filter(
                reservation_id=reservation.id
            )
            .aggregate(
                total=Sum("amount")
            )
            .get("total")
            or Decimal("0.00")
        )

        montant_rembourse = (
            refunds
            .filter(
                reservation_id=reservation.id,
                status=Refund.Status.VALIDE,
            )
            .aggregate(
                total=Sum("amount")
            )
            .get("total")
            or Decimal("0.00")
        )

        montant_net_paye = (
            montant_paye - montant_rembourse
        )

        reste = (
            montant_reservation
            - montant_net_paye
        )

        if reste > Decimal("0.00"):
            reste_a_recouvrer += reste

    # ========================================================
    # SOLDE DES COMPTES
    # ========================================================

    solde_comptes = (
        accounts
        .aggregate(
            total=Sum("balance")
        )
        .get("total")
        or Decimal("0.00")
    )

    # ========================================================
    # RESULTAT NET
    # ========================================================

    resultat_net = (
        total_encaisse
        - total_depenses
        - total_rembourse
    )

    # ========================================================
    # COMPTES FINANCIERS
    # ========================================================

    comptes = []

    for account in accounts:

        comptes.append({
            "id": account.id,
            "name": account.name,
            "account_type": account.account_type,
            "account_type_display": (
                account.get_account_type_display()
            ),
            "balance": float(
                account.balance
                or Decimal("0.00")
            ),
            "is_active": account.is_active,
        })

    # ========================================================
    # PAIEMENTS PAR MODE
    # ========================================================

    paiements_par_mode = []

    for method, label in Payment.Method.choices:

        total = (
            payments
            .filter(
                method=method
            )
            .aggregate(
                total=Sum("amount")
            )
            .get("total")
            or Decimal("0.00")
        )

        paiements_par_mode.append({
            "method": method,
            "label": label,
            "amount": float(total),
        })

    # ========================================================
    # DEPENSES PAR CATEGORIE
    # ========================================================
    #
    # Expense.category est actuellement un CharField simple.
    #
    # Il n'existe donc PAS :
    #
    # Expense.ExpenseType.choices
    #
    # Les catégories utilisées par le formulaire sont définies
    # ici de manière cohérente avec le frontend.
    # ========================================================

    expense_categories = [
        ("EAU", "Eau"),
        ("ELECTRICITE", "Électricité"),
        ("SALAIRE", "Salaire"),
        ("AUTRE", "Autre"),
    ]

    depenses_par_categorie = []

    for category, label in expense_categories:

        total = (
            expenses
            .filter(
                category=category
            )
            .exclude(
                status=Expense.Status.ANNULEE
            )
            .aggregate(
                total=Sum("amount")
            )
            .get("total")
            or Decimal("0.00")
        )

        depenses_par_categorie.append({
            "category": category,
            "label": label,
            "amount": float(total),
        })

    # ========================================================
    # RESERVATIONS PAR STATUT
    # ========================================================

    reservations_par_statut = []

    for status_value, label in Reservation.Status.choices:

        total = reservations.filter(
            status=status_value
        ).count()

        reservations_par_statut.append({
            "status": status_value,
            "label": label,
            "count": total,
        })

    # ========================================================
    # REVENUS MENSUELS
    # ========================================================

    revenus_mensuels = (
        payments
        .filter(
            payment_date__isnull=False
        )
        .annotate(
            mois=TruncMonth("payment_date")
        )
        .values("mois")
        .annotate(
            total=Sum("amount")
        )
        .order_by("mois")
    )

    revenus_chart = []

    for item in revenus_mensuels:

        mois = item.get("mois")

        if not mois:
            continue

        revenus_chart.append({
            "month": mois.strftime("%Y-%m"),
            "amount": float(
                item.get("total")
                or Decimal("0.00")
            ),
        })

    # ========================================================
    # DEPENSES MENSUELLES
    # ========================================================

    depenses_mensuelles = (
        expenses
        .exclude(
            status=Expense.Status.ANNULEE
        )
        .filter(
            expense_date__isnull=False
        )
        .annotate(
            mois=TruncMonth("expense_date")
        )
        .values("mois")
        .annotate(
            total=Sum("amount")
        )
        .order_by("mois")
    )

    depenses_chart = []

    for item in depenses_mensuelles:

        mois = item.get("mois")

        if not mois:
            continue

        depenses_chart.append({
            "month": mois.strftime("%Y-%m"),
            "amount": float(
                item.get("total")
                or Decimal("0.00")
            ),
        })

    # ========================================================
    # MOUVEMENTS FINANCIERS
    # ========================================================

    total_entrees = (
        movements
        .filter(
            movement_type=CashMovement.MovementType.ENTREE
        )
        .aggregate(
            total=Sum("amount")
        )
        .get("total")
        or Decimal("0.00")
    )

    total_sorties = (
        movements
        .filter(
            movement_type=CashMovement.MovementType.SORTIE
        )
        .aggregate(
            total=Sum("amount")
        )
        .get("total")
        or Decimal("0.00")
    )

    # ========================================================
    # REPONSE FINALE
    # ========================================================

    return Response({
        "summary": {
            "total_reservations": total_reservations,

            "reservations_actives": reservations_actives,

            "reservations_annulees": reservations_annulees,

            "reservations_terminees": reservations_terminees,

            "chiffre_affaires": float(
                chiffre_affaires
            ),

            "total_encaisse": float(
                total_encaisse
            ),

            "total_depenses": float(
                total_depenses
            ),

            "total_rembourse": float(
                total_rembourse
            ),

            "reste_a_recouvrer": float(
                reste_a_recouvrer
            ),

            "solde_comptes": float(
                solde_comptes
            ),

            "resultat_net": float(
                resultat_net
            ),

            "total_entrees": float(
                total_entrees
            ),

            "total_sorties": float(
                total_sorties
            ),
        },

        "accounts": comptes,

        "payments_by_method": paiements_par_mode,

        "expenses_by_category": depenses_par_categorie,

        "reservations_by_status": reservations_par_statut,

        "monthly": {
            "revenues": revenus_chart,
            "expenses": depenses_chart,
        },
    })
# ============================================================
# EXPORT EXCEL
# ============================================================


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_excel(request):

    reservations = (
        Reservation.objects
        .select_related(
            "client",
            "hall",
            "tarif",
        )
        .prefetch_related("payments")
        .all()
    )

    payments = (
        Payment.objects
        .select_related(
            "reservation",
            "reservation__client",
            "financial_account",
        )
        .filter(
            status=Payment.Status.VALIDE
        )
    )

    expenses = (
        Expense.objects
        .select_related(
            "created_by"
        )
        .all()
    )

    movements = (
        CashMovement.objects
        .select_related(
            "account",
            "reservation",
            "payment",
        )
        .all()
    )

    refunds = Refund.objects.all()

    workbook = Workbook()

    # ========================================================
    # FEUILLE SYNTHESE
    # ========================================================

    ws = workbook.active
    ws.title = "Synthèse"

    ws.append([
        "RAPPORT FINANCIER - ELISABETH"
    ])

    ws.append([])

    # Chiffre d'affaires théorique
    chiffre_affaires = Decimal("0.00")

    for reservation in reservations:

        if reservation.status == Reservation.Status.ANNULEE:
            continue

        if reservation.tarif:
            chiffre_affaires += (
                reservation.tarif.amount
                or Decimal("0.00")
            )

    encaisse = (
        payments
        .aggregate(
            total=Sum("amount")
        )
        .get("total")
        or Decimal("0.00")
    )

    depenses = (
        expenses
        .aggregate(
            total=Sum("amount")
        )
        .get("total")
        or Decimal("0.00")
    )

    remboursements = (
        refunds
        .aggregate(
            total=Sum("amount")
        )
        .get("total")
        or Decimal("0.00")
    )

    reste = Decimal("0.00")

    for reservation in reservations:

        if reservation.status == Reservation.Status.ANNULEE:
            continue

        montant = Decimal("0.00")

        if reservation.tarif:
            montant = (
                reservation.tarif.amount
                or Decimal("0.00")
            )

        paye = (
            payments
            .filter(
                reservation=reservation
            )
            .aggregate(
                total=Sum("amount")
            )
            .get("total")
            or Decimal("0.00")
        )

        difference = montant - paye

        if difference > Decimal("0.00"):
            reste += difference

    resultat = (
        encaisse
        - depenses
        - remboursements
    )

    synthese = [
        ["Indicateur", "Montant"],
        [
            "Chiffre d'affaires",
            float(chiffre_affaires),
        ],
        [
            "Total encaissé",
            float(encaisse),
        ],
        [
            "Total dépenses",
            float(depenses),
        ],
        [
            "Total remboursements",
            float(remboursements),
        ],
        [
            "Reste à recouvrer",
            float(reste),
        ],
        [
            "Résultat net",
            float(resultat),
        ],
    ]

    for row in synthese:
        ws.append(row)

    ws["A1"].font = Font(
        bold=True,
        size=16,
    )

    # ========================================================
    # RESERVATIONS
    # ========================================================

    ws_res = workbook.create_sheet(
        "Réservations"
    )

    ws_res.append([
        "Numéro",
        "Client",
        "Salle",
        "Événement",
        "Date",
        "Tarif",
        "Payé",
        "Reste",
        "Statut",
        "Paiement",
    ])

    for reservation in reservations:

        tarif = Decimal("0.00")

        if reservation.tarif:
            tarif = (
                reservation.tarif.amount
                or Decimal("0.00")
            )

        paye = (
            payments
            .filter(
                reservation=reservation
            )
            .aggregate(
                total=Sum("amount")
            )
            .get("total")
            or Decimal("0.00")
        )

        reste_reservation = tarif - paye

        if reste_reservation < Decimal("0.00"):
            reste_reservation = Decimal("0.00")

        ws_res.append([
            reservation.reservation_number,

            (
                reservation.client.full_name
                if reservation.client
                else ""
            ),

            (
                reservation.hall.name
                if reservation.hall
                else ""
            ),

            reservation.event_type,

            reservation.event_date,

            float(tarif),

            float(paye),

            float(reste_reservation),

            reservation.get_status_display(),

            reservation.get_payment_status_display(),
        ])

    # ========================================================
    # PAIEMENTS
    # ========================================================

    ws_pay = workbook.create_sheet(
        "Paiements"
    )

    ws_pay.append([
        "ID",
        "Réservation",
        "Client",
        "Montant",
        "Mode",
        "Compte",
        "Date",
        "Référence",
        "Statut",
    ])

    for payment in payments:

        ws_pay.append([
            payment.id,

            (
                payment.reservation.reservation_number
                if payment.reservation
                else ""
            ),

            (
                payment.reservation.client.full_name
                if (
                    payment.reservation
                    and payment.reservation.client
                )
                else ""
            ),

            float(payment.amount),

            payment.get_method_display(),

            (
                payment.financial_account.name
                if payment.financial_account
                else ""
            ),

            payment.payment_date,

            payment.reference or "",

            payment.get_status_display(),
        ])

    # ========================================================
    # DEPENSES
    # ========================================================

    ws_exp = workbook.create_sheet(
        "Dépenses"
    )

    ws_exp.append([
        "ID",
        "Catégorie",
        "Description",
        "Montant",
        "Compte",
        "Date",
    ])

    for expense in expenses:

        ws_exp.append([
            expense.id,
            expense.get_category_display(),
            expense.description,
            float(expense.amount),

            (
                expense.financial_account.name
                if expense.financial_account
                else ""
            ),

            expense.expense_date,
        ])

    # ========================================================
    # MOUVEMENTS
    # ========================================================

    ws_mov = workbook.create_sheet(
        "Mouvements"
    )

    ws_mov.append([
        "ID",
        "Type",
        "Montant",
        "Compte",
        "Description",
        "Réservation",
        "Date",
    ])

    for movement in movements:

        ws_mov.append([
            movement.id,

            movement.get_movement_type_display(),

            float(movement.amount),

            (
                movement.account.name
                if movement.account
                else ""
            ),

            movement.description,

            (
                movement.reservation.reservation_number
                if movement.reservation
                else ""
            ),

            movement.created_at,
        ])

    # ========================================================
    # LARGEUR DES COLONNES
    # ========================================================

    for sheet in workbook.worksheets:

        for column in sheet.columns:

            max_length = 0

            column_letter = (
                column[0].column_letter
            )

            for cell in column:

                value = str(
                    cell.value or ""
                )

                if len(value) > max_length:
                    max_length = len(value)

            sheet.column_dimensions[
                column_letter
            ].width = min(
                max_length + 3,
                40,
            )

        for cell in sheet[1]:

            cell.font = Font(
                bold=True
            )

            cell.alignment = Alignment(
                horizontal="center"
            )

    # ========================================================
    # REPONSE
    # ========================================================

    response = HttpResponse(
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )

    response[
        "Content-Disposition"
    ] = (
        'attachment; filename="rapport-elisabeth.xlsx"'
    )

    workbook.save(response)

    return response








# ============================================================
# EXPORT PDF
# ============================================================


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_pdf(request):

    reservations = (
        Reservation.objects
        .select_related("tarif")
        .prefetch_related("payments")
        .all()
    )

    payments = Payment.objects.filter(
        status=Payment.Status.VALIDE
    )

    expenses = Expense.objects.all()

    refunds = Refund.objects.all()

    # ========================================================
    # CHIFFRE D'AFFAIRES
    # ========================================================

    chiffre_affaires = Decimal("0.00")

    for reservation in reservations:

        if reservation.status == Reservation.Status.ANNULEE:
            continue

        if reservation.tarif:
            chiffre_affaires += (
                reservation.tarif.amount
                or Decimal("0.00")
            )

    # ========================================================
    # ENCAISSE
    # ========================================================

    encaisse = (
        payments
        .aggregate(
            total=Sum("amount")
        )
        .get("total")
        or Decimal("0.00")
    )

    # ========================================================
    # DEPENSES
    # ========================================================

    depenses = (
        expenses
        .aggregate(
            total=Sum("amount")
        )
        .get("total")
        or Decimal("0.00")
    )

    # ========================================================
    # REMBOURSEMENTS
    # ========================================================

    remboursements = (
        refunds
        .aggregate(
            total=Sum("amount")
        )
        .get("total")
        or Decimal("0.00")
    )

    # ========================================================
    # RESTE A RECOUVRER
    # ========================================================

    reste = Decimal("0.00")

    for reservation in reservations:

        if reservation.status == Reservation.Status.ANNULEE:
            continue

        montant = Decimal("0.00")

        if reservation.tarif:
            montant = (
                reservation.tarif.amount
                or Decimal("0.00")
            )

        paye = (
            payments
            .filter(
                reservation=reservation
            )
            .aggregate(
                total=Sum("amount")
            )
            .get("total")
            or Decimal("0.00")
        )

        difference = montant - paye

        if difference > Decimal("0.00"):
            reste += difference

    # ========================================================
    # RESULTAT
    # ========================================================

    resultat = (
        encaisse
        - depenses
        - remboursements
    )

    # ========================================================
    # REPONSE PDF
    # ========================================================

    response = HttpResponse(
        content_type="application/pdf"
    )

    response[
        "Content-Disposition"
    ] = (
        'attachment; filename="rapport-elisabeth.pdf"'
    )

    document = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()

    elements = []

    elements.append(
        Paragraph(
            "LA CASA DA FESTA ELISABETH",
            styles["Title"],
        )
    )

    elements.append(
        Paragraph(
            "Rapport général d'activité",
            styles["Heading2"],
        )
    )

    elements.append(
        Spacer(1, 20)
    )

    data = [
        [
            "Indicateur",
            "Montant",
        ],

        [
            "Chiffre d'affaires",
            f"{chiffre_affaires:,.2f} $",
        ],

        [
            "Total encaissé",
            f"{encaisse:,.2f} $",
        ],

        [
            "Total dépenses",
            f"{depenses:,.2f} $",
        ],

        [
            "Total remboursements",
            f"{remboursements:,.2f} $",
        ],

        [
            "Reste à recouvrer",
            f"{reste:,.2f} $",
        ],

        [
            "Résultat net",
            f"{resultat:,.2f} $",
        ],
    ]

    table = Table(
        data,
        colWidths=[300, 150],
    )

    table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#1e293b"),
            ),
            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white,
            ),
            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Helvetica-Bold",
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey,
            ),
            (
                "PADDING",
                (0, 0),
                (-1, -1),
                8,
            ),
        ])
    )

    elements.append(table)

    elements.append(
        Spacer(1, 20)
    )

    elements.append(
        Paragraph(
            f"Nombre total de réservations : "
            f"{reservations.count()}",
            styles["BodyText"],
        )
    )

    elements.append(
        Paragraph(
            f"Nombre de paiements validés : "
            f"{payments.count()}",
            styles["BodyText"],
        )
    )

    elements.append(
        Paragraph(
            f"Nombre de dépenses : "
            f"{expenses.count()}",
            styles["BodyText"],
        )
    )

    document.build(elements)

    return response



class RefundViewSet(viewsets.ModelViewSet):
    queryset = Refund.objects.select_related("reservation", "financial_account", "created_by").all()
    serializer_class = RefundSerializer
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def perform_create(self, serializer):
        refund = serializer.save(created_by=self.request.user)
        if refund.status == Refund.Status.VALIDE:
            self._process_refund_payout(refund, self.request.user)

    @action(detail=True, methods=["post"], url_path="valider")
    @transaction.atomic
    def valider(self, request, pk=None):
        refund = Refund.objects.select_for_update().get(pk=pk)

        if refund.status == Refund.Status.VALIDE:
            return Response(
                {"detail": "Ce remboursement est déjà validé."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        self._process_refund_payout(refund, request.user)

        refund.status = Refund.Status.VALIDE
        refund.save(update_fields=["status"])

        # Recalculer le bilan financier de la réservation
        if refund.reservation:
            refund.reservation.recalculate_financials()

        return Response(RefundSerializer(refund, context={"request": request}).data)

    def _process_refund_payout(self, refund, user):
        account = FinancialAccount.objects.select_for_update().get(pk=refund.financial_account_id)

        if account.balance < refund.amount:
            raise serializers.ValidationError({
                "detail": f"Solde insuffisant dans la caisse '{account.name}' pour effectuer ce remboursement. Solde actuel : {account.balance} $."
            })

        movement_exists = CashMovement.objects.filter(
            refund=refund,
            movement_type=CashMovement.MovementType.SORTIE,
        ).exists()

        if not movement_exists:
            # 1. Diminuer le solde de la caisse
            account.balance -= refund.amount
            account.save(update_fields=["balance"])

            # 2. Créer la sortie de caisse
            CashMovement.objects.create(
                account=account,
                refund=refund,
                reservation=refund.reservation,
                movement_type=CashMovement.MovementType.SORTIE,
                amount=refund.amount,
                description=f"Sortie Remboursement #{refund.id} - Réservation #{refund.reservation_id}",
                created_by=user,
            )