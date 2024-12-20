import numpy
import pandas as pd
from geopy.geocoders import Nominatim
import openmeteo_requests
import requests_cache
from dash import Dash, dcc, html, Input, Output
import plotly.express as px
from retry_requests import retry


# Function gets city coordinates from user input ("City" or "City, Country")
def get_coordinates(city_name: str) -> dict:
    try:
        geolocator = Nominatim(user_agent='myapplication')
        location = geolocator.geocode(city_name)
        if location is not None:
            return {
                'coordinates': (location.latitude, location.longitude),
                'display_name': location.address
            }
        else:
            return {'coordinates': None, 'Message': f'Location not found for {city_name}'}
    except Exception as e:
        return {'coordinates': None, 'Message': f'Error while acquiring {city_name} coordinates: {str(e)}'}


user_input = ['Moscow, US', 'Moscow, Russia', 'SFLK;LKS;FDLKFSD', 'LA, US', 'NYC']


def get_weather_data(user_input: list[str], num_days: int):
    city_data = dict()

    lats = []
    longs = []
    city_names = []

    for city in user_input:
        city_data[city] = get_coordinates(city)
        if city_data[city]['coordinates'] is not None:
            lats.append(city_data[city]['coordinates'][0])
            longs.append(city_data[city]['coordinates'][1])
            city_names.append(city_data[city]['display_name'])
        else:
            print(city_data[city]['Message'])
            lats.append(0)
            longs.append(0)
            city_names.append('Location not found')

    cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    openmeteo = openmeteo_requests.Client(session=retry_session)

    # Make sure all required weather variables are listed here
    # The order of variables in hourly or daily is important to assign them correctly below
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lats,
        "longitude": longs,
        "hourly": ["temperature_2m", "relative_humidity_2m", "precipitation_probability",
                   "cloud_cover", "wind_speed_10m"],
        "timezone": "auto",
        "forecast_days": num_days
    }
    responses = openmeteo.weather_api(url, params=params)

    weather_data = dict()

    # Process first location. Add a for-loop for multiple locations or weather models
    for c_n in range(len(lats)):
        response = responses[c_n]
        city_name = city_names[c_n]
        # print(city_name)
        # print(f"Coordinates {response.Latitude()}°N {response.Longitude()}°E")

        # Process hourly data. The order of variables needs to be the same as requested.
        if city_name != "Location not found":
            hourly = response.Hourly()
            hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()
            hourly_relative_humidity_2m = hourly.Variables(1).ValuesAsNumpy()
            hourly_precipitation_probability = hourly.Variables(2).ValuesAsNumpy()
            hourly_cloud_cover = hourly.Variables(3).ValuesAsNumpy()
            hourly_wind_speed_10m = hourly.Variables(4).ValuesAsNumpy()
        else:
            hourly_temperature_2m = numpy.nan
            hourly_relative_humidity_2m = numpy.nan
            hourly_precipitation_probability = numpy.nan
            hourly_cloud_cover = numpy.nan
            hourly_wind_speed_10m = numpy.nan

        hourly_data = {"date": pd.date_range(
            start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
            end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=hourly.Interval()),
            inclusive="left"
        ), "temperature_2m": hourly_temperature_2m, "relative_humidity_2m": hourly_relative_humidity_2m,
            "precipitation_probability": hourly_precipitation_probability, "cloud_cover": hourly_cloud_cover,
            "wind_speed_10m": hourly_wind_speed_10m}
        hourly_dataframe = pd.DataFrame(data=hourly_data)

        weather_data[city_name] = hourly_dataframe

    return weather_data, city_names


weather_data, city_names = get_weather_data(user_input=user_input, num_days=3)

print(city_names[1])


