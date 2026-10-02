"""Operaciones transaccionales del ciclo de estados e inventario de contratos."""

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import EquipmentStock, Rental


ALLOWED_STATUS_TRANSITIONS = {
    # Define el flujo válido; los estados finales no pueden reabrirse.
    Rental.Status.PENDING: {Rental.Status.PAID, Rental.Status.CANCELLED},
    Rental.Status.PAID: {Rental.Status.DELIVERED, Rental.Status.CANCELLED},
    Rental.Status.DELIVERED: {Rental.Status.COMPLETED, Rental.Status.CANCELLED},
    Rental.Status.COMPLETED: set(),
    Rental.Status.CANCELLED: set(),
}


@transaction.atomic
def transition_rental_status(rental_id, new_status):
    """Valida una transición y actualiza estado y stock bajo bloqueo transaccional."""
    rental = Rental.objects.select_for_update().select_related(
        'equipment',
        'branch',
    ).get(pk=rental_id)

    if new_status not in Rental.Status.values:
        raise ValidationError('El estado del contrato no es válido.')
    if new_status == rental.status:
        return rental
    if new_status not in ALLOWED_STATUS_TRANSITIONS[rental.status]:
        raise ValidationError(
            f'No se puede cambiar el contrato de {rental.get_status_display()} '
            f'a {rental.Status(new_status).label}.'
        )

    stock = None
    if new_status == Rental.Status.PAID or (
        rental.has_consumed_stock
        and new_status in (Rental.Status.COMPLETED, Rental.Status.CANCELLED)
    ):
        stock = EquipmentStock.objects.select_for_update().filter(
            equipment=rental.equipment,
            branch=rental.branch,
        ).first()
        if stock is None:
            raise ValidationError('No existe inventario registrado para esta maquinaria y sede.')

    if new_status == Rental.Status.PAID:
        available = stock.quantity
        if available < rental.quantity:
            raise ValidationError(
                f'Inventario insuficiente en {rental.branch.name}: '
                f'{available} unidad(es) disponible(s), {rental.quantity} solicitada(s).'
            )
        stock.quantity -= rental.quantity
    elif rental.has_consumed_stock and new_status in (
        Rental.Status.COMPLETED,
        Rental.Status.CANCELLED,
    ):
        stock.quantity += rental.quantity

    if stock is not None:
        stock.save(update_fields=('quantity',))

    rental.status = new_status
    rental.save(update_fields=('status',))
    return rental
