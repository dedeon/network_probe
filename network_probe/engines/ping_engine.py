"""Ping 拨测引擎"""
import subprocess
import re
import time
import platform
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal


class PingEngine(QThread):
    """
    Ping 拨测线程
    信号:
        result_ready(dict): 每条探测结果
        error_occurred(str): 错误消息
        finished_signal(): 拨测完成
    """
    result_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, target: str, interval_ms: int = 200, timeout_ms: int = 2000,
                 packet_size: int = 64, ttl: int = 64, parent=None):
        super().__init__(parent)
        self.target = target
        self.interval_ms = interval_ms
        self.timeout_ms = timeout_ms
        self.packet_size = packet_size
        self.ttl = ttl
        self._running = False
        self._seq = 0

    def run(self):
        self._running = True
        self._seq = 0
        system = platform.system().lower()

        while self._running:
            self._seq += 1
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.') + f"{datetime.now().microsecond // 1000:03d}"

            try:
                # 构建 ping 命令
                if system == 'windows':
                    cmd = [
                        'ping', '-n', '1',
                        '-w', str(self.timeout_ms),
                        '-l', str(self.packet_size),
                        '-i', str(self.ttl),
                        self.target
                    ]
                else:
                    # Linux/Mac
                    timeout_sec = max(1, self.timeout_ms // 1000)
                    cmd = [
                        'ping', '-c', '1',
                        '-W', str(timeout_sec),
                        '-s', str(self.packet_size),
                        '-t', str(self.ttl),
                        self.target
                    ]

                start_time = time.perf_counter()
                result = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=self.timeout_ms / 1000 + 2
                )
                elapsed = (time.perf_counter() - start_time) * 1000

                # 解析结果
                output = result.stdout + result.stderr
                record = self._parse_output(output, result.returncode, timestamp, elapsed, system)

            except subprocess.TimeoutExpired:
                record = {
                    'timestamp': timestamp,
                    'seq': self._seq,
                    'rtt_ms': None,
                    'ttl': None,
                    'status': 'timeout'
                }
            except Exception as e:
                record = {
                    'timestamp': timestamp,
                    'seq': self._seq,
                    'rtt_ms': None,
                    'ttl': None,
                    'status': 'error'
                }
                self.error_occurred.emit(str(e))

            self.result_ready.emit(record)

            # 等待间隔
            if self._running:
                sleep_time = max(0.01, self.interval_ms / 1000 - 0.01)
                # 使用短间隔轮询以便及时响应停止
                end_wait = time.perf_counter() + sleep_time
                while self._running and time.perf_counter() < end_wait:
                    time.sleep(0.05)

        self.finished_signal.emit()

    def _parse_output(self, output: str, returncode: int, timestamp: str,
                      elapsed_ms: float, system: str) -> dict:
        """解析 ping 命令输出"""
        record = {
            'timestamp': timestamp,
            'seq': self._seq,
            'rtt_ms': None,
            'ttl': None,
            'status': 'timeout'
        }

        if returncode != 0 and 'unreachable' in output.lower():
            record['status'] = 'unreachable'
            return record

        # 提取 RTT
        rtt_patterns = [
            r'time[=<](\d+\.?\d*)\s*ms',    # Windows/Linux
            r'时间[=<](\d+\.?\d*)\s*ms',     # 中文Windows
            r'rtt.*?=\s*[\d.]+/([\d.]+)',    # Linux summary
        ]
        for pattern in rtt_patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                record['rtt_ms'] = round(float(match.group(1)), 2)
                record['status'] = 'success'
                break

        # 提取 TTL
        ttl_match = re.search(r'ttl[=:]?\s*(\d+)', output, re.IGNORECASE)
        if ttl_match:
            record['ttl'] = int(ttl_match.group(1))

        # 如果没有从输出解析到RTT但return code为0，使用elapsed时间
        if record['rtt_ms'] is None and returncode == 0:
            if 'bytes from' in output.lower() or '来自' in output.lower() or 'reply from' in output.lower():
                record['rtt_ms'] = round(elapsed_ms, 2)
                record['status'] = 'success'

        return record

    def stop(self):
        self._running = False
