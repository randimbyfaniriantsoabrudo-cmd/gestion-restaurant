from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register("plats", views.PlatViewSet, basename="plat")
router.register("tables", views.TableViewSet, basename="table")
router.register("employes", views.EmployeViewSet, basename="employe")
router.register("reservations", views.ReservationViewSet, basename="reservation")
router.register("comptes", views.CompteViewSet, basename="compte")
router.register("historique", views.HistoriqueViewSet, basename="historique")

urlpatterns = [
    path("login/", views.LoginView.as_view()),
    path("register/", views.register),
    path("dashboard/", views.dashboard_stats),
    path("", include(router.urls)),
]