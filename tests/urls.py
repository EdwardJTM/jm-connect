from django.http import HttpResponse
from django.urls import include, path

urlpatterns = [
    path('home/', lambda request: HttpResponse(request.user.get_username())),
    path('', include('jm_connect.urls')),
]
