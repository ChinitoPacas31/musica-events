"""
MASHUP MUSICAL 

APIs integradas para mostrar:
- Conciertos de artistas (Ticketmaster)
- Datos del artista y playlists (Spotify)
- Clima en ciudades de conciertos (OpenWeather)
- Geocodificación (Google Maps)

Estructura:
- Servicios separados por funcionalidad (ConcertService, WeatherService, etc.)
- Ruta principal que orquesta la integración de datos
- Manejo de errores en cada llamada API
"""

import requests  
import os
from flask import Flask, render_template, request
from dotenv import load_dotenv
import random
import googlemaps  

# ======================
# CONFIGURACIÓN INICIAL
# ======================

# Carga variables de entorno desde archivo .env (para API keys)
load_dotenv(override=True)

# Inicializa la aplicación Flask
app = Flask(__name__)

# ======================
# CONSTANTES Y CLIENTES
# ======================

# Todas las API keys se cargan desde variables de entorno por seguridad
TICKETMASTER_API_KEY = os.getenv("TICKETMASTER_API_KEY")  # Key para Ticketmaster API
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")    # Key para OpenWeather API
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")       # Credenciales para Spotify API
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")   # Key para Google Maps API

MAX_RESULTS = 9  # Límite máximo de conciertos a mostrar en los resultados

# Cliente de Google Maps para geocodificación
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

# ======================
# SERVICIO DE CONCIERTOS
# ======================
class ConcertService:
    """Encapsula toda la lógica relacionada con la obtención de datos de conciertos"""
    
    @staticmethod
    def get_events(artist_name):
        """
        Obtiene eventos musicales de Ticketmaster para un artista específico.
        
        Args:
            artist_name (str): Nombre del artista a buscar
            
        Returns:
            list: Lista de eventos (puede estar vacía si hay error o no hay resultados)
            
        Proceso:
            1. Prepara los parámetros de búsqueda (filtra por música y ordena por fecha)
            2. Hace la petición a Ticketmaster API con timeout de 10 segundos
            3. Procesa la respuesta extrayendo los eventos del campo _embedded
            4. Maneja errores de conexión o respuestas inválidas
        """
        try:
            # Parámetros para la API de Ticketmaster
            params = {
                "apikey": TICKETMASTER_API_KEY,
                "keyword": artist_name,
                "size": MAX_RESULTS,
                "classificationName": "Music",  # Solo eventos musicales
                "sort": "date,asc"  # Ordena por fecha (más cercanos primero)
            }
            
            # Petición GET con manejo de timeout
            response = requests.get(
                "https://app.ticketmaster.com/discovery/v2/events.json",
                params=params,
                timeout=10
            )
            response.raise_for_status()  
            
            # Extrae eventos del campo _embedded (o lista vacía si no existe)
            return response.json().get("_embedded", {}).get("events", [])
            
        except requests.exceptions.RequestException as e:
            # Registra error en logs y devuelve lista vacía (degradación elegante)
            app.logger.error(f"Error Ticketmaster: {str(e)}")
            return []

# ======================
# SERVICIO DEL CLIMA
# ======================
class WeatherService:
    """Maneja la obtención de datos climáticos para ciudades específicas"""
    
    @staticmethod
    def get_weather(city):
        """
        Obtiene condiciones climáticas actuales para una ciudad.
        
        Args:
            city (str): Nombre de la ciudad a consultar
            
        Returns:
            dict: Diccionario con descripción del clima y temperatura
                  Ej: {"description": "Cielo despejado", "temperature": 22.5}
                  Devuelve valores por defecto si hay error o ciudad inválida
        """
        # Validación para ciudad vacía o desconocida
        if not city or city == "Ciudad desconocida":
            return {"description": "Ciudad no especificada", "temperature": "N/A"}

        # Construye URL para OpenWeather API 
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=es"
        
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            clima_data = response.json()

            # Formatea los datos para la vista
            return {
                "description": clima_data["weather"][0]["description"].capitalize(),
                "temperature": round(clima_data["main"]["temp"], 1)  # 1 decimal
            }
        except requests.exceptions.RequestException as e:
            app.logger.error(f"Error OpenWeather: {str(e)}")
            return {"description": "Datos no disponibles", "temperature": "N/A"}

# ======================
# SERVICIO DE SPOTIFY
# ======================
class SpotifyService:
    """Maneja todas las interacciones con la API de Spotify"""
    
    @staticmethod
    def get_artist_info(artist_name):
        """
        Busca información básica de un artista en Spotify.
        
        Args:
            artist_name (str): Nombre del artista a buscar
            
        Returns:
            dict/None: Información del artista o None si hay error/no existe
            
        Proceso:
            1. Obtiene token de acceso (autenticación OAuth)
            2. Busca artistas coincidentes
            3. Devuelve el primer resultado (si existe)
        """
        try:
            # Paso 1: Obtener token de acceso (Client Credentials Flow)
            auth_response = requests.post(
                "https://accounts.spotify.com/api/token",
                data={"grant_type": "client_credentials"},
                auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
            )
            auth_response.raise_for_status()
            access_token = auth_response.json().get("access_token")
            
            # Paso 2: Buscar artista
            headers = {"Authorization": f"Bearer {access_token}"}
            search_url = "https://api.spotify.com/v1/search"
            params = {"q": artist_name, "type": "artist", "limit": 1}
            
            response = requests.get(search_url, headers=headers, params=params)
            response.raise_for_status()
            artists = response.json().get("artists", {}).get("items", [])
            
            # Devuelve el primer artista o None
            return artists[0] if artists else None
            
        except requests.exceptions.RequestException as e:
            app.logger.error(f"Error Spotify: {str(e)}")
            return None

    @staticmethod
    def get_top_tracks(artist_id):
        """
        Obtiene las canciones más populares de un artista en Spotify.
        
        Args:
            artist_id (str): ID único del artista en Spotify
            
        Returns:
            list: Canciones populares (vacía si hay error)
        """
        try:
            # Obtener token 
            auth_response = requests.post(
                "https://accounts.spotify.com/api/token",
                data={"grant_type": "client_credentials"},
                auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
            )
            auth_response.raise_for_status()
            access_token = auth_response.json().get("access_token")

            # Consultar top tracks para mercado de EE.UU.
            headers = {"Authorization": f"Bearer {access_token}"}
            top_tracks_url = f"https://api.spotify.com/v1/artists/{artist_id}/top-tracks?market=US"

            response = requests.get(top_tracks_url, headers=headers)
            response.raise_for_status()
            return response.json().get("tracks", [])
            
        except requests.exceptions.RequestException as e:
            app.logger.error(f"Error Spotify obtaining top tracks: {str(e)}")
            return []

    @staticmethod
    def get_playlists_by_genre(genre):
        """
        Busca playlists relacionadas con un género musical.
        
        Args:
            genre (str): Género musical (ej: "rock", "pop")
            
        Returns:
            list: Playlists encontradas (vacía si hay error)
        """
        try:
            # Obtener token (similar a métodos anteriores)
            auth_response = requests.post(
                "https://accounts.spotify.com/api/token",
                data={"grant_type": "client_credentials"},
                auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
            )
            auth_response.raise_for_status()
            access_token = auth_response.json().get("access_token")

            # Buscar playlists por género
            headers = {"Authorization": f"Bearer {access_token}"}
            search_url = f"https://api.spotify.com/v1/search?q={genre}&type=playlist&limit=10"

            response = requests.get(search_url, headers=headers)
            response.raise_for_status()
            return response.json().get("playlists", {}).get("items", [])
            
        except requests.exceptions.RequestException as e:
            app.logger.error(f"Error Spotify obtaining recommended playlists: {str(e)}")
            return []

# ======================
# RUTA PRINCIPAL
# ======================
@app.route("/", methods=["GET", "POST"])
def index():
    """
    Ruta principal que maneja:
    - GET: Muestra formulario de búsqueda
    - POST: Procesa búsqueda y muestra resultados
    
    Flujo para POST:
    1. Obtener artista del formulario
    2. Consultar Spotify (info, top canciones)
    3. Consultar Ticketmaster (conciertos)
    4. Para cada concierto:
       - Obtener clima de la ciudad
       - Geocodificar ciudad para mapa
    5. Renderizar plantilla con todos los datos
    """
    # Valores iniciales
    artist_name = ""
    artist_info = None
    top_tracks = []
    events_with_playlists = []
    
    if request.method == "POST":
        # Paso 1: Obtener artista del formulario
        artist_name = request.form.get("artista", "").strip()

        # Validación básica
        if not artist_name:
            return render_template("index.html", error="Please write an artist")
        
        # Paso 2: Obtener información del artista desde Spotify
        artist_info = SpotifyService.get_artist_info(artist_name)
        
        if artist_info:
            # Paso 3: Obtener canciones populares si existe el artista
            artist_id = artist_info["id"]
            top_tracks = SpotifyService.get_top_tracks(artist_id)
            
            # Paso 4: Obtener playlists por género (primer género disponible)
            artist_genres = artist_info.get("genres", [])
            if artist_genres:
                genre = artist_genres[0]
                playlists = SpotifyService.get_playlists_by_genre(genre)
                if playlists:
                    # Selecciona playlist aleatoria para recomendación
                    random_playlist = random.choice(playlists)
                    artist_info["playlist"] = random_playlist
        
        # Paso 5: Obtener conciertos del artista
        events = ConcertService.get_events(artist_name)
        
        if not events:
            return render_template("index.html", 
                                 error=f"No concert found for {artist_name}",
                                 artist_name=artist_name,
                                 artist_info=artist_info,
                                 top_tracks=top_tracks,
                                 google_maps_api_key=GOOGLE_MAPS_API_KEY)
        
        # Paso 6: Procesar cada evento (clima + geocodificación)
        for event in events:
            venue = event.get("_embedded", {}).get("venues", [{}])[0]
            city = venue.get("city", {}).get("name", "Ciudad desconocida")
            
            # Geocodificación con Google Maps
            geocode_result = gmaps.geocode(city)
            lat, lng = None, None
            if geocode_result:
                location = geocode_result[0]['geometry']['location']
                lat, lng = location['lat'], location['lng']

            # Obtener clima para la ciudad
            weather_data = WeatherService.get_weather(city)

            # Estructura de datos para la plantilla
            event_data = {
                "city": city,
                "date": event.get("dates", {}).get("start", {}).get("localDate", "Fecha no disponible"),
                "venue": venue.get("name", "Lugar no disponible"),
                "tickets_url": event.get("url", "#"),
                "weather": weather_data,
                "location": {"lat": lat, "lng": lng},
                "playlist": artist_info.get("playlist", {}) if artist_info else {}
            }
            events_with_playlists.append(event_data)

        # Renderizar con todos los datos
        return render_template("index.html", 
                             events=events_with_playlists,
                             artist_name=artist_name,
                             artist_info=artist_info,
                             top_tracks=top_tracks,
                             google_maps_api_key=GOOGLE_MAPS_API_KEY)
    
    # GET: Mostrar formulario vacío
    return render_template("index.html", 
                         artist_name=artist_name,
                         artist_info=artist_info,
                         top_tracks=top_tracks,
                         google_maps_api_key=GOOGLE_MAPS_API_KEY)

# ======================
# INICIO DE LA APLICACIÓN
# ======================
if __name__ == "__main__":
    # Modo debug para desarrollo (auto-recarga y mensajes detallados)
    app.run(debug=True)