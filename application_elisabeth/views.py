from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

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
    Notification,
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
    NotificationSerializer,
    PersonnelSerializer,
    HallSerializer,
    HallImageSerializer,
    HallVideoSerializer,
    TarifSerializer,
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
    queryset = Hall.objects.all().prefetch_related(
        "images",
        "videos",
    )

    serializer_class = HallSerializer

    parser_classes = [
        MultiPartParser,
        FormParser,
        JSONParser,
    ]

    def create(self, request, *args, **kwargs):
        """
        Création d'une salle avec éventuellement plusieurs
        images et plusieurs vidéos.
        """

        # -----------------------------
        # DONNÉES DE LA SALLE
        # -----------------------------
        name = request.data.get("name")
        description = request.data.get("description", "")
        capacity = request.data.get("capacity", 0)
        price = request.data.get("price", 0)
        is_active = request.data.get("is_active", "true")

        if not name:
            return Response(
                {
                    "name": [
                        "Le nom de la salle est obligatoire."
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Conversion du booléen envoyé par FormData
        if isinstance(is_active, str):
            is_active = is_active.lower() in [
                "true",
                "1",
                "yes",
                "on",
            ]

        # -----------------------------
        # CRÉATION DE LA SALLE
        # -----------------------------
        serializer = self.get_serializer(
            data={
                "name": name,
                "description": description,
                "capacity": capacity,
                "price": price,
                "is_active": is_active,
            }
        )

        serializer.is_valid(raise_exception=True)

        hall = serializer.save()

        # -----------------------------
        # IMAGES
        # -----------------------------
        images = request.FILES.getlist("images")

        for image in images:
            HallImage.objects.create(
                hall=hall,
                image=image,
            )

        # -----------------------------
        # VIDÉOS
        # -----------------------------
        videos = request.FILES.getlist("videos")

        for video in videos:
            HallVideo.objects.create(
                hall=hall,
                video=video,
            )

        # -----------------------------
        # RÉPONSE FINALE
        # -----------------------------
        output_serializer = self.get_serializer(
            hall,
            context={
                "request": request,
            },
        )

        return Response(
            output_serializer.data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        """
        Modification d'une salle.

        Les nouvelles images/vidéos peuvent également être ajoutées.
        Les anciennes ne sont pas supprimées automatiquement.
        """

        partial = kwargs.pop("partial", False)

        hall = self.get_object()

        serializer = self.get_serializer(
            hall,
            data=request.data,
            partial=partial,
        )

        serializer.is_valid(raise_exception=True)

        hall = serializer.save()

        # Ajouter de nouvelles images si présentes
        images = request.FILES.getlist("images")

        for image in images:
            HallImage.objects.create(
                hall=hall,
                image=image,
            )

        # Ajouter de nouvelles vidéos si présentes
        videos = request.FILES.getlist("videos")

        for video in videos:
            HallVideo.objects.create(
                hall=hall,
                video=video,
            )

        output_serializer = self.get_serializer(
            hall,
            context={
                "request": request,
            },
        )

        return Response(output_serializer.data)

    def destroy(self, request, *args, **kwargs):
        """
        Suppression de la salle.
        Les images et vidéos associées sont supprimées
        automatiquement grâce à on_delete=CASCADE.
        """

        hall = self.get_object()

        hall.delete()

        return Response(
            {
                "detail": "Salle supprimée avec succès."
            },
            status=status.HTTP_204_NO_CONTENT,
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

    def perform_create(self, serializer):
        """
        Création d'un paiement.

        Le paiement est créé avec l'utilisateur connecté.
        Le compte financier reste facultatif.
        """

        payment = serializer.save(
            created_by=self.request.user
        )

        # Notification uniquement après création
        if payment.reservation:
            # ✅ CORRECT
    Notification.objects.create(
        user=request.user, # ou payment.user / reservation.client.user selon votre logique
        title="Paiement reçu",
        message="Le paiement a été enregistré avec succès.",
        notification_type="PAIEMENT",  # Nom du champ dans models.py
    )
                title="Nouveau paiement",
                message=(
                    f"Un paiement de {payment.amount} $ "
                    f"a été enregistré pour la réservation "
                    f"{payment.reservation.reservation_number}."
                ),
                reservation=payment.reservation,
                payment=payment,
            )

    @action(
        detail=True,
        methods=["post"],
        url_path="valider",
    )
    @transaction.atomic
    def valider(self, request, pk=None):
        """
        Valide un paiement.

        La validation :
        - change le statut du paiement à VALIDE ;
        - génère le mouvement financier ENTRÉE si nécessaire ;
        - met à jour le statut de paiement de la réservation ;
        - génère le reçu PDF.
        """

        payment = self.get_object()

        if payment.status == Payment.Status.VALIDE:
            return Response(
                {
                    "detail": "Ce paiement est déjà validé."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if payment.status == Payment.Status.ANNULE:
            return Response(
                {
                    "detail": (
                        "Un paiement annulé ne peut pas être validé."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment.status = Payment.Status.VALIDE
        payment.save(
            update_fields=["status"]
        )

        # ----------------------------------------------------
        # MOUVEMENT FINANCIER
        # ----------------------------------------------------

        if payment.financial_account:

            CashMovement.objects.create(
                account=payment.financial_account,
                payment=payment,
                reservation=payment.reservation,
                movement_type=(
                    CashMovement.MovementType.ENTREE
                ),
                amount=payment.amount,
                description=(
                    f"Paiement validé "
                    f"{payment.id}"
                ),
                created_by=request.user,
            )

        # ----------------------------------------------------
        # MISE À JOUR RÉSERVATION
        # ----------------------------------------------------

        if payment.reservation:

            reservation = payment.reservation

            total_paye = (
                Payment.objects
                .filter(
                    reservation=reservation,
                    status=Payment.Status.VALIDE,
                )
                .aggregate(
                    total=Sum("amount")
                )
                .get("total")
                or Decimal("0.00")
            )

            montant_reservation = Decimal("0.00")

            if reservation.tarif:
                montant_reservation = (
                    reservation.tarif.amount
                    or Decimal("0.00")
                )

            if total_paye >= montant_reservation:
                reservation.payment_status = (
                    Reservation.PaymentStatus.PAYE
                )

            elif total_paye > Decimal("0.00"):
                reservation.payment_status = (
                    Reservation.PaymentStatus.PARTIEL
                )

            else:
                reservation.payment_status = (
                    Reservation.PaymentStatus.NON_PAYE
                )

            reservation.save(
                update_fields=["payment_status"]
            )

            # ------------------------------------------------
            # NOTIFICATION
            # ------------------------------------------------

            Notification.objects.create(
                user=request.user,
                notification_type=(
                    Notification.NotificationType.PAYMENT_VALIDATED
                ),
                title="Paiement validé",
                message=(
                    f"Le paiement de "
                    f"{payment.amount} $ "
                    f"pour la réservation "
                    f"{reservation.reservation_number} "
                    f"a été validé."
                ),
                reservation=reservation,
                payment=payment,
            )

        # ----------------------------------------------------
        # REÇU PDF
        # ----------------------------------------------------

        try:
            generate_payment_receipt_pdf(payment)
        except Exception:
            # Le paiement reste valide même si la génération
            # du reçu rencontre un problème.
            pass

        return Response(
            PaymentSerializer(
                payment,
                context={
                    "request": request,
                },
            ).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="annuler",
    )
    @transaction.atomic
    def annuler(self, request, pk=None):
        """
        Annule un paiement qui n'a pas encore été validé.
        """

        payment = self.get_object()

        if payment.status == Payment.Status.VALIDE:
            return Response(
                {
                    "detail": (
                        "Un paiement déjà validé ne peut pas "
                        "être annulé directement. "
                        "Utilisez une procédure de remboursement "
                        "ou de correction."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment.status = Payment.Status.ANNULE

        payment.save(
            update_fields=["status"]
        )

        if payment.reservation:

            Notification.objects.create(
                user=request.user,
                notification_type=(
                    Notification.NotificationType.PAYMENT_CANCELLED
                ),
                title="Paiement annulé",
                message=(
                    f"Le paiement de {payment.amount} $ "
                    f"pour la réservation "
                    f"{payment.reservation.reservation_number} "
                    f"a été annulé."
                ),
                reservation=payment.reservation,
                payment=payment,
            )

        return Response(
            PaymentSerializer(
                payment,
                context={
                    "request": request,
                },
            ).data
        )

    @action(
        detail=True,
        methods=["get"],
        url_path="recu",
    )
    def recu(self, request, pk=None):
        """
        Génère/télécharge le reçu PDF du paiement.
        """

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

        pdf = generate_payment_receipt_pdf(payment)

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
        .select_related(
            "financial_account",
            "created_by",
        )
        .all()
        .order_by("-expense_date", "-id")
    )

    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def perform_create(self, serializer):

        caisse = (
            FinancialAccount.objects
            .filter(
                account_type=FinancialAccount.AccountType.CAISSE,
                is_active=True,
            )
            .order_by("id")
            .first()
        )

        if not caisse:
            raise serializers.ValidationError({
                "detail": (
                    "Aucun compte Caisse actif n'existe. "
                    "Veuillez créer une caisse avant "
                    "d'enregistrer une dépense."
                )
            })

        expense = serializer.save(
            financial_account=caisse,
            created_by=self.request.user,
        )

        Notification.objects.create(
            user=self.request.user,
            notification_type=(
                Notification.NotificationType.EXPENSE_CREATED
            ),
            title="Dépense enregistrée",
            message=(
                f"Une dépense de {expense.amount} $ "
                f"a été enregistrée : "
                f"{expense.description}"
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


# ============================================================
# NOTIFICATIONS
# ============================================================

class NotificationViewSet(viewsets.ModelViewSet):

    queryset = (
        Notification.objects
        .select_related(
            "user",
            "reservation",
            "reservation__client",
            "payment",
        )
        .all()
        .order_by(
            "-created_at",
            "-id",
        )
    )

    serializer_class = NotificationSerializer

    permission_classes = [IsAuthenticated]

    @action(
        detail=True,
        methods=["post"],
        url_path="lire",
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
            NotificationSerializer(
                notification,
                context={
                    "request": request,
                },
            ).data
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
    queryset = Personnel.objects.all().order_by("nom", "prenom")
    serializer_class = PersonnelSerializer
    permission_classes = []





# ============================================================
# TABLEAU DE BORD / RAPPORTS
# ============================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_report(request):
    """
    Tableau de bord global de l'application.

    Les montants des réservations sont récupérés depuis
    Reservation.tarif.amount.

    Les montants réellement encaissés proviennent uniquement
    des paiements VALIDES.
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
        .prefetch_related("payments")
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
    #
    # Reservation ne possède PAS total_amount.
    #
    # Le montant est porté par :
    #
    # reservation.tarif.amount
    #
    # On additionne donc les tarifs des réservations
    # non annulées.
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
        .aggregate(
            total=Sum("amount")
        )
        .get("total")
        or Decimal("0.00")
    )

    # ========================================================
    # REMBOURSEMENTS
    # ========================================================

    total_rembourse = (
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
    #
    # Il n'existe pas de remaining_amount sur Reservation.
    #
    # On calcule :
    #
    # tarif - paiements validés liés à la réservation
    #
    # ========================================================

    reste_a_recouvrer = Decimal("0.00")

    for reservation in reservations:

        if reservation.status == Reservation.Status.ANNULEE:
            continue

        montant_reservation = Decimal("0.00")

        if reservation.tarif:
            montant_reservation = (
                reservation.tarif.amount
                or Decimal("0.00")
            )

        montant_paye = (
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

        reste = montant_reservation - montant_paye

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
            "balance": float(
                account.balance
                or Decimal("0.00")
            ),
        })

    # ========================================================
    # PAIEMENTS PAR MODE
    # ========================================================

    paiements_par_mode = []

    for method, label in Payment.Method.choices:

        total = (
            payments
            .filter(method=method)
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

    depenses_par_categorie = []

    for category, label in Expense.ExpenseType.choices:

        total = (
            expenses
            .filter(category=category)
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
    #
    # Ici on utilise les paiements VALIDES.
    # Cela représente les encaissements réels par mois.
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
            movement_type__in=[
                CashMovement.MovementType.SORTIE,
                CashMovement.MovementType.REMBOURSEMENT,
            ]
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
            "financial_account"
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


