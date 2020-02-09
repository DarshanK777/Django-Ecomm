from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, View, DetailView
from django.shortcuts import redirect
from django.utils import timezone
from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Item, OrderItem, Order, Address, Payment, Coupon, Refund, UserProfile
from .forms import CheckOutForm, CouponForm, RefundForm, PaymentForm
from django.core.exceptions import ObjectDoesNotExist
# Create your views here.
import random
import string
import stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


def create_ref_code():
    return ''.join(random.choice(string.ascii_lowercase + string.digits, k=20))


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


def _is_valid_form(values):
    valid = True
    for field in values:
        if field == '':
            valid = False

    return valid


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

            shipping_address = Address.objects.filter(
                user=self.request.user,
                address_type="S",
                default=True
            )

            if shipping_address.exists():
                context.update({
                    'default_shipping_address': shipping_address[0]
                })

            billing_address = Address.objects.filter(
                user=self.request.user,
                address_type="B",
                default=True
            )

            if billing_address.exists():
                context.update({
                    'default_billing_address': billing_address[0]
                })

            return render(self.request, "checkout.html", context=context)

        except ObjectDoesNotExist:
            messages.info(self.request, "Order Doesnt Exist")
            return redirect('core:checkout')

    def post(self, *args, **kwargs):
        form = CheckOutForm(self.request.POST or None)

        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            if form.is_valid():

                use_default_shipping = form.cleaned_data.get(
                    'use_default_shipping')

                if use_default_shipping:
                    address_qs = Address.objects.filter(
                        user=self.request.user,
                        address_type="S",
                        default=True
                    )

                    if address_qs.exists():
                        shipping_address = address_qs[0]
                        order.shipping_address = shipping_address
                        order.save()
                    else:
                        messages.info(self.request, "no default address")
                        return redirect('core:checkout')
                else:

                    shipping_address1 = form.cleaned_data.get(
                        'shipping_address')
                    shipping_address2 = form.cleaned_data.get(
                        'shipping_address2')
                    shipping_country = form.cleaned_data.get(
                        'shipping_country')
                    shipping_zip = form.cleaned_data.get('shipping_zip')
                    if _is_valid_form([shipping_address1, shipping_country, shipping_zip]):
                        shipping_address = Address(
                            user=self.request.user,
                            street_address=shipping_address1,
                            apartment_address=shipping_address2,
                            country=shipping_country,
                            zip=shipping_zip,
                            address_type='S'
                        )
                        shipping_address.save()
                        order.shipping_address = shipping_address
                        order.save()

                        set_default_shipping = form.cleaned_data.get(
                            'set_default_shipping')
                        if set_default_shipping:
                            shipping_address.default = True
                            shipping_address.save()
                    else:
                        messages.info(self.request, "please fill the form")

                # this is for billing address

                use_default_billing = form.cleaned_data.get(
                    'use_default_shipping')

                same_billing_address = form.cleaned_data.get(
                    'same_billing_address')

                if same_billing_address:
                    billing_address = shipping_address
                    billing_address.pk = None
                    billing_address.save()
                    billing_address.address_type = "B"
                    order.billing_address = billing_address
                    order.save()

                elif use_default_billing:
                    address_qs = Address.objects.filter(
                        user=self.request.user,
                        address_type="B",
                        default=True
                    )

                    if address_qs.exists():
                        billing_address = address_qs[0]
                        order.billing_address = billing_address
                        order.save()

                    else:
                        messages.info(self.request, "no default address")
                        return redirect('core:checkout')
                else:

                    billing_address1 = form.cleaned_data.get(
                        'billing_address')
                    billing_address2 = form.cleaned_data.get(
                        'billing_address2')
                    billing_country = form.cleaned_data.get(
                        'billing_country')
                    billing_zip = form.cleaned_data.get('billing_zip')
                    if _is_valid_form([billing_address1, billing_country, billing_zip]):
                        billing_address = Address(
                            user=self.request.user,
                            street_address=billing_address1,
                            apartment_address=billing_address2,
                            country=billing_country,
                            zip=billing_zip,
                            address_type='B'
                        )
                        billing_address.save()
                        order.billing_address = billing_address
                        order.save()

                        set_default_billing = form.cleaned_data.get(
                            'set_default_billing')
                        if set_default_billing:
                            billing_address.default = True
                            billing_address.save()
                    else:
                        messages.info(self.request, "please fill the form")

                payment_option = form.cleaned_data.get('payment_option')

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
                userprofile = self.request.user.userprofile
                if userprofile.one_click_purchasing:
                    # fetch the users card list
                    cards = stripe.Customer.list_sources(
                        userprofile.stripe_customer_id,
                        limit=3,
                        object='card'
                    )
                card_list = cards['data']
                if len(card_list) > 0:
                    # update the context with the default card
                    context.update({
                        'card': card_list[0]
                    })
                return render(self.request, "payment.html", context)
            else:
                messages.warning(
                    self.request, "You have not added a billing address")
                return redirect("core:checkout")

        except ObjectDoesNotExist:
            messages.warning(self.request, "NO Orders Present")
            return redirect('core:checkout')

    def post(self, *args, **kwargs):
        # order = Order.objects.get(user=self.request.user, ordered=False)
        # amount = int(order.get_total() * 100),
        # token = self.request.POST.get('stripeToken')

        order = Order.objects.get(user=self.request.user, ordered=False)
        form = PaymentForm(self.request.POST)
        userprofile = UserProfile.objects.get(user=self.request.user)
        if form.is_valid():
            token = form.cleaned_data.get('stripeToken')
            save = form.cleaned_data.get('save')
            use_default = form.cleaned_data.get('use_default')

            if save:
                if userprofile.stripe_customer_id != '' and userprofile.stripe_customer_id is not None:
                    customer = stripe.Customer.retrieve(
                        userprofile.stripe_customer_id)
                    customer.sources.create(source=token)

                else:
                    customer = stripe.Customer.create(
                        email=self.request.user.email,
                    )
                    customer.sources.create(source=token)
                    userprofile.stripe_customer_id = customer['id']
                    userprofile.one_click_purchasing = True
                    userprofile.save()

            amount = int(order.get_total() * 100)

        try:
            if use_default or save:
                # charge the customer because we cannot charge the token more than once
                charge = stripe.Charge.create(
                    amount=amount,  # cents
                    currency="usd",
                    customer=userprofile.stripe_customer_id
                )
            else:
                # charge once off on the token
                charge = stripe.Charge.create(
                    amount=amount,  # cents
                    currency="usd",
                    source=token
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
            order.ref_code = create_ref_code
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
            print(order.coupon)
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


class AddCouponView(View):
    def post(self, *args, **kwargs):
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


class RequestRefundView(View):
    def get(self, *args, **kwargs):
        form = RefundForm()
        context = {
            'form': form
        }
        return render(self.request, "request-refund", context)

    def post(self, *args, **kwargs):
        form = RefundForm(self.request.Post or None)
        if form.is_valid():
            ref_code = form.cleaned_data.get('ref_code')
            message = form.cleaned_data.get('message')
            email = form.cleaned_data.get('email')

            try:
                order = Order.objects.get(ref_code=ref_code)
                order.refund_requested = True
                order.save()

                refund = Refund()
                refund.order = order
                refund.reason = message
                refund.email = email
                refund.save()
                return redirect('/')

            except ObjectDoesNotExist:
                messages.info(self.request, "asdasdas")
                return redirect('core:request-refund')
