from django.urls import path
from . import views

app_name = 'movies'

urlpatterns = [
    path('', views.movie_home, name='home'),      
    path('friends-activity/', views.friends_activity, name='friends_activity'),
    path('list/', views.movie_list, name='movie_list'), 
    path('search/', views.movie_search, name='movie_search'), 
    path('<int:pk>/', views.movie_detail, name='movie_detail'),
    path('all/', views.movies_all, name='movies_all'),
    path('movie/<int:movie_id>/watched/', views.toggle_watched, name='toggle_watched'),
    path("my-films/", views.my_films, name="my_films"),
    path('api/recommend/', views.recommend_movie_api, name='recommend_api'),
]
