"""即时拨测面板"""
import os
import time
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QRadioButton, QPushButton, QTextEdit, QButtonGroup,
    QFileDialog, QMessageBox, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QFont, QTextCursor, QColor, QTextCharFormat

from engines.ping_engine import PingEngine
from engines.dns_engine import DnsEngine
from engines.curl_engine import CurlEngine
from engines.tcp_keepalive_engine import TcpKeepaliveEngine
from storage.manager import StorageManager
from utils.validators import parse_target_with_port, is_ip_address


class InstantProbePanel(QWidget):
    """即时拨测功能面板"""

    def __init__(self, storage: StorageManager, status_callback=None, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.status_callback = status_callback
        self.engine = None
        self.current_record_dir = None
        self.records = []
        self.start_time = None
        self.auto_scroll = True
        self._seq_count = 0
        self._success_count = 0
        self._loss_count = 0
        self._rtt_sum = 0.0
        self._last_10_rtts = []
        self._viewing_history = False  # 标记当前是否正在查看非当前任务的历史记录

        self._init_ui()
        self._load_history()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 8, 12, 8)

        # ── 输入区域 ──
        input_frame = QFrame()
        input_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        input_frame.setStyleSheet("QFrame { background: #f8f9fa; border-radius: 6px; padding: 8px; }")
        input_layout = QVBoxLayout(input_frame)
        input_layout.setSpacing(8)

        # 目标地址行
        addr_row = QHBoxLayout()
        addr_label = QLabel("目标地址：")
        addr_label.setFixedWidth(70)
        addr_label.setFont(QFont("Microsoft YaHei", 10))
        self.addr_input = QLineEdit()
        self.addr_input.setPlaceholderText("输入 地址:端口，如 8.8.8.8:53 或 www.baidu.com:443")
        self.addr_input.setFont(QFont("Microsoft YaHei", 10))
        self.addr_input.setMinimumHeight(32)
        self.addr_error = QLabel("")
        self.addr_error.setStyleSheet("color: red; font-size: 12px;")
        self.addr_error.setVisible(False)
        addr_row.addWidget(addr_label)
        addr_row.addWidget(self.addr_input)
        input_layout.addLayout(addr_row)
        input_layout.addWidget(self.addr_error)

        # 拨测方式行
        method_row = QHBoxLayout()
        method_label = QLabel("拨测方式：")
        method_label.setFixedWidth(70)
        method_label.setFont(QFont("Microsoft YaHei", 10))
        self.method_group = QButtonGroup()
        self.radio_ping = QRadioButton("Ping")
        self.radio_dns = QRadioButton("DNS")
        self.radio_curl = QRadioButton("Curl")
        self.radio_keepalive = QRadioButton("长连接")
        self.radio_ping.setChecked(True)
        self.radio_ping.setFont(QFont("Microsoft YaHei", 10))
        self.radio_dns.setFont(QFont("Microsoft YaHei", 10))
        self.radio_curl.setFont(QFont("Microsoft YaHei", 10))
        self.radio_keepalive.setFont(QFont("Microsoft YaHei", 10))
        self.method_group.addButton(self.radio_ping, 0)
        self.method_group.addButton(self.radio_dns, 1)
        self.method_group.addButton(self.radio_curl, 2)
        self.method_group.addButton(self.radio_keepalive, 3)
        self.radio_ping.setToolTip("ICMP协议探测，测量网络连通性和往返时延")
        self.radio_dns.setToolTip("DNS域名解析探测，测量DNS查询耗时和结果")
        self.radio_curl.setToolTip("HTTP(S)请求探测，测量各阶段耗时和HTTP状态码")
        self.radio_keepalive.setToolTip("TCP长连接探测，持续建立TCP连接并发送心跳，测量建连成功率、心跳RTT和连接稳定性")
        method_row.addWidget(method_label)
        method_row.addWidget(self.radio_ping)
        method_row.addWidget(self.radio_dns)
        method_row.addWidget(self.radio_curl)
        method_row.addWidget(self.radio_keepalive)
        method_row.addStretch()
        input_layout.addLayout(method_row)

        # 按钮行
        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("▶ 开始拨测")
        self.btn_start.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        self.btn_start.setMinimumHeight(36)
        self.btn_start.setStyleSheet("""
            QPushButton { background: #1a73e8; color: white; border-radius: 4px; padding: 4px 20px; }
            QPushButton:hover { background: #1557b0; }
            QPushButton:disabled { background: #ccc; }
        """)
        self.btn_stop = QPushButton("⏹ 停止")
        self.btn_stop.setFont(QFont("Microsoft YaHei", 10))
        self.btn_stop.setMinimumHeight(36)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("""
            QPushButton { background: #d93025; color: white; border-radius: 4px; padding: 4px 20px; }
            QPushButton:hover { background: #b71c1c; }
            QPushButton:disabled { background: #ccc; color: #888; }
        """)
        btn_row.addWidget(self.btn_start)
        btn_row.addWidget(self.btn_stop)
        btn_row.addStretch()
        input_layout.addLayout(btn_row)

        layout.addWidget(input_frame)

        # ── 历史记录切换栏 ──
        history_row = QHBoxLayout()
        history_label = QLabel("历史记录：")
        history_label.setFont(QFont("Microsoft YaHei", 9))
        history_row.addWidget(history_label)

        self.history_buttons = []
        for i in range(3):
            btn = QPushButton(f"第{i+1}次")
            btn.setCheckable(True)
            btn.setVisible(False)
            btn.setFont(QFont("Microsoft YaHei", 9))
            btn.setStyleSheet("""
                QPushButton { padding: 3px 10px; border: 1px solid #ddd; border-radius: 3px; }
                QPushButton:checked { background: #1a73e8; color: white; border-color: #1a73e8; }
                QPushButton:hover { background: #e8f0fe; }
            """)
            btn.clicked.connect(lambda checked, idx=i: self._switch_history(idx))
            history_row.addWidget(btn)
            self.history_buttons.append(btn)

        history_row.addStretch()

        self.btn_export = QPushButton("📄 导出日志")
        self.btn_export.setFont(QFont("Microsoft YaHei", 9))
        self.btn_export.setEnabled(False)
        self.btn_export.setStyleSheet("""
            QPushButton { padding: 3px 12px; border: 1px solid #1a73e8; color: #1a73e8; border-radius: 3px; }
            QPushButton:hover { background: #e8f0fe; }
            QPushButton:disabled { border-color: #ccc; color: #ccc; }
        """)
        history_row.addWidget(self.btn_export)
        layout.addLayout(history_row)

        # ── 实时结果窗口 ──
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setFont(QFont("Consolas", 10))
        self.result_text.setStyleSheet("""
            QTextEdit {
                background: #1e1e2e; color: #cdd6f4; border-radius: 6px;
                padding: 8px; selection-background-color: #45475a;
            }
        """)
        self.result_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.result_text, stretch=1)

        # ── 回到最新按钮 ──
        self.btn_scroll_bottom = QPushButton("↓ 回到最新")
        self.btn_scroll_bottom.setFont(QFont("Microsoft YaHei", 9))
        self.btn_scroll_bottom.setVisible(False)
        self.btn_scroll_bottom.setStyleSheet("""
            QPushButton { background: rgba(26,115,232,0.9); color: white;
                         border-radius: 12px; padding: 4px 12px; }
        """)
        layout.addWidget(self.btn_scroll_bottom, alignment=Qt.AlignmentFlag.AlignCenter)

        # ── 连接信号 ──
        self.btn_start.clicked.connect(self._start_probe)
        self.btn_stop.clicked.connect(self._stop_probe)
        self.btn_export.clicked.connect(self._export_log)
        self.btn_scroll_bottom.clicked.connect(self._scroll_to_bottom)
        self.result_text.verticalScrollBar().valueChanged.connect(self._on_scroll)

        # 状态更新定时器
        self._status_timer = QTimer()
        self._status_timer.timeout.connect(self._update_status)

    def _get_protocol(self) -> str:
        if self.radio_ping.isChecked():
            return 'ping'
        elif self.radio_dns.isChecked():
            return 'dns'
        elif self.radio_curl.isChecked():
            return 'curl'
        else:
            return 'keepalive'

    def _start_probe(self):
        raw_input = self.addr_input.text().strip()
        protocol = self._get_protocol()

        # 输入校验：解析 地址:端口
        host, port, error_msg = parse_target_with_port(raw_input)
        if error_msg:
            self.addr_error.setText(f"⚠ {error_msg}")
            self.addr_error.setVisible(True)
            return

        if protocol == 'dns' and is_ip_address(host):
            self.addr_error.setText("⚠ DNS拨测需要输入域名，不支持纯IP地址")
            self.addr_error.setVisible(True)
            return

        self.addr_error.setVisible(False)

        # 创建记录（target 保存完整的 host:port）
        target_display = f"{host}:{port}"
        self.current_record_dir = self.storage.create_record('instant', protocol, target_display)
        self.records = []
        self._seq_count = 0
        self._success_count = 0
        self._loss_count = 0
        self._rtt_sum = 0.0
        self._last_10_rtts = []
        self.start_time = time.time()
        self.auto_scroll = True
        self._viewing_history = False

        # 清空结果窗口
        self.result_text.clear()

        # UI状态
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_export.setEnabled(False)
        self.addr_input.setEnabled(False)
        self.radio_ping.setEnabled(False)
        self.radio_dns.setEnabled(False)
        self.radio_curl.setEnabled(False)
        self.radio_keepalive.setEnabled(False)

        # 创建引擎（传入端口参数）
        # DNS拨测：端口是DNS服务器端口（默认53），不是目标域名的服务端口
        if protocol == 'ping':
            self.engine = PingEngine(host, port=port)
        elif protocol == 'dns':
            self.engine = DnsEngine(host, port=53)
        elif protocol == 'curl':
            self.engine = CurlEngine(host, port=port)
        elif protocol == 'keepalive':
            self.engine = TcpKeepaliveEngine(host, port=port)

        self.engine.result_ready.connect(self._on_result)
        self.engine.error_occurred.connect(self._on_error)
        self.engine.finished_signal.connect(self._on_finished)
        self.engine.start()

        self._status_timer.start(1000)
        self._load_history()

    def _stop_probe(self):
        if self.engine:
            self.engine.stop()

    @pyqtSlot(dict)
    def _on_result(self, record: dict):
        """处理每条探测结果"""
        protocol = self._get_protocol()

        # 更新计数器
        self._seq_count += 1
        if record.get('status') in ('success', 'connect_ok'):
            self._success_count += 1
            rtt = record.get('rtt_ms') or record.get('latency_ms') or record.get('total_ms') or record.get('heartbeat_rtt_ms') or record.get('connect_rtt_ms') or 0
            self._rtt_sum += rtt
            self._last_10_rtts.append(rtt)
            if len(self._last_10_rtts) > 10:
                self._last_10_rtts.pop(0)
        else:
            self._loss_count += 1

        # 存储（始终保存，不管是否在查看历史）
        self.records.append(record)
        self.storage.append_record(self.current_record_dir, protocol, record)

        # 仅当用户没有切换到查看其他历史记录时，才更新结果显示
        if not self._viewing_history:
            line = self._format_result_line(record, protocol)
            self._append_result(line, record.get('status') in ('success', 'connect_ok'))

    def _format_result_line(self, record: dict, protocol: str) -> str:
        ts = record.get('timestamp', '')
        seq = record.get('seq', 0)
        status = record.get('status', '')

        status_map = {
            'success': '成功', 'timeout': '超时', 'unreachable': '不可达',
            'error': '错误', 'tls_error': 'TLS失败',
            'connect_ok': '建连成功', 'connect_timeout': '建连超时',
            'connect_refused': '连接拒绝', 'connect_error': '建连失败',
            'conn_lost': '连接丢失', 'conn_reset': '连接重置',
            'disconnect': '断线', 'reconnecting': '重连中',
        }
        status_text = status_map.get(status, status)

        if protocol == 'ping':
            rtt = f"{record.get('rtt_ms')}ms" if record.get('rtt_ms') is not None else '--'
            ttl = str(record.get('ttl', '--')) if record.get('ttl') is not None else '--'
            return f"[{ts}]  seq={seq:<5} RTT={rtt:<10} TTL={ttl:<5} 状态={status_text}"

        elif protocol == 'dns':
            lat = f"{record.get('latency_ms')}ms" if record.get('latency_ms') is not None else '--'
            ip = record.get('answer_ip', '--') or '--'
            return f"[{ts}]  seq={seq:<5} 耗时={lat:<10} 结果={ip:<18} 状态={status_text}"

        elif protocol == 'curl':
            dns = f"{record.get('dns_ms')}ms" if record.get('dns_ms') is not None else '--'
            tcp = f"{record.get('tcp_ms')}ms" if record.get('tcp_ms') is not None else '--'
            tls = f"{record.get('tls_ms')}ms" if record.get('tls_ms') is not None else '--'
            ttfb = f"{record.get('ttfb_ms')}ms" if record.get('ttfb_ms') is not None else '--'
            total = f"{record.get('total_ms')}ms" if record.get('total_ms') is not None else '--'
            code = str(record.get('http_code', '--')) if record.get('http_code') is not None else '--'
            return (f"[{ts}]  seq={seq:<4} DNS={dns:<8} TCP={tcp:<8} TLS={tls:<8} "
                    f"TTFB={ttfb:<8} 总计={total:<10} HTTP={code:<5} 状态={status_text}")

        elif protocol == 'keepalive':
            event = record.get('event', '')
            event_map = {'connect': '🔗建连', 'connect_fail': '❌建连失败',
                         'heartbeat': '💓心跳', 'disconnect': '🔌断线',
                         'reconnect_wait': '⏳重连等待'}
            event_text = event_map.get(event, event)
            sid = record.get('session_id', '--')
            conn_rtt = f"{record.get('connect_rtt_ms')}ms" if record.get('connect_rtt_ms') is not None else '--'
            hb_rtt = f"{record.get('heartbeat_rtt_ms')}ms" if record.get('heartbeat_rtt_ms') is not None else '--'
            sess_dur = ''
            if record.get('session_duration_ms') is not None:
                dur_ms = record['session_duration_ms']
                if dur_ms >= 60000:
                    sess_dur = f"{dur_ms/60000:.1f}min"
                elif dur_ms >= 1000:
                    sess_dur = f"{dur_ms/1000:.1f}s"
                else:
                    sess_dur = f"{dur_ms:.0f}ms"
            return (f"[{ts}]  seq={seq:<4} {event_text:<10} 会话#{sid:<3} "
                    f"建连RTT={conn_rtt:<10} 心跳RTT={hb_rtt:<10} "
                    f"会话时长={sess_dur:<10} 状态={status_text}")

        return f"[{ts}]  seq={seq}  状态={status_text}"

    def _append_result(self, line: str, is_success: bool):
        """追加一行结果到显示窗口"""
        cursor = self.result_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        if is_success:
            fmt.setForeground(QColor("#a6e3a1"))  # 绿色
        else:
            fmt.setForeground(QColor("#f38ba8"))  # 红色

        cursor.insertText(line + '\n', fmt)

        if self.auto_scroll:
            self.result_text.setTextCursor(cursor)
            self.result_text.ensureCursorVisible()

    def _on_scroll(self):
        """检测用户是否手动上翻"""
        scrollbar = self.result_text.verticalScrollBar()
        at_bottom = scrollbar.value() >= scrollbar.maximum() - 30
        if not at_bottom and self.engine and self.engine.isRunning():
            self.auto_scroll = False
            self.btn_scroll_bottom.setVisible(True)
        elif at_bottom:
            self.auto_scroll = True
            self.btn_scroll_bottom.setVisible(False)

    def _scroll_to_bottom(self):
        self.auto_scroll = True
        self.btn_scroll_bottom.setVisible(False)
        cursor = self.result_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.result_text.setTextCursor(cursor)

    @pyqtSlot(str)
    def _on_error(self, msg: str):
        self._append_result(f"[错误] {msg}", False)

    @pyqtSlot()
    def _on_finished(self):
        """拨测完成"""
        self._status_timer.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_export.setEnabled(True)
        self.addr_input.setEnabled(True)
        self.radio_ping.setEnabled(True)
        self.radio_dns.setEnabled(True)
        self.radio_curl.setEnabled(True)
        self.radio_keepalive.setEnabled(True)

        # 更新 meta
        if self.current_record_dir and self.start_time:
            duration = time.time() - self.start_time
            self.storage.update_meta(self.current_record_dir, {
                'end_time': datetime.now().isoformat(timespec='milliseconds'),
                'duration_sec': round(duration, 1),
                'total_sent': self._seq_count,
                'total_success': self._success_count,
                'loss_rate': round(self._loss_count / self._seq_count * 100, 2) if self._seq_count > 0 else 0
            })

        self._load_history()
        self._update_status()

    def _update_status(self):
        """更新状态栏"""
        if self.status_callback and self.start_time:
            elapsed = time.time() - self.start_time
            mins = int(elapsed) // 60
            secs = int(elapsed) % 60
            avg_rtt = (self._rtt_sum / self._success_count) if self._success_count > 0 else 0
            last10_avg = sum(self._last_10_rtts) / len(self._last_10_rtts) if self._last_10_rtts else 0

            status = (f"即时拨测 | 已探测: {self._seq_count}  "
                      f"成功: {self._success_count}  丢包: {self._loss_count}  "
                      f"近10次均RTT: {last10_avg:.1f}ms | "
                      f"运行: {mins}分{secs:02d}秒")
            self.status_callback(status)

    def _load_history(self):
        """加载并显示历史记录按钮"""
        records = self.storage.get_records('instant')
        for i, btn in enumerate(self.history_buttons):
            if i < len(records):
                meta = records[i]
                protocol_map = {'ping': 'Ping', 'dns': 'DNS', 'curl': 'Curl', 'keepalive': '长连接'}
                protocol_text = protocol_map.get(meta.get('protocol', ''), meta.get('protocol', ''))
                start_time = meta.get('start_time', '')[:16].replace('T', ' ')
                label = f"第{i+1}次 {start_time} {protocol_text}"
                if meta.get('end_time') is None:
                    label += " (进行中)"
                btn.setText(label)
                btn.setVisible(True)
                btn.setProperty('record_dir', meta.get('_dir'))
            else:
                btn.setVisible(False)

        # 高亮当前记录
        for btn in self.history_buttons:
            btn.setChecked(btn.property('record_dir') == self.current_record_dir)

    def _switch_history(self, idx: int):
        """切换历史记录显示"""
        records = self.storage.get_records('instant')
        if idx >= len(records):
            return

        for i, btn in enumerate(self.history_buttons):
            btn.setChecked(i == idx)

        meta = records[idx]
        record_dir = meta.get('_dir')
        protocol = meta.get('protocol', 'ping')

        # 判断是否正在查看非当前运行的任务
        is_current_task = (record_dir == self.current_record_dir)
        engine_running = self.engine and self.engine.isRunning()

        if engine_running and not is_current_task:
            # 正在运行任务，但用户切换到查看其他历史记录
            self._viewing_history = True
        else:
            self._viewing_history = False

        # 加载历史数据并显示
        data = self.storage.load_records_data(record_dir)
        self.result_text.clear()
        for r in data:
            line = self._format_result_line(r, protocol)
            is_success = r.get('status') in ('success', 'connect_ok')
            self._append_result(line, is_success)

        # 更新导出按钮状态
        self.btn_export.setEnabled(meta.get('end_time') is not None)
        self.btn_export.setProperty('export_dir', record_dir)

    def _export_log(self):
        """导出日志"""
        export_dir = self.btn_export.property('export_dir') or self.current_record_dir
        if not export_dir:
            return

        meta = self.storage.load_meta(export_dir)
        if not meta:
            return

        default_name = (f"probe_instant_{meta.get('protocol', 'ping')}_"
                        f"{meta.get('target', 'unknown').replace('.', '_').replace(':', '_')}_"
                        f"{meta.get('start_time', '')[:19].replace('T', '_').replace(':', '').replace('-', '')}.txt")

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出拨测日志", default_name, "文本文件 (*.txt);;所有文件 (*)"
        )

        if file_path:
            try:
                self.storage.export_log(export_dir, file_path)
                reply = QMessageBox.information(
                    self, "导出成功",
                    f"日志已成功导出到：\n{file_path}",
                    QMessageBox.StandardButton.Ok
                )
            except Exception as e:
                QMessageBox.critical(self, "导出失败", f"导出失败：{str(e)}")
