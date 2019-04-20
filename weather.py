# -*- encoding: utf-8 -*-
import requests
import datetime
import random
weekday_arr=("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")


class Weather:
    def __init__(self, config):
        self.fromtimestamp = datetime.datetime.fromtimestamp
        self.weather_api_base_url = "http://api.openweathermap.org/data/2.5"
        try:
            self.weather_api_key = config['secret']['openweathermap_api_key']
        except KeyError:
            self.weather_api_key = "XXXXXXXXXXXXXXXXXXXXX"
        try:
            self.default_city_name = config['secret']['default_city'].encode('utf8')
        except KeyError:
            self.default_city_name = "Berlin"
        try:
            self.units = config['global']['units']
        except KeyError:
            self.units = "metric"

    def parse_open_weather_map_forecast_response(self, response, location,date_requested):
        # Parse the output of Open Weather Map's forecast endpoint
        try:
            today_old = self.fromtimestamp(response["list"][0]["dt"]).day
            print(date_requested)
            today=int(date_requested.split("-")[2])
            time_difference=today-today_old
            #print("today=",self.fromtimestamp(response["list"][0]["dt"]).day)
            today_forecasts = list(
                filter(lambda forecast: self.fromtimestamp(forecast["dt"]).day == today, response["list"]))

            all_min = [x["main"]["temp_min"] for x in today_forecasts]
            all_max = [x["main"]["temp_max"] for x in today_forecasts]
            all_conditions = [x["weather"][0]["description"].encode('utf8') for x in today_forecasts]
            rain = list(filter(lambda forecast: forecast["weather"][0]["main"] == "Rain", today_forecasts))
            snow = list(filter(lambda forecast: forecast["weather"][0]["main"] == "Snow", today_forecasts))

            return {
                "rc": 0,
                "location": location,
                "inLocation": " in {0}".format(location) if location else "",
                "temperature": int(today_forecasts[0]["main"]["temp"]),
                "temperatureMin": int(min(all_min)),
                "temperatureMax": int(max(all_max)),
                "rain": len(rain) > 0,
                "snow": len(snow) > 0,
                "mainCondition": max(set(all_conditions), key=all_conditions.count).lower(),
                "time_difference":time_difference
            }
        except KeyError:  # error 404 (locality not found or api key is wrong)
            return {'rc': 2}
    
    def error_response(self, data):
        error_num = data['rc']
        if error_num == 1:
            response = random.choice(["Es ist leider kein Internet verfügbar.",
                                      "Ich bin nicht mit dem Internet verbunden.",
                                      "Es ist kein Internet vorhanden."])
            if 'location' in data.keys() and data['location'] == self.default_city_name:
                response = "Schau doch aus dem Fenster. " + response
        elif error_num == 2:
            response = random.choice(["Wetter konnte nicht abgerufen werden. Entweder gibt es den Ort nicht, oder der "
                                      "API-Schlüssel ist ungültig.",
                                      "Fehler beim Abrufen. Entweder gibt es den Ort nicht, oder der API-Schlüssel "
                                      "ist ungültig."])
        else:
            response = random.choice(["Es ist ein Fehler aufgetreten.", "Hier ist ein Fehler aufgetreten."])
        return response

    def get_weather_forecast(self, intentMessage):
        # Parse the query slots, and fetch the weather forecast from Open Weather Map's API
        locations = []
        date_requested=datetime.datetime.now().strftime("%Y-%m-%d") 
        if isinstance(intentMessage.slots,dict):
            for (slot_value, slot) in intentMessage.slots.items():
                if slot_value not in ['forecast_condition_name', 'forecast_start_date_time',
                                      'forecast_item', 'forecast_temperature_name']:
                    locations.append(slot[0].slot_value.value)
                elif slot_value == 'forecast_start_date_time':
                    print("anderes Datum")
                    date_requested=intentMessage.slots.forecast_start_date_time.first().value
                    date_requested=date_requested.split(' ')[0]#.split(" ")[0]
                    print(date_requested)
        location_objects = [loc_obj for loc_obj in locations if loc_obj is not None]
        if location_objects:
            location = location_objects[0].value.encode('utf8')
        else:
            location = self.default_city_name
        forecast_url = "{0}/forecast?q={1}&APPID={2}&units={3}&lang=de".format(
            self.weather_api_base_url, location, self.weather_api_key, self.units)
        try:
            r_forecast = requests.get(forecast_url)
            return self.parse_open_weather_map_forecast_response(r_forecast.json(), location,date_requested)
        except (requests.exceptions.ConnectionError, ValueError):
            return {'rc': 1}  # Error: No internet connection

    @staticmethod
    def add_warning_if_needed(response, weather_forecast):
        if weather_forecast["rain"] and "rain" not in weather_forecast["mainCondition"]\
                and "regen" not in weather_forecast["mainCondition"]:
            response += ' Es könnte regnen.'
        if weather_forecast["snow"] and "snow" not in weather_forecast["mainCondition"]:
            response += ' Es könnte schneien.'
        return response

    def forecast(self, intentMessage):
        """
                Complete answer:
                    - condition
                    - current temperature
                    - max and min temperature
                    - warning about rain or snow if needed
        """
        weather_forecast = self.get_weather_forecast(intentMessage)
        if weather_forecast['rc'] != 0:
            response = self.error_response(weather_forecast)
        else:
            if weather_forecast["time_difference"]==0:
                day_string="heute"
            elif weather_forecast["time_difference"]==1:
                day_string="morgen"
            else:
                temp_day=datetime.datetime.today().weekday()+weather_forecast["time_difference"]
                if temp_day > 13:
                    day_string=""
                elif temp_day > 6:
                    temp_day=temp_day-7
                    day_string="am " + weekday_arr[temp_day]
                
                elif temp_day > 1:
                    day_string="am " + weekday_arr[temp_day]
              
    
            response = ("Wetter {5} {1}: {0}. "
                        "Aktuelle Temperatur ist {2} Grad. "
                        "Höchsttemperatur: {3} Grad. "
                        "Tiefsttemperatur: {4} Grad.").format(
                weather_forecast["mainCondition"],
                weather_forecast["inLocation"],
                weather_forecast["temperature"],
                weather_forecast["temperatureMax"],
                weather_forecast["temperatureMin"],
                day_string
            )
            response = self.add_warning_if_needed(response, weather_forecast)
        response = response.decode('utf8')
        return response

    def forecast_condition(self, intentMessage):
        """
        Condition-focused answer:
            - condition
            - warning about rain or snow if needed
        """
        weather_forecast = self.get_weather_forecast(intentMessage)
        if weather_forecast['rc'] != 0:
            response = self.error_response(weather_forecast)
        else:
            response = "Wetter heute{1}: {0}.".format(
                weather_forecast["mainCondition"],
                weather_forecast["inLocation"]
            )
            response = self.add_warning_if_needed(response, weather_forecast)
        response = response.decode('utf8')
        return response

    def forecast_temperature(self, intentMessage):
        """
        Temperature-focused answer:
            - current temperature
            - max and min temperature
        """
        weather_forecast = self.get_weather_forecast(intentMessage)
        if weather_forecast['rc'] != 0:
            response = self.error_response(weather_forecast)
        else:
            response = ("{0} hat es aktuell {1} Grad. "
                        "Heute wird die Höchsttemperatur {2} Grad sein "
                        "und die Tiefsttemperatur {3} Grad.").format(
                weather_forecast["inLocation"],
                weather_forecast["temperature"],
                weather_forecast["temperatureMax"],
                weather_forecast["temperatureMin"])
        response = response.decode('utf8')
        return response
