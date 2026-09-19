# services/pdf_service.py
from django.template.loader import render_to_string
from weasyprint import HTML
from django.core.files.base import ContentFile

def _pdf_from_html(html: str) -> ContentFile:
    pdf_bytes = HTML(string=html).write_pdf()
    return ContentFile(pdf_bytes)

def generate_receipt_pdf(payment, request=None):
    html = render_to_string("pdfs/receipt.html", {"payment": payment})
    return _pdf_from_html(html)

def generate_contract_pdf(reservation, request=None):
    html = render_to_string("pdfs/contract.html", {"reservation": reservation})
    return _pdf_from_html(html)
