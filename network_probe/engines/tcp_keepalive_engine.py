"""TCP 长连接拨测引擎 —— 纯 TCP 保活探测（不发送应用层数据）"""
import select
import socket
import struct
import time
import random
import sys
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal


class TcpKeepaliveEngine(QThread):
    """
    TCP 长连接拨测线程（纯 TCP 保活模式）

    工作流程:
        1. 建立 TCP 连接，记录建连耗时
        2. 开启 OS 级 TCP keepalive，设置探测间隔
        3. 以固定间隔检测连接是否仍然存活（通过 select + 非阻塞 recv 探测）
        4. 不发送任何应用层数据，避免被对端因协议不匹配而 RST
        5. 连接异常断开后，按指数退避策略自动重连
        6. 记录每次探活结果、连接/断线事件

    信号:
        result_ready(dict): 每条探测结果（心跳或事件）
        error_occurred(str): 错误消息
        finished_signal(): 拨测完成
    """
    result_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    finished_signal = pyqtSignal()

    # Windows 平台 TCP keepalive ioctl 常量
    SIO_KEEPALIVE_VALS = 0x98000004

    def __init__(self, target: str, port: int = 80,
                 heartbeat_interval_ms: int = 2000,
                 heartbeat_timeout_ms: int = 3000,
                 connect_timeout_ms: int = 5000,
                 parent=None):
        super().__init__(parent)
        self.target = target
        self.port = port
        self.heartbeat_interval_ms = heartbeat_interval_ms
        self.heartbeat_timeout_ms = heartbeat_timeout_ms
        self.connect_timeout_ms = connect_timeout_ms
        self._running = False
        self._seq = 0

        # 会话统计（引擎内部维护，用于生成事件记录）
        self._session_id = 0
        self._session_start_time = 0.0
        self._reconnect_attempt = 0
        self._max_backoff_ms = 30000  # 最大退避 30 秒
        self._base_backoff_ms = 1000  # 基础退避 1 秒

    def run(self):
        self._running = True
        self._seq = 0
        self._session_id = 0

        # 先做一次 DNS 解析，将域名转为 IP（避免每次建连都做 DNS）
        self._resolved_target = self._resolve_host(self.target)
        if self._resolved_target is None:
            # DNS 解析失败，已在 _resolve_host 中发出错误信号
            self.finished_signal.emit()
            return

        sock = None
        try:
            while self._running:
                # ── 建立连接 ──
                sock = self._try_connect()
                if sock is None:
                    # 连接失败，已在 _try_connect 中发出记录和退避
                    continue
                if not self._running:
                    self._safe_close(sock)
                    sock = None
                    break

                # 连接成功，重置重连计数
                self._reconnect_attempt = 0
                self._session_id += 1
                self._session_start_time = time.perf_counter()

                # ── 保活探测循环 ──
                while self._running:
                    # 等待心跳间隔
                    sleep_sec = max(0.1, self.heartbeat_interval_ms / 1000)
                    end_wait = time.perf_counter() + sleep_sec
                    while self._running and time.perf_counter() < end_wait:
                        time.sleep(0.05)

                    if not self._running:
                        break

                    self._seq += 1
                    timestamp = self._now_str()

                    probe_result = self._probe_connection(sock, timestamp)
                    self.result_ready.emit(probe_result)

                    if probe_result.get('status') in ('conn_lost', 'conn_reset', 'error'):
                        # 连接断开，发出断线事件
                        session_duration = time.perf_counter() - self._session_start_time
                        disconnect_record = {
                            'timestamp': timestamp,
                            'seq': self._seq,
                            'event': 'disconnect',
                            'session_id': self._session_id,
                            'session_duration_ms': round(session_duration * 1000, 2),
                            'connect_rtt_ms': None,
                            'heartbeat_rtt_ms': None,
                            'status': 'disconnect',
                        }
                        self.result_ready.emit(disconnect_record)
                        self._safe_close(sock)
                        sock = None
                        break

                # 正常停止时也要关闭 socket
                if sock is not None:
                    self._safe_close(sock)
                    sock = None

                # 如果仍在运行，进入重连
                if self._running:
                    self._reconnect_attempt += 1

        except Exception as e:
            # 顶层异常兜底，防止线程崩溃导致应用闪退
            self.error_occurred.emit(f"引擎异常: {e}")
        finally:
            # 确保 socket 一定被关闭
            if sock is not None:
                self._safe_close(sock)

        self.finished_signal.emit()

    def _resolve_host(self, host: str) -> str | None:
        """将域名解析为 IP 地址，如果已是 IP 则直接返回"""
        try:
            # getaddrinfo 同时支持域名和 IP，返回 (family, type, proto, canonname, sockaddr)
            results = socket.getaddrinfo(host, self.port, socket.AF_INET, socket.SOCK_STREAM)
            if results:
                ip = results[0][4][0]  # 取第一个结果的 IP
                return ip
            self.error_occurred.emit(f"DNS 解析失败: {host} 无结果")
            return None
        except socket.gaierror as e:
            self.error_occurred.emit(f"DNS 解析失败: {host} - {e}")
            return None
        except Exception as e:
            self.error_occurred.emit(f"DNS 解析异常: {host} - {e}")
            return None

    def _try_connect(self) -> socket.socket | None:
        """尝试建立 TCP 连接，失败时按指数退避等待"""
        timestamp = self._now_str()
        self._seq += 1

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.connect_timeout_ms / 1000)

            start = time.perf_counter()
            sock.connect((self._resolved_target, self.port))
            connect_rtt = (time.perf_counter() - start) * 1000

            # 建连成功
            record = {
                'timestamp': timestamp,
                'seq': self._seq,
                'event': 'connect',
                'session_id': self._session_id + 1,
                'session_duration_ms': None,
                'connect_rtt_ms': round(connect_rtt, 2),
                'heartbeat_rtt_ms': None,
                'status': 'connect_ok',
            }
            self.result_ready.emit(record)

            # 设置 TCP keepalive（操作系统级）
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

            # Windows: 通过 SIO_KEEPALIVE_VALS 设置 keepalive 参数
            # ioctl 第二参数需要 3 元素 tuple: (onoff, keepalivetime_ms, keepaliveinterval_ms)
            if sys.platform == 'win32':
                keepalive_time_ms = self.heartbeat_interval_ms   # 空闲多久后开始探测
                keepalive_interval_ms = 1000                     # 探测包间隔 1 秒
                try:
                    sock.ioctl(
                        self.SIO_KEEPALIVE_VALS,
                        (1, keepalive_time_ms, keepalive_interval_ms)
                    )
                except OSError:
                    pass  # 非 Windows 或权限不足时忽略

            # 设置超时用于后续 select/recv 探测
            sock.settimeout(self.heartbeat_timeout_ms / 1000)
            return sock

        except socket.timeout:
            record = {
                'timestamp': timestamp,
                'seq': self._seq,
                'event': 'connect_fail',
                'session_id': self._session_id + 1,
                'session_duration_ms': None,
                'connect_rtt_ms': None,
                'heartbeat_rtt_ms': None,
                'status': 'connect_timeout',
            }
            self.result_ready.emit(record)

        except ConnectionRefusedError:
            record = {
                'timestamp': timestamp,
                'seq': self._seq,
                'event': 'connect_fail',
                'session_id': self._session_id + 1,
                'session_duration_ms': None,
                'connect_rtt_ms': None,
                'heartbeat_rtt_ms': None,
                'status': 'connect_refused',
            }
            self.result_ready.emit(record)

        except OSError as e:
            record = {
                'timestamp': timestamp,
                'seq': self._seq,
                'event': 'connect_fail',
                'session_id': self._session_id + 1,
                'session_duration_ms': None,
                'connect_rtt_ms': None,
                'heartbeat_rtt_ms': None,
                'status': 'connect_error',
            }
            self.result_ready.emit(record)
            self.error_occurred.emit(f"连接失败: {e}")

        # 连接失败 —— 指数退避等待
        if self._running:
            backoff = self._calc_backoff()
            backoff_record = {
                'timestamp': self._now_str(),
                'seq': self._seq,
                'event': 'reconnect_wait',
                'session_id': self._session_id + 1,
                'session_duration_ms': None,
                'connect_rtt_ms': None,
                'heartbeat_rtt_ms': None,
                'reconnect_wait_ms': round(backoff, 0),
                'status': 'reconnecting',
            }
            self.result_ready.emit(backoff_record)

            end_wait = time.perf_counter() + backoff / 1000
            while self._running and time.perf_counter() < end_wait:
                time.sleep(0.05)
            self._reconnect_attempt += 1

        return None

    def _probe_connection(self, sock: socket.socket, timestamp: str) -> dict:
        """
        探测 TCP 连接是否仍然存活（不发送任何应用层数据）

        原理：
            - 使用 select() 检查 socket 是否有可读事件
            - 如果没有可读事件（超时），说明连接静默存活 → 探活成功
            - 如果有可读事件，尝试 recv：
              - recv 返回空 bytes → 对端 FIN，连接关闭
              - recv 抛出 ConnectionResetError → 对端 RST
              - recv 返回数据 → 对端发了数据（不太常见，也算连接存活）
        """
        session_duration_ms = round(
            (time.perf_counter() - self._session_start_time) * 1000, 2
        )

        try:
            # 在 Windows 上，select 需要 socket 处于非阻塞模式才稳定
            sock.setblocking(False)
            try:
                # 用 select 检测 socket 是否有可读事件，超时时间较短
                timeout_sec = min(self.heartbeat_timeout_ms / 1000, 1.0)
                readable, _, exceptional = select.select([sock], [], [sock], timeout_sec)
            finally:
                # 恢复为阻塞+超时模式
                sock.setblocking(True)
                sock.settimeout(self.heartbeat_timeout_ms / 1000)

            if exceptional:
                # socket 异常
                return {
                    'timestamp': timestamp,
                    'seq': self._seq,
                    'event': 'heartbeat',
                    'session_id': self._session_id,
                    'session_duration_ms': session_duration_ms,
                    'connect_rtt_ms': None,
                    'heartbeat_rtt_ms': None,
                    'status': 'error',
                }

            if readable:
                # socket 有可读事件 —— 可能是对端关闭/RST/数据
                try:
                    data = sock.recv(1024)
                    if data:
                        # 对端发了数据（意外但连接存活）
                        return {
                            'timestamp': timestamp,
                            'seq': self._seq,
                            'event': 'heartbeat',
                            'session_id': self._session_id,
                            'session_duration_ms': session_duration_ms,
                            'connect_rtt_ms': None,
                            'heartbeat_rtt_ms': None,
                            'status': 'success',
                        }
                    else:
                        # recv 返回空 = 对端正常关闭（FIN）
                        return {
                            'timestamp': timestamp,
                            'seq': self._seq,
                            'event': 'heartbeat',
                            'session_id': self._session_id,
                            'session_duration_ms': session_duration_ms,
                            'connect_rtt_ms': None,
                            'heartbeat_rtt_ms': None,
                            'status': 'conn_lost',
                        }
                except (ConnectionResetError, ConnectionAbortedError):
                    return {
                        'timestamp': timestamp,
                        'seq': self._seq,
                        'event': 'heartbeat',
                        'session_id': self._session_id,
                        'session_duration_ms': session_duration_ms,
                        'connect_rtt_ms': None,
                        'heartbeat_rtt_ms': None,
                        'status': 'conn_reset',
                    }
                except OSError as e:
                    self.error_occurred.emit(f"探活失败: {e}")
                    return {
                        'timestamp': timestamp,
                        'seq': self._seq,
                        'event': 'heartbeat',
                        'session_id': self._session_id,
                        'session_duration_ms': session_duration_ms,
                        'connect_rtt_ms': None,
                        'heartbeat_rtt_ms': None,
                        'status': 'error',
                    }
            else:
                # select 超时 —— 没有任何事件，连接静默存活
                return {
                    'timestamp': timestamp,
                    'seq': self._seq,
                    'event': 'heartbeat',
                    'session_id': self._session_id,
                    'session_duration_ms': session_duration_ms,
                    'connect_rtt_ms': None,
                    'heartbeat_rtt_ms': None,
                    'status': 'success',
                }

        except (ConnectionResetError, ConnectionAbortedError):
            return {
                'timestamp': timestamp,
                'seq': self._seq,
                'event': 'heartbeat',
                'session_id': self._session_id,
                'session_duration_ms': session_duration_ms,
                'connect_rtt_ms': None,
                'heartbeat_rtt_ms': None,
                'status': 'conn_reset',
            }

        except BrokenPipeError:
            return {
                'timestamp': timestamp,
                'seq': self._seq,
                'event': 'heartbeat',
                'session_id': self._session_id,
                'session_duration_ms': session_duration_ms,
                'connect_rtt_ms': None,
                'heartbeat_rtt_ms': None,
                'status': 'conn_lost',
            }

        except OSError as e:
            self.error_occurred.emit(f"探活失败: {e}")
            return {
                'timestamp': timestamp,
                'seq': self._seq,
                'event': 'heartbeat',
                'session_id': self._session_id,
                'session_duration_ms': session_duration_ms,
                'connect_rtt_ms': None,
                'heartbeat_rtt_ms': None,
                'status': 'error',
            }

    def _calc_backoff(self) -> float:
        """计算指数退避时间（ms），带随机抖动"""
        base = self._base_backoff_ms * (2 ** min(self._reconnect_attempt, 10))
        capped = min(base, self._max_backoff_ms)
        # 添加 ±20% 随机抖动
        jitter = capped * 0.2 * (random.random() * 2 - 1)
        return max(self._base_backoff_ms, capped + jitter)

    @staticmethod
    def _safe_close(sock: socket.socket):
        """安全关闭 socket"""
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass

    @staticmethod
    def _now_str() -> str:
        now = datetime.now()
        return now.strftime('%Y-%m-%d %H:%M:%S.') + f"{now.microsecond // 1000:03d}"

    def stop(self):
        self._running = False
