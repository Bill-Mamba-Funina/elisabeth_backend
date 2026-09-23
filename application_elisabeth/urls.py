from django.urls import path, include

from rest_framework.routers import DefaultRouter

from .views import (
    ClientViewSet,
    HallViewSet,
    ServiceViewSet,
    MaterialViewSet,
    ReservationViewSet,
    ReservationServiceViewSet,
    ReservationMaterialViewSet,
    FinancialAccountViewSet,
    PaymentViewSet,
    CashMovementViewSet,
    ExpenseViewSet,
    ContractViewSet,
    NotificationViewSet,
    calendar_view,
)


router = DefaultRouter()

router.register(
    "clients",
    ClientViewSet,
    basename="client"
)

router.register(
    "halls",
    HallViewSet,
    basename="hall"
)

router.register(
    "services",
    ServiceViewSet,
    basename="service"
)

router.register(
    "materials",
    MaterialViewSet,
    basename="material"
)

router.register(
    "reservations",
    ReservationViewSet,
    basename="reservation"
)

router.register(
    "reservation-services",
    ReservationServiceViewSet,
    basename="reservation-service"
)

router.register(
    "reservation-materials",
    ReservationMaterialViewSet,
    basename="reservation-material"
)

router.register(
    "accounts",
    FinancialAccountViewSet,
    basename="financial-account"
)

router.register(
    "payments",
    PaymentViewSet,
    basename="payment"
)

router.register(
    "cash-movements",
    CashMovementViewSet,
    basename="cash-movement"
)

router.register(
    "expenses",
    ExpenseViewSet,
    basename="expense"
)

router.register(
    "contracts",
    ContractViewSet,
    basename="contract"
)

router.register(
    "notifications",
    NotificationViewSet,
    basename="notification"
)


urlpatterns = [
    path("", include(router.urls)),

    path(
        "calendar/<int:year>/<int:month>/",
        calendar_view,
        name="calendar",
    ),
]