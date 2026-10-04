from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db.models.functions import Lower, Trim

class RegisterForm(UserCreationForm):
    email = forms.EmailField(label='Email', required=True, max_length=254)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.annotate(normalized_email=Lower(Trim('email'))).filter(normalized_email=email).exists():
            raise forms.ValidationError('Этот email уже используется.')
        return email
