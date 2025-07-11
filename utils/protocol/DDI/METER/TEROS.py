import math

def TEROS12_calculate(params) -> dict:
    """Calculate values for the TEROS 12 sensor.
    Args:
        value1 (float): The first value, typically the raw sensor reading.
        value2 (float): The second value, typically the temperature reading.
        value3 (float): The third value, typically the electrical conductivity reading.
    Returns:
        dict: A dictionary containing the calculated values:
            - 'temperature': The temperature in degrees Celsius.
            - 'electricalConductivity': The electrical conductivity in mS/cm.
            - 'VWCmineral': The volumetric water content for mineral soils.
            - 'VWCsoilless': The volumetric water content for soilless media.
    """
    value1 = params.get('value1', 0)
    value2 = params.get('value2', 0)
    value3 = params.get('value3', 0)
    if not (isinstance(value1, (int, float)) and isinstance(value2, (int, float)) and isinstance(value3, (int, float))):
        raise ValueError("All input values must be numeric.")
    result = {}
    # Constants for the TEROS 12 sensor
    result['temperature'] = float(value2)
    result['electricalConductivity'] = float(value3)
    result['VWCmineral'] = (3.879E-4)*float(value1) - 0.6956
    result['VWCsoilless'] = (6.771E-10)*float(value1)**3 - 5.105E-6*float(value1)**2 + 1.302E-2*float(value1) - 10.848
    
    return result
    

def TEROS21_calculate(params) -> dict:
    """
    Calculate values for the TEROS 21 sensor.
    Args:
        value1 (float): The first value, typically the raw sensor reading.
        value2 (float): The second value, typically the temperature reading.
    Returns:
        dict: A dictionary containing the calculated values:
            - 'matricPotential': The matric potential in kPa.
            - 'temperature': The temperature in degrees Celsius.
    """
    value1 = params.get('value1', 0)
    value2 = params.get('value2', 0)
    if not isinstance(value1, (int, float)) and isinstance(value2, (int, float)):
        raise ValueError("All input values must be numeric.")
    result = {}
    # Constants for the TEROS 12 sensor
    result['matricPotential'] = float(value1)
    result['temperature'] = float(value2)
    
    return result

def TEROS32_calculate(params) -> dict:
    """
    Calculate values for the TEROS 32 sensor.
    Args:
        value1 (float): The first value, typically the raw sensor reading.
        value2 (float): The second value, typically the temperature reading.
    Returns:
        dict: A dictionary containing the calculated values:
            - 'matricPotential': The matric potential in kPa.
            - 'temperature': The temperature in degrees Celsius.
    """
    value1 = params.get('value1', 0)
    value2 = params.get('value2', 0)
    if not isinstance(value1, (int, float)) and isinstance(value2, (int, float)):
        raise ValueError("All input values must be numeric.")
    result = {}
    # Constants for the TEROS 12 sensor
    result['matricPotential'] = float(value1)
    result['temperature'] = float(value2)
    
    return result

calculation_methods = {
    "TEROS12": TEROS12_calculate,
    "TEROS21": TEROS21_calculate,
    "TEROS32": TEROS32_calculate,
}