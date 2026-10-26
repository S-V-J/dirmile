from django.urls import path

from weather import views

urlpatterns = [
    path("places/", views.places_search, name="places-search"),
]
