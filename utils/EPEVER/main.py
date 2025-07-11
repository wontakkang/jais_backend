from utils.EPEVER.constants import EPEVER_const
import struct
import math

class EPEVER_PDU:
    def __init__(self):
        self.array_data = {
            "address": 0x3100,
            "format": '',
            "type": [],
            "count": 0,
            "name": [],
            "scale": [],
        }
        self.load_data = {
            "address": 0x310C,
            "format": '',
            "type": [],
            "count": 0,
            "name": [],
            "scale": [],
        }
        self.battery_SOC = {
            "address": 0x311A,
            "format": '',
            "type": [],
            "count": 0,
            "name": [],
            "scale": [],
        }
        self.Status = {
            "address": 0x3200,
            "format": '',
            "type": [],
            "count": 0,
            "name": [],
            "scale": [],
        }
        self.LOG = {
            "address": 0x3302,
            "format": '',
            "type": [],
            "count": 0,
            "name": [],
            "scale": [],
        }
        self.battery = {
            "address": 0x331A,
            "format": '',
            "type": [],
            "count": 0,
            "name": [],
            "scale": [],
        }
        self.array_data['name'].append('array_Voltage')
        self.array_data['format'] += EPEVER_const.array_Voltage[0]
        self.array_data['type'].append(EPEVER_const.array_Voltage[1])
        self.array_data['scale'].append(EPEVER_const.array_Voltage[2])
        self.array_data['name'].append('array_Current')
        self.array_data['format'] += EPEVER_const.array_Current[0]
        self.array_data['type'].append(EPEVER_const.array_Current[1])
        self.array_data['scale'].append(EPEVER_const.array_Current[2])
        self.array_data['name'].append('array_Power')
        self.array_data['format'] += EPEVER_const.array_Power[0]
        self.array_data['type'].append(EPEVER_const.array_Power[1])
        self.array_data['scale'].append(EPEVER_const.array_Power[2])
        self.array_data['count'] = math.ceil(struct.calcsize(self.array_data['format'])/2)

        self.load_data['name'].append('load_Voltage')
        self.load_data['format'] += EPEVER_const.load_Voltage[0]
        self.load_data['type'].append(EPEVER_const.load_Voltage[1])
        self.load_data['scale'].append(EPEVER_const.load_Voltage[2])
        self.load_data['name'].append('load_Current')
        self.load_data['format'] += EPEVER_const.load_Current[0]
        self.load_data['type'].append(EPEVER_const.load_Current[1])
        self.load_data['scale'].append(EPEVER_const.load_Current[2])
        self.load_data['name'].append('load_Power')
        self.load_data['format'] += EPEVER_const.load_Power[0]
        self.load_data['type'].append(EPEVER_const.load_Power[1])
        self.load_data['scale'].append(EPEVER_const.load_Power[2])
        self.load_data['name'].append('battery_temp')
        self.load_data['format'] += EPEVER_const.battery_temp[0]
        self.load_data['type'].append(EPEVER_const.battery_temp[1])
        self.load_data['scale'].append(EPEVER_const.battery_temp[2])
        self.load_data['name'].append('device_temp')
        self.load_data['format'] += EPEVER_const.device_temp[0]
        self.load_data['type'].append(EPEVER_const.device_temp[1])
        self.load_data['scale'].append(EPEVER_const.device_temp[2])
        self.load_data['count'] = math.ceil(struct.calcsize(self.load_data['format'])/2)
        self.battery_SOC['name'].append('battery_SOC')
        self.battery_SOC['format'] += EPEVER_const.battery_SOC[0]
        self.battery_SOC['type'].append(EPEVER_const.battery_SOC[1])
        self.battery_SOC['scale'].append(EPEVER_const.battery_SOC[2])
        self.battery_SOC['count'] = math.ceil(struct.calcsize(self.battery_SOC['format'])/2)
        
        self.Status['name'].append('battery_Status')
        self.Status['type'].append(EPEVER_const.battery_Status[1])
        self.Status['scale'].append(EPEVER_const.battery_Status[2])
        self.Status['name'].append('charging_Equipment_Status')
        self.Status['type'].append(EPEVER_const.charging_Equipment_Status[1])
        self.Status['scale'].append(EPEVER_const.charging_Equipment_Status[2])
        self.Status['name'].append('discharging_Equipment_Status')
        self.Status['type'].append(EPEVER_const.discharging_Equipment_Status[1])
        self.Status['scale'].append(EPEVER_const.discharging_Equipment_Status[2])
        self.Status['count'] = math.ceil(struct.calcsize(self.Status['format'])/2)

        self.LOG['name'].append('maximum_Battery_Voltage_Today')
        self.LOG['format'] += EPEVER_const.maximum_Battery_Voltage_Today[0]
        self.LOG['type'].append(EPEVER_const.maximum_Battery_Voltage_Today[1])
        self.LOG['scale'].append(EPEVER_const.maximum_Battery_Voltage_Today[2])
        self.LOG['name'].append('minimum_Battery_Voltage_Today')
        self.LOG['format'] += EPEVER_const.minimum_Battery_Voltage_Today[0]
        self.LOG['type'].append(EPEVER_const.minimum_Battery_Voltage_Today[1])
        self.LOG['scale'].append(EPEVER_const.minimum_Battery_Voltage_Today[2])
        self.LOG['name'].append('consumed_Energy_Today')
        self.LOG['format'] += EPEVER_const.consumed_Energy_Today[0]
        self.LOG['type'].append(EPEVER_const.consumed_Energy_Today[1])
        self.LOG['scale'].append(EPEVER_const.consumed_Energy_Today[2])
        self.LOG['name'].append('consumed_Energy_Month')
        self.LOG['format'] += EPEVER_const.consumed_Energy_Month[0]
        self.LOG['type'].append(EPEVER_const.consumed_Energy_Month[1])
        self.LOG['scale'].append(EPEVER_const.consumed_Energy_Month[2])
        self.LOG['name'].append('consumed_Energy_Year')
        self.LOG['format'] += EPEVER_const.consumed_Energy_Year[0]
        self.LOG['type'].append(EPEVER_const.consumed_Energy_Year[1])
        self.LOG['scale'].append(EPEVER_const.consumed_Energy_Year[2])
        self.LOG['name'].append('total_Consumed_Energy')
        self.LOG['format'] += EPEVER_const.total_Consumed_Energy[0]
        self.LOG['type'].append(EPEVER_const.total_Consumed_Energy[1])
        self.LOG['scale'].append(EPEVER_const.total_Consumed_Energy[2])
        self.LOG['name'].append('generated_Energy_Today')
        self.LOG['format'] += EPEVER_const.generated_Energy_Today[0]
        self.LOG['type'].append(EPEVER_const.generated_Energy_Today[1])
        self.LOG['scale'].append(EPEVER_const.generated_Energy_Today[2])
        self.LOG['name'].append('generated_Energy_Month')
        self.LOG['format'] += EPEVER_const.generated_Energy_Month[0]
        self.LOG['type'].append(EPEVER_const.generated_Energy_Month[1])
        self.LOG['scale'].append(EPEVER_const.generated_Energy_Month[2])
        self.LOG['name'].append('generated_Energy_Year')
        self.LOG['format'] += EPEVER_const.generated_Energy_Year[0]
        self.LOG['type'].append(EPEVER_const.generated_Energy_Year[1])
        self.LOG['scale'].append(EPEVER_const.generated_Energy_Year[2])
        self.LOG['name'].append('total_Generated_Energy')
        self.LOG['format'] += EPEVER_const.total_Generated_Energy[0]
        self.LOG['type'].append(EPEVER_const.total_Generated_Energy[1])
        self.LOG['scale'].append(EPEVER_const.total_Generated_Energy[2])
        self.LOG['count'] = math.ceil(struct.calcsize(self.LOG['format'])/2)
        
        self.battery['name'].append('battery_Voltage')
        self.battery['format'] += EPEVER_const.battery_Voltage[0]
        self.battery['type'].append(EPEVER_const.battery_Voltage[1])
        self.battery['scale'].append(EPEVER_const.battery_Voltage[2])
        self.battery['name'].append('battery_Current_H')
        self.battery['format'] += EPEVER_const.battery_Current_H[0]
        self.battery['type'].append(EPEVER_const.battery_Current_H[1])
        self.battery['scale'].append(EPEVER_const.battery_Current_H[2])
        self.battery['name'].append('battery_Current_L')
        self.battery['format'] += EPEVER_const.battery_Current_L[0]
        self.battery['type'].append(EPEVER_const.battery_Current_L[1])
        self.battery['scale'].append(EPEVER_const.battery_Current_L[2])
        self.battery['count'] = math.ceil(struct.calcsize(self.battery['format'])/2)


EPEVER_pdu = EPEVER_PDU()
