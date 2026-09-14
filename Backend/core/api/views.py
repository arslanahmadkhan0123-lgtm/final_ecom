from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.exceptions import PermissionDenied
from .models import Category, Product, ProductImage, PendingSignup
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from .serializers import (
    SignupSerializer,
    LoginSerializer,
    CategorySerializer,
    ProductSerializer,
    CartSerializer,
    CartItemSerializer,
    OrderSerializer,
    OrderItemSerializer,
    PaymentSerializer,
)
from .models import (
    Cart,
    CartItem,
    Order,
    OrderItem,
    Payment,
)
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.core import signing
from datetime import timedelta
import uuid
import logging

logger = logging.getLogger(__name__)


class SignupAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)

        if serializer.is_valid():
            validated = serializer.validated_data
            pending_email = PendingSignup.objects.filter(
                email=validated["email"]
            ).first()
            pending_username = PendingSignup.objects.filter(
                username=validated["username"]
            ).first()

            if pending_email and pending_email.username != validated["username"]:
                return Response(
                    {"message": "A verification email is already pending for this email."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if pending_username and pending_username.email != validated["email"]:
                return Response(
                    {"message": "A verification email is already pending for this username."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            pending, _ = PendingSignup.objects.update_or_create(
                email=validated["email"],
                defaults={
                    "username": validated["username"],
                    "password_hash": make_password(validated["password"]),
                },
            )

            token = signing.dumps(
                {"pending_id": pending.id},
                salt="email-verification"
            )
            verification_url = (
                f"{settings.FRONTEND_URL}/?verify={token}"
            )

            try:
                send_mail(
                    "Verify your e-commerce account",
                    (
                        f"Hi {pending.username},\n\n"
                        "Verify your email address to activate your account:\n"
                        f"{verification_url}\n\n"
                        "This link expires in 24 hours."
                    ),
                    settings.DEFAULT_FROM_EMAIL,
                    [pending.email],
                    fail_silently=False,
                )
            except Exception:
                logger.exception("Could not send verification email")
                pending.delete()
                return Response(
                    {
                        "message": (
                            "Verification email could not be sent. "
                            "Check Gmail SMTP settings and the backend log."
                        )
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )

            response_data = {
                "message": "Account created. Check your email to verify it.",
            }
            if settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
                response_data["verification_url"] = verification_url

            return Response(response_data, status=status.HTTP_202_ACCEPTED)

        return Response(
            {
                "message": "Signup failed",
                "errors": serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )


class VerifyEmailAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        token = request.query_params.get("token")
        if not token:
            return Response(
                {"error": "Verification token is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            payload = signing.loads(
                token,
                salt="email-verification",
                max_age=settings.EMAIL_VERIFICATION_MAX_AGE,
            )
            pending = PendingSignup.objects.get(id=payload["pending_id"])
            user = User.objects.create(
                username=pending.username,
                email=pending.email,
                password=pending.password_hash,
                is_active=True,
            )
            pending.delete()
        except (signing.BadSignature, signing.SignatureExpired, PendingSignup.DoesNotExist, KeyError):
            return Response(
                {"error": "This verification link is invalid or expired."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])

        return Response({"message": "Email verified. You can now sign in."})


class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.validated_data["user"]

            refresh = RefreshToken.for_user(user)

            if user.is_staff or user.is_superuser:
                role = "admin"
            else:
                role = "buyer"

            return Response(
                {
                    "message": "Login successful",
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "role": role
                    },
                    "tokens": {
                        "access": str(refresh.access_token),
                        "refresh": str(refresh)
                    }
                },
                status=status.HTTP_200_OK
            )

        return Response(
            {
                "message": "Login failed",
                "errors": serializer.errors
            },
            status=status.HTTP_401_UNAUTHORIZED
        )

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by("id")
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = Category.objects.all().order_by("id")

        search = self.request.query_params.get("search")

        if search:
            queryset = queryset.filter(
                name__icontains=search
            )

        return queryset

    def perform_create(self, serializer):
        if not self.request.user.is_staff:
            raise PermissionDenied(
                "Only admin can create categories."
            )

        serializer.save()

    def perform_update(self, serializer):
        if not self.request.user.is_staff:
            raise PermissionDenied(
                "Only admin can update categories."
            )

        serializer.save()

    def perform_destroy(self, instance):
        if not self.request.user.is_staff:
            raise PermissionDenied(
                "Only admin can delete categories."
            )

        instance.delete()

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related(
        "category"
    ).order_by("-created_at")

    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = Product.objects.select_related(
            "category"
        ).order_by("-created_at")

        # Public users sirf active products dekhenge
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_active=True)

        category_id = self.request.query_params.get("category")
        recommended = self.request.query_params.get("is_recommended")
        search = self.request.query_params.get("search")

        if category_id:
            queryset = queryset.filter(category_id=category_id)

        if recommended is not None:
            queryset = queryset.filter(
                is_recommended=recommended.lower() == "true"
            )

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
        |           Q(description__icontains=search)
        |           Q(category__name__icontains=search)
            )

        return queryset

    def perform_create(self, serializer):
        if not self.request.user.is_staff:
            raise PermissionDenied(
                "Only admin can create products."
            )

        product = serializer.save()
        for image in self.request.FILES.getlist("images"):
            ProductImage.objects.create(product=product, image=image)

    def perform_update(self, serializer):
        if not self.request.user.is_staff:
            raise PermissionDenied(
                "Only admin can update products."
            )

        product = serializer.save()
        images = self.request.FILES.getlist("images")
        if images:
            product.images.all().delete()
            for image in images:
                ProductImage.objects.create(product=product, image=image)

    def perform_destroy(self, instance):
        if not self.request.user.is_staff:
            raise PermissionDenied(
                "Only admin can delete products."
            )

        instance.delete()

class CartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cart, created = Cart.objects.get_or_create(
            user=request.user
        )

        serializer = CartSerializer(cart)

        return Response(serializer.data)

    def delete(self, request):
        cart, created = Cart.objects.get_or_create(
            user=request.user
        )

        cart.items.all().delete()

        return Response(
            {"message": "Cart cleared successfully."},
            status=status.HTTP_200_OK
        )


class CartItemCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        product_id = request.data.get("product")
        quantity = request.data.get("quantity", 1)

        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return Response(
                {"error": "Quantity must be a valid number."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if quantity < 1:
            return Response(
                {"error": "Quantity must be at least 1."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            product = Product.objects.get(
                id=product_id,
                is_active=True
            )
        except Product.DoesNotExist:
            return Response(
                {"error": "Product not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if quantity > product.stock:
            return Response(
                {"error": "Not enough stock available."},
                status=status.HTTP_400_BAD_REQUEST
            )

        cart, created = Cart.objects.get_or_create(
            user=request.user
        )

        cart_item, item_created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={
                "quantity": quantity,
                "price_at_add": product.price,
            }
        )

        if not item_created:
            new_quantity = cart_item.quantity + quantity

            if new_quantity > product.stock:
                return Response(
                    {"error": "Not enough stock available."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            cart_item.quantity = new_quantity
            cart_item.save()

        serializer = CartItemSerializer(cart_item)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )


class CartItemUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            cart_item = CartItem.objects.get(
                id=pk,
                cart__user=request.user
            )
        except CartItem.DoesNotExist:
            return Response(
                {"error": "Cart item not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        quantity = request.data.get("quantity")

        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return Response(
                {"error": "Quantity must be a valid number."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if quantity < 1:
            return Response(
                {"error": "Quantity must be at least 1."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if quantity > cart_item.product.stock:
            return Response(
                {"error": "Not enough stock available."},
                status=status.HTTP_400_BAD_REQUEST
            )

        cart_item.quantity = quantity
        cart_item.save()

        serializer = CartItemSerializer(cart_item)

        return Response(serializer.data)


class CartItemDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            cart_item = CartItem.objects.get(
                id=pk,
                cart__user=request.user
            )
        except CartItem.DoesNotExist:
            return Response(
                {"error": "Cart item not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        cart_item.delete()

        return Response(
            {"message": "Item removed from cart."},
            status=status.HTTP_200_OK
        )


class CheckoutView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        shipping_name = request.data.get("shipping_name")
        shipping_phone = request.data.get("shipping_phone")
        shipping_address = request.data.get("shipping_address")
        city = request.data.get("city")
        payment_method = request.data.get("payment_method")

        if not shipping_name:
            return Response(
                {"error": "Shipping name is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not shipping_phone:
            return Response(
                {"error": "Shipping phone is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not shipping_address:
            return Response(
                {"error": "Shipping address is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not city:
            return Response(
                {"error": "City is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if payment_method not in ["COD", "BANK"]:
            return Response(
                {
                    "error": "Invalid payment method.",
                    "allowed_methods": ["COD", "BANK"]
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        cart = Cart.objects.filter(
            user=request.user
        ).first()

        if not cart or not cart.items.exists():
            return Response(
                {"error": "Your cart is empty."},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():

            cart_items = cart.items.select_related("product")

            for item in cart_items:

                if not item.product.is_active:
                    return Response(
                        {
                            "error": f"{item.product.name} is no longer available."
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

                if item.quantity > item.product.stock:
                    return Response(
                        {
                            "error": f"Only {item.product.stock} units of {item.product.name} are available."
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

            product_total = sum(
                item.quantity * item.price_at_add
                for item in cart_items
            )

            delivery_fee = 200

            total_amount = product_total + delivery_fee

            order_number = (
                f"ORD-{timezone.now().strftime('%Y%m%d%H%M%S')}"
                f"-{uuid.uuid4().hex[:6].upper()}"
            )

            estimated_delivery_date = (
                timezone.localdate() + timedelta(days=5)
            )

            order = Order.objects.create(
                order_number=order_number,
                user=request.user,
                total_amount=total_amount,
                delivery_fee=delivery_fee,
                payment_method=payment_method,
                payment_status="Pending",
                order_status="Pending",
                shipping_name=shipping_name,
                shipping_phone=shipping_phone,
                shipping_address=shipping_address,
                city=city,
                estimated_delivery_date=estimated_delivery_date,
            )

            for item in cart_items:

                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    product_name=item.product.name,
                    price=item.price_at_add,
                    quantity=item.quantity,
                )

                item.product.stock -= item.quantity
                item.product.save(
                    update_fields=["stock"]
                )

            Payment.objects.create(
                order=order,
                payment_method=payment_method,
                amount=total_amount,
                payment_status="Pending",
            )

            cart.items.all().delete()

        return Response(
            OrderSerializer(order).data,
            status=status.HTTP_201_CREATED
        )

class MyOrdersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        orders = Order.objects.filter(
            user=request.user
        ).prefetch_related(
            "items"
        ).order_by("-created_at")

        serializer = OrderSerializer(
            orders,
            many=True
        )

        return Response(serializer.data)


class AdminOrdersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return Response(
                {"error": "Only admin can view all orders."},
                status=status.HTTP_403_FORBIDDEN
            )

        orders = Order.objects.filter(
            user__is_staff=False
        ).select_related(
            "user", "payment"
        ).prefetch_related(
            "items"
        ).order_by("-created_at")

        data = []
        for order in orders:
            serialized = OrderSerializer(order).data
            serialized["customer"] = {
                "id": order.user.id,
                "username": order.user.username,
                "email": order.user.email,
            }
            serialized["payment"] = PaymentSerializer(order.payment).data
            data.append(serialized)

        return Response(data)


class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):

        try:
            order = Order.objects.prefetch_related(
                "items"
            ).get(
                id=order_id,
                user=request.user
            )

        except Order.DoesNotExist:
            return Response(
                {
                    "error": "Order not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = OrderSerializer(order)

        return Response(serializer.data)


DEMO_BANK_DETAILS = {
    "bank_name": "Demo Bank",
    "account_title": "Demo Store",
    "account_number": "DEMO-000000",
    "iban": "DEMO-IBAN-000000",
    "note": "DEMO ONLY - NO REAL MONEY TRANSFER",
}

class BankDetailsView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        return Response(
            DEMO_BANK_DETAILS,
            status=status.HTTP_200_OK
        )

class PaymentCreateView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        order_id = request.data.get("order_id")
        transaction_reference = request.data.get(
            "transaction_reference"
        )

        if not order_id:
            return Response(
                {"error": "order_id is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            order = Order.objects.get(
                id=order_id,
                user=request.user
            )
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if order.payment_method != "BANK":
            return Response(
                {
                    "error": "Payment details are only required for Bank Transfer."
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        if not transaction_reference:
            return Response(
            {
                "error": "Transaction reference is required for Bank Transfer."
            },
                status=status.HTTP_400_BAD_REQUEST
            )

        payment = Payment.objects.filter(
            order=order
        ).first()

        if not payment:
            payment = Payment.objects.create(
                order=order,
                payment_method="BANK",
                amount=order.total_amount,
            )

        if payment.payment_status == "Paid":
            return Response(
                {"error": "This payment is already paid."},
                status=status.HTTP_400_BAD_REQUEST
            )

        payment.transaction_reference = transaction_reference
        payment.save()

        return Response(
            PaymentSerializer(payment).data,
            status=status.HTTP_200_OK
        )


class PaymentDetailView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):

        try:
            payment = Payment.objects.get(
                order__id=order_id,
                order__user=request.user
            )
        except Payment.DoesNotExist:
            return Response(
                {"error": "Payment not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            PaymentSerializer(payment).data,
            status=status.HTTP_200_OK
        )


class OrderStatusUpdateView(APIView):

    permission_classes = [IsAuthenticated]

    def patch(self, request, order_id):

        # Only admin/staff can update order status
        if not request.user.is_staff:
            return Response(
                {"error": "Only admin can update order status."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get order
        try:
            order = Order.objects.get(
                id=order_id
            )
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        new_status = request.data.get("order_status")

        # Allowed statuses
        allowed_statuses = [
            "Pending",
            "Confirmed",
            "Processing",
            "Shipped",
            "Out for Delivery",
            "Delivered",
            "Cancelled",
        ]

        if new_status not in allowed_statuses:
            return Response(
                {
                    "error": "Invalid order status.",
                    "allowed_statuses": allowed_statuses,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Delivered order cannot be changed
        if order.order_status == "Delivered":
            return Response(
                {"error": "Delivered order cannot be changed."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Cancelled order cannot be changed
        if order.order_status == "Cancelled":
            return Response(
                {"error": "Cancelled order cannot be changed."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Proper order status transitions
        allowed_transitions = {
            "Pending": ["Confirmed", "Cancelled"],
            "Confirmed": ["Processing", "Cancelled"],
            "Processing": ["Shipped", "Cancelled"],
            "Shipped": ["Out for Delivery"],
            "Out for Delivery": ["Delivered"],
        }

        current_status = order.order_status

        if new_status not in allowed_transitions.get(
            current_status, []
        ):
            return Response(
                {
                    "error": f"Cannot change order status from "
                              f"{current_status} to {new_status}.",
                    "current_status": current_status,
                    "allowed_next_statuses": allowed_transitions.get(
                        current_status, []
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # BANK payment must be Paid before delivery
        if new_status == "Delivered":

            if (
                order.payment_method == "BANK"
                and order.payment_status != "Paid"
            ):
                return Response(
                    {
                        "error": "Bank payment must be verified "
                                 "before delivery."
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # COD payment is considered paid on delivery
            if order.payment_method == "COD":
                order.payment_status = "Paid"

                if hasattr(order, "payment"):
                    order.payment.payment_status = "Paid"
                    order.payment.verified_at = timezone.now()
                    order.payment.save()

        # Update order status
        order.order_status = new_status

        order.save()

        return Response(
            OrderSerializer(order).data,
            status=status.HTTP_200_OK
        )

class OrderCancelView(APIView):

    permission_classes = [IsAuthenticated]

    def patch(self, request, order_id):

        try:
            order = Order.objects.get(
                id=order_id,
                user=request.user
            )
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        cancellable_statuses = [
            "Pending",
            "Confirmed",
        ]

        if order.order_status not in cancellable_statuses:
            return Response(
                {
                    "error": "This order cannot be cancelled now."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():

            order.order_status = "Cancelled"

            order_items = order.items.select_related("product")

            for item in order_items:

                if item.product:
                    item.product.stock += item.quantity
                    item.product.save(
                        update_fields=["stock"]
                    )

            order.save()

        return Response(
            {
                "message": "Order cancelled successfully.",
                "order": OrderSerializer(order).data,
            },
            status=status.HTTP_200_OK
        )

class GlobalSearchView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        query = request.query_params.get("q", "").strip()

        if not query:
            return Response(
                {
                    "error": "Search query is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        categories = Category.objects.filter(
            name__icontains=query
        ).order_by("name")

        products = Product.objects.filter(
            is_active=True
        ).filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(category__name__icontains=query)
        ).select_related(
            "category"
        ).order_by("-created_at")

        category_serializer = CategorySerializer(
            categories,
            many=True
        )

        product_serializer = ProductSerializer(
            products,
            many=True,
            context={"request": request}
        )

        return Response(
            {
                "query": query,
                "categories": category_serializer.data,
                "products": product_serializer.data,
                "total_categories": categories.count(),
                "total_products": products.count()
            },
            status=status.HTTP_200_OK
        )

