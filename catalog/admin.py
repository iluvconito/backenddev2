from django.contrib import admin

from .models import Branch, Equipment, Rental


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
	list_display = ('name', 'region', 'phone')
	search_fields = ('name', 'region')


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
	list_display = ('name', 'brand', 'category', 'daily_rate', 'available')
	list_filter = ('category', 'available')
	search_fields = ('name', 'brand')


@admin.register(Rental)
class RentalAdmin(admin.ModelAdmin):
	list_display = ('equipment', 'customer_name', 'branch', 'start_date', 'end_date', 'status')
	list_filter = ('status', 'branch')
	search_fields = ('customer_name', 'user__username', 'equipment__name')
