"""URL configuration for the ideagraph web UI app."""

from __future__ import annotations

from django.urls import path

from ideagraph.server.web import views

app_name = "web"

urlpatterns = [
    path("", views.index, name="index"),
    path("graphs/", views.graphs_list, name="graphs"),
    path("graphs/<slug:slug>/", views.graph_detail, name="graph-detail"),
    path("graphs/<slug:slug>/data/", views.graph_data, name="graph-data"),
]
