from django.contrib import admin
from django.utils import timezone
from .models import (
    Category,
    Product,
    Cart,
    CartItem,
    Order,
    OrderItem,
    Payment,
    ProductImage,
)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["id", "name"]
    search_fields = ["name"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines = [ProductImageInline]
    list_display = [
        "id",
        "name",
        "category",
        "price",
        "stock",
        "is_active",
        "is_recommended",
    ]

    list_filter = [
        "category",
        "is_active",
        "is_recommended",
    ]

    search_fields = [
        "name",
        "description",
    ]

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "updated_at")


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = (
        "cart",
        "product",
        "quantity",
        "price_at_add",
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "user",
        "total_amount",
        "payment_method",
        "payment_status",
        "order_status",
        "city",
        "estimated_delivery_date",
        "created_at",
        "delivery_fee",
    )

    list_filter = (
        "payment_method",
        "payment_status",
        "order_status",
        "city",
    )

    search_fields = (
        "order_number",
        "user__username",
        "shipping_name",
        "shipping_phone",
    )


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "product_name",
        "price",
        "quantity",
    )

    search_fields = (
        "product_name",
        "order__order_number",
    )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "order",
        "payment_method",
        "amount",
        "payment_status",
        "transaction_reference",
        "verified_at",
        "created_at",
    )

    list_filter = (
        "payment_method",
        "payment_status",
    )

    search_fields = (
        "transaction_reference",
        "order__order_number",
    )

    def save_model(self, request, obj, form, change):

        if obj.payment_status == "Paid":
            obj.verified_at = timezone.now()

            obj.order.payment_status = "Paid"
            obj.order.save(
                update_fields=["payment_status", "updated_at"]
            )

        elif obj.payment_status != "Paid":
            obj.verified_at = None

            obj.order.payment_status = obj.payment_status
            obj.order.save(
                update_fields=["payment_status", "updated_at"]
            )

        super().save_model(request, obj, form, change)