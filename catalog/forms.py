from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Branch, Rental


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(label='Correo electrónico')

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
        labels = {'username': 'Usuario'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class RentalForm(forms.ModelForm):
    class Meta:
        model = Rental
        fields = ('customer_name', 'branch', 'start_date', 'end_date')
        labels = {
            'customer_name': 'Nombre de quien retira',
            'branch': 'Sede de retiro',
            'start_date': 'Desde',
            'end_date': 'Hasta',
        }
        widgets = {
            'customer_name': forms.TextInput(attrs={'placeholder': 'Nombre y apellido', 'autocomplete': 'name'}),
            'branch': forms.Select(),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['branch'].queryset = Branch.objects.all()
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        equipment = self.initial.get('equipment')

        if start_date and start_date < timezone.localdate():
            self.add_error('start_date', 'El arriendo debe comenzar hoy o en una fecha futura.')
        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', 'La fecha de término debe ser posterior al inicio.')
        if start_date and end_date and equipment:
            overlaps = Rental.objects.filter(
                equipment=equipment,
                start_date__lte=end_date,
                end_date__gte=start_date,
            ).exclude(status=Rental.Status.CANCELLED)
            if overlaps.exists():
                self.add_error(None, 'Esta maquinaria ya está reservada para parte de esas fechas.')
        return cleaned_data
