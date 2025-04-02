import requests
import os
from flask import Flask, render_template, request
from dotenv import load_dotenv
import random
import googlemaps  

# Configuración inicial
load_dotenv(override=True)
app = Flask(__name__)

# Constantes
TICKETMASTER_API_KEY = os.getenv("TICKETMASTER_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
MAX_RESULTS = 9  # Límite de conciertos a mostrar

# Inicializar cliente de Google Maps
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

class ConcertService:
    @staticmethod
    def get_events(artist_name):
        """Obtiene eventos de Ticketmaster con manejo robusto de errores"""
        try:
            params = {
                "apikey": TICKETMASTER_API_KEY,
                "keyword": artist_name,
                "size": MAX_RESULTS,
                "classificationName": "Music",
                "sort": "date,asc"
            }
            
            response = requests.get(
                "https://app.ticketmaster.com/discovery/v2/events.json",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            return response.json().get("_embedded", {}).get("events", [])
            
        except requests.exceptions.RequestException as e:
            app.logger.error(f"Error Ticketmaster: {str(e)}")
            return []  # Si hay error, devuelve una lista vacía


class WeatherService:
    @staticmethod
    def get_weather(city):
        """Obtiene datos climáticos con manejo de errores"""
        if not city or city == "Ciudad desconocida":
            return {"description": "Ciudad no especificada", "temperature": "N/A"}

        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=es"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            clima_data = response.json()

            return {
                "description": clima_data["weather"][0]["description"].capitalize(),
                "temperature": round(clima_data["main"]["temp"], 1)
            }
        except requests.exceptions.RequestException as e:
            app.logger.error(f"Error OpenWeather: {str(e)}")
            return {"description": "Datos no disponibles", "temperature": "N/A"}


class SpotifyService:
    @staticmethod
    def get_artist_info(artist_name):
        """Obtiene información del artista desde Spotify"""
        try:
            auth_response = requests.post(
                "https://accounts.spotify.com/api/token",
                data={"grant_type": "client_credentials"},
                auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
            )
            auth_response.raise_for_status()
            access_token = auth_response.json().get("access_token")
            
            headers = {"Authorization": f"Bearer {access_token}"}
            search_url = "https://api.spotify.com/v1/search"
            params = {"q": artist_name, "type": "artist", "limit": 1}
            
            response = requests.get(search_url, headers=headers, params=params)
            response.raise_for_status()
            artists = response.json().get("artists", {}).get("items", [])
            
            if artists:
                return artists[0]
            return None
        except requests.exceptions.RequestException as e:
            app.logger.error(f"Error Spotify: {str(e)}")
            return None

    @staticmethod
    def get_top_tracks(artist_id):
        """Obtiene las canciones más populares del artista desde Spotify"""
        try:
            auth_response = requests.post(
                "https://accounts.spotify.com/api/token",
                data={"grant_type": "client_credentials"},
                auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
            )
            auth_response.raise_for_status()
            access_token = auth_response.json().get("access_token")

            headers = {"Authorization": f"Bearer {access_token}"}
            top_tracks_url = f"https://api.spotify.com/v1/artists/{artist_id}/top-tracks?market=US"

            response = requests.get(top_tracks_url, headers=headers)
            response.raise_for_status()
            top_tracks = response.json().get("tracks", [])

            return top_tracks
        except requests.exceptions.RequestException as e:
            app.logger.error(f"Error Spotify obtaining top tracks: {str(e)}")
            return []

    @staticmethod
    def get_playlists_by_genre(genre):
        """Obtiene playlists basadas en un género musical"""
        try:
            auth_response = requests.post(
                "https://accounts.spotify.com/api/token",
                data={"grant_type": "client_credentials"},
                auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
            )
            auth_response.raise_for_status()
            access_token = auth_response.json().get("access_token")

            headers = {"Authorization": f"Bearer {access_token}"}
            search_url = f"https://api.spotify.com/v1/search?q={genre}&type=playlist&limit=10"

            response = requests.get(search_url, headers=headers)
            response.raise_for_status()
            playlists = response.json().get("playlists", {}).get("items", [])

            return playlists
        except requests.exceptions.RequestException as e:
            app.logger.error(f"Error Spotify obtaining recommended playlists: {str(e)}")
            return []


@app.route("/", methods=["GET", "POST"])
def index():
    artist_name = ""
    artist_info = None
    top_tracks = []
    events_with_playlists = []
    
    if request.method == "POST":
        artist_name = request.form.get("artista", "").strip()

        if not artist_name:
            return render_template("index.html", error="Please write an artist")
        
        # Obtener información del artista desde Spotify
        artist_info = SpotifyService.get_artist_info(artist_name)
        
        if artist_info:
            artist_id = artist_info["id"]
            # Obtener las canciones más populares del artista
            top_tracks = SpotifyService.get_top_tracks(artist_id)
            # Obtener los géneros del artista
            artist_genres = artist_info.get("genres", [])
            if artist_genres:
                genre = artist_genres[0]  # Tomamos el primer género disponible
                # Buscar playlists relacionadas con ese género
                playlists = SpotifyService.get_playlists_by_genre(genre)
                # Si encontramos playlists, seleccionamos una aleatoriamente
                if playlists:
                    random_playlist = random.choice(playlists)
                    artist_info["playlist"] = random_playlist  # Agregar la playlist a la información del artista
        
        # Obtener conciertos
        events = ConcertService.get_events(artist_name)
        
        if not events:
            # Si no se encontraron conciertos, solo renderiza la vista con el mensaje de error.
            return render_template("index.html", error=f"No concert found for {artist_name}", artist_name=artist_name, artist_info=artist_info, top_tracks=top_tracks, google_maps_api_key=GOOGLE_MAPS_API_KEY)
        
        # Procesar con datos climáticos y agregar playlists a los eventos
        for event in events:
            venue = event.get("_embedded", {}).get("venues", [{}])[0]
            city = venue.get("city", {}).get("name", "Ciudad desconocida")
            
            # Obtener coordenadas de la ciudad usando la API de Google Maps
            geocode_result = gmaps.geocode(city)
            if geocode_result:
                location = geocode_result[0]['geometry']['location']
                lat, lng = location['lat'], location['lng']
            else:
                lat, lng = None, None

            weather_data = WeatherService.get_weather(city)

            event_data = {
                "city": city,
                "date": event.get("dates", {}).get("start", {}).get("localDate", "Fecha no disponible"),
                "venue": venue.get("name", "Lugar no disponible"),
                "tickets_url": event.get("url", "#"),
                "weather": weather_data,
                "location": {"lat": lat, "lng": lng},  # Usamos la latitud y longitud de Google Maps
                "playlist": artist_info.get("playlist", {})  # Agregar la playlist relacionada
            }
            events_with_playlists.append(event_data)

        # Solo renderizar si hay eventos, y pasar todos los datos.
        return render_template("index.html", events=events_with_playlists, artist_name=artist_name, artist_info=artist_info, top_tracks=top_tracks, google_maps_api_key=GOOGLE_MAPS_API_KEY)
    
    # En el caso de un GET, solo renderizamos la página sin datos de eventos
    return render_template("index.html", artist_name=artist_name, artist_info=artist_info, top_tracks=top_tracks, google_maps_api_key=GOOGLE_MAPS_API_KEY)

if __name__ == "__main__":
    app.run(debug=True)
