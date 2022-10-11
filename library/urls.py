from django.urls import path, include
from rest_framework import routers


from . import views, viewsets

router = routers.DefaultRouter()
router.register(r'books', viewsets.BookViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework'))
]