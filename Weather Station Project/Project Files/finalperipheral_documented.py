import sys
from micropython import const
import uasyncio as asyncio
import aioble
import bluetooth
import struct
from bme680 import *
from machine import Pin, I2C

############################# CONFIGS FOR ALL INTERFACES #######################################
# I2C Configuration for BME680
i2c = I2C(0, scl=Pin(1), sda=Pin(0))
bme_sensor = BME680_I2C(i2c=i2c)
result_temp = 0


########### BLE CONFIGS FOR PERIPHERAL ########
_ENV_SENSE_UUID = bluetooth.UUID(0x181A)
_ENV_SENSE_TEMP_UUID = bluetooth.UUID(0x2A6E)
_ENV_SENSE_PRESSURE_UUID = bluetooth.UUID(0x2A6D)
_ENV_SENSE_HUMIDITY_UUID = bluetooth.UUID(0x2A6F)
_ADV_APPEARANCE_GENERIC_THERMOMETER = const(768)
# How frequently to send advertising beacons.
_ADV_INTERVAL_MS = 250_000
# Register service as GATT server.
temp_service = aioble.Service(_ENV_SENSE_UUID)

#### Defining UUIDS for all characterestics
"""
BLE has in built "OBSERVABLE DESIGN" properties.initialising the characterestics with "notify=True"
setsup this BLE PERIPHERAL to notify the PAIRED devices after each write to those 
characterestics

"""
aggr_temp_characteristic = aioble.Characteristic(
    temp_service, bluetooth.UUID(0x2A1C), read=True, notify=True
)


aggr_pressure_characteristic = aioble.Characteristic(
    temp_service, bluetooth.UUID(0x2A20), read=True, notify=True
)


aggr_humidity_characteristic = aioble.Characteristic(
    temp_service, bluetooth.UUID(0x2A24), read=True, notify=True
)

last_10_pres_timeseries_characteristic = aioble.Characteristic(
    temp_service, bluetooth.UUID(0x2A25), read=True, notify=True
)
last_10_hum_timeseries_characteristic = aioble.Characteristic(
    temp_service, bluetooth.UUID(0x2A26), read=True, notify=True
)

last_10_temp_timeseries_characteristic = aioble.Characteristic(
    temp_service, bluetooth.UUID(0x2A27), read=True, notify=True

)

#register the service
aioble.register_services(temp_service)
############################# CONFIGS FOR ALL INTERFACES END#######################################

######################## VARIABLES FOR STORING PROCESSING RESULTS ###################
temperature_values = []
pressure_values = []
humidity_values = []

avg_temperature = 0
min_temperature = float('inf')  # Initialize to positive infinity
max_temperature = float('-inf')  # Initialize to negative infinity

avg_pressure = 0
min_pressure = float('inf')
max_pressure = float('-inf')

avg_humidity = 0
min_humidity = float('inf')
max_humidity = float('-inf')
######################## VARIABLES FOR STORING PROCESSING RESULTS END###################

################################## ENCODING UTILS ##################################
def _encode_temperature(temp_deg_c):
    return struct.pack("<h", int(temp_deg_c * 100))  # Encode temperature with two decimal places

def _encode_pressure(pressure):
    return struct.pack("<h", int(pressure * 10))  # Encode pressure with two decimal places

def _encode_humidity(humidity):
    return struct.pack("<H", int(humidity * 100))  # Encode humidity with two decimal places

################################## ENCODING UTILS END##################################

############################# SENSOR TASK FOR COLLECTING THE SENSOR STATS #################
async def sensor_task():
    # global stats.Declare the variables as global
    global temperature_values, pressure_values, humidity_values  # Declare the variable as global
    global avg_temperature, min_temperature, max_temperature
    global avg_pressure, min_pressure, max_pressure
    global avg_humidity, min_humidity, max_humidity
    while True:
        try:
            p = bme_sensor.pressure
            h = bme_sensor.humidity

            t = bme_sensor.temperature

            # Print sensor values for debugging
            print("Temperature:", t)
            print("Pressure:", p)
            print("Humidity:", h)

            # Update statistics
            temperature_values.append(t)
            if len(temperature_values) > 10:
                temperature_values = temperature_values[-10:]

            avg_temperature = sum(temperature_values) / len(temperature_values)
            min_temperature = min(min_temperature, t)
            max_temperature = max(max_temperature, t)

            pressure_values.append(p)
            if len(pressure_values) > 10:
                pressure_values = pressure_values[-10:]

            avg_pressure = sum(pressure_values) / len(pressure_values)
            min_pressure = min(min_pressure, p)
            max_pressure = max(max_pressure, p)

            humidity_values.append(h)
            if len(humidity_values) > 10:
                humidity_values = humidity_values[-10:]

            avg_humidity = sum(humidity_values) / len(humidity_values)
            min_humidity = min(min_humidity, h)
            max_humidity = max(max_humidity, h)

            # Print calculated values for debugging
            print("Average Temperature:", avg_temperature)
            print("Min Temperature:", min_temperature)
            print("Max Temperature:", max_temperature)
            print("Average Pressure:", avg_pressure)
            print("Min Pressure:", min_pressure)
            print("Max Pressure:", max_pressure)
            print("Average Humidity:", avg_humidity)
            print("Min Humidity:", min_humidity)
            print("Max Humidity:", max_humidity)

            # Write all the stats to respective characteristics
            aggr_temp_characteristic.write(
                _encode_temperature(avg_temperature) + _encode_temperature(min_temperature) + _encode_temperature(
                    max_temperature))

            aggr_pressure_characteristic.write(
                _encode_pressure(avg_pressure) + _encode_pressure(min_pressure) + _encode_pressure(max_pressure))

            aggr_humidity_characteristic.write(
                _encode_humidity(avg_humidity) + _encode_humidity(min_humidity) + _encode_humidity(max_humidity))

            last_10_temp_timeseries_characteristic.write(struct.pack("<10H", *map(lambda x: int(x * 100), temperature_values)))
            last_10_hum_timeseries_characteristic.write(struct.pack("<10H", *map(lambda x: int(x * 100), humidity_values)))
            last_10_pres_timeseries_characteristic.write(struct.pack("<10H", *map(lambda x: int(x * 10), pressure_values)))
            #Write to characterestics end

            await asyncio.sleep_ms(1000)

        except Exception as e:
            print("Exception in sensor_task:", e)

############################# SENSOR TASK FOR COLLECTING THE SENSOR STATS END#################
# Serially wait for connections. no advertising while central pico is connected.
async def peripheral_task():
    while True:
        try:
            async with await aioble.advertise(
                    _ADV_INTERVAL_MS,
                    name="ble-sensor",
                    services=[_ENV_SENSE_UUID],
                    appearance=_ADV_APPEARANCE_GENERIC_THERMOMETER,
            ) as connection:
                print("Connection from", connection.device)
                while connection.is_connected():
                    await asyncio.sleep_ms(500)
                print("Disconnected")

        except Exception as e:
            print("Exception in peripheral_task:", e)


# Run both sensor and peripheral tasks.
async def main():
    t1 = asyncio.create_task(sensor_task())
    t2 = asyncio.create_task(peripheral_task())
    await asyncio.gather(t1, t2)


asyncio.run(main())


