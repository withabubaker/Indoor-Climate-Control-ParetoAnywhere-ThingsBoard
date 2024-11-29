import time
import paho.mqtt.client as mqtt
import json
from rpi_lcd import LCD
from datetime import date
import requests
import os

lcd = LCD()
switch_status = False
fan_status = 'false'
MQTT_Broker ='thingsboard.cloud'
S1_ACCESS_TOKEN = os.getenv('S1_ACCESS_TOKEN') 
Fan_ACCESS_TOKEN= os.getenv('Fan_ACCESS_TOKEN')
url = "http://192.168.2.13:3001/devices/ac233fa4d282/2"


#Callback function to control the fan from Thingsboard dashboard
def on_message(client, userdata, message): 
    global switch_status
    try:
        payload = json.loads(message.payload.decode())
        print("Received control message:", payload)
    
        if "method" in payload and payload["method"] == 'Setswitch':
            switch_status = payload["params"]
            print(f"Switch status updated to: {switch_status}")

            # turn on/off the fan
            os.system("irsend SEND_ONCE Fan1-Remote KEY_POWER")
            print("The fan controlled from the dashboard")

            response_topic = message.topic.replace('request', 'response')
            client.publish(response_topic, json.dumps({"result": "success"}))
            telemetry_topic = "v1/devices/me/attributes"
            client.publish(telemetry_topic, json.dumps({"Setswitch": switch_status}))
    except Exception as e:
        print("An error occurred:", e)


#control the switch button on Thingsboard from python code
def toggle_switch(client, new_status):
    global fan_status 
    try:
        fan_status = new_status
        print(f"Toggling switch to: {fan_status}")
        
        # Publish the updated status to the dashboard
        telemetry_topic = "v1/devices/me/attributes"
        client.publish(telemetry_topic, json.dumps({"Setswitch": fan_status}))
        print("Switch status updated on dashboard.")
    except Exception as e:
        print("An error occurred while toggling the switch:", e)

   
def get_data(url):
    try:
        today = date.today()
        response = requests.get(url)
        data = response.json()
        device_data = data.get('devices',{})
        temperature = device_data['ac233fa4d282/2']['dynamb'].get('temperature')
        humidity = device_data['ac233fa4d282/2']['dynamb'].get("relativeHumidity")

        payload = {

                "temperature": temperature,
                "humidity": humidity
        }

        return round(humidity,2), round(temperature,2), today, payload
    except requests.exceptions.RequestException as e:
        print("Error getting the data: ", e)
    except Exception as e:
        print("An error occured: ", e)
        return None, None, None, None


#send data to LCD screen
def lcd_display(temp, hum, today): 
    lcd.text(f"{today}", 1)
    lcd.text("T:"f"{temp} H:"f"{hum}",2)


#send data to thingsboard dashbaord
def update_temp_Hum_dashboard(client,payload): 
    try:
        if payload is None:
            print("No payload to send")
            return

        topic = "v1/devices/me/telemetry"
        client.publish(topic, json.dumps(payload))
        print("Data sent to ThingBoard:", payload)

    except Exception as e:
        print("An error occurred:", e)


def main():
    global switch_status
    global fan_status
    try:
        client_fan = mqtt.Client()
        client_fan.username_pw_set(Fan_ACCESS_TOKEN)
        client_fan.on_message = on_message
        client_fan.connect(MQTT_Broker, 1883, keepalive=60)
        client_fan.subscribe("v1/devices/me/rpc/request/+")
        client_fan.loop_start()

        client_S1 = mqtt.Client()
        client_S1.username_pw_set(S1_ACCESS_TOKEN)
        client_S1.connect(MQTT_Broker, 1883, keepalive=60)
        client_S1.loop_start()

        while True:

            humidity, temperature, today, payload = get_data(url)
            update_temp_Hum_dashboard(client_S1,payload)
            if temperature is not None and humidity is not None:
                lcd_display(temperature, humidity, today)
                if temperature >= 22 and (fan_status == 'false' or switch_status == False):
                    fan_status = 'true'
                    switch_status = True
                    os.system("irsend SEND_ONCE Fan1-Remote KEY_POWER")
                    toggle_switch(client_fan, fan_status)
                    print('The Fan Turned ON')
                elif temperature < 22 and (fan_status == 'true' or switch_status == True):
                    fan_status = 'false'
                    switch_status = False
                    os.system("irsend SEND_ONCE Fan1-Remote KEY_POWER")
                    toggle_switch(client_fan, fan_status)
                    print('The Fan Turned OFF')

                else:
                    # Error case: No change in fan status
                    print('Error detected. The fan status remains unchanged.')

                time.sleep(10)
            else: 
                time.sleep(30)

    except KeyboardInterrupt:
        print("User interupted")
        
    except Exception as e:
        print("An unexpected error occured:", e)

    finally:
        client_fan.loop_stop()
        client_fan.disconnect()
        client_S1.loop_stop()
        client_S1.disconnect()
        lcd.clear()


if __name__ == "__main__":
    main()

      

