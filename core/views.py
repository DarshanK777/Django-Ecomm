from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, View, DetailView
from django.shortcuts import redirect
from django.utils import timezone
from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Item, OrderItem, Order, BillingAddress, Payment, Coupon
from .forms import CheckOutForm, CouponForm
from django.core.exceptions import ObjectDoesNotExist
# Create your views here.

import stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


def itemList(request):
    context = {
        "items": Item.objects.all()
    }
    return render(request, 'home-page.html', context)


def products(request):
    context = {
        'items': Item.objects.all()
    }
    return render(request, 'products.html', context)


class CheckoutView(View):
    def get(self, *args, **kwargs):
        form = CheckOutForm()

        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            context = {
                'form': form,
                'couponform': CouponForm(),
                'order': order,
                "DISPLAY_COUPON_FORM": False
            }
            return render(self.request, "checkout.html", context=context)

        except ObjectDoesNotExist:
            messages.info(self.request, "Order Doesnt Exist")
            return redirect('core:checkout')

    def post(self, *args, **kwargs):
        form = CheckOutForm(self.request.POST or None)

        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            if form.is_valid():
                street_address = form.cleaned_data.get('street_address')
                apartment_address = form.cleaned_data.get('apartment_address')
                country = form.cleaned_data.get('country')
                zip = form.cleaned_data.get('zip')
                # same_billing_addr = form.cleaned_data.get('same_billing_addr')
                # save_info = form.cleaned_data.get('save_info')
                payment_option = form.cleaned_data.get('payment_option')

                billing_address = BillingAddress(
                    user=self.request.user,
                    street_address=street_address,
                    apartment_address=apartment_address,
                    country=country,
                    zip=zip
                )
                billing_address.save()
                order.billing_address = billing_address
                order.save()

                if payment_option == 'S':
                    return redirect('core:payment', payment_option='stripe')
                elif payment_option == 'P':
                    return redirect('core:payment', payment_option='paypal')
                else:
                    messages.warning(
                        self.request, "Invalid payment Option Selected"
                    )
                    return redirect("core:checkout")
            return redirect('core:checkout')

        except ObjectDoesNotExist:

            messages.info(self.request, "NO order in cart")
            return redirect("core:order-summary")

        return redirect('core:checkout')


class PaymentView(View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            if order.billing_address:
                context = {
                    'order': order,
                    "DISPLAY_COUPON_FORM": False
                }
                return render(self.request, "payment.html", context)
        except ObjectDoesNotExist:
            messages.warning(self.request, "NO Orders Present")
            return redirect('core:checkout')

    def post(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        amount = int(order.get_total() * 100),
        token = self.request.POST.get('stripeToken')

        try:
            charge = stripe.Charge.create(
                amount=amount,
                currency="usd",
                source=token,

            )
            payment = Payment()
            payment.stripe_charge_id = charge['id']
            payment.user = self.request.user
            payment.amount = amount
            payment.save()

            order_item = order.items.all()
            order_item.update(ordered=True)
            for item in order_item:
                item.save()

            order.ordered = True
            order.payment = payment
            order.save()
            messages.success('payment Succesfull')
            return redirect("/")

        except stripe.error.CardError as e:
            # Since it's a decline, stripe.error.CardError will be caught
            body = e.json_body
            err = body.get('error', {})

            messages.error(self.request, f"{err.get('message')}")
            print('Status is: %s' % e.http_status)
            print('Type is: %s' % e.error.type)
            print('Code is: %s' % e.error.code)
            # param is '' in this case
            print('Param is: %s' % e.error.param)
            print('Message is: %s' % e.error.message)

        except stripe.error.RateLimitError as e:
            messages.warning(self.request, "RateLimitError")
            # Too many requests made to the API too quickly
            return redirect("/")
        except stripe.error.InvalidRequestError as e:
            messages.warning(self.request, "InvalidRequestError")
            # Invalid parameters were supplied to Stripe's API
            return redirect("/")
        except stripe.error.AuthenticationError as e:
            messages.warning(self.request, "AuthenticationError")
            # Authentication with Stripe's API failed
            # (maybe you changed API keys recently)
            return redirect("/")
        except stripe.error.APIConnectionError as e:
            messages.warning(self.request, "APIConnectionError")
            # Network communication with Stripe failed
            return redirect("/")
        except stripe.error.StripeError as e:
            messages.warning(self.request, "StripeError")
            # Display a very generic error to the user, and maybe send
            # yourself an email
            return redirect("/")
        except Exception as e:
            # send some to me myself
            return redirect("/")


class HomeView(ListView):
    model = Item
    paginate_by = 8
    template_name = "home.html"


class OrderSummaryView(LoginRequiredMixin, View):

    def get(self, *args, **kwargs):

        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            context = {
                'object': order
            }

            return render(self.request, 'order_summary.html', context)

        except ObjectDoesNotExist:
            messages.info(self.request, "NO order in cart")
            return redirect("/")


class ItemDetailView(DetailView):
    model = Item
    template_name = 'product.html'


@login_required
def addToCart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_item, created = OrderItem.objects.get_or_create(
        item=item,
        user=request.user,
        ordered=False
    )  # get_or_create returns a tuple thus has to save in 2 dif variables
    # print(created) # True
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        if order.items.filter(item__slug=item.slug).exists():
            order_item.quantity += 1
            order_item.save()
            messages.info(request, "this item's quantity updated ")
            return redirect("core:order-summary")
        else:
            messages.info(request, "this item was added to the cart")
            order.items.add(order_item)
            return redirect("core:order-summary")

    else:
        ordered_date = timezone.now()
        order = Order.objects.create(
            user=request.user, ordered_date=ordered_date)
        order.items.add(order_item)
        messages.info(request, "this item was added to the cart")
        return redirect("core:order-summary")


@login_required
def removeFromCart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            )[0]
            order.items.remove(order_item)
            messages.info(request, "this item was removed from the cart")
            return redirect("core:order-summary")
        else:
            messages.info(request, "this item was not in the cart")
            return redirect("core:product", slug=slug)

    else:
        messages.info(request, "Dont have active order")
        return redirect("core:product", slug=slug)


@login_required
def removeSingleItemFromCart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(
        user=request.user,
        ordered=False
    )
    if order_qs.exists():
        order = order_qs[0]
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            )[0]
            if order_item.quantity > 1:
                order_item.quantity -= 1
                order_item.save()
            else:
                order.items.remove(order_item)
            messages.info(request, "This item quantity was updated.")
            return redirect("core:order-summary")
        else:
            messages.info(request, "This item was not in your cart")
            return redirect("core:product", slug=slug)
    else:
        messages.info(request, "You do not have an active order")
        return redirect("core:product", slug=slug)


def get_coupon(request, code):
    try:
        coupon = Coupon.objects.get(code=code)
        return coupon
    except ObjectDoesNotExist:
        messages.info(request, "Coupon does not exist")
        return redirect("core:checkout")


class AddCouponView(request, code):
    def post(self, *args, **kwargs):

        if request.method == "POST":
            form = CouponForm(self.request.POST or None)
            if form._is_valid():

                try:
                    code = form.cleaned_data.get('code')
                    order = Order.objects.get(
                        user=self.request.user, ordered=False)
                    coupon = get_coupon(self.request, code)
                    order.save()
                    messages.success(self.request, "Succesfully added coupon")
                    return redirect('core:checkout')

                except ObjectDoesNotExist:
                    messages.info(
                        self.request, "you do not have an active order")
                    return redirect("core:checkout")
