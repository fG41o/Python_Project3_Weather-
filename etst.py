from flask import Flask, render_template, request
import requests

app = Flask(__name__)


# Function to get location key from AccuWeather API from user input
def get_location_key(city: str) -> int:
    api_key = '4nyShYGdfmuAcVsHg2CuyxYbvXDmMFNW'
    url = f'http://dataservice.accuweather.com/locations/v1/cities/search?apikey={api_key}&q={city}'

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad responses (4xx or 5xx)

        data = response.json()
        if data:
            return [data[0]['Key']]  # Return the first location key
        else:
            error_message = "No data found for the specified city."
            print(error_message)
            return [None, error_message]
    except requests.exceptions.HTTPError as http_err:
        error_message = f"HTTP error occurred: {http_err}"
        print(error_message)  # Print HTTP error
    except requests.exceptions.RequestException as req_err:
        error_message = f"Request error occurred: {req_err}"
        print(error_message)  # Print general request error
    except Exception as e:
        error_message = f"An error occurred: {e}"
        print(error_message)  # Print any other exception
    return [None, error_message]


# Function to get weather data from AccuWeather API using location key
def get_weather(location_key: int) -> dict[str]:
    api_key = '4nyShYGdfmuAcVsHg2CuyxYbvXDmMFNW'
    url = f'http://dataservice.accuweather.com/currentconditions/v1/{location_key}?apikey={api_key}&language=en-us' \
          f'&details=true&units=metric'

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad responses (4xx or 5xx)

        data = response.json()
        if data:
            weather_info = {
                'temperature': data[0]['Temperature']['Metric']['Value'],  # Temperature in Celsius
                'humidity': data[0]['RelativeHumidity'],  # Humidity percentage
                'wind_speed': data[0]['Wind']['Speed']['Metric']['Value'],  # Wind speed in m/s
                'weather_text': data[0]['WeatherText'],  # Weather description
                'precipitation_value': data[0].get('PrecipitationSummary', {}).get('Precipitation', {}).get('Metric',
                                                                                                            {}).get(
                    'Value', 0)  # Precipitation value in mm
            }
            return [weather_info]
        else:
            error_message = "No weather data found."
            print(error_message)
            return [None, error_message]
    except requests.exceptions.HTTPError as http_err:
        error_message = f"HTTP error occurred: {http_err}"
        print(error_message)  # Print HTTP error
    except requests.exceptions.RequestException as req_err:
        error_message = f"Request error occurred: {req_err}"
        print(error_message)  # Print general request error
    except Exception as e:
        error_message = f"An error occurred: {e}"
        print(error_message)  # Print any other exception
    return [None, error_message]


# function for deciding if weather is good
def check_bad_weather(weather_data: dict[str]) -> bool:
    go_away = False  # False if weather is good, True, if weather is bad
    if weather_data['temperature'] > 35 or weather_data['temperature'] < 0 or weather_data['wind_speed'] > 50 or \
            weather_data['precipitation_value'] > 2:
        go_away = True
    return go_away


# Route for the main page with the form
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        start_city = request.form['start_city']
        end_city = request.form['end_city']

        # Get location keys for both cities
        start_location_key = get_location_key(start_city)
        end_location_key = get_location_key(end_city)

        if start_location_key[0] and end_location_key[0]:
            # Get weather data for both cities
            start_weather = get_weather(start_location_key)
            end_weather = get_weather(end_location_key)

            if start_weather[0] and end_weather[0]:
                # See if the weather is suitable
                goaway = check_bad_weather(start_weather) or check_bad_weather(end_weather)
                return render_template('results.html',
                                       start_city=start_city,
                                       end_city=end_city,
                                       start_weather=start_weather,
                                       end_weather=end_weather,
                                       flag=goaway)
            else:
                if start_weather[0] is None:
                    error_message = start_weather[1]
                else:
                    error_message = end_weather[1]
                return render_template('index.html', error=error_message)
        else:
            if start_location_key[0] is None:
                error_message = start_location_key[1]
            else:
                error_message = end_location_key[1]
            return render_template('index.html', error=error_message)

    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True)
