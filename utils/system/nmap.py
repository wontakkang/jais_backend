from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import nmap
import time

class NmapScanner:
    def __init__(self, target, fields=None):
        self.target = target
        # 가능한 모든 필드 정의
        self.available_fields = {
            'ip': 'IP Address',
            'status': 'Host Status (up/down)',
            'os': 'OS Guess',
            'mac': 'MAC Address',
            'vendor': 'MAC Vendor',
            'hostname': 'Host DNS Name',
            'device_type': 'Device Type Guess',
            'latency': 'Latency (ms)',
            'runtime': 'Scan Runtime (sec)'
        }
        # 유저가 선택한 필드만 저장
        self.fields = fields if fields else ['ip', 'status', 'os', 'hostname', 'device_type']
        self.results = []
        self.runtime = 0
        self.worker_count = 13
        self.scan_chunks = [
            "192.168.0.1-10",
            "192.168.0.11-20",
            "192.168.0.21-30",
            "192.168.0.31-40",
            "192.168.0.41-50",
            "192.168.0.51-60",
            "192.168.0.61-70",
            "192.168.0.71-80",
            "192.168.0.81-90",
            "192.168.0.91-100",
            "192.168.0.101-110",
            "192.168.0.111-120",
            "192.168.0.121-130",
            "192.168.0.131-140",
            "192.168.0.141-150",
            "192.168.0.151-160",
            "192.168.0.161-170",
            "192.168.0.171-180",
            "192.168.0.181-190",
            "192.168.0.191-200",
            "192.168.0.201-210",
            "192.168.0.211-220",
            "192.168.0.221-230",
            "192.168.0.231-240",
            "192.168.0.241-250",
            "192.168.0.251-254"
        ]

    def scan(self):
        start_time = time.time()
        self.results = []
        # -O 옵션은 OS 추정 포함
        is_root = os.geteuid() == 0 if hasattr(os, "geteuid") else False
        nmap_args = '-O' if is_root else '-sn'
        
        def scan_chunk(chunk):
            try:
                # print(f"📡 병렬 스캔 중: {chunk}")
                scanner = nmap.PortScanner()
                scanner.scan(hosts=chunk, arguments=nmap_args, timeout=45)
                return self.parse_result_from(scanner)  # self.parse_result_from(scanner)가 결과 리스트 반환하도록 구현되어야 함
            except nmap.PortScannerTimeout:
                # print(f"⏱️ 스캔 타임아웃 발생: {chunk}")
                return []
            except nmap.PortScannerError as e:
                # print(f"❌ 스캔 오류 발생: {e}")
                return []
        
        with ThreadPoolExecutor(max_workers=self.worker_count) as executor:
            futures = [executor.submit(scan_chunk, chunk) for chunk in self.scan_chunks]

            for future in as_completed(futures):
                result = future.result()
                if result:
                    self.results.extend(result)  # parse_result_from()는 리스트를 반환해야 함
        end_time = time.time()
        self.runtime = round(end_time - start_time, 2)
        
    def parse_result_from(self, scanner):
        result_list = []
        for host in scanner.all_hosts():
            host_info = scanner[host]
            host_data = {}
            if 'ip' in self.fields:
                host_data['ip'] = host

            if 'status' in self.fields:
                host_data['status'] = host_info.state()

            if 'os' in self.fields:
                os_guess = 'Unknown'
                if 'osmatch' in host_info and host_info['osmatch']:
                    os_guess = host_info['osmatch'][0]['name']
                host_data['os'] = os_guess

            if 'mac' in self.fields:
                mac = host_info['addresses'].get('mac', 'Unknown')
                host_data['mac'] = mac

            if 'vendor' in self.fields:
                mac = host_data.get('mac', '')
                vendor = host_info.get('vendor', {}).get(mac, 'Unknown')
                host_data['vendor'] = vendor

            # 🎯 추가된 기능: device_type 추론
            if 'device_type' in self.fields:
                device_type = 'Unknown'
                vendor = host_data.get('vendor', '').lower()
                os = host_data.get('os', '').lower()
                ports = host_info.get('tcp', {}).keys()

                if 'synology' in vendor or 'nas' in os:
                    device_type = 'NAS'
                elif 'printer' in os or 'canon' in vendor or 'hp' in vendor or 9100 in ports:
                    device_type = 'Printer'
                elif 'windows' in os:
                    device_type = 'Windows PC'
                elif 'linux' in os or 'ubuntu' in os:
                    device_type = 'Linux Device'
                elif any(keyword in vendor for keyword in ['aruba', 'd-link', 'tplink', 'mikrotik', 'asus']) or \
                    any(keyword in os for keyword in ['router', 'wap', 'access point']):
                    device_type = 'Access Point / Router'
                elif not ports:
                    device_type = 'Passive/Idle Device'
                else:
                    device_type = 'Unknown / Custom'
                
                host_data['device_type'] = device_type
            if 'classify_device' in self.fields:
                # 서버 기준
                if any(kw in host_data['os'].lower() for kw in ["server"]) or any(kw in host_data['device_type'].lower() for kw in ["nas"]) or any(kw in host_data['vendor'].lower() for kw in ["nexcom", "ezex", "ls(lg)"]):
                    host_data['classify_device'] = "server"
                elif "linux" in host_data['os'] and host_data['mac'] == "94:DE:80:70:BE:48":
                    host_data['classify_device'] = "server"
                elif host_data['ip'] in ["192.168.0.57", "192.168.0.13", "192.168.0.74", "192.168.0.75", "192.168.0.71"]:
                    host_data['classify_device'] = "server"
                # 유휴 장치 (idle_device)
                elif any(kw in host_data['device_type'].lower() for kw in ["passive", "printer"]):
                    host_data['classify_device'] = "idle_device"
                elif any(kw in host_data['vendor'].lower() for kw in ["tp-link", "aruba", "Netgear"]):
                    host_data['classify_device'] = "idle_device"
                elif any(kw in host_data['os'].lower() for kw in ["switch", "firewall", "router", "access point", "network"]):
                    host_data['classify_device'] = "idle_device"
                # 유저 PC
                elif any(kw in host_data['os'].lower() for kw in ["windows 10", "windows 11", "windows 7", "windows xp", "windows 8"]):
                    host_data['classify_device'] = "user_pc"
                elif any(kw in host_data['vendor'].lower() for kw in ["asustek"]):
                    host_data['classify_device'] = "user_pc"
                # 모바일 장치
                elif any(kw in host_data['os'].lower() for kw in ["ios", "macos", "apple", "android"]):
                    host_data['classify_device'] = "mobile"
                elif any(kw in host_data['vendor'] for kw in ["Samsung Electronics"]):
                    host_data['classify_device'] = "mobile"

                # 커스텀 장치나 산업용 제어기 (새로운 카테고리)
                elif any(kw in host_data['vendor'].lower() for kw in ["s1", "crestron", "cig shanghai", "urovo", "canon"]):
                    host_data['classify_device'] = "custom_device"
                elif host_data['ip'] in [f"192.168.0.{i}" for i in range(246, 254)] or host_data['ip'] in [f"192.168.0.242"]:
                    host_data['classify_device'] = "custom_device"
                # 알 수 없는 것들
                elif "unknown" in host_data['os'] or "unknown" in host_data['device_type'] or "custom" in host_data['device_type']:
                    host_data['classify_device'] = "unknown"
                else:
                    host_data['classify_device'] = "unknown"
            # ✅ 중복 방지: IP가 기존에 존재하지 않을 때만 추가
            existing_ips = {entry['ip'] for entry in self.results}
            if host_data['ip'] not in existing_ips:
                result_list.append(host_data)
        return result_list

    def run(self):
        self.scan()
        if 'runtime' in self.fields:
            print(f"Total Scan Runtime: {self.runtime} seconds\n")
        return self.results

    def show_available_fields(self):
        print("✅ Available Fields you can request:")
        for key, desc in self.available_fields.items():
            print(f" - {key}: {desc}")
