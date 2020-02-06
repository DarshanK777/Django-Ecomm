from django import forms
from django_countries.fields import CountryField
from django_countries.widgets import CountrySelectWidget

PAYMENT_CHOICES = (('S', 'Stripe'), ('P', 'Paypal'))


class CheckOutForm(forms.Form):
    street_address = forms.CharField()
    apartment_address = forms.CharField(required=False)
    country = CountryField(blank_label='(select Country)').formfield(widget=CountrySelectWidget(
        attrs={
            'class': 'custom-select d-block w-100'
        }
    ))
    zip = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control'
        })
    )
    same_billing_addr = forms.BooleanField(
        widget=forms.CheckboxInput(), required=False)
    save_info = forms.BooleanField(
        widget=forms.CheckboxInput(), required=False)
    payment_option = forms.ChoiceField(
        widget=forms.RadioSelect(), choices=PAYMENT_CHOICES)


class CouponForm(forms.Form):
    code = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': "Promo Code",
        'aria-label': 'Recipient\'s Username',
        'aria-describeby': "basic-addon2"

    }))
