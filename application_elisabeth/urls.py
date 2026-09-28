from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ClientViewSet,
    HallViewSet,
    MaterialViewSet,
    ReservationViewSet,
    FinancialAccountViewSet,
    PaymentViewSet,
    CashMovementViewSet,
    ExpenseViewSet,
    ContractViewSet,
    PersonnelViewSet,
    calendar_view,
    dashboard_report,
    dashboard_excel,
    dashboard_pdf,
    TarifViewSet,
    RefundViewSet,
)


# ============================================================
# ROUTER API
# ============================================================

router = DefaultRouter()

router.register(
    r"clients",
    ClientViewSet,
    basename="client",
)

router.register(
    r"halls",
    HallViewSet,
    basename="hall",
)

router.register(
    r"tarifs",
    TarifViewSet,
    basename="tarif",
)

router.register(
    r"materials",
    MaterialViewSet,
    basename="material",
)

router.register(
    r"reservations",
    ReservationViewSet,
    basename="reservation",
)

router.register(
    r"accounts",
    FinancialAccountViewSet,
    basename="financial-account",
)

router.register(
    r"payments",
    PaymentViewSet,
    basename="payment",
)

router.register(
    r"cash-movements",
    CashMovementViewSet,
    basename="cash-movement",
)

router.register(
    r"expenses",
    ExpenseViewSet,
    basename="expense",
)

router.register(
    r"contracts",
    ContractViewSet,
    basename="contract",
)

router.register(
    r"refunds",
    RefundViewSet,
    basename="refund",
)

router.register(
    r"personnel",
    PersonnelViewSet,
    basename="personnel",
)


# ============================================================
# URLS
# ============================================================

urlpatterns = [
    # CRUD principaux
    path(
        "",
        include(router.urls),
    ),

    # ========================================================
    # CALENDRIER
    # ========================================================

    path(
        "calendar/<int:year>/<int:month>/",
        calendar_view,
        name="calendar",
    ),

    # ========================================================
    # TABLEAU DE BORD
    # ========================================================

    path(
        "dashboard/",
        dashboard_report,
        name="dashboard",
    ),

    # ========================================================
    # EXPORTS DU TABLEAU DE BORD
    # ========================================================

    path(
        "dashboard/export/excel/",
        dashboard_excel,
        name="dashboard-excel",
    ),

    path(
        "dashboard/export/pdf/",
        dashboard_pdf,
        name="dashboard-pdf",
    ),
]

