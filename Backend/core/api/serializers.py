from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import serializers
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


class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=8
    )

    password_confirm = serializers.CharField(
        write_only=True
    )

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "password",
            "password_confirm"
        ]

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                "Username already exists."
            )

        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "Email already exists."
            )

        return value

    def validate(self, data):
        if data["password"] != data["password_confirm"]:
            raise serializers.ValidationError(
                "Passwords do not match."
            )

        return data

    def create(self, validated_data):
        validated_data.pop("password_confirm")

        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"]
        )

        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        username = data.get("username")
        password = data.get("password")

        user = authenticate(
            username=username,
            password=password
        )

        if user is None:
            raise serializers.ValidationError(
                "Invalid username or password."
            )

        if not user.is_active:
            raise serializers.ValidationError(
                "This account is inactive."
            )

        data["user"] = user

        return data
    

class CategorySerializer(serializers.ModelSerializer):

    class Meta:
        model = Category
        fields = ["id", "name"]


class ProductSerializer(serializers.ModelSerializer):

    category_name = serializers.CharField(
        source="category.name",
        read_only=True
    )
    images = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "category",
            "category_name",
            "description",
            "price",
            "image",
            "images",
            "stock",
            "is_active",
            "is_recommended",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_images(self, obj):
        return [self.context["request"].build_absolute_uri(item.image.url) for item in obj.images.all()]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not data["image"] and data["images"]:
            data["image"] = data["images"][0]
        return data

class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_price = serializers.DecimalField(
        source="product.price",
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            "id",
            "product",
            "product_name",
            "product_price",
            "quantity",
            "price_at_add",
            "subtotal",
        ]
        read_only_fields = [
            "price_at_add",
            "product_name",
            "product_price",
            "subtotal",
        ]

    def get_subtotal(self, obj):
        return obj.quantity * obj.price_at_add

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            "id",
            "items",
            "total_items",
            "total_amount",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "items",
            "total_items",
            "total_amount",
            "created_at",
            "updated_at",
        ]

    def get_total_items(self, obj):
        return sum(item.quantity for item in obj.items.all())

    def get_total_amount(self, obj):
        return sum(
            item.quantity * item.price_at_add
            for item in obj.items.all()
        )


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "product_name",
            "price",
            "quantity",
        ]
        read_only_fields = [
            "id",
            "product",
            "product_name",
            "price",
        ]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "items",
            "total_amount",
            "delivery_fee",
            "payment_method",
            "payment_status",
            "order_status",
            "shipping_name",
            "shipping_phone",
            "shipping_address",
            "city",
            "estimated_delivery_date",
            "created_at",
            "updated_at",

        ]

        read_only_fields = [
            "id",
            "order_number",
            "items",
            "total_amount",
            "delivery_fee",
            "payment_status",
            "order_status",
            "estimated_delivery_date",
            "created_at",
            "updated_at",
        ]


class PaymentSerializer(serializers.ModelSerializer):

    order_number = serializers.CharField(
        source="order.order_number",
        read_only=True
    )

    class Meta:
        model = Payment
        fields = [
            "id",
            "order",
            "order_number",
            "payment_method",
            "amount",
            "transaction_reference",
            "payment_status",
            "payment_proof",
            "verified_at",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "order",
            "order_number",
            "amount",
            "payment_method",
            "payment_status",
            "verified_at",
            "created_at",
            "updated_at",
        ]