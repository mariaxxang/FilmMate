import json 
from django.shortcuts import get_object_or_404, render, redirect
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt 
from django.views.decorators.http import require_POST 
from django.contrib.auth.decorators import login_required
from django.db.models import Avg

from movies.models import Movie, WatchedMovie
from genres.models import Genre
from lists.models import List
from reviews.forms import ReviewForm
from users.models import FriendRequest
from .vector.chroma_utils import get_recommendation, find_similar_movies_by_content


def movie_home(request):
    """Homepage showing popular films and recent friend activity."""
    popular_films = Movie.objects.all()[7:14]
    friend_activities = []

    pending_requests = []
    if request.user.is_authenticated:
        # Friend requests
        pending_requests = (
            FriendRequest.objects.filter(to_user=request.user)
            .select_related('from_user')
            .order_by('-created')
        )

        # Friends activity
        friends = request.user.friends.all()

        # Get up to 7 most recent movies watched by friends
        friend_activities = (
            WatchedMovie.objects.filter(user__in=friends)
            .select_related('user', 'movie')
            .order_by('-watched_at')[:7]
        )

    context = {
        'popular_films': popular_films,
        'friend_activities': friend_activities,
        'pending_requests': pending_requests,
    }
    return render(request, 'movies/home.html', context)

@login_required
def friends_activity(request):
    friends = request.user.friends.all()
    activities = (
        WatchedMovie.objects.filter(user__in=friends)
        .select_related('user', 'movie')
        .order_by('-watched_at')
    )
    paginator = Paginator(activities, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'movies/friends_activity.html', {'page_obj': page_obj})

def movie_list(request):
    movies = Movie.objects.all()
    context = {
        'movies': movies,
    }
    return render(request, 'movies/list.html', context)

def movie_search(request):
    query = request.GET.get('q', '').strip()
    if query:
        results = Movie.objects.filter(title__icontains=query)
    else:
        results = Movie.objects.none() 

    friend_activities = []

    context = {
        'popular_films': results,
        'friend_activities': friend_activities,
        'query': query,
    }
    return render(request, 'movies/home.html', context)


def movie_detail(request, pk):
    """Show movie details + reviews + toggle watchlist + mark as watched + submit review + SIMILAR MOVIES."""
    movie = get_object_or_404(Movie, pk=pk)
    reviews = movie.review_set.all().select_related("user").order_by("-date")

    if request.user.is_authenticated:
        watchlist, _ = List.objects.get_or_create(user=request.user, name="Watchlist")
        in_watchlist = movie in watchlist.movies.all()

        watched = WatchedMovie.objects.filter(user=request.user, movie=movie).exists()
    else:
        in_watchlist = False
        watched = False

    form = ReviewForm()

    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect('users:login')

        action = request.POST.get('action')

        if action == 'toggle_watchlist':
            if in_watchlist:
                watchlist.movies.remove(movie)
            else:
                watchlist.movies.add(movie)
            return redirect('movies:movie_detail', pk=pk)

        elif action == 'mark_watched':
            WatchedMovie.objects.get_or_create(user=request.user, movie=movie)
            if in_watchlist:
                watchlist.movies.remove(movie)
            return redirect('movies:movie_detail', pk=pk)

        elif action == 'submit_review':
            form = ReviewForm(request.POST)
            if form.is_valid():
                review = form.save(commit=False)
                review.user = request.user
                review.movie = movie
                review.save()

                avg_rating = movie.review_set.aggregate(Avg("rating"))["rating__avg"] or 0
                movie.rating = round(avg_rating, 1)
                movie.save(update_fields=["rating"])

                return redirect('movies:movie_detail', pk=pk)

    genre_names = " ".join([g.name for g in movie.genres.all()])
    search_text = f"{movie.title} {genre_names} {movie.description}"

    similar_movies = find_similar_movies_by_content(search_text, movie.id, top_k=4)

    context = {
        'movie': movie,
        'reviews': reviews,
        'in_watchlist': in_watchlist,
        'watched': watched,
        'form': form,
        'similar_movies': similar_movies, # <-- Подаваме ги към темплейта
    }
    return render(request, 'movies/movie_detail.html', context)


@login_required
def toggle_watched(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    watched_entry, created = WatchedMovie.objects.get_or_create(user=request.user, movie=movie)

    if not created:
        watched_entry.delete()

    return redirect('movies:movie_detail', pk=movie_id)

@login_required
def my_films(request):
    """Display all movies the user has watched, with their ratings."""
    watched_movies = WatchedMovie.objects.filter(user=request.user).select_related("movie")
    reviews = {r.movie.id: r for r in request.user.review_set.all()}

    # Combine watched movies with rating info (if reviewed)
    watched_data = []
    for entry in watched_movies:
        movie = entry.movie
        review = reviews.get(movie.id)
        watched_data.append({
            "movie": movie,
            "rating": review.rating if review else None,
            "review_text": review.text if review else None,
        })

    context = {"watched_data": watched_data}
    return render(request, "movies/my_films.html", context)


def movies_all(request):
    query = request.GET.get('q', '')
    genre_filter = request.GET.get('genre', '')
    sort = request.GET.get('sort', 'title')

    movies = Movie.objects.all()

    # Search
    if query:
        movies = movies.filter(title__icontains=query)

    # Filter by genre
    if genre_filter:
        movies = movies.filter(genres__name__iexact=genre_filter).distinct()

    # Sorting
    if sort in ['title', 'year', 'director']:
        movies = movies.order_by(sort)

    # Pagination
    paginator = Paginator(movies, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    genres = Genre.objects.all()

    return render(request, 'movies/movies_all.html', {
        'page_obj': page_obj,
        'genres': genres,
        'query': query,
        'genre_filter': genre_filter,
        'sort': sort,
    })

# --- AI RECOMMENDATION API (UPDATED) ---

@csrf_exempt
@require_POST
def recommend_movie_api(request):
    try:
        data = json.loads(request.body)
        user_query = data.get('message', '').strip()

        if not user_query:
            return JsonResponse({'status': 'error', 'message': 'Please say something!'}, status=400)

        # The function now returns { "text_response": "...", "recommendations": [...] }
        ai_data = get_recommendation(user_query)

        return JsonResponse({
            'status': 'success',
            'message': ai_data.get('text_response', ''),
            'movies': ai_data.get('recommendations', [])
        })

    except Exception as e:
        print(f"Error: {e}")
        return JsonResponse({'status': 'error', 'message': 'Server error.'}, status=500)