from django.urls import include, path

from .views import index, chat_api

app_name = 'chat'

urlpatterns = [
    path('api/', chat_api),
    path('', index, name='chat'),
]
