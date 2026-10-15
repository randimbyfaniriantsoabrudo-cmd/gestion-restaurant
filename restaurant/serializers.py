from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import Employe, Historique, Plat, Profil, Reservation, Table

User = get_user_model()


class PlatSerializer(serializers.ModelSerializer):
    categorie_display = serializers.CharField(source="get_categorie_display", read_only=True)

    class Meta:
        model = Plat
        fields = ["id", "nom", "description", "prix", "categorie", "categorie_display", "disponible"]


class TableSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    client_actuel = serializers.SerializerMethodField()
    reservation_active_id = serializers.SerializerMethodField()

    class Meta:
        model = Table
        fields = ["id", "numero", "capacite", "statut", "statut_display", "client_actuel", "reservation_active_id"]

    def get_client_actuel(self, obj):
        return obj.client_actuel()

    def get_reservation_active_id(self, obj):
        resa = obj.reservation_active()
        return resa.id if resa else None


class EmployeSerializer(serializers.ModelSerializer):
    poste_display = serializers.CharField(source="get_poste_display", read_only=True)

    class Meta:
        model = Employe
        fields = ["id", "nom", "telephone", "poste", "poste_display", "salaire"]


class ReservationSerializer(serializers.ModelSerializer):
    table_numero = serializers.CharField(source="table.numero", read_only=True)
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = Reservation
        fields = [
            "id", "client_nom", "client_telephone", "date_reservation",
            "nombre_personnes", "table", "table_numero", "statut", "statut_display",
        ]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class CompteSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="utilisateur.username", read_only=True)
    email = serializers.CharField(source="utilisateur.email", read_only=True)
    is_staff = serializers.BooleanField(source="utilisateur.is_staff", read_only=True)
    traite_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = Profil
        fields = ["id", "username", "email", "is_staff", "statut", "traite_par_nom", "date_traitement", "date_creation"]

    def get_traite_par_nom(self, obj):
        return obj.traite_par.username if obj.traite_par else None


class HistoriqueSerializer(serializers.ModelSerializer):
    acteur_nom = serializers.CharField(source="acteur.username", read_only=True)

    class Meta:
        model = Historique
        fields = ["id", "horodatage", "acteur_nom", "action", "type_objet", "description"]