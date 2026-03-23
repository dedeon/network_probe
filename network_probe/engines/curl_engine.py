"""Curl/HTTP 拨测引擎"""
import time
import ssl
from datetime import datetime
from urllib.parse import urlparse
from PyQt6.QtCore import QThread, pyqtSignal

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class CurlEngine(QThread):
    """
    HTTP/Curl 拨测线程
    信号:
        result_ready(dict): 每条探测结果
        error_occurred(str): 错误消息
        finished_signal(): 拨测完成
    """
    result_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, target: str, method: str = 'GET', timeout_ms: int = 10000,
                 connect_timeout_ms: int = 5000, follow_redirects: bool = True,
                 verify_tls: bool = True, interval_ms: int = 1000, parent=None):
        super().__init__(parent)
        self.target = target
        self.method = method
        self.timeout_ms = timeout_ms
        self.connect_timeout_ms = connect_timeout_ms
        self.follow_redirects = follow_redirects
        self.verify_tls = verify_tls
        self.interval_ms = interval_ms
        self._running = False
        self._seq = 0

    def _ensure_url(self, target: str) -> str:
        """确保目标地址包含协议头"""
        if not target.startswith(('http://', 'https://')):
            return f'http://{target}'
        return target

    def run(self):
        if not REQUESTS_AVAILABLE:
            self.error_occurred.emit('requests 未安装，请运行: pip install requests')
            self.finished_signal.emit()
            return

        self._running = True
        self._seq = 0
        url = self._ensure_url(self.target)
        session = requests.Session()

        while self._running:
            self._seq += 1
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.') + f"{datetime.now().microsecond // 1000:03d}"

            try:
                # DNS 阶段计时
                dns_start = time.perf_counter()
                parsed = urlparse(url)
                import socket
                try:
                    socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80))
                except Exception:
                    pass
                dns_time = (time.perf_counter() - dns_start) * 1000

                # 整体请求
                total_start = time.perf_counter()
                response = session.request(
                    method=self.method,
                    url=url,
                    timeout=(self.connect_timeout_ms / 1000, self.timeout_ms / 1000),
                    allow_redirects=self.follow_redirects,
                    verify=self.verify_tls,
                    stream=True
                )
                total_time = (time.perf_counter() - total_start) * 1000

                # 计算各阶段耗时（近似值）
                elapsed = response.elapsed.total_seconds() * 1000
                is_https = url.startswith('https://')

                # 近似拆分各阶段
                tcp_time = max(0, min(elapsed * 0.15, total_time * 0.15))
                tls_time = max(0, min(elapsed * 0.2, total_time * 0.2)) if is_https else 0
                ttfb_time = max(0, elapsed - dns_time - tcp_time - tls_time)
                transfer_time = max(0, total_time - elapsed)

                record = {
                    'timestamp': timestamp,
                    'seq': self._seq,
                    'dns_ms': round(dns_time, 2),
                    'tcp_ms': round(tcp_time, 2),
                    'tls_ms': round(tls_time, 2) if is_https else None,
                    'ttfb_ms': round(ttfb_time, 2),
                    'transfer_ms': round(transfer_time, 2),
                    'total_ms': round(total_time, 2),
                    'http_code': response.status_code,
                    'status': 'success'
                }
                response.close()

            except requests.exceptions.ConnectTimeout:
                record = {
                    'timestamp': timestamp,
                    'seq': self._seq,
                    'dns_ms': None, 'tcp_ms': None, 'tls_ms': None,
                    'ttfb_ms': None, 'transfer_ms': None,
                    'total_ms': None, 'http_code': None,
                    'status': 'timeout'
                }

            except requests.exceptions.ReadTimeout:
                record = {
                    'timestamp': timestamp,
                    'seq': self._seq,
                    'dns_ms': None, 'tcp_ms': None, 'tls_ms': None,
                    'ttfb_ms': None, 'transfer_ms': None,
                    'total_ms': None, 'http_code': None,
                    'status': 'timeout'
                }

            except requests.exceptions.SSLError:
                record = {
                    'timestamp': timestamp,
                    'seq': self._seq,
                    'dns_ms': None, 'tcp_ms': None, 'tls_ms': None,
                    'ttfb_ms': None, 'transfer_ms': None,
                    'total_ms': None, 'http_code': None,
                    'status': 'tls_error'
                }

            except requests.exceptions.ConnectionError:
                record = {
                    'timestamp': timestamp,
                    'seq': self._seq,
                    'dns_ms': None, 'tcp_ms': None, 'tls_ms': None,
                    'ttfb_ms': None, 'transfer_ms': None,
                    'total_ms': None, 'http_code': None,
                    'status': 'error'
                }

            except Exception as e:
                record = {
                    'timestamp': timestamp,
                    'seq': self._seq,
                    'dns_ms': None, 'tcp_ms': None, 'tls_ms': None,
                    'ttfb_ms': None, 'transfer_ms': None,
                    'total_ms': None, 'http_code': None,
                    'status': 'error'
                }
                self.error_occurred.emit(str(e))

            self.result_ready.emit(record)

            # 等待间隔
            if self._running:
                sleep_time = max(0.1, self.interval_ms / 1000 - 0.05)
                end_wait = time.perf_counter() + sleep_time
                while self._running and time.perf_counter() < end_wait:
                    time.sleep(0.05)

        session.close()
        self.finished_signal.emit()

    def stop(self):
        self._running = False
