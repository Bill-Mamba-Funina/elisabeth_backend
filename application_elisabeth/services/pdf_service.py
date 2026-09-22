from io import BytesIO

from django.core.files.base import ContentFile

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def generate_payment_receipt_pdf(payment):
    """
    Génère le reçu PDF d'un paiement.

    Le PDF est retourné sous forme de ContentFile
    afin de pouvoir être enregistré directement
    dans Payment.receipt_pdf.
    """

    buffer = BytesIO()

    pdf = canvas.Canvas(
        buffer,
        pagesize=A4
    )

    width, height = A4

    # --------------------------------------------------------
    # EN-TETE
    # --------------------------------------------------------

    pdf.setFont(
        "Helvetica-Bold",
        18
    )

    pdf.drawCentredString(
        width / 2,
        height - 60,
        "LA CASA DA FESTA ELISABETH"
    )

    pdf.setFont(
        "Helvetica-Bold",
        14
    )

    pdf.drawCentredString(
        width / 2,
        height - 90,
        "REÇU DE PAIEMENT"
    )

    # --------------------------------------------------------
    # INFORMATIONS
    # --------------------------------------------------------

    y = height - 140

    pdf.setFont(
        "Helvetica",
        11
    )

    reservation = payment.reservation

    lines = [
        (
            "N° paiement",
            str(payment.id)
        ),
        (
            "Réservation",
            reservation.reservation_number
        ),
        (
            "Client",
            reservation.client.full_name
        ),
        (
            "Salle",
            reservation.hall.name
        ),
        (
            "Événement",
            reservation.event_type
        ),
        (
            "Date événement",
            reservation.event_date.strftime("%d/%m/%Y")
        ),
        (
            "Montant payé",
            f"{payment.amount} $"
        ),
        (
            "Mode de paiement",
            payment.get_method_display()
        ),
        (
            "Référence",
            payment.reference or "-"
        ),
        (
            "Date du paiement",
            payment.payment_date.strftime(
                "%d/%m/%Y %H:%M"
            )
        ),
        (
            "Total réservation",
            f"{reservation.total_amount} $"
        ),
        (
            "Total payé",
            f"{reservation.paid_amount} $"
        ),
        (
            "Reste à payer",
            f"{reservation.remaining_amount} $"
        ),
        (
            "Statut",
            reservation.get_payment_status_display()
        ),
    ]

    for label, value in lines:

        pdf.setFont(
            "Helvetica-Bold",
            10
        )

        pdf.drawString(
            60,
            y,
            f"{label} :"
        )

        pdf.setFont(
            "Helvetica",
            10
        )

        pdf.drawString(
            200,
            y,
            str(value)
        )

        y -= 24

    # --------------------------------------------------------
    # SIGNATURE / INFORMATIONS
    # --------------------------------------------------------

    y -= 30

    pdf.line(
        60,
        y,
        width - 60,
        y
    )

    y -= 30

    pdf.setFont(
        "Helvetica",
        9
    )

    pdf.drawString(
        60,
        y,
        "Document généré automatiquement par "
        "La Casa da Festa Elisabeth."
    )

    y -= 20

    pdf.drawString(
        60,
        y,
        "Merci pour votre confiance."
    )

    pdf.showPage()
    pdf.save()

    buffer.seek(0)

    return ContentFile(
        buffer.getvalue(),
        name=f"recu-paiement-{payment.id}.pdf"
    )