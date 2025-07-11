from fastapi import APIRouter
from utils.config import settings
from utils.logger import log_exceptions, setup_logger
import RPi.GPIO as GPIO
import re
import serial, time
DDI_logger = setup_logger(name="DDI_logger", log_file=f"{settings.LOG_DIR}/DDI_protocol.log")
from utils.protocol.DDI.METER import all_dict as TEROS_methods

# CRC-6/CDMA2000-A 구현
def crc6_cdma2000(data: bytes) -> int:
    poly = 0x27
    crc = 0x3F
    mask = 0x3F
    for byte in data:
        for i in range(8):
            bit = (byte >> (7 - i)) & 1
            top = (crc >> 5) & 1
            c = top ^ bit
            crc = ((crc << 1) & mask)
            if c:
                crc ^= poly
    return crc


class DDI_protocol:

    COM_PORT_INFO = {
        "COM0": ['/dev/ttyS0', 18],
        "COM1": ['/dev/ttyAMA4', 11],
        "COM2": ['/dev/ttyAMA5', 19],
        "COM3": ['/dev/ttyAMA3', 6],
    }
    slaves = []
    def __init__(self, **kwargs):
        # GPIO 설정 및 접근 가능 여부 판단
        try:
            GPIO.cleanup()
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            self.gpio_available = True
        except Exception as err:
            DDI_logger.warning(f"GPIO unavailable: {err}. Disabling GPIO.")
            self.gpio_available = False

    def getData(self, buckets):
        postData = {}
        for b in buckets:
            # 센서명(label)과 COM 포트 추출
            labels = b.get("labels", [])
            slave = {
                "bucket_id": b.get("id"),
                "serial": b.get("name"),
            }
            # label에 ':' 포함 시 앞부분은 key, 뒷부분은 value로 분리하여 slave에 추가
            for lbl in labels:
                if ':' in lbl['name']:
                    key, val = lbl['name'].split(':', 1)
                    slave[key.lower()] = val
            if 'port' in slave:
                self.slaves.append(slave)
        DDI_logger.info(f"add slaves({len(self.slaves)}): {self.slaves}")
        valid_slaves = []
        for slave in self.slaves:
            if self.gpio_available and slave['port'] in self.COM_PORT_INFO and slave['serial'] not in ['_tasks', '_monitoring', '_autogen']:
                # GPIO 핀 설정
                GPIO.setup(self.COM_PORT_INFO[slave['port']][1], GPIO.OUT)
                DDI_logger.info(f"valid port {slave['port']} {self.COM_PORT_INFO[slave['port']]} for {slave['serial']}")
                valid_slaves.append(slave)
        DDI_logger.info(f"GPIO setup complete. Valid slaves({len(valid_slaves)}): {valid_slaves}")
                
        for slave in valid_slaves:
            # 포트가 유효하고 GPIO setup 성공한 경우만 처리
            DDI_logger.info(f"processing measurement : port {slave['port']} for {slave['serial']}")
            DDI_power_pin = self.COM_PORT_INFO[slave['port']][1]
            DDI_port = self.COM_PORT_INFO[slave['port']][0]
            try:
                GPIO.setup(DDI_power_pin, GPIO.OUT)
                GPIO.output(DDI_power_pin, GPIO.LOW)
            except Exception as err:
                DDI_logger.error(f"GPIO.setup Stopping...{err}")
                GPIO.output(DDI_power_pin, GPIO.HIGH)
                time.sleep(0.1)
            try:
                con = serial.Serial(port=DDI_port, baudrate=1200, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS, exclusive=False, timeout=3)
                DDI_logger.info(f'scheduler.py:: Scheduler serial_connect : {con}')
                GPIO.output(DDI_power_pin, GPIO.HIGH)
                time.sleep(0.250)
            except Exception as err:
                DDI_logger.error(f"serial connect Stopping...{err}")
                GPIO.output(DDI_power_pin, GPIO.HIGH)
                time.sleep(0.1)
                pass
            _buffer = con.readline()
            DDI_logger.info(f"serial buffer: {_buffer}")
            # 체크섬 계산을 위한 데이터 섹션 분리
            idx = _buffer.find(b'\r')
            data_section = _buffer[:idx] if idx != -1 else _buffer
            expected_crc = crc6_cdma2000(data_section)
                    # 파싱 시작: 비ASCII 무시 후 탭·공백으로 분리
            import re
            text = _buffer.decode('ascii', 'ignore').strip('\r\n')
            tokens = [t for t in re.split(r'[\t\r\n ]+', text) if t]
            # 숫자 토큰과 체크섬 토큰 분리
            num_pattern = re.compile(r'^-?\d+(?:\.\d+)?$')
            numeric_tokens = [t for t in tokens if num_pattern.match(t)]
            checksum_tokens = [t for t in tokens if not num_pattern.match(t)]
            # raw 저장
            postData.setdefault(slave['serial'], {})['raw'] = tokens
            # 데이터 동적 매핑
            data = {}
            for idx, val in enumerate(numeric_tokens, start=1):
                data[f'value{idx}'] = float(val)
            if checksum_tokens:
                actual = checksum_tokens[0]
                # 실제 CRC 값(첫 문자 기준)
                actual_crc = ord(actual[0])
                data['senserType'] = actual
                data['expected_checksum'] = expected_crc
                data['checksum_valid'] = (actual_crc == expected_crc)
            postData[slave['serial']]['data'] = data
            DDI_logger.info(f"serial data Preprocess...{slave} : {postData}")
            # 데이터 처리
            if slave['device'] in TEROS_methods:
                postData[slave['serial']]['result'] = TEROS_methods[slave['device']](data)
        return postData
ddi_intance = DDI_protocol()