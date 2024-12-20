import numpy
import pandas as pd
from geopy.geocoders import Nominatim
import openmeteo_requests
import requests_cache
from dash import Dash, dcc, html, Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from retry_requests import retry


def titles_generator(ln):
    return


# Функция для получения координат города
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


# Функция для получения данных о погоде
def get_weather_data(user_input: list[str], num_days: int) -> object:
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

    return weather_data, city_names, lats, longs


# Создание экземпляра Dash приложения
app = Dash(__name__)

app.layout = html.Div([
    html.H1("Прогноз погоды по маршруту"),

    dcc.Input(id='city-input', type='text', placeholder='Введите город'),

    html.Button('Добавить город', id='add-button', n_clicks=0),

    html.Div(id='cities-container', children=[]),

    dcc.Input(id='days-input', type='number', value=3, min=1, max=7),

    html.Button('Получить погоду', id='submit-button', n_clicks=0),

    dcc.Graph(id='weather-map'),

    dcc.Graph(id='weather-graphs'),

    # Добавление ConfirmDialog для ошибок
    dcc.ConfirmDialog(
        id='error-dialog',
        message='',  # Сообщение будет обновляться в зависимости от ошибки
        displayed=False  # По умолчанию не показывать диалог
    ),

])


@app.callback(
    [Output('cities-container', 'children'),
     Output('error-dialog', 'message'),
     Output('error-dialog', 'displayed')],
    Input('add-button', 'n_clicks'),
    State('city-input', 'value'),
    State('cities-container', 'children')
)
def add_city(n_clicks, city_input, children):
    if n_clicks > 0 and city_input:
        # Check for duplicates
        existing_cities = [child['props']['value'] for child in children if child['type'] == 'Input']

        if city_input in existing_cities:
            return children, f'Город "{city_input}" уже добавлен!', True

        new_city_input = dcc.Input(type='text', value=city_input, style={'margin': '5px'})
        children.append(new_city_input)

        return children, "", False

    return children, "", False


@app.callback(
    Output('weather-map', 'figure'),
    Output('weather-graphs', 'figure'),
    Input('submit-button', 'n_clicks'),
    State('cities-container', 'children'),
    State('days-input', 'value')
)
def update_output(n_clicks, cities_container, num_days):
    if n_clicks > 0 and cities_container:
        cities_list = [child['props']['value'].strip().title() for child in cities_container if
                       child['type'] == 'Input']
        weather_data, city_data, lats, longs = get_weather_data(cities_list, num_days)

        print(city_data)
        print(weather_data)

        # Создание карты погоды
        map_fig = px.scatter_geo(
            lat=lats,
            lon=longs,
            text=cities_list,
            title="Карта прогноза погоды",
            template="plotly"
        )

        # Добавление линии маршрута
        map_fig.add_trace(go.Scattergeo(
            lat=lats,
            lon=longs,
            mode='lines+text',
            line=dict(width=2, color='blue'),
            text= None,
            textposition="top center",
            name='Маршрут'
        ))

        # Формирование заголовков с названиями городов
        parameters = ["Wind Speed", "Humidity", "Temperature", "Precipitation Probability", "Cloud Cover"]

        # Формирование заголовков с названиями городов
        titles = []
        for param in parameters:
            for city in cities_list:
                titles.append(f"{param} - {city}")


        # Создание графиков
        fig = make_subplots(rows=5, cols=len(city_data), subplot_titles=titles, shared_xaxes=False)

        for i, city in enumerate(city_data):
            if city in weather_data and not weather_data[city].empty:
                print(f"Data for {city}: {weather_data[city]}")  # Отладочное сообщение
                fig.add_trace(go.Scatter(x=weather_data[city]['date'],
                                         y=weather_data[city]['wind_speed_10m'],
                                         mode='lines+markers',
                                         name='Wind Speed',
                                         line=dict(color='blue'),
                                         showlegend=False),
                              row=1,
                              col=i + 1)
                fig.add_trace(go.Scatter(x=weather_data[city]['date'],
                                         y=weather_data[city]['relative_humidity_2m'],
                                         mode='lines+markers', name=f'Humidity in {cities_list[i]}',
                                         line=dict(color='green'),
                                         showlegend=False),
                              row=2, col=i + 1)
                fig.add_trace(go.Scatter(x=weather_data[city]['date'],
                                         y=weather_data[city]['temperature_2m'],
                                         mode='lines+markers',
                                         name=f'Temperature in {cities_list[i]}',
                                         line=dict(color='red'),
                                         showlegend=False),
                              row=3, col=i + 1)
                fig.add_trace(
                    go.Scatter(x=weather_data[city]['date'],
                               y=weather_data[city]['precipitation_probability'],
                               mode='lines+markers',
                               name=f'Precipitation Probabilityin in {cities_list[i]}',
                               line=dict(color='orange'),
                               showlegend=False),
                            row=4, col=i + 1)
                fig.add_trace(
                    go.Scatter(x=weather_data[city]['date'],
                               y=weather_data[city]['cloud_cover'],
                               mode='lines+markers',
                               name=f'Cloud Cover in {cities_list[i]}',
                               line=dict(color='purple'),
                               showlegend=False),
                    row=5, col=i + 1)
            else:
                print(f"No data available for {city} or data is empty.")

        fig.update_layout(height=1500, width=1200,
                          title_text="Weather Parameters over Time",
                          xaxis_title="Time")

        return map_fig, fig

    return {}, {}


if __name__ == '__main__':
    app.run_server(debug=True)
