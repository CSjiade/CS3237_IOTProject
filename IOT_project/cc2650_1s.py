# -*- coding: utf-8 -*-
"""
TI CC2650 SensorTag
-------------------
Adapted by Ashwin from the following sources:
 - https://github.com/IanHarvey/bluepy/blob/a7f5db1a31dba50f77454e036b5ee05c3b7e2d6e/bluepy/sensortag.py
 - https://github.com/hbldh/bleak/blob/develop/examples/sensortag.py
"""
import asyncio
import platform
import struct
from bleak import BleakClient
from mqtt import Publisher
import json
import joblib
import numpy as np
import datetime



#set up the MQTT publisher
mqtt_pub = Publisher("sensor1/data", "localhost", 1883)


# declare relevant global variables
global arr
arr = []

global count
count = 0


global bax_mean
bax_mean = []
global bay_mean
bay_mean = []
global baz_mean
baz_mean = []
global bgx_mean
bgx_mean = []
global bgy_mean
bgy_mean = []
global bgz_mean
bgz_mean = []


global bmx_mean
bmx_mean = 0
global bmy_mean
bmy_mean = 0
global bmz_mean
bmz_mean = 0


global accelx_arr
accelx_arr = []

global accely_arr
accely_arr = []

global accelz_arr
accelz_arr = []




# magnitude values currently not in used

global accel_mag
accel_mag = 0

global gyro_mag
gyro_mag = 0

global  mag_mag
mag_mag = 0


class Service:

    """
    Here is a good documentation about the concepts in ble;
    https://learn.adafruit.com/introduction-to-bluetooth-low-energy/gatt
    In TI SensorTag there is a control characteristic and a data characteristic which define a service or sensor
    like the Light Sensor, Humidity Sensor etc
    Please take a look at the official TI user guide as well at
    https://processors.wiki.ti.com/index.php/CC2650_SensorTag_User's_Guide
    """
    def __init__(self):
        self.data_uuid = None
        self.ctrl_uuid = None
        self.period_uuid = None

    async def read(self, client):
        raise NotImplementedError()




class Sensor(Service):


    def callback(self, sender: int, data: bytearray):
        raise NotImplementedError()

    # async def enable(self, client, *args):
    #     # start the sensor on the device
    #     write_value = bytearray([0x01])
    #     await client.write_gatt_char(self.ctrl_uuid, write_value)
    #     write_value = bytearray([0x0A]) # check the sensor period applicable values in the sensor tag guide mentioned above
    #     await client.write_gatt_char(self.period_uuid, write_value)
    #     return self

    async def read(self, client):
        val = await client.read_gatt_char(self.data_uuid)
        return self.callback(1, val)

    async def start_listener(self, client, *args):
        write_value = bytearray([0x01])
        await client.write_gatt_char(self.ctrl_uuid, write_value)
        # listen using the handler
        await client.start_notify(self.data_uuid, self.callback)




class MovementSensorMPU9250SubService:

    def __init__(self):
        self.bits = 0

    def enable_bits(self):
        return self.bits

    def cb_sensor(self, data):
        raise NotImplementedError


class MovementSensorMPU9250(Sensor):
    GYRO_XYZ = 7
    ACCEL_XYZ = 7 << 3
    MAG_XYZ = 1 << 6
    ACCEL_RANGE_2G  = 0 << 8
    ACCEL_RANGE_4G  = 1 << 8
    ACCEL_RANGE_8G  = 2 << 8
    ACCEL_RANGE_16G = 3 << 8

    def __init__(self):
        super().__init__()
        self.data_uuid = "f000aa81-0451-4000-b000-000000000000"
        self.ctrl_uuid = "f000aa82-0451-4000-b000-000000000000"
        self.ctrlBits = 0
        self.sub_callbacks = []

    def register(self, cls_obj: MovementSensorMPU9250SubService):
        self.ctrlBits |= cls_obj.enable_bits()
        self.sub_callbacks.append(cls_obj.cb_sensor)

    async def start_listener(self, client, *args):
        # start the sensor on the device
        await client.write_gatt_char(self.ctrl_uuid, struct.pack("<H", self.ctrlBits))

        # listen using the handler
        await client.start_notify(self.data_uuid, self.callback)

    def callback(self, sender: int, data: bytearray):
        global accel_mag
        global gyro_mag
        global  mag_mag
        global count
        count = count + 1
        dataDict = {}
        global bax_mean
        global bay_mean
        global baz_mean
        global bgx_mean
        global bgy_mean
        global bgz_mean
        global bmx_mean
        global bmy_mean
        global bmz_mean
        unpacked_data = struct.unpack("<hhhhhhhhh", data)

        for cb in self.sub_callbacks:
            cb(unpacked_data)
            value = cb(unpacked_data)
            dataDict.update(value)
        bax_mean.append(dataDict["accelX"])
        bay_mean.append(dataDict["accelY"])
        baz_mean.append(dataDict["accelZ"])
        bgx_mean.append(dataDict["gyroX"])
        bgy_mean.append(dataDict["gyroX"])
        bgz_mean.append(dataDict["gyroY"])
        #send data to mqtt subscriber.
        """
        Counter is set as 50 of 10hz samping rate and machine learning model is 
        running on 5 second window of data
        """
        if count == 50:
            arr.append(np.percentile(bax_mean,25))
            arr.append(np.percentile(bgy_mean,75))
            arr.append(np.median(bay_mean))
            arr.append(np.mean(bgx_mean))
            arr.append(np.mean(bgy_mean))
            arr.append(np.percentile(bgx_mean,25))
            arr.append(np.median(bax_mean))
            arr.append(np.percentile(bay_mean,75))
            arr.append(np.percentile(bgy_mean,25))
            arr.append(np.percentile(bax_mean,10))
            arr.append(np.median(bgx_mean))
            arr.append(np.percentile(bay_mean,90))
            arr.append(np.percentile(bgx_mean,10))
            arr.append(np.min(bay_mean))
            arr.append(np.max(bax_mean))
            arr.append(np.median(baz_mean))
            arr.append(np.mean(bay_mean))
            arr.append(np.mean(bax_mean))
            arr.append(np.var(bgy_mean))
            arr.append(np.min(bgz_mean))
            json_msg = {
                'sensor': 1,
                'payload': arr,
                 'peak': bax_mean
            }
            mqtt_pub.publish(json.dumps(json_msg))


            #After message is published reset values for next input of data
            count = 0
            bmx_mean = 0
            bmy_mean = 0
            bmz_mean = 0
            accelx_arr.clear()
            arr.clear()
            bax_mean.clear()
            bay_mean.clear()
            baz_mean.clear()
            bgx_mean.clear()
            bgy_mean.clear()
            bgz_mean.clear()
            accel_mag = 0
            gyro_mag = 0
            mag_mag = 0


class AccelerometerSensorMovementSensorMPU9250(MovementSensorMPU9250SubService):
    def __init__(self):
        super().__init__()
        self.bits = MovementSensorMPU9250.ACCEL_XYZ | MovementSensorMPU9250.ACCEL_RANGE_4G
        self.scale = 8.0/32768.0 # TODO: why not 4.0, as documented? @Ashwin Need to verify

    def cb_sensor(self, data):
        '''Returns (x_accel, y_accel, z_accel) in units of g'''
        rawVals = data[3:6]
        valueTup = tuple([ v*self.scale for v in rawVals ])
        dictValue = {"accelX" : valueTup[0] , "accelY": valueTup[1], "accelZ": valueTup[2]}
        #print(datetime.datetime.now())
        #print("[MovementSensor] Accelerometer:", dictValue)
        return dictValue



class MagnetometerSensorMovementSensorMPU9250(MovementSensorMPU9250SubService):

    def __init__(self):
        super().__init__()
        self.bits = MovementSensorMPU9250.MAG_XYZ
        self.scale = 4912.0 / 32760
        # Reference: MPU-9250 register map v1.4

    def cb_sensor(self, data):
        '''Returns (x_mag, y_mag, z_mag) in units of uT'''
        rawVals = data[6:9]
        valueTup = tuple([ v*self.scale for v in rawVals ])
        dictValue = {"magnetX" : valueTup[0] , "magnetY": valueTup[1], "magnetZ": valueTup[2]}
        #print("[MovementSensor] Magnetometer:", tuple([ v*self.scale for v in rawVals ]))
        return dictValue


class GyroscopeSensorMovementSensorMPU9250(MovementSensorMPU9250SubService):
    def __init__(self):
        super().__init__()
        self.bits = MovementSensorMPU9250.GYRO_XYZ
        self.scale = 500.0/65536.0

    def cb_sensor(self, data):
        '''Returns (x_gyro, y_gyro, z_gyro) in units of degrees/sec'''
        rawVals = data[0:3]
        valueTup = tuple([ v*self.scale for v in rawVals ])
        dictValue = {"gyroX" : valueTup[0] , "gyroY": valueTup[1], "gyroZ": valueTup[2]}
        #print("[MovementSensor] Gyroscope:", dictValue)
        return dictValue


class OpticalSensor(Sensor):
    def __init__(self):
        super().__init__()
        self.data_uuid = "f000aa71-0451-4000-b000-000000000000"
        self.ctrl_uuid = "f000aa72-0451-4000-b000-000000000000"

    def callback(self, sender: int, data: bytearray):
        raw = struct.unpack('<h', data)[0]
        m = raw & 0xFFF
        e = (raw & 0xF000) >> 12
        #print("[OpticalSensor] Reading from light sensor:", 0.01 * (m << e))


class HumiditySensor(Sensor):

    def __init__(self):
        super().__init__()
        self.data_uuid = "f000aa21-0451-4000-b000-000000000000"
        self.ctrl_uuid = "f000aa22-0451-4000-b000-000000000000"
        self.tempData = " "
        self.humidityData = " "

    def callback(self, sender: int, data: bytearray):
        (rawT, rawH) = struct.unpack('<HH', data)
        temp = -40.0 + 165.0 * (rawT / 65536.0)
        RH = 100.0 * (rawH/65536.0)
        #print(f"[HumiditySensor] Ambient temp: {temp}; Relative Humidity: {RH}")
        self.tempData = temp
        self.humidityData = RH

        #place ML model here



class BarometerSensor(Sensor):
    def __init__(self):
        super().__init__()
        self.data_uuid = "f000aa41-0451-4000-b000-000000000000"
        self.ctrl_uuid = "f000aa42-0451-4000-b000-000000000000"

    def callback(self, sender: int, data: bytearray):
        (tL, tM, tH, pL, pM, pH) = struct.unpack('<BBBBBB', data)
        temp = (tH*65536 + tM*256 + tL) / 100.0
        press = (pH*65536 + pM*256 + pL) / 100.0
        #print(f"[BarometerSensor] Ambient temp: {temp}; Pressure Millibars: {press}")



class LEDAndBuzzer(Service):
    """
        Adapted from various sources. Src: https://evothings.com/forum/viewtopic.php?t=1514 and the original TI spec
        from https://processors.wiki.ti.com/index.php/CC2650_SensorTag_User's_Guide#Activating_IO
        Codes:
            1 = red
            2 = green
            3 = red + green
            4 = buzzer
            5 = red + buzzer
            6 = green + buzzer
            7 = all
    """

    def __init__(self):
        super().__init__()
        self.data_uuid = "f000aa65-0451-4000-b000-000000000000"
        self.ctrl_uuid = "f000aa66-0451-4000-b000-000000000000"

    async def notify(self, client, code):
        # enable the config
        write_value = bytearray([0x01])
        await client.write_gatt_char(self.ctrl_uuid, write_value)

        # turn on the red led as stated from the list above using 0x01
        write_value = bytearray([code])
        await client.write_gatt_char(self.data_uuid, write_value)

async def run(address):
    async with BleakClient(address) as client:
        x = await client.is_connected()
        print("Connected: {0}".format(x))

        # led_and_buzzer = LEDAndBuzzer()
        #
        # light_sensor = OpticalSensor()
        # await light_sensor.start_listener(client)

        humidity_sensor = HumiditySensor()
        await humidity_sensor.start_listener(client)

        barometer_sensor = BarometerSensor()
        await barometer_sensor.start_listener(client)

        acc_sensor = AccelerometerSensorMovementSensorMPU9250()
        gyro_sensor = GyroscopeSensorMovementSensorMPU9250()

        movement_sensor = MovementSensorMPU9250()
        movement_sensor.register(acc_sensor)
        movement_sensor.register(gyro_sensor)
        magneto_sensor = MagnetometerSensorMovementSensorMPU9250()
        movement_sensor.register(magneto_sensor)

        await movement_sensor.start_listener(client)

        #cntr = 0

        while True:
            # we don't want to exit the "with" block initiating the client object as the connection is disconnected
            # unless the object is stored
            await asyncio.sleep(0.1)

            # if cntr == 0:
            #     # shine the red light
            #     await led_and_buzzer.notify(client, 0x01)
            #
            # if cntr == 5:
            #     # shine the green light
            #     await led_and_buzzer.notify(client, 0x02)
            #
            # cntr += 1
            #
            # if cntr == 10:
            #     cntr = 0


if __name__ == "__main__":
    """
    To find the address, once your sensor tag is blinking the green led after pressing the button, run the discover.py
    file which was provided as an example from bleak to identify the sensor tag device
    """
    import os

    os.environ["PYTHONASYNCIODEBUG"] = str(1)
    address = (
            "CDAF700C-02BA-48D4-A150-0EA43D79B2A7"
            if platform.system() != "Darwin"
            else "CDAF700C-02BA-48D4-A150-0EA43D79B2A7"
    )
    mqtt_pub.run()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run(address))
    loop.run_forever()
