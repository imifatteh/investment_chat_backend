from django.urls import path
from polygon_ai.views import aggs_data_view

urlpatterns = [path("aggs_data/<str:ticker>/", aggs_data_view, name="aggs_data")]
