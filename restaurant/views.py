from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import filters, permissions, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .models import Employe, Historique, Plat, Profil, Reservation, Table, enregistrer
from .serializers import (
    CompteSerializer, EmployeSerializer, HistoriqueSerializer, PlatSerializer,
    RegisterSerializer, ReservationSerializer, TableSerializer,
)


class StandardPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = "page_size"


class IsStaff(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class PlatViewSet(viewsets.ModelViewSet):
    serializer_class = PlatSerializer
    pagination_class = StandardPagination
    permission_classes = [IsStaff]
    filter_backends = [filters.SearchFilter]
    search_fields = ["nom", "categorie"]

    def get_queryset(self):
        qs = Plat.objects.all().order_by("nom")
        categorie = self.request.query_params.get("categorie")
        if categorie:
            qs = qs.filter(categorie=categorie)
        return qs

    def perform_create(self, serializer):
        plat = serializer.save()
        enregistrer(self.request.user, "creation", "plat", f"Ajout du plat « {plat.nom} »")

    def perform_update(self, serializer):
        plat = serializer.save()
        enregistrer(self.request.user, "modification", "plat", f"Modification du plat « {plat.nom} »")

    def perform_destroy(self, instance):
        nom = instance.nom
        instance.delete()
        enregistrer(self.request.user, "suppression", "plat", f"Suppression du plat « {nom} »")


class TableViewSet(viewsets.ModelViewSet):
    serializer_class = TableSerializer
    pagination_class = StandardPagination
    permission_classes = [IsStaff]
    filter_backends = [filters.SearchFilter]
    search_fields = ["numero"]

    def get_queryset(self):
        qs = Table.objects.all().order_by("numero")
        statut = self.request.query_params.get("statut")
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    @action(detail=False, methods=["get"])
    def disponibles(self, request):
        qs = Table.objects.filter(statut=Table.Statut.LIBRE).order_by("numero")
        return Response(self.get_serializer(qs, many=True).data)

    def perform_create(self, serializer):
        table = serializer.save()
        enregistrer(self.request.user, "creation", "table", f"Ajout de la table {table.numero}")

    def perform_update(self, serializer):
        table = serializer.save()
        enregistrer(self.request.user, "modification", "table", f"Modification de la table {table.numero}")

    def perform_destroy(self, instance):
        numero = instance.numero
        instance.delete()
        enregistrer(self.request.user, "suppression", "table", f"Suppression de la table {numero}")


class EmployeViewSet(viewsets.ModelViewSet):
    serializer_class = EmployeSerializer
    pagination_class = StandardPagination
    permission_classes = [IsStaff]
    filter_backends = [filters.SearchFilter]
    search_fields = ["nom", "telephone"]

    def get_queryset(self):
        qs = Employe.objects.all().order_by("nom")
        poste = self.request.query_params.get("poste")
        if poste:
            qs = qs.filter(poste=poste)
        return qs

    def perform_create(self, serializer):
        emp = serializer.save()
        enregistrer(self.request.user, "creation", "employe", f"Ajout de l'employé {emp.nom}")

    def perform_update(self, serializer):
        emp = serializer.save()
        enregistrer(self.request.user, "modification", "employe", f"Modification de l'employé {emp.nom}")

    def perform_destroy(self, instance):
        nom = instance.nom
        instance.delete()
        enregistrer(self.request.user, "suppression", "employe", f"Suppression de l'employé {nom}")


class ReservationViewSet(viewsets.ModelViewSet):
    serializer_class = ReservationSerializer
    pagination_class = StandardPagination
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ["client_nom", "client_telephone"]

    def get_queryset(self):
        qs = Reservation.objects.select_related("table").order_by("-date_reservation")
        statut = self.request.query_params.get("statut")
        if statut:
            qs = qs.filter(statut=statut)
        else:
            qs = qs.exclude(statut__in=Reservation.TERMINALES)
        return qs

    def _sauver(self, serializer):
        try:
            serializer.save()
        except DjangoValidationError as e:
            detail = e.message_dict if hasattr(e, "message_dict") else {"detail": e.messages}
            raise DRFValidationError(detail)

    def perform_create(self, serializer):
        self._sauver(serializer)
        resa = serializer.instance
        enregistrer(
            self.request.user, "creation", "reservation",
            f"Réservation de {resa.client_nom} pour la table {resa.table.numero}",
        )

    def perform_update(self, serializer):
        resa_avant = serializer.instance
        client = resa_avant.client_nom
        nouveau_statut = serializer.validated_data.get("statut", resa_avant.statut)
        self._sauver(serializer)
        if nouveau_statut in Reservation.TERMINALES:
            libelle = "terminée" if nouveau_statut == "terminee" else "annulée"
            enregistrer(self.request.user, nouveau_statut, "reservation", f"Réservation de {client} marquée {libelle}")
        else:
            enregistrer(self.request.user, "modification", "reservation", f"Modification de la réservation de {client}")

    def perform_destroy(self, instance):
        client = instance.client_nom
        instance.delete()
        enregistrer(self.request.user, "suppression", "reservation", f"Suppression de la réservation de {client}")


def get_profil(user):
    profil, _ = Profil.objects.get_or_create(utilisateur=user, defaults={"statut": Profil.Statut.VALIDE})
    return profil


class LoginView(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        profil = get_profil(user)
        if profil.statut == Profil.Statut.EN_ATTENTE:
            raise PermissionDenied("Votre compte est en attente de validation par un administrateur.")
        if profil.statut == Profil.Statut.REFUSE:
            raise PermissionDenied("Votre demande de compte a été refusée.")
        if profil.statut == Profil.Statut.BLOQUE:
            raise PermissionDenied("Votre compte a été bloqué.")
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "username": user.username, "is_staff": user.is_staff})


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(
        {"detail": "Compte créé. Il doit être validé par un administrateur avant de pouvoir vous connecter."},
        status=201,
    )


class CompteViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CompteSerializer
    permission_classes = [IsStaff]
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = Profil.objects.select_related("utilisateur", "traite_par").order_by("-date_creation")
        statut = self.request.query_params.get("statut")
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def _traiter(self, request, profil, statut, action_nom):
        if profil.utilisateur.is_superuser:
            raise PermissionDenied("Ce compte ne peut pas être modifié.")
        profil.statut = statut
        profil.traite_par = request.user
        profil.date_traitement = timezone.now()
        profil.save()
        enregistrer(request.user, action_nom, "compte", f"{action_nom.capitalize()} du compte {profil.utilisateur.username}")
        return Response(self.get_serializer(profil).data)

    @action(detail=True, methods=["post"])
    def valider(self, request, pk=None):
        return self._traiter(request, self.get_object(), Profil.Statut.VALIDE, "validation")

    @action(detail=True, methods=["post"])
    def refuser(self, request, pk=None):
        return self._traiter(request, self.get_object(), Profil.Statut.REFUSE, "refus")

    @action(detail=True, methods=["post"])
    def bloquer(self, request, pk=None):
        return self._traiter(request, self.get_object(), Profil.Statut.BLOQUE, "blocage")

    @action(detail=True, methods=["post"])
    def debloquer(self, request, pk=None):
        return self._traiter(request, self.get_object(), Profil.Statut.VALIDE, "deblocage")

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def promouvoir(self, request, pk=None):
        profil = self.get_object()
        if profil.utilisateur.is_superuser:
            raise PermissionDenied("Ce compte est déjà superutilisateur.")
        profil.utilisateur.is_staff = True
        profil.utilisateur.save()
        enregistrer(request.user, "promotion", "compte", f"Promotion admin de {profil.utilisateur.username}")
        return Response(self.get_serializer(profil).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def retrograder(self, request, pk=None):
        profil = self.get_object()
        if profil.utilisateur.is_superuser:
            raise PermissionDenied("Ce compte ne peut pas être rétrogradé.")
        profil.utilisateur.is_staff = False
        profil.utilisateur.save()
        enregistrer(request.user, "retrogradation", "compte", f"Retrait des droits admin de {profil.utilisateur.username}")
        return Response(self.get_serializer(profil).data)


class HistoriqueViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = HistoriqueSerializer
    permission_classes = [IsStaff]
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = Historique.objects.select_related("acteur")
        type_objet = self.request.query_params.get("type")
        if type_objet:
            qs = qs.filter(type_objet=type_objet)
        return qs


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def dashboard_stats(request):
    reservations_par_statut = {
        s: Reservation.objects.filter(statut=s).count()
        for s in ["en_attente", "confirmee", "annulee", "terminee"]
    }
    plats_par_categorie = {
        c: Plat.objects.filter(categorie=c).count()
        for c in ["entree", "plat", "dessert", "boisson"]
    }
    return Response({
        "total_plats": Plat.objects.count(),
        "total_tables": Table.objects.count(),
        "tables_libres": Table.objects.filter(statut=Table.Statut.LIBRE).count(),
        "tables_reservees": Table.objects.filter(statut=Table.Statut.RESERVEE).count(),
        "tables_occupees": Table.objects.filter(statut=Table.Statut.OCCUPEE).count(),
        "total_employes": Employe.objects.count(),
        "reservations_aujourdhui": Reservation.objects.filter(date_reservation__date=timezone.localdate()).count(),
        "reservations_par_statut": reservations_par_statut,
        "plats_par_categorie": plats_par_categorie,
    })