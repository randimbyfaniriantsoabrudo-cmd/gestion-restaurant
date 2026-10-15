from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import Profil


class ValidatedTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        statut = Profil.objects.filter(utilisateur=user).values_list("statut", flat=True).first()
        if statut is not None and statut != Profil.Statut.VALIDE:
            raise AuthenticationFailed("Compte non validé.")
        return user, token