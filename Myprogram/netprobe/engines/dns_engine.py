"""DNS 拨测引擎"""
import time
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal

try:
    import dns.resolver
    import dns.rdatatype
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False


class DnsEngine(QThread):
    """
    DNS 拨测线程
    信号:
        result_ready(dict): 每条探测结果
        error_occurred(str): 错误消息
        finished_signal(): 拨测完成
    """
    result_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, target: str, dns_server: str = None,
                 query_type: str = 'A', timeout_ms: int = 2000,
                 interval_ms: int = 500, parent=None):
        super().__init__(parent)
        self.target = target
        self.dns_server = dns_server
        self.query_type = query_type
        self.timeout_ms = timeout_ms
        self.interval_ms = interval_ms
        self._running = False
        self._seq = 0

    def run(self):
        if not DNS_AVAILABLE:
            self.error_occurred.emit('dnspython 未安装，请运行: pip install dnspython')
            self.finished_signal.emit()
            return

        self._running = True
        self._seq = 0

        # 配置 resolver
        resolver = dns.resolver.Resolver()
        if self.dns_server:
            resolver.nameservers = [self.dns_server]
        resolver.timeout = self.timeout_ms / 1000
        resolver.lifetime = self.timeout_ms / 1000

        while self._running:
            self._seq += 1
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.') + f"{datetime.now().microsecond // 1000:03d}"

            try:
                start_time = time.perf_counter()
                rdtype = dns.rdatatype.from_text(self.query_type)
                answers = resolver.resolve(self.target, rdtype)
                elapsed = (time.perf_counter() - start_time) * 1000

                # 提取解析结果
                ips = []
                for rdata in answers:
                    ips.append(str(rdata))
                answer_ip = ','.join(ips) if ips else '--'

                # 获取 TTL
                ttl = answers.rrset.ttl if answers.rrset else None

                record = {
                    'timestamp': timestamp,
                    'seq': self._seq,
                    'latency_ms': round(elapsed, 2),
                    'answer_ip': answer_ip,
                    'rcode': 'NOERROR',
                    'ttl': ttl,
                    'status': 'success'
                }

            except dns.resolver.NXDOMAIN:
                elapsed = (time.perf_counter() - start_time) * 1000
                record = {
                    'timestamp': timestamp,
                    'seq': self._seq,
                    'latency_ms': round(elapsed, 2),
                    'answer_ip': '--',
                    'rcode': 'NXDOMAIN',
                    'ttl': None,
                    'status': 'error'
                }

            except dns.resolver.NoAnswer:
                elapsed = (time.perf_counter() - start_time) * 1000
                record = {
                    'timestamp': timestamp,
                    'seq': self._seq,
                    'latency_ms': round(elapsed, 2),
                    'answer_ip': '--',
                    'rcode': 'NOERROR',
                    'ttl': None,
                    'status': 'error'
                }

            except dns.resolver.Timeout:
                record = {
                    'timestamp': timestamp,
                    'seq': self._seq,
                    'latency_ms': None,
                    'answer_ip': '--',
                    'rcode': 'TIMEOUT',
                    'ttl': None,
                    'status': 'timeout'
                }

            except dns.resolver.NoNameservers:
                record = {
                    'timestamp': timestamp,
                    'seq': self._seq,
                    'latency_ms': None,
                    'answer_ip': '--',
                    'rcode': 'SERVFAIL',
                    'ttl': None,
                    'status': 'error'
                }

            except Exception as e:
                record = {
                    'timestamp': timestamp,
                    'seq': self._seq,
                    'latency_ms': None,
                    'answer_ip': '--',
                    'rcode': str(e),
                    'ttl': None,
                    'status': 'error'
                }
                self.error_occurred.emit(str(e))

            self.result_ready.emit(record)

            # 等待间隔
            if self._running:
                sleep_time = max(0.01, self.interval_ms / 1000 - 0.01)
                end_wait = time.perf_counter() + sleep_time
                while self._running and time.perf_counter() < end_wait:
                    time.sleep(0.05)

        self.finished_signal.emit()

    def stop(self):
        self._running = False
