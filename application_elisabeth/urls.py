from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CashMovementViewSet,
    ClientViewSet,
    ContractViewSet,
    ExpenseViewSet,
    FinancialAccountViewSet,
    HallImageViewSet,
    HallVideoViewSet,
    HallViewSet,
    MaterialViewSet,
    PaymentViewSet,
    PersonnelViewSet,
    RefundViewSet,
    ReservationViewSet,
    TarifViewSet,
    calendar_view,
    dashboard_excel,
    dashboard_pdf,
    dashboard_report,
)

app_name = "api"

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
    r"hall-images",
    HallImageViewSet,
    basename="hall-image",
)

router.register(
    r"hall-videos",
    HallVideoViewSet,
    basename="hall-video",
)

router.register(
    r"materials",
    MaterialViewSet,
    basename="material",
)

router.register(
    r"accounts",
    FinancialAccountViewSet,
    basename="financial-account",
)

router.register(
    r"tarifs",
    TarifViewSet,
    basename="tarif",
)

router.register(
    r"payments",
    PaymentViewSet,
    basename="payment",
)

router.register(
    r"reservations",
    ReservationViewSet,
    basename="reservation",
)

router.register(
    r"expenses",
    ExpenseViewSet,
    basename="expense",
)

router.register(
    r"cash-movements",
    CashMovementViewSet,
    basename="cash-movement",
)

router.register(
    r"contracts",
    ContractViewSet,
    basename="contract",
)

router.register(
    r"personnel",
    PersonnelViewSet,
    basename="personnel",
)

router.register(
    r"refunds",
    RefundViewSet,
    basename="refund",
)


# ============================================================
# URLS
# ============================================================

urlpatterns = [
    # --------------------------------------------------------
    # ROUTER PRINCIPAL
    # --------------------------------------------------------
    path(
        "",
        include(router.urls),
    ),
    # --------------------------------------------------------
    # CALENDRIER
    # --------------------------------------------------------
    path(
        "calendar/",
        calendar_view,
        name="calendar-current",
    ),
    path(
        "calendar/<int:year>/<int:month>/",
        calendar_view,
        name="calendar-month",
    ),
    # --------------------------------------------------------
    # TABLEAU DE BORD & EXPORTS
    # --------------------------------------------------------
    path(
        "dashboard/",
        dashboard_report,
        name="dashboard-report",
    ),
    path(
        "dashboard/excel/",
        dashboard_excel,
        name="dashboard-excel",
    ),
    path(
        "dashboard/pdf/",
        dashboard_pdf,
        name="dashboard-pdf",
    ),
]