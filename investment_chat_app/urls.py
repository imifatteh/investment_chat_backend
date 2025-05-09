from django.urls import path
from . import views

urlpatterns = [
    path("forms/", views.SECFilingsAPIView.as_view(), name="secfilings_list")
]
