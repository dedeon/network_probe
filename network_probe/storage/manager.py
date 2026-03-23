"""数据存储管理模块 - 负责历史记录的本地持久化"""
import json
import csv
import os
import shutil
from datetime import datetime
from typing import Optional


class StorageManager:
    """
    本地数据存储管理器
    目录结构:
        data/
        ├── history/
        │   ├── instant/
        │   │   ├── record_1/
        │   │   │   ├── meta.json
        │   │   │   └── data.csv
        │   │   ├── record_2/
        │   │   └── record_3/
        │   └── longterm/
        │       ├── record_1/
        │       │   ├── meta.json
        │       │   ├── data.csv
        │       │   └── stats.json
        │       ├── record_2/
        │       └── record_3/
        └── config.json
    """

    MAX_HISTORY = 3

    def __init__(self, base_dir: str = None):
        if base_dir is None:
            # 使用程序所在目录下的 data 文件夹
            base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
        self.base_dir = base_dir
        self.instant_dir = os.path.join(base_dir, 'history', 'instant')
        self.longterm_dir = os.path.join(base_dir, 'history', 'longterm')
        self.config_path = os.path.join(base_dir, 'config.json')
        self._ensure_dirs()

    def _ensure_dirs(self):
        """确保目录结构存在"""
        os.makedirs(self.instant_dir, exist_ok=True)
        os.makedirs(self.longterm_dir, exist_ok=True)

    def _get_history_dir(self, mode: str) -> str:
        return self.instant_dir if mode == 'instant' else self.longterm_dir

    def get_records(self, mode: str) -> list[dict]:
        """获取指定模式下的所有历史记录（按时间排序）"""
        history_dir = self._get_history_dir(mode)
        records = []
        if not os.path.exists(history_dir):
            return records

        for name in sorted(os.listdir(history_dir)):
            record_dir = os.path.join(history_dir, name)
            meta_path = os.path.join(record_dir, 'meta.json')
            if os.path.isdir(record_dir) and os.path.exists(meta_path):
                with open(meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                meta['_dir'] = record_dir
                meta['_name'] = name
                records.append(meta)

        # 按开始时间排序
        records.sort(key=lambda r: r.get('start_time', ''))
        return records

    def create_record(self, mode: str, protocol: str, target: str,
                      planned_duration_min: Optional[int] = None) -> str:
        """创建新的拨测记录目录，返回记录目录路径"""
        history_dir = self._get_history_dir(mode)

        # 轮换：删除最旧的记录
        existing = self.get_records(mode)
        while len(existing) >= self.MAX_HISTORY:
            oldest = existing.pop(0)
            oldest_dir = oldest['_dir']
            if os.path.exists(oldest_dir):
                shutil.rmtree(oldest_dir)

        # 创建新记录目录
        now = datetime.now()
        record_id = f"{mode[:4]}_{now.strftime('%Y%m%d_%H%M%S')}"
        record_dir = os.path.join(history_dir, record_id)
        os.makedirs(record_dir, exist_ok=True)

        # 写入 meta.json
        meta = {
            'record_id': record_id,
            'mode': mode,
            'protocol': protocol,
            'target': target,
            'start_time': now.isoformat(timespec='milliseconds'),
            'end_time': None,
            'duration_sec': 0,
            'planned_duration_min': planned_duration_min,
            'total_sent': 0,
            'total_success': 0,
            'loss_rate': 0.0,
        }
        with open(os.path.join(record_dir, 'meta.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        return record_dir

    def update_meta(self, record_dir: str, updates: dict):
        """更新记录的 meta.json"""
        meta_path = os.path.join(record_dir, 'meta.json')
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        else:
            meta = {}
        meta.update(updates)
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

    def append_record(self, record_dir: str, protocol: str, record: dict):
        """追加一条探测记录到 data.csv"""
        data_path = os.path.join(record_dir, 'data.csv')
        file_exists = os.path.exists(data_path)

        if protocol == 'ping':
            fieldnames = ['timestamp', 'seq', 'rtt_ms', 'ttl', 'status']
        elif protocol == 'dns':
            fieldnames = ['timestamp', 'seq', 'latency_ms', 'answer_ip', 'rcode', 'status']
        elif protocol == 'curl':
            fieldnames = ['timestamp', 'seq', 'dns_ms', 'tcp_ms', 'tls_ms',
                          'ttfb_ms', 'transfer_ms', 'total_ms', 'http_code', 'status']
        else:
            fieldnames = list(record.keys())

        with open(data_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            if not file_exists:
                writer.writeheader()
            writer.writerow(record)

    def save_stats(self, record_dir: str, stats: dict):
        """保存统计结果到 stats.json"""
        stats_path = os.path.join(record_dir, 'stats.json')
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

    def load_records_data(self, record_dir: str) -> list[dict]:
        """加载记录的所有探测数据"""
        data_path = os.path.join(record_dir, 'data.csv')
        records = []
        if not os.path.exists(data_path):
            return records
        with open(data_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 类型转换
                for key in ['rtt_ms', 'latency_ms', 'dns_ms', 'tcp_ms',
                            'tls_ms', 'ttfb_ms', 'transfer_ms', 'total_ms']:
                    if key in row and row[key]:
                        try:
                            row[key] = float(row[key])
                        except (ValueError, TypeError):
                            row[key] = None
                for key in ['seq', 'ttl', 'http_code']:
                    if key in row and row[key]:
                        try:
                            row[key] = int(row[key])
                        except (ValueError, TypeError):
                            row[key] = None
                records.append(row)
        return records

    def load_stats(self, record_dir: str) -> Optional[dict]:
        """加载统计结果"""
        stats_path = os.path.join(record_dir, 'stats.json')
        if not os.path.exists(stats_path):
            return None
        with open(stats_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def load_meta(self, record_dir: str) -> Optional[dict]:
        """加载 meta.json"""
        meta_path = os.path.join(record_dir, 'meta.json')
        if not os.path.exists(meta_path):
            return None
        with open(meta_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def export_log(self, record_dir: str, export_path: str, stats: dict = None):
        """导出拨测日志到文本文件"""
        meta = self.load_meta(record_dir)
        records = self.load_records_data(record_dir)
        if stats is None:
            stats = self.load_stats(record_dir)

        with open(export_path, 'w', encoding='utf-8') as f:
            f.write('=' * 50 + '\n')
            f.write('网络拨测日志\n')
            f.write('=' * 50 + '\n')

            mode_text = '长时间拨测' if meta.get('mode') == 'longterm' else '即时拨测'
            protocol_map = {'ping': 'Ping', 'dns': 'DNS', 'curl': 'Curl/HTTP'}
            protocol_text = protocol_map.get(meta.get('protocol', ''), meta.get('protocol', ''))

            f.write(f"任务类型    : {mode_text}\n")
            f.write(f"拨测方式    : {protocol_text}\n")
            f.write(f"目标地址    : {meta.get('target', '')}\n")
            if meta.get('planned_duration_min'):
                f.write(f"设定时长    : {meta['planned_duration_min']} 分钟\n")
            f.write(f"开始时间    : {meta.get('start_time', '')}\n")
            f.write(f"结束时间    : {meta.get('end_time', '')}\n")

            duration = meta.get('duration_sec', 0)
            mins = int(duration) // 60
            secs = int(duration) % 60
            f.write(f"实际时长    : {mins}分{secs:02d}秒\n")
            f.write('=' * 50 + '\n')

            # 原始探测记录
            f.write('【原始探测记录】\n')
            protocol = meta.get('protocol', 'ping')
            if protocol == 'ping':
                f.write(f"{'时间':<26}{'序号':<8}{'RTT(ms)':<10}{'TTL':<6}{'状态'}\n")
                for r in records:
                    rtt = f"{r.get('rtt_ms', '--')}" if r.get('rtt_ms') is not None else '--'
                    ttl = str(r.get('ttl', '--')) if r.get('ttl') is not None else '--'
                    status_map = {'success': '成功', 'timeout': '超时', 'unreachable': '不可达', 'error': '错误'}
                    status = status_map.get(r.get('status', ''), r.get('status', ''))
                    f.write(f"{r.get('timestamp', ''):<26}{r.get('seq', ''):<8}{rtt:<10}{ttl:<6}{status}\n")
            elif protocol == 'dns':
                f.write(f"{'时间':<26}{'序号':<8}{'耗时(ms)':<10}{'解析结果':<20}{'状态'}\n")
                for r in records:
                    lat = f"{r.get('latency_ms', '--')}" if r.get('latency_ms') is not None else '--'
                    ip = r.get('answer_ip', '--') or '--'
                    status_map = {'success': '成功', 'timeout': '超时', 'error': '失败'}
                    status = status_map.get(r.get('status', ''), r.get('status', ''))
                    f.write(f"{r.get('timestamp', ''):<26}{r.get('seq', ''):<8}{lat:<10}{ip:<20}{status}\n")
            elif protocol == 'curl':
                f.write(f"{'时间':<26}{'序号':<6}{'DNS':<8}{'TCP':<8}{'TLS':<8}{'TTFB':<8}{'总计':<10}{'HTTP':<6}{'状态'}\n")
                for r in records:
                    dns = f"{r.get('dns_ms', '--')}" if r.get('dns_ms') is not None else '--'
                    tcp = f"{r.get('tcp_ms', '--')}" if r.get('tcp_ms') is not None else '--'
                    tls = f"{r.get('tls_ms', '--')}" if r.get('tls_ms') is not None else '--'
                    ttfb = f"{r.get('ttfb_ms', '--')}" if r.get('ttfb_ms') is not None else '--'
                    total = f"{r.get('total_ms', '--')}" if r.get('total_ms') is not None else '--'
                    code = str(r.get('http_code', '--')) if r.get('http_code') is not None else '--'
                    status_map = {'success': '成功', 'timeout': '超时', 'error': '连接失败', 'tls_error': 'TLS失败'}
                    status = status_map.get(r.get('status', ''), r.get('status', ''))
                    f.write(f"{r.get('timestamp', ''):<26}{r.get('seq', ''):<6}{dns:<8}{tcp:<8}{tls:<8}{ttfb:<8}{total:<10}{code:<6}{status}\n")

            f.write('=' * 50 + '\n')

            # 统计结果
            if stats:
                f.write('【统计分析结果】\n')
                if protocol == 'ping':
                    f.write('--- 发包统计 ---\n')
                    f.write(f"总发包数          : {stats.get('sent_count', 0)}\n")
                    f.write(f"成功接收          : {stats.get('recv_count', 0)}\n")
                    f.write(f"丢包数量          : {stats.get('loss_count', 0)}\n")
                    f.write(f"丢包率            : {stats.get('loss_rate', 0):.2f}%\n")
                    f.write(f"最大连续丢包      : {stats.get('max_burst_loss', 0)} 次\n\n")

                    f.write('--- 时延统计 ---\n')
                    f.write(f"最小RTT           : {stats.get('rtt_min', 0)} ms\n")
                    f.write(f"最大RTT           : {stats.get('rtt_max', 0)} ms\n")
                    f.write(f"平均RTT           : {stats.get('rtt_avg', 0)} ms\n")
                    f.write(f"P50               : {stats.get('rtt_p50', 0)} ms\n")
                    f.write(f"P90               : {stats.get('rtt_p90', 0)} ms\n")
                    f.write(f"P95               : {stats.get('rtt_p95', 0)} ms\n")
                    f.write(f"P99               : {stats.get('rtt_p99', 0)} ms\n\n")

                    f.write('--- 抖动统计 ---\n')
                    f.write(f"平均抖动          : {stats.get('jitter_avg', 0)} ms\n")
                    f.write(f"最大抖动          : {stats.get('jitter_max', 0)} ms\n")
                    f.write(f"RTT标准差         : {stats.get('rtt_mdev', 0)} ms\n\n")

                elif protocol == 'dns':
                    f.write('--- 查询统计 ---\n')
                    f.write(f"总查询数          : {stats.get('total_count', 0)}\n")
                    f.write(f"解析成功          : {stats.get('success_count', 0)}\n")
                    f.write(f"成功率            : {stats.get('success_rate', 0):.2f}%\n")
                    f.write(f"超时次数          : {stats.get('timeout_count', 0)}\n")
                    f.write(f"SERVFAIL          : {stats.get('servfail_count', 0)}\n\n")

                    f.write('--- 时延统计 ---\n')
                    f.write(f"最小耗时          : {stats.get('latency_min', 0)} ms\n")
                    f.write(f"最大耗时          : {stats.get('latency_max', 0)} ms\n")
                    f.write(f"平均耗时          : {stats.get('latency_avg', 0)} ms\n")
                    f.write(f"P50               : {stats.get('latency_p50', 0)} ms\n")
                    f.write(f"P90               : {stats.get('latency_p90', 0)} ms\n")
                    f.write(f"P99               : {stats.get('latency_p99', 0)} ms\n\n")

                # 质量评级
                if 'rating' in stats:
                    f.write('--- 质量评级 ---\n')
                    f.write(f"综合评级          : {stats['rating']['stars']}  {stats['rating']['text']}\n")

                f.write('=' * 50 + '\n')
