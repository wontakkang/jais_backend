
class Defaults:
    array_Voltage = ['h', 'int', 0.01]
    array_Current = ['h', 'int', 0.01]
    array_Power = ['i', 'int', 0.01]

    load_Voltage = ['h', 'int', 0.01]
    load_Current = ['h', 'int', 0.01]
    load_Power = ['i', 'int', 0.01]
    battery_temp = ['h', 'int', 0.01]
    device_temp = ['h', 'int', 0.01]

    battery_SOC = ['h', 'int', 1]

    battery_Status = ['h', 'int', 1]
    charging_Equipment_Status = ['h', 'int', 1]
    discharging_Equipment_Status = ['h', 'int', 1]

    maximum_Battery_Voltage_Today = ['h', 'int', 0.01]
    minimum_Battery_Voltage_Today = ['h', 'int', 0.01]
    consumed_Energy_Today = ['i', 'dint', 0.01]
    consumed_Energy_Month = ['i', 'dint', 0.01]
    consumed_Energy_Year = ['i', 'dint', 0.01]
    total_Consumed_Energy = ['i', 'dint', 0.01]
    generated_Energy_Today = ['i', 'dint', 0.01]
    generated_Energy_Month = ['i', 'dint', 0.01]
    generated_Energy_Year = ['i', 'dint', 0.01]
    total_Generated_Energy = ['i', 'dint', 0.01]
    
    battery_Voltage = ['H', 'int', 0.01]
    battery_Current_H = ['h', 'int', 0.01]
    battery_Current_L = ['h', 'int', 0.01]

EPEVER_const = Defaults()
