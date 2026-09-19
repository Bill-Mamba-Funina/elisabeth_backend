from rest_framework import serializers
from django.db.models import Sum
from .models import (
    Client, Hall, Reservation, Payment, Service, ReservationService,
    Material, ReservationMaterialUsage, ExpenseCategory, Expense, CashMovement,
    ReservationStatus, EventType
)

class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ["id", "full_name", "phone", "email", "address", "created_at"]


class HallSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hall
        fields = ["id", "name", "capacity", "daily_rate", "status"]


class ReservationSerializer(serializers.ModelSerializer):
    paid_total = serializers.SerializerMethodField()
    remaining = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Reservation
        fields = [
            "id","hall","client","event_type","event_title",
            "date","start_time","end_time",
            "guests_count",
            "base_rate","discount","deposit",
            "status",
            "total_price","paid_total","remaining",
            "created_at","updated_at"
        ]

    def get_paid_total(self, obj):
        v = obj.payments.aggregate(Sum("amount")).get("amount__sum")
        return v or 0

    def get_remaining(self, obj):
        total_price = self.get_total_price(obj)
        return max(total_price - self.get_paid_total(obj), 0)

    def get_total_price(self, obj):
        return max(obj.base_rate - obj.discount, 0)


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id","receipt_number","reservation","date","amount","mode","recorded_by","created_at"]
        read_only_fields = ["recorded_by", "created_at"]


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ["id","name","unit_price"]


class ReservationServiceSerializer(serializers.ModelSerializer):
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = ReservationService
        fields = ["id","reservation","service","quantity","unit_price_snapshot","line_total"]

    def get_line_total(self, obj):
        return obj.quantity * obj.unit_price_snapshot


class MaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Material
        fields = ["id","name","total_available"]


class ReservationMaterialUsageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReservationMaterialUsage
        fields = ["id","reservation","material","quantity_requested","quantity_used"]


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ["id","name"]


class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = ["id","category","amount","date","note","recorded_by","created_at"]
        read_only_fields = ["recorded_by","created_at"]


class CashMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashMovement
        fields = ["id","movement_type","amount","date","note","payment","expense","created_at"]
        read_only_fields = ["created_at"]
