"""Formularios HTML con validación para cuentas, stock y solicitudes de arriendo."""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Branch, Equipment, EquipmentStock, Rental, equipment_availability


class RegistrationForm(UserCreationForm):
    """Registra clientes y aplica el estilo común a sus campos."""

    email = forms.EmailField(label='Correo electrónico')

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
        labels = {'username': 'Usuario'}

    def __init__(self, *args, **kwargs):
        """Asigna clases CSS a los controles generados por Django."""
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class InventoryEquipmentForm(forms.ModelForm):
    """Captura datos de maquinaria y su inventario inicial en una sede."""

    branch = forms.ModelChoiceField(queryset=Branch.objects.all(), label='Sede inicial')
    quantity = forms.IntegerField(min_value=0, initial=1, label='Unidades en esta sede')

    class Meta:
        model = Equipment
        fields = (
            'name',
            'brand',
            'category',
            'image_url',
            'description',
            'daily_rate',
            'fixed_deposit',
            'available',
        )
        labels = {
            'name': 'Nombre de la maquinaria',
            'brand': 'Marca',
            'category': 'Categoría',
            'image_url': 'URL de la imagen',
            'description': 'Descripción',
            'daily_rate': 'Tarifa diaria (CLP)',
            'fixed_deposit': 'Garantía fija (CLP)',
            'available': 'Disponible para arriendo',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        """Aplica la presentación común a los campos del formulario."""
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class InventoryStockForm(forms.ModelForm):
    """Actualiza el total físico de un equipo para una sede."""

    class Meta:
        model = EquipmentStock
        fields = ('equipment', 'branch', 'quantity')
        labels = {
            'equipment': 'Maquinaria',
            'branch': 'Sede',
            'quantity': 'Cantidad total en esta sede',
        }
        help_texts = {
            'quantity': 'Ingresa el nuevo total de unidades para esta maquinaria y sede.',
        }

    def __init__(self, *args, **kwargs):
        """Ordena opciones y aplica estilos antes de renderizar el formulario."""
        super().__init__(*args, **kwargs)
        self.fields['equipment'].queryset = Equipment.objects.order_by('name')
        self.fields['branch'].queryset = Branch.objects.all()
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    def clean(self):
        """Reutiliza el registro de stock existente para evitar duplicados."""
        cleaned_data = super().clean()
        equipment = cleaned_data.get('equipment')
        branch = cleaned_data.get('branch')
        if equipment and branch:
            existing_stock = EquipmentStock.objects.filter(
                equipment=equipment,
                branch=branch,
            ).first()
            if existing_stock:
                self.instance = existing_stock
        return cleaned_data


class RentalForm(forms.ModelForm):
    """Valida identidad, fechas y disponibilidad de solicitudes web."""

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

    def __init__(self, *args, equipment=None, **kwargs):
        """Limita sedes disponibles y recibe el equipo sujeto a la solicitud."""
        super().__init__(*args, **kwargs)
        self.equipment = equipment
        self.fields['branch'].queryset = Branch.objects.all()
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    def clean(self):
        """Rechaza fechas pasadas, rangos invertidos y sedes sin stock."""
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        branch = cleaned_data.get('branch')

        if start_date and start_date < timezone.localdate():
            self.add_error('start_date', 'El arriendo debe comenzar hoy o en una fecha futura.')
        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', 'La fecha de término debe ser posterior al inicio.')
        if start_date and end_date and end_date >= start_date and self.equipment and branch:
            available_by_branch = equipment_availability(self.equipment, start_date, end_date)
            available_quantity = next(
                (entry['quantity'] for entry in available_by_branch if entry['branch'].pk == branch.pk),
                0,
            )
            if available_quantity < 1:
                self.add_error(None, 'Esta maquinaria ya está reservada en esta sede para parte de esas fechas.')
        return cleaned_data
