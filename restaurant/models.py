from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

telephone_validator = RegexValidator(
    regex=r"^\d{10}$", message="Le téléphone doit contenir exactement 10 chiffres."
)
nom_validator = RegexValidator(
    regex=r"^[A-Za-zÀ-ÖØ-öø-ÿ' -]+$", message="Le nom ne doit contenir que des lettres."
)


class Plat(models.Model):
    class Categorie(models.TextChoices):
        ENTREE = "entree", "Entrée"
        PLAT = "plat", "Plat principal"
        DESSERT = "dessert", "Dessert"
        BOISSON = "boisson", "Boisson"

    nom = models.CharField(max_length=150, unique=True, validators=[nom_validator])
    description = models.TextField(blank=True)
    prix = models.DecimalField(max_digits=10, decimal_places=2)
    categorie = models.CharField(max_length=20, choices=Categorie.choices)
    disponible = models.BooleanField(default=True)

    def __str__(self):
        return self.nom


class Table(models.Model):
    class Statut(models.TextChoices):
        LIBRE = "libre", "Libre"
        RESERVEE = "reservee", "Réservée"
        OCCUPEE = "occupee", "Occupée"

    numero = models.CharField(max_length=20, unique=True)
    capacite = models.PositiveIntegerField()
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.LIBRE)

    def reservation_active(self):
        return self.reservations.filter(
            statut__in=[Reservation.Statut.EN_ATTENTE, Reservation.Statut.CONFIRMEE]
        ).order_by("-date_reservation").first()

    def client_actuel(self):
        resa = self.reservation_active()
        return resa.client_nom if resa else "-"
    client_actuel.short_description = "Client"

    def __str__(self):
        return f"Table {self.numero}"


class Employe(models.Model):
    class Poste(models.TextChoices):
        SERVEUR = "serveur", "Serveur"
        CUISINIER = "cuisinier", "Cuisinier"
        CHEF = "chef", "Chef cuisinier"
        CAISSIER = "caissier", "Caissier"
        MANAGER = "manager", "Manager"
        PLONGEUR = "plongeur", "Plongeur"

    nom = models.CharField(max_length=150, validators=[nom_validator])
    telephone = models.CharField(
        max_length=10, unique=True, validators=[telephone_validator]
    )
    poste = models.CharField(max_length=20, choices=Poste.choices)
    salaire = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.nom} ({self.get_poste_display()})"


class Reservation(models.Model):
    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        CONFIRMEE = "confirmee", "Confirmée"
        ANNULEE = "annulee", "Annulée"
        TERMINEE = "terminee", "Terminée"

    client_nom = models.CharField(max_length=150, validators=[nom_validator])
    client_telephone = models.CharField(max_length=10, validators=[telephone_validator])
    date_reservation = models.DateTimeField()
    nombre_personnes = models.PositiveIntegerField()
    table = models.ForeignKey(Table, on_delete=models.PROTECT, related_name="reservations")
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE
    )

    ACTIFS = ["en_attente", "confirmee"]
    TERMINALES = ["terminee", "annulee"]
    DUREE_MINUTES = 90

    def clean(self):
        errors = {}
        if self.pk is None and self.date_reservation and self.date_reservation < timezone.now():
            errors["date_reservation"] = "La date de réservation ne peut pas être dans le passé."
        if self.table_id:
            if self.nombre_personnes and self.nombre_personnes > self.table.capacite:
                errors["nombre_personnes"] = (
                    f"La table {self.table.numero} ne peut accueillir que "
                    f"{self.table.capacite} personne(s)."
                )
            if self.statut in self.ACTIFS and self.date_reservation:
                debut = self.date_reservation
                fin = debut + timedelta(minutes=self.DUREE_MINUTES)
                autres = self.table.reservations.filter(statut__in=self.ACTIFS).exclude(pk=self.pk)
                for autre in autres:
                    autre_debut = autre.date_reservation
                    autre_fin = autre_debut + timedelta(minutes=self.DUREE_MINUTES)
                    if debut < autre_fin and autre_debut < fin:
                        errors["date_reservation"] = (
                            f"La table {self.table.numero} est déjà réservée entre "
                            f"{autre_debut.strftime('%d/%m/%Y %H:%M')} et "
                            f"{autre_fin.strftime('%d/%m/%Y %H:%M')}."
                        )
                        break
                if self.table.statut == Table.Statut.OCCUPEE:
                    errors["table"] = f"La table {self.table.numero} est occupée."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        self._synchroniser_table(self.table)

    def delete(self, *args, **kwargs):
        table = self.table
        super().delete(*args, **kwargs)
        self._synchroniser_table(table)

    @staticmethod
    def _synchroniser_table(table):
        active = table.reservations.filter(statut__in=Reservation.ACTIFS).exists()
        nouveau_statut = Table.Statut.RESERVEE if active else Table.Statut.LIBRE
        if table.statut != nouveau_statut:
            table.statut = nouveau_statut
            table.save()

    def __str__(self):
        return f"{self.client_nom} - {self.table} - {self.date_reservation}"


class Profil(models.Model):
    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        VALIDE = "valide", "Validé"
        REFUSE = "refuse", "Refusé"
        BLOQUE = "bloque", "Bloqué"

    utilisateur = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profil"
    )
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE)
    traite_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="comptes_traites",
    )
    date_traitement = models.DateTimeField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.utilisateur} ({self.get_statut_display()})"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def creer_profil(sender, instance, created, **kwargs):
    if created:
        statut = (
            Profil.Statut.VALIDE
            if (instance.is_staff or instance.is_superuser)
            else Profil.Statut.EN_ATTENTE
        )
        Profil.objects.get_or_create(utilisateur=instance, defaults={"statut": statut})


class Historique(models.Model):
    horodatage = models.DateTimeField(auto_now_add=True)
    acteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="actions"
    )
    action = models.CharField(max_length=50)
    type_objet = models.CharField(max_length=50, default="")
    description = models.CharField(max_length=255)

    class Meta:
        ordering = ["-horodatage"]

    def __str__(self):
        return f"{self.horodatage} - {self.acteur} - {self.action}"


def enregistrer(acteur, action, type_objet, description):
    Historique.objects.create(
        acteur=acteur, action=action, type_objet=type_objet, description=description
    )