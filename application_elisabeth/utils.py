import re


def normalize_phone(phone: str | None) -> str:
    """
    Normalise un numéro de téléphone en supprimant les espaces,
    parenthèses, tirets et autres caractères inutiles.

    Exemple :
        "+243 812 345 678" -> "+243812345678"
        "0812-345-678"     -> "0812345678"
    """
    if not phone:
        return ""

    phone = str(phone).strip()

    # Conserver uniquement les chiffres et le signe +.
    phone = re.sub(r"[^\d+]", "", phone)

    # Éviter plusieurs signes +.
    if "+" in phone:
        phone = "+" + phone.replace("+", "")

    return phone