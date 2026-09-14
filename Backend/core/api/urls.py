from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.routers import DefaultRouter
from .views import (
    SignupAPIView,
    VerifyEmailAPIView,
    LoginAPIView,
    CategoryViewSet,
    ProductViewSet,
    MyOrdersView,
    OrderDetailView,
    CheckoutView,
    AdminOrdersView,
)

from .views import (
    CartView,
    CartItemCreateView,
    CartItemUpdateView,
    CartItemDeleteView,
)

from .views import (
    PaymentCreateView,
    PaymentDetailView,
    OrderStatusUpdateView,
    OrderCancelView,
    BankDetailsView,
    GlobalSearchView,
)


router = DefaultRouter()

router.register(
    "categories",
    CategoryViewSet,
    basename="category"
)

router.register(
    "products",
    ProductViewSet,
    basename="product"
)


urlpatterns = [
    path(
        "signup/",
        SignupAPIView.as_view(),
        name="signup"
    ),
    path(
        "verify-email/",
        VerifyEmailAPIView.as_view(),
        name="verify-email"
    ),

    path(
        "login/",
        LoginAPIView.as_view(),
        name="login"
    ),

    path(
        "token/refresh/",
        TokenRefreshView.as_view(),
        name="token_refresh"
    ),

    path(
        "",
        include(router.urls)
    ),
    path("cart/", CartView.as_view(), name="cart"),
    path(
        "cart/items/",
        CartItemCreateView.as_view(),
        name="cart-item-create"
    ),
    path(
        "cart/items/<int:pk>/",
        CartItemUpdateView.as_view(),
        name="cart-item-update"
    ),
    path(
        "cart/items/<int:pk>/delete/",
        CartItemDeleteView.as_view(),
        name="cart-item-delete"
    ),
    path(
        "orders/checkout/",
        CheckoutView.as_view(),
        name="checkout"
    ),
    path(
        "orders/",
        MyOrdersView.as_view(),
        name="my-orders"
    ),
    path(
        "admin/orders/",
        AdminOrdersView.as_view(),
        name="admin-orders"
    ),

    path(
        "orders/<int:order_id>/",
        OrderDetailView.as_view(),
        name="order-detail"
    ),
    path(
        "payments/",
        PaymentCreateView.as_view(),
        name="payment-create"
    ),
    path(
        "payments/bank-details/",
        BankDetailsView.as_view(),
        name="bank-details"
    ),

    path(
        "payments/<int:order_id>/",
        PaymentDetailView.as_view(),
        name="payment-detail"
    ),

    path(
        "orders/<int:order_id>/status/",
        OrderStatusUpdateView.as_view(),
        name="order-status-update"
    ),

    path(
        "orders/<int:order_id>/cancel/",
        OrderCancelView.as_view(),
        name="order-cancel"
    ),

    path(
        "search/",
        GlobalSearchView.as_view(),
        name="global-search"
    ),
]