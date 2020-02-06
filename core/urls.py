from django.urls import path
from .views import (HomeView, ItemDetailView, CheckoutView,
                    addToCart, OrderSummaryView, removeSingleItemFromCart, removeFromCart, PaymentView, AddCouponView)

app_name = 'core'

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('checkout/', CheckoutView.as_view(), name='checkout'),
    path('order-summary/', OrderSummaryView.as_view(), name='order-summary'),
    path('products/<slug>/', ItemDetailView.as_view(), name='product'),
    path('addToCart/<slug>/', addToCart, name="add-to-cart"),
    path('add_coupon/<code>/', AddCouponView.as_view(), name="add_coupon"),
    path('removeFromCart/<slug>/', removeFromCart, name="remove-from-cart"),
    path('removeSingleItemFromCart/<slug>/', removeSingleItemFromCart,
         name="remove-single-item-from-cart"),
    path('payment/<payment_option>/', PaymentView.as_view(),
         name="payment"),

]
