from io import BytesIO
from decimal import Decimal

from django.core.files.base import ContentFile

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


def generate_payment_receipt_pdf(payment):
    """
    Génère le reçu PDF d'un paiement.

    Cette fonction :
    1. génère le PDF en mémoire ;
    2. enregistre le PDF dans payment.receipt_pdf ;
    3. retourne les données binaires du PDF.

    Le téléchargement HTTP est ensuite géré par PaymentViewSet.recu().
    """

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()

    elements = []

    # ========================================================
    # TITRE
    # ========================================================

    elements.append(
        Paragraph(
            "LA CASA DA FESTA ELISABETH",
            styles["Title"],
        )
    )

    elements.append(
        Spacer(1, 8)
    )

    elements.append(
        Paragraph(
            "REÇU DE PAIEMENT",
            styles["Heading2"],
        )
    )

    elements.append(
        Spacer(1, 20)
    )

    # ========================================================
    # INFORMATIONS PAIEMENT
    # ========================================================

    reservation = payment.reservation

    client_name = ""

    if reservation and reservation.client:
        client_name = reservation.client.full_name

    reservation_number = ""

    if reservation:
        reservation_number = (
            reservation.reservation_number or ""
        )

    amount = (
        payment.amount
        or Decimal("0.00")
    )

    payment_date = ""

    if payment.payment_date:
        payment_date = payment.payment_date.strftime(
            "%d/%m/%Y %H:%M"
        )

    method = ""

    if payment.method:
        try:
            method = payment.get_method_display()
        except Exception:
            method = str(payment.method)

    reference = payment.reference or ""

    account_name = ""

    if payment.financial_account:
        account_name = payment.financial_account.name

    data = [
        ["Informations", "Détails"],

        [
            "N° paiement",
            f"#{payment.id}",
        ],

        [
            "Réservation",
            reservation_number,
        ],

        [
            "Client",
            client_name,
        ],

        [
            "Montant payé",
            f"{amount:,.2f} $",
        ],

        [
            "Mode de paiement",
            method,
        ],

        [
            "Compte",
            account_name,
        ],

        [
            "Date du paiement",
            payment_date,
        ],

        [
            "Référence",
            reference,
        ],

        [
            "Statut",
            "VALIDÉ",
        ],
    ]

    table = Table(
        data,
        colWidths=[
            55 * mm,
            105 * mm,
        ],
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
                "FONTNAME",
                (0, 1),
                (0, -1),
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
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE",
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
        Spacer(1, 25)
    )

    elements.append(
        Paragraph(
            "Merci pour votre confiance.",
            styles["BodyText"],
        )
    )

    elements.append(
        Spacer(1, 10)
    )

    elements.append(
        Paragraph(
            "La Casa da Festa Elisabeth",
            styles["BodyText"],
        )
    )

    # ========================================================
    # GENERATION
    # ========================================================

    document.build(elements)

    pdf_content = buffer.getvalue()

    buffer.close()

    # ========================================================
    # ENREGISTREMENT DU PDF DANS PAYMENT.RECEIPT_PDF
    # ========================================================

    filename = (
        f"recu-paiement-{payment.id}.pdf"
    )

    # On évite de recréer inutilement le même fichier.
    payment.receipt_pdf.save(
        filename,
        ContentFile(pdf_content),
        save=True,
    )

    return pdf_content



def generate_refund_receipt_pdf(refund):
    """
    Génère le reçu PDF d'un remboursement.

    Retourne un ContentFile prêt à être enregistré
    dans Refund.receipt_pdf.
    """

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()

    title_style = styles["Title"]
    normal_style = styles["Normal"]

    elements = []

    elements.append(
        Paragraph(
            "LA CASA DA FESTA ELISABETH",
            title_style,
        )
    )

    elements.append(
        Spacer(1, 10)
    )

    elements.append(
        Paragraph(
            "REÇU DE REMBOURSEMENT",
            styles["Heading2"],
        )
    )

    elements.append(
        Spacer(1, 15)
    )

    reservation = refund.reservation
    payment = refund.payment

    reservation_number = (
        getattr(
            reservation,
            "reservation_number",
            None,
        )
        or f"#{reservation.id}"
    )

    client = getattr(
        reservation,
        "client",
        None,
    )

    client_name = "—"

    if client:
        client_name = (
            getattr(
                client,
                "full_name",
                None,
            )
            or str(client)
        )

    data = [
        ["N° remboursement", f"#{refund.id}"],
        ["N° paiement", f"#{payment.id}"],
        ["Réservation", reservation_number],
        ["Client", client_name],
        [
            "Montant remboursé",
            f"{refund.amount} $",
        ],
        [
            "Mode",
            refund.method or payment.method or "—",
        ],
        [
            "Date",
            refund.refund_date.strftime("%d/%m/%Y"),
        ],
        [
            "Statut",
            refund.get_status_display(),
        ],
        [
            "Motif",
            refund.reason or "Non précisé",
        ],
    ]

    table = Table(
        data,
        colWidths=[
            60 * mm,
            105 * mm,
        ],
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey,
                ),
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.whitesmoke,
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (0, -1),
                    "Helvetica-Bold",
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "PADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
            ]
        )
    )

    elements.append(table)

    elements.append(
        Spacer(1, 25)
    )

    elements.append(
        Paragraph(
            "Ce document constitue le reçu du remboursement enregistré dans le système.",
            normal_style,
        )
    )

    elements.append(
        Spacer(1, 30)
    )

    elements.append(
        Paragraph(
            "La Casa da Festa Elisabeth",
            normal_style,
        )
    )

    document.build(elements)

    buffer.seek(0)

    return ContentFile(
        buffer.read(),
        name=f"recu_remboursement_{refund.id}.pdf",
    )