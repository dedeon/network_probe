"""长时间拨测面板"""
import os
import time
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QRadioButton, QPushButton, QTextEdit, QButtonGroup,
    QFileDialog, QMessageBox, QFrame, QProgressBar,
    QSizePolicy, QGridLayout, QSpinBox, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QFont, QTextCursor, QColor, QTextCharFormat

from ..engines.ping_engine import PingEngine
from ..engines.dns_engine import DnsEngine
from ..storage.manager import StorageManager
from ..utils.validators import validate_target, is_ip_address
from ..utils.statistics import calculate_ping_stats, calculate_dns_stats, quality_rating


class LongtermProbePanel(QWidget):
    """长时间拨测功能面板"""

    def __init__(self, storage: StorageManager, status_callback=None, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.status_callback = status_callback
        self.engine = None
        self.current_record_dir = None
        self.records = []
        self.start_time = None
        self.planned_duration_sec = 0
        self.auto_scroll = True
        self._seq_count = 0
        self._success_count = 0
        self._loss_count = 0
        self._rtt_sum = 0.0
        self._last_10_rtts = []

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
        self.addr_input.setPlaceholderText("输入 IP 地址或域名")
        self.addr_input.setFont(QFont("Microsoft YaHei", 10))
        self.addr_input.setMinimumHeight(32)
        self.addr_error = QLabel("")
        self.addr_error.setStyleSheet("color: red; font-size: 12px;")
        self.addr_error.setVisible(False)
        addr_row.addWidget(addr_label)
        addr_row.addWidget(self.addr_input)
        input_layout.addLayout(addr_row)
        input_layout.addWidget(self.addr_error)

        # 拨测时长行
        dur_row = QHBoxLayout()
        dur_label = QLabel("拨测时长：")
        dur_label.setFixedWidth(70)
        dur_label.setFont(QFont("Microsoft YaHei", 10))
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 1440)
        self.duration_spin.setValue(60)
        self.duration_spin.setSuffix(" 分钟")
        self.duration_spin.setFont(QFont("Microsoft YaHei", 10))
        self.duration_spin.setMinimumHeight(32)
        self.duration_spin.setFixedWidth(150)
        self.duration_spin.setToolTip("拨测时长范围：1~1440分钟（最长24小时）")
        dur_row.addWidget(dur_label)
        dur_row.addWidget(self.duration_spin)
        dur_row.addStretch()
        input_layout.addLayout(dur_row)

        # 拨测方式行
        method_row = QHBoxLayout()
        method_label = QLabel("拨测方式：")
        method_label.setFixedWidth(70)
        method_label.setFont(QFont("Microsoft YaHei", 10))
        self.method_group = QButtonGroup()
        self.radio_ping = QRadioButton("Ping")
        self.radio_dns = QRadioButton("DNS")
        self.radio_ping.setChecked(True)
        self.radio_ping.setFont(QFont("Microsoft YaHei", 10))
        self.radio_dns.setFont(QFont("Microsoft YaHei", 10))
        self.method_group.addButton(self.radio_ping, 0)
        self.method_group.addButton(self.radio_dns, 1)
        method_row.addWidget(method_label)
        method_row.addWidget(self.radio_ping)
        method_row.addWidget(self.radio_dns)
        method_row.addStretch()
        input_layout.addLayout(method_row)

        # 按钮 + 进度行
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

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setMinimumHeight(20)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { border: 1px solid #ddd; border-radius: 4px; text-align: center; }
            QProgressBar::chunk { background: #1a73e8; border-radius: 3px; }
        """)
        self.progress_label = QLabel("")
        self.progress_label.setFont(QFont("Microsoft YaHei", 9))
        self.progress_label.setVisible(False)
        btn_row.addWidget(self.progress_bar)
        btn_row.addWidget(self.progress_label)
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
        self.result_text.setMinimumHeight(150)
        layout.addWidget(self.result_text, stretch=1)

        # 回到最新按钮
        self.btn_scroll_bottom = QPushButton("↓ 回到最新")
        self.btn_scroll_bottom.setFont(QFont("Microsoft YaHei", 9))
        self.btn_scroll_bottom.setVisible(False)
        self.btn_scroll_bottom.setStyleSheet("""
            QPushButton { background: rgba(26,115,232,0.9); color: white;
                         border-radius: 12px; padding: 4px 12px; }
        """)
        layout.addWidget(self.btn_scroll_bottom, alignment=Qt.AlignmentFlag.AlignCenter)

        # ── 统计结果面板（可滚动） ──
        self.stats_frame = QFrame()
        self.stats_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        self.stats_frame.setStyleSheet("QFrame { background: #f0f4f8; border-radius: 6px; padding: 8px; }")
        self.stats_frame.setVisible(False)
        self.stats_layout = QVBoxLayout(self.stats_frame)

        # 统计标题
        self.stats_title = QLabel("📊 拨测统计结果")
        self.stats_title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        self.stats_title.setStyleSheet("color: #1a478a;")
        self.stats_layout.addWidget(self.stats_title)

        self.stats_info = QLabel("")
        self.stats_info.setFont(QFont("Microsoft YaHei", 9))
        self.stats_info.setWordWrap(True)
        self.stats_layout.addWidget(self.stats_info)

        # 统计数据网格
        self.stats_grid_widget = QWidget()
        self.stats_grid = QGridLayout(self.stats_grid_widget)
        self.stats_layout.addWidget(self.stats_grid_widget)

        # 质量评级
        self.rating_label = QLabel("")
        self.rating_label.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        self.rating_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stats_layout.addWidget(self.rating_label)

        layout.addWidget(self.stats_frame)

        # ── 连接信号 ──
        self.btn_start.clicked.connect(self._start_probe)
        self.btn_stop.clicked.connect(self._stop_probe)
        self.btn_export.clicked.connect(self._export_log)
        self.btn_scroll_bottom.clicked.connect(self._scroll_to_bottom)
        self.result_text.verticalScrollBar().valueChanged.connect(self._on_scroll)

        # 定时器
        self._status_timer = QTimer()
        self._status_timer.timeout.connect(self._update_progress)

    def _get_protocol(self) -> str:
        return 'ping' if self.radio_ping.isChecked() else 'dns'

    def _start_probe(self):
        target = self.addr_input.text().strip()
        protocol = self._get_protocol()
        duration_min = self.duration_spin.value()

        # 输入校验
        valid, addr_type = validate_target(target)
        if not valid:
            self.addr_error.setText("⚠ 请输入有效的 IP 地址或域名")
            self.addr_error.setVisible(True)
            return

        if protocol == 'dns' and is_ip_address(target):
            self.addr_error.setText("⚠ DNS拨测需要输入域名，不支持纯IP地址")
            self.addr_error.setVisible(True)
            return

        self.addr_error.setVisible(False)

        # 创建记录
        self.planned_duration_sec = duration_min * 60
        self.current_record_dir = self.storage.create_record(
            'longterm', protocol, target, planned_duration_min=duration_min
        )
        self.records = []
        self._seq_count = 0
        self._success_count = 0
        self._loss_count = 0
        self._rtt_sum = 0.0
        self._last_10_rtts = []
        self.start_time = time.time()
        self.auto_scroll = True

        # 清空结果和统计
        self.result_text.clear()
        self.stats_frame.setVisible(False)

        # UI状态
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_export.setEnabled(False)
        self.addr_input.setEnabled(False)
        self.duration_spin.setEnabled(False)
        self.radio_ping.setEnabled(False)
        self.radio_dns.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_label.setVisible(True)

        # 创建引擎
        if protocol == 'ping':
            self.engine = PingEngine(target)
        elif protocol == 'dns':
            self.engine = DnsEngine(target)

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
        if record.get('status') == 'success':
            self._success_count += 1
            rtt = record.get('rtt_ms') or record.get('latency_ms') or 0
            self._rtt_sum += rtt
            self._last_10_rtts.append(rtt)
            if len(self._last_10_rtts) > 10:
                self._last_10_rtts.pop(0)
        else:
            self._loss_count += 1

        # 存储
        self.records.append(record)
        self.storage.append_record(self.current_record_dir, protocol, record)

        # 格式化显示
        line = self._format_result_line(record, protocol)
        self._append_result(line, record.get('status') == 'success')

        # 检查是否到时间
        if self.start_time and time.time() - self.start_time >= self.planned_duration_sec:
            self._stop_probe()

    def _format_result_line(self, record: dict, protocol: str) -> str:
        ts = record.get('timestamp', '')
        seq = record.get('seq', 0)
        status = record.get('status', '')
        status_map = {
            'success': '成功', 'timeout': '超时', 'unreachable': '不可达',
            'error': '错误', 'tls_error': 'TLS失败'
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
        return f"[{ts}]  seq={seq}  状态={status_text}"

    def _append_result(self, line: str, is_success: bool):
        cursor = self.result_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        if is_success:
            fmt.setForeground(QColor("#a6e3a1"))
        else:
            fmt.setForeground(QColor("#f38ba8"))
        cursor.insertText(line + '\n', fmt)
        if self.auto_scroll:
            self.result_text.setTextCursor(cursor)
            self.result_text.ensureCursorVisible()

    def _on_scroll(self):
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
        """拨测完成 - 计算统计并显示"""
        self._status_timer.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_export.setEnabled(True)
        self.addr_input.setEnabled(True)
        self.duration_spin.setEnabled(True)
        self.radio_ping.setEnabled(True)
        self.radio_dns.setEnabled(True)
        self.progress_bar.setValue(100)

        protocol = self._get_protocol()

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

        # 计算统计
        if self.records:
            if protocol == 'ping':
                stats = calculate_ping_stats(self.records)
                rating_enum, rating_text, rating_stars = quality_rating(
                    stats.get('loss_rate', 0),
                    stats.get('rtt_avg', 0),
                    stats.get('jitter_avg', 0)
                )
                stats['rating'] = {'enum': rating_enum, 'text': rating_text, 'stars': rating_stars}
                self._show_ping_stats(stats)
            elif protocol == 'dns':
                stats = calculate_dns_stats(self.records)
                rating_enum, rating_text, rating_stars = quality_rating(
                    100 - stats.get('success_rate', 100),
                    stats.get('latency_avg', 0),
                    stats.get('jitter_avg', 0)
                )
                stats['rating'] = {'enum': rating_enum, 'text': rating_text, 'stars': rating_stars}
                self._show_dns_stats(stats)

            # 保存统计
            if self.current_record_dir:
                self.storage.save_stats(self.current_record_dir, stats)

        self._load_history()

    def _show_ping_stats(self, stats: dict):
        """显示Ping统计面板"""
        self.stats_frame.setVisible(True)

        meta = self.storage.load_meta(self.current_record_dir)
        target = meta.get('target', '') if meta else ''
        duration_min = meta.get('planned_duration_min', '') if meta else ''
        start = meta.get('start_time', '')[:19].replace('T', ' ') if meta else ''
        end = meta.get('end_time', '')[:19].replace('T', ' ') if meta else ''

        self.stats_info.setText(
            f"目标：{target}    方式：Ping    时长：{duration_min}分钟\n"
            f"开始：{start}    结束：{end}"
        )

        # 清空网格
        while self.stats_grid.count():
            item = self.stats_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 发包统计列
        self._add_stat_section("📦 发包统计", [
            ("总发包数", str(stats.get('sent_count', 0))),
            ("成功接收", str(stats.get('recv_count', 0))),
            ("丢包数量", str(stats.get('loss_count', 0))),
            ("丢包率", f"{stats.get('loss_rate', 0)}%"),
            ("最大连续丢包", f"{stats.get('max_burst_loss', 0)}次"),
        ], 0, 0)

        # 时延统计列
        self._add_stat_section("⏱ 时延统计 (ms)", [
            ("最小值", f"{stats.get('rtt_min', 0)} ms"),
            ("最大值", f"{stats.get('rtt_max', 0)} ms"),
            ("平均值", f"{stats.get('rtt_avg', 0)} ms"),
            ("P50", f"{stats.get('rtt_p50', 0)} ms"),
            ("P90", f"{stats.get('rtt_p90', 0)} ms"),
            ("P95", f"{stats.get('rtt_p95', 0)} ms"),
            ("P99", f"{stats.get('rtt_p99', 0)} ms"),
        ], 0, 1)

        # 抖动统计列
        self._add_stat_section("📈 抖动统计", [
            ("平均抖动", f"{stats.get('jitter_avg', 0)} ms"),
            ("最大抖动", f"{stats.get('jitter_max', 0)} ms"),
            ("RTT标准差", f"{stats.get('rtt_mdev', 0)} ms"),
        ], 0, 2)

        # 质量评级
        rating = stats.get('rating', {})
        rating_color = {
            'EXCELLENT': '#1b8a2d', 'GOOD': '#1a73e8',
            'FAIR': '#f9a825', 'POOR': '#e65100', 'BAD': '#d93025'
        }.get(rating.get('enum', ''), '#333')
        self.rating_label.setText(f"{rating.get('stars', '')}  {rating.get('text', '')}")
        self.rating_label.setStyleSheet(f"color: {rating_color}; font-size: 18px;")

    def _show_dns_stats(self, stats: dict):
        """显示DNS统计面板"""
        self.stats_frame.setVisible(True)

        meta = self.storage.load_meta(self.current_record_dir)
        target = meta.get('target', '') if meta else ''
        duration_min = meta.get('planned_duration_min', '') if meta else ''
        start = meta.get('start_time', '')[:19].replace('T', ' ') if meta else ''
        end = meta.get('end_time', '')[:19].replace('T', ' ') if meta else ''

        self.stats_info.setText(
            f"目标：{target}    方式：DNS    时长：{duration_min}分钟\n"
            f"开始：{start}    结束：{end}"
        )

        while self.stats_grid.count():
            item = self.stats_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._add_stat_section("🔍 查询统计", [
            ("总查询数", str(stats.get('total_count', 0))),
            ("解析成功", str(stats.get('success_count', 0))),
            ("成功率", f"{stats.get('success_rate', 0)}%"),
            ("超时次数", str(stats.get('timeout_count', 0))),
            ("SERVFAIL", str(stats.get('servfail_count', 0))),
        ], 0, 0)

        self._add_stat_section("⏱ 时延统计 (ms)", [
            ("最小值", f"{stats.get('latency_min', 0)} ms"),
            ("最大值", f"{stats.get('latency_max', 0)} ms"),
            ("平均值", f"{stats.get('latency_avg', 0)} ms"),
            ("P50", f"{stats.get('latency_p50', 0)} ms"),
            ("P90", f"{stats.get('latency_p90', 0)} ms"),
            ("P99", f"{stats.get('latency_p99', 0)} ms"),
        ], 0, 1)

        self._add_stat_section("📈 解析结果", [
            ("IP变化次数", str(stats.get('ip_change_count', 0))),
            ("最后解析IP", stats.get('last_resolved_ip', '--')),
            ("平均TTL", f"{stats.get('avg_ttl', 0)}s"),
            ("平均抖动", f"{stats.get('jitter_avg', 0)} ms"),
            ("最大抖动", f"{stats.get('jitter_max', 0)} ms"),
        ], 0, 2)

        rating = stats.get('rating', {})
        rating_color = {
            'EXCELLENT': '#1b8a2d', 'GOOD': '#1a73e8',
            'FAIR': '#f9a825', 'POOR': '#e65100', 'BAD': '#d93025'
        }.get(rating.get('enum', ''), '#333')
        self.rating_label.setText(f"{rating.get('stars', '')}  {rating.get('text', '')}")
        self.rating_label.setStyleSheet(f"color: {rating_color}; font-size: 18px;")

    def _add_stat_section(self, title: str, items: list[tuple], row: int, col: int):
        """添加统计分区到网格"""
        section = QFrame()
        section.setStyleSheet("QFrame { background: white; border-radius: 4px; padding: 8px; }")
        section_layout = QVBoxLayout(section)
        section_layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #1a478a;")
        section_layout.addWidget(title_label)

        for name, value in items:
            item_row = QHBoxLayout()
            name_label = QLabel(f"{name}：")
            name_label.setFont(QFont("Microsoft YaHei", 9))
            name_label.setStyleSheet("color: #555;")
            value_label = QLabel(str(value))
            value_label.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            value_label.setStyleSheet("color: #222;")
            item_row.addWidget(name_label)
            item_row.addStretch()
            item_row.addWidget(value_label)
            section_layout.addLayout(item_row)

        section_layout.addStretch()
        self.stats_grid.addWidget(section, row, col)

    def _update_progress(self):
        """更新进度条和状态"""
        if not self.start_time:
            return

        elapsed = time.time() - self.start_time
        remaining = max(0, self.planned_duration_sec - elapsed)
        progress = min(100, int(elapsed / self.planned_duration_sec * 100)) if self.planned_duration_sec > 0 else 0
        self.progress_bar.setValue(progress)

        remaining_min = int(remaining) // 60
        remaining_sec = int(remaining) % 60
        self.progress_label.setText(f"{progress}%  剩余 {remaining_min}分{remaining_sec:02d}秒")

        # 进度条颜色根据丢包率
        loss_rate = (self._loss_count / self._seq_count * 100) if self._seq_count > 0 else 0
        if loss_rate >= 5:
            self.progress_bar.setStyleSheet("""
                QProgressBar { border: 1px solid #ddd; border-radius: 4px; text-align: center; }
                QProgressBar::chunk { background: #d93025; border-radius: 3px; }
            """)
        elif loss_rate > 0:
            self.progress_bar.setStyleSheet("""
                QProgressBar { border: 1px solid #ddd; border-radius: 4px; text-align: center; }
                QProgressBar::chunk { background: #e8710a; border-radius: 3px; }
            """)
        else:
            self.progress_bar.setStyleSheet("""
                QProgressBar { border: 1px solid #ddd; border-radius: 4px; text-align: center; }
                QProgressBar::chunk { background: #1a73e8; border-radius: 3px; }
            """)

        # 状态栏
        if self.status_callback:
            elapsed_min = int(elapsed) // 60
            elapsed_sec = int(elapsed) % 60
            avg_rtt = (self._rtt_sum / self._success_count) if self._success_count > 0 else 0
            status = (f"长时拨测 | 发包: {self._seq_count}  丢包: {self._loss_count}  "
                      f"均RTT: {avg_rtt:.1f}ms | "
                      f"进度: {progress}%  剩余: {remaining_min}分{remaining_sec:02d}秒")
            self.status_callback(status)

        # 自动停止检查
        if elapsed >= self.planned_duration_sec:
            self._stop_probe()

    def _load_history(self):
        records = self.storage.get_records('longterm')
        for i, btn in enumerate(self.history_buttons):
            if i < len(records):
                meta = records[i]
                protocol_map = {'ping': 'Ping', 'dns': 'DNS'}
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

        for btn in self.history_buttons:
            btn.setChecked(btn.property('record_dir') == self.current_record_dir)

    def _switch_history(self, idx: int):
        records = self.storage.get_records('longterm')
        if idx >= len(records):
            return

        for i, btn in enumerate(self.history_buttons):
            btn.setChecked(i == idx)

        meta = records[idx]
        record_dir = meta.get('_dir')
        protocol = meta.get('protocol', 'ping')

        # 加载历史数据
        data = self.storage.load_records_data(record_dir)
        self.result_text.clear()
        for r in data:
            line = self._format_result_line(r, protocol)
            is_success = r.get('status') == 'success'
            self._append_result(line, is_success)

        # 加载历史统计
        stats = self.storage.load_stats(record_dir)
        if stats:
            self.current_record_dir = record_dir
            if protocol == 'ping':
                self._show_ping_stats(stats)
            elif protocol == 'dns':
                self._show_dns_stats(stats)
        else:
            self.stats_frame.setVisible(False)

        self.btn_export.setEnabled(meta.get('end_time') is not None)
        self.btn_export.setProperty('export_dir', record_dir)

    def _export_log(self):
        export_dir = self.btn_export.property('export_dir') or self.current_record_dir
        if not export_dir:
            return

        meta = self.storage.load_meta(export_dir)
        if not meta:
            return

        stats = self.storage.load_stats(export_dir)

        default_name = (f"probe_longterm_{meta.get('protocol', 'ping')}_"
                        f"{meta.get('target', 'unknown').replace('.', '_').replace(':', '_')}_"
                        f"{meta.get('start_time', '')[:19].replace('T', '_').replace(':', '').replace('-', '')}.txt")

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出拨测日志", default_name, "文本文件 (*.txt);;所有文件 (*)"
        )

        if file_path:
            try:
                self.storage.export_log(export_dir, file_path, stats)
                QMessageBox.information(self, "导出成功", f"日志已成功导出到：\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "导出失败", f"导出失败：{str(e)}")
