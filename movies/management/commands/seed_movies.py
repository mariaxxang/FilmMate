from django.core.management.base import BaseCommand
from ...factories import MovieFactory
import tmdbsimple as tmdb
import os
import random

tmdb.API_KEY = os.getenv("TMDB_API_KEY")

class Command(BaseCommand):
    help = "Seed movies and genres from TMDb API using MovieFactory"

    def handle(self, *args, **options):
        # Get TMDb genre mapping once
        try:
            genre_list = tmdb.Genres().movie_list().get('genres', [])
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Failed to fetch genres: {e}"))
            genre_list = []

        movies = []
        for _ in range(30): 
            page = random.randint(1, 500) 
            try:
                response = tmdb.Discover().movie(page=page)
                results = response.get('results', [])
                if not results:
                    continue
                movies.extend(results)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to fetch movies for page {page}: {e}"))
                continue

        movies = movies[:150] 

        for item in movies:
            title = item.get('title') or 'Untitled Movie'
            release_date = item.get('release_date') or ''
            year = int(release_date[:4]) if release_date else 0
            description = item.get('overview') or 'No description available'
            genre_ids = item.get('genre_ids', [])
            poster_path = item.get('poster_path')

            director = 'Unknown'
            try:
                credits = tmdb.Movies(item['id']).credits()
                for member in credits.get('crew', []):
                    if member.get('job') == 'Director':
                        director = member.get('name') or 'Unknown'
                        break
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Failed to fetch director for {title}: {e}"))

            # Create movie via factory
            movie = MovieFactory.create_movie(
                title=title,
                year=year,
                director=director,
                description=description,
                genre_ids=genre_ids,
                genre_list=genre_list,
                poster_path=poster_path
            )

            if movie:
                self.stdout.write(self.style.SUCCESS(f"Movie '{movie.title}' added."))
            else:
                self.stdout.write(self.style.NOTICE(f"Movie '{title}' already exists. Skipping."))
