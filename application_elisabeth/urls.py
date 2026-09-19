from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import (
    ClientViewSet, HallViewSet, ReservationViewSet, PaymentViewSet,
    ServiceViewSet, ReservationServiceViewSet, MaterialViewSet,
    ReservationMaterialUsageViewSet, ExpenseCategoryViewSet, ExpenseViewSet,
    CashMovementViewSet,
    dashboard, reservations_calendar
)

router = DefaultRouter()
router.register(r"clients", ClientViewSet)
router.register(r"halls", HallViewSet)
router.register(r"reservations", ReservationViewSet)
router.register(r"payments", PaymentViewSet)
router.register(r"services", ServiceViewSet)
router.register(r"reservation-services", ReservationServiceViewSet)
router.register(r"materials", MaterialViewSet)
router.register(r"reservation-materials", ReservationMaterialUsageViewSet)
router.register(r"expense-categories", ExpenseCategoryViewSet)
router.register(r"expenses", ExpenseViewSet)
router.register(r"cash-movements", CashMovementViewSet, basename="cash-movements")

urlpatterns = [
    path("", include(router.urls)),
    path("dashboard/", dashboard, name="dashboard"),
    path("calendar/<int:year>/<int:month>/", reservations_calendar, name="calendar"),
]
