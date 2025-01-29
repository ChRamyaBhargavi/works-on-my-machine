import machine
from machine import Pin, I2C
from bme680 import BME680_I2C
import struct
import aioble
import bluetooth
import uasyncio as asyncio
############################# CONFIGS FOR ALL INTERFACES #######################################
# config for i2c interface with BME680 sensor
i2c = I2C(0, scl=Pin(1), sda=Pin(0))
bme_sensor = BME680_I2C(i2c=i2c)

#config for uart-serial interface
uart = machine.UART(1, baudrate=115000, tx=4, rx=5)

# BLE config for the sensor service
_ENV_SENSE_UUID = bluetooth.UUID(0x181A)
#BLE time series charactersetics
_ENV_SENSE_TEMP_UUID = bluetooth.UUID(0x2A27)
_ENV_SENSE_PRES_UUID = bluetooth.UUID(0x2A25)
_ENV_SENSE_HUM_UUID = bluetooth.UUID(0x2A26)
#BLE aggregation characterestics
_ENV_SENSE_PRES_AGGR_UUID = bluetooth.UUID(0x2A20)
_ENV_SENSE_TEMP_AGGR_UUID = bluetooth.UUID(0x2A1C)
_ENV_SENSE_HUM_AGGR_UUID = bluetooth.UUID(0x2A24)
######################### CONFIGS FOR ALL INTERFACES END #######################################


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
#packed values(binary encoded values) to send over the custom protocol
pres_aggr_packed = b''
temp_aggr_packed = b''
hum_aggr_packed = b''
time_series_packed = b''
######################### VARIABLES FOR STORING PROCESSING RESULTS END ###################

################################## ENCODING UTILS ##################################
def _encode_temperature(temp_deg_c):
    return struct.pack("<H", int(temp_deg_c * 100))  # Encode temperature with two decimal places


# Helper to encode the pressure and humidity values
def _encode_pressure(pressure):
    return struct.pack("<H", int(pressure * 100))  # Encode pressure with two decimal places


def _encode_humidity(humidity):
    return struct.pack("<H", int(humidity * 100))  # Encode humidity with two decimal places
################################## ENCODING UTILS END ##################################

############################# SENSOR TASK FOR COLLECTING THE SENSOR STATS #################
async def sensor_task():
    # global temperature_values  # Declare the variable as global
    global temperature_values, pressure_values, humidity_values  # Declare the variable as global
    global avg_temperature, min_temperature, max_temperature
    global avg_pressure, min_pressure, max_pressure
    global avg_humidity, min_humidity, max_humidity
    global hum_aggr_packed, pres_aggr_packed, temp_aggr_packed, time_series_packed
    while True:
        try:
            # Simulate pressure and humidity for testing
            p = bme_sensor.pressure
            h = bme_sensor.humidity

            t = bme_sensor.temperature

            # Print sensor values for debugging
            print("Temperature:", t)
            print("Pressure:", p)
            print("Humidity:", h)

            # Update statistics
            temperature_values.append(t)
            print("reached Values.appent")
            if len(temperature_values) > 10:
                temperature_values = temperature_values[-10:]

            avg_temperature = sum(temperature_values) / len(temperature_values)
            min_temperature = min(min_temperature, t)
            print("reached avg min max")
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

            print("Average Temperature:", avg_temperature)
            print("Min Temperature:", min_temperature)
            print("Max Temperature:", max_temperature)
            print("Average Pressure:", avg_pressure)
            print("Min Pressure:", min_pressure)
            print("Max Pressure:", max_pressure)
            print("Average Humidity:", avg_humidity)
            print("Min Humidity:", min_humidity)
            print("Max Humidity:", max_humidity)

            hum_aggr_packed = _encode_humidity(avg_humidity) + _encode_humidity(min_humidity) + _encode_humidity(
                max_humidity)
            pres_aggr_packed = _encode_pressure(avg_pressure) + _encode_pressure(min_pressure) + _encode_pressure(
                max_pressure)
            temp_aggr_packed = _encode_temperature(avg_temperature) + _encode_temperature(
                min_temperature) + _encode_temperature(max_temperature)
            time_series_packed = struct.pack("<10H", *map(lambda x: int(x * 100), humidity_values)) + struct.pack(
                "<10H", *map(lambda x: int(x * 100), temperature_values)) + struct.pack("<10H",
                                                                                        *map(lambda x: int(x * 10),
                                                                                             pressure_values))
            await asyncio.sleep(0.1)
        except Exception as e:
            print("Exception in sensor_task:", e)

############################# SENSOR TASK FOR COLLECTING THE SENSOR STATS END #################

##################################### BLE  FUNCTIONS ###################################

#find BLE device
async def find_temp_sensor():
    async with aioble.scan(5000, interval_us=30000, window_us=30000, active=True) as scanner:
        async for result in scanner:
            if result.name() == "ble-sensor" and _ENV_SENSE_UUID in result.services():
                return result.device
    return None

#connect to the characterestic and fetch the result based on command id of service
async def connect_ble(characteristic_command):
    device = await find_temp_sensor()
    connection = await device.connect()
    result = []
    async with connection:
        try:
            temp_service = await connection.service(_ENV_SENSE_UUID)
            if characteristic_command == 0x05:

                temp_characteristic = await temp_service.characteristic(_ENV_SENSE_TEMP_UUID)
                pres_chracterestic = await temp_service.characteristic(_ENV_SENSE_PRES_UUID)
                hum_characterestic = await temp_service.characteristic(_ENV_SENSE_HUM_UUID)
                print("Service and characteristic found")
                result_temp = await temp_characteristic.read()
                result_pres = await pres_chracterestic.read()
                result_hum = await hum_characterestic.read()

                # length_result_temp = len(result_temp)
                result = result_hum + result_temp + result_pres

                print("packed:", result)
                print("unpacked :", list(struct.unpack("<30H", result)))
            elif characteristic_command == 0x02:  # aggr_hum
                aggr_characterestic = await temp_service.characteristic(_ENV_SENSE_HUM_AGGR_UUID)
                result = await aggr_characterestic.read()

            elif characteristic_command == 0x03:  # press_aggr
                aggr_characterestic = await temp_service.characteristic(_ENV_SENSE_PRES_AGGR_UUID)
                result = await aggr_characterestic.read()

            elif characteristic_command == 0x04:  # temp_aggr
                aggr_characterestic = await temp_service.characteristic(_ENV_SENSE_TEMP_AGGR_UUID)
                result = await aggr_characterestic.read()

        except asyncio.TimeoutError:
            print("Timeout discovering services/characteristics")
            return

        return result
################################### BLE  FUNCTIONS END ###################################



############################### ADAPTER FUNCTION ############################################

# Takes in the custom protocol ids and returns the result. this abstarcts the caller from
#the communication interface of the sensor
async def sensor_operation(device_id, device_type_id, operation_id, command_id, param_arr, temp_characteristic):
    global hum_aggr_packed, pres_aggr_packed, temp_aggr_packed
    response_payload = b''
    result = b''

    if command_id == 0x05:
        nresults = 0x1e
        unit_id = 0x02
        error_id = 0x00
        if device_id == 0x02:
            result = await connect_ble(command_id)
        elif device_id == 0x01:
            result = time_series_packed

    elif command_id in (0x02, 0x03, 0x04):
        nresults = 0x03
        unit_id = 0x02  # for array
        error_id = 0x00
        print("entered aggregation")
        if device_id == 0x02:
            result += await connect_ble(command_id)
        elif device_id == 0x01:
            if command_id == 0x02:
                print("hum :", hum_aggr_packed)
                result += hum_aggr_packed
            elif command_id == 0x03:
                print("pres :", pres_aggr_packed)
                result += pres_aggr_packed
            elif command_id == 0x04:
                print("temp :", temp_aggr_packed)
                result += temp_aggr_packed
                print("unpacked:", struct.unpack("<3H", result))
    print("result", result)
    response_payload = bytes([nresults, unit_id]) + bytes(result) + bytes([error_id])

    return response_payload
##################################### ADAPTER FUNCTION ###################################


############################ CUSTOM PROTOCOL COMMUNICATION #####################################
def read_until(uart, delimiter=b'\n', max_bytes=256):
    buffer = bytearray(max_bytes)
    index = 0

    while True:
        byte = uart.read(1)
        if byte == delimiter:
            break
        if byte:
            buffer[index] = byte[0]
            index += 1

    return bytes(buffer[:index])


async def process_request(request_command, temp_characteristic):
    protocol_id = request_command[0]
    channel_id = request_command[1]
    device_id = request_command[2]
    device_type_id = request_command[3]
    operation_id = request_command[4]
    command_id = struct.unpack("<h", request_command[5:7])[0]
    nparams = request_command[7]

    if protocol_id == 0x01 and channel_id == 0x01 and operation_id == 0x01:
        result_payload = await sensor_operation(device_id, device_type_id, operation_id, command_id, None,
                                                temp_characteristic)

        headers = bytes([protocol_id, channel_id, device_id, device_type_id, operation_id]) + request_command[5:7]

        nresults = 0x1e
        unit_id = 0x02
        error_id = 0x00

        response_payload = headers + result_payload

        # For debugging purposes, print the response_payload
        print("Response Payload:", response_payload)

        return response_payload
############################ CUSTOM PROTOCOL COMMUNICATION END #####################################

async def main():
    # Start the background task
    asyncio.create_task(sensor_task())
    temp_characteristic = None

    while temp_characteristic is None:
        temp_characteristic = await connect_ble(temp_characteristic)
        await asyncio.sleep(1)
    #listen for requests over the serial uart interface
    while True:
        if uart.any():
            request_command = read_until(uart)
            response_command = await process_request(request_command, temp_characteristic)
            uart.write(response_command + b'\n')
            await asyncio.sleep(0.3)


asyncio.run(main())


