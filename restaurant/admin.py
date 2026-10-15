from django.contrib import admin
from django.db.models import Q
from .models import Employe, Plat, Reservation, Table


@admin.register(Plat)
class PlatAdmin(admin.ModelAdmin):
    list_display = ("nom", "categorie", "prix", "disponible")
    list_filter = ("categorie", "disponible")
    search_fields = ("nom",)


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ("numero", "capacite", "statut", "client_actuel")
    list_filter = ("statut",)


@admin.register(Employe)
class EmployeAdmin(admin.ModelAdmin):
    list_display = ("nom", "poste", "telephone", "salaire")
    list_filter = ("poste",)
    search_fields = ("nom", "telephone")


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("client_nom", "table", "date_reservation", "nombre_personnes", "statut")
    list_filter = ("statut",)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "table":
            object_id = request.resolver_match.kwargs.get("object_id")
            qs = Q(statut=Table.Statut.LIBRE)
            if object_id:
                current = Reservation.objects.filter(pk=object_id).values_list("table_id", flat=True).first()
                if current:
                    qs |= Q(pk=current)
            kwargs["queryset"] = Table.objects.filter(qs).order_by("numero")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)