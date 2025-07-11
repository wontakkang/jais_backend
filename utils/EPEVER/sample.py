      
def gathering_data_15m():
    client = ModbusTcpClient("30.3.10.1", 502)
    if client.connect():  # Connection to slave device
        content = {}
        for slave_id in [1, 3]:
            measurement = f"EPEVER{slave_id}"
            tags = {"location": "DE-ET-04", "device": f"EPEVER{slave_id}"}
            for name in ['array_data', 'load_data', 'battery_SOC', 'battery', 'LOG']:
                try: 
                    response = client.read_input_registers(
                        getattr(EPEVER_pdu, name)['address'],
                        getattr(EPEVER_pdu, name)["count"],
                        slave_id
                    )
                except Exception as err:
                    route_logger.debug(f"{name} {err}")
                # Check if response has the 'registers' attribute
                try:
                    if hasattr(response, 'registers'):
                        bytesData = struct.pack(f"{len(response.registers) * 'H'}", *response.registers)
                        resData = struct.unpack(getattr(EPEVER_pdu, name)['format'], bytesData)
                        for index, value in enumerate(getattr(EPEVER_pdu, name)['name']):
                            content[value] = resData[index] * getattr(EPEVER_pdu, name)['scale'][index]
                except Exception as err:
                    route_logger.debug(f"{slave_id} {name} {response.registers} {err}")
                time.sleep(0.2)
            fields = content
            inFlux_instance.execute_write(measurement=measurement, tags=tags, fields=fields)

        client.close()
        print("Data written successfully.")
    else:
        print("Failed to connect to Modbus device.")