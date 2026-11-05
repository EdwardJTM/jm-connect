from django.urls import path

from . import views

app_name = 'jm_connect'

urlpatterns = [
    path('api/v1/handoff/', views.HandoffView.as_view(), name='handoff'),
    path('jm/enter/<str:token>/', views.enter, name='enter'),
]
