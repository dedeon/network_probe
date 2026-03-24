"""统计分析工具"""
import math
from typing import Optional


def percentile(sorted_data: list[float], p: float) -> float:
    """计算百分位数 (P50/P90/P95/P99)"""
    if not sorted_data:
        return 0.0
    n = len(sorted_data)
    k = (n - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    d0 = sorted_data[int(f)] * (c - k)
    d1 = sorted_data[int(c)] * (k - f)
    return d0 + d1


def calculate_jitter(rtt_list: list[float]) -> tuple[float, float]:
    """
    计算抖动指标
    返回 (平均抖动, 最大抖动)
    平均抖动 = 相邻RTT差值绝对值的均值
    """
    if len(rtt_list) < 2:
        return 0.0, 0.0
    diffs = [abs(rtt_list[i] - rtt_list[i - 1]) for i in range(1, len(rtt_list))]
    avg_jitter = sum(diffs) / len(diffs)
    max_jitter = max(diffs)
    return avg_jitter, max_jitter


def calculate_std_dev(values: list[float]) -> float:
    """计算总体标准差"""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return math.sqrt(variance)


def max_consecutive_loss(statuses: list[str]) -> int:
    """计算最大连续丢包次数"""
    max_burst = 0
    current_burst = 0
    for s in statuses:
        if s != 'success':
            current_burst += 1
            max_burst = max(max_burst, current_burst)
        else:
            current_burst = 0
    return max_burst


def calculate_ping_stats(records: list[dict]) -> dict:
    """计算Ping统计指标"""
    total = len(records)
    if total == 0:
        return {}

    success_rtts = [r['rtt_ms'] for r in records if r['status'] == 'success' and r.get('rtt_ms') is not None]
    statuses = [r['status'] for r in records]

    success_count = len(success_rtts)
    loss_count = total - success_count
    loss_rate = (loss_count / total) * 100 if total > 0 else 0

    sorted_rtts = sorted(success_rtts) if success_rtts else []
    rtt_min = min(success_rtts) if success_rtts else 0
    rtt_max = max(success_rtts) if success_rtts else 0
    rtt_avg = sum(success_rtts) / len(success_rtts) if success_rtts else 0

    jitter_avg, jitter_max = calculate_jitter(success_rtts)
    rtt_mdev = calculate_std_dev(success_rtts)
    burst_loss = max_consecutive_loss(statuses)

    return {
        'sent_count': total,
        'recv_count': success_count,
        'loss_count': loss_count,
        'loss_rate': round(loss_rate, 2),
        'max_burst_loss': burst_loss,
        'rtt_min': round(rtt_min, 2),
        'rtt_max': round(rtt_max, 2),
        'rtt_avg': round(rtt_avg, 2),
        'rtt_p50': round(percentile(sorted_rtts, 50), 2),
        'rtt_p90': round(percentile(sorted_rtts, 90), 2),
        'rtt_p95': round(percentile(sorted_rtts, 95), 2),
        'rtt_p99': round(percentile(sorted_rtts, 99), 2),
        'jitter_avg': round(jitter_avg, 2),
        'jitter_max': round(jitter_max, 2),
        'rtt_mdev': round(rtt_mdev, 2),
    }


def calculate_dns_stats(records: list[dict]) -> dict:
    """计算DNS统计指标"""
    total = len(records)
    if total == 0:
        return {}

    success_latencies = [r['latency_ms'] for r in records if r['status'] == 'success' and r.get('latency_ms') is not None]
    statuses = [r['status'] for r in records]

    success_count = len(success_latencies)
    timeout_count = sum(1 for r in records if r.get('rcode') == 'TIMEOUT')
    servfail_count = sum(1 for r in records if r.get('rcode') == 'SERVFAIL')
    nxdomain_count = sum(1 for r in records if r.get('rcode') == 'NXDOMAIN')

    sorted_lat = sorted(success_latencies) if success_latencies else []
    lat_min = min(success_latencies) if success_latencies else 0
    lat_max = max(success_latencies) if success_latencies else 0
    lat_avg = sum(success_latencies) / len(success_latencies) if success_latencies else 0

    jitter_avg, jitter_max = calculate_jitter(success_latencies)
    lat_mdev = calculate_std_dev(success_latencies)

    # IP变化次数
    ips = [r.get('answer_ip', '') for r in records if r['status'] == 'success']
    ip_changes = sum(1 for i in range(1, len(ips)) if ips[i] != ips[i - 1])
    last_ip = ips[-1] if ips else '--'

    # 平均TTL
    ttls = [r.get('ttl', 0) for r in records if r['status'] == 'success' and r.get('ttl')]
    avg_ttl = sum(ttls) / len(ttls) if ttls else 0

    success_rate = (success_count / total) * 100 if total > 0 else 0

    return {
        'total_count': total,
        'success_count': success_count,
        'success_rate': round(success_rate, 2),
        'timeout_count': timeout_count,
        'servfail_count': servfail_count,
        'nxdomain_count': nxdomain_count,
        'latency_min': round(lat_min, 2),
        'latency_max': round(lat_max, 2),
        'latency_avg': round(lat_avg, 2),
        'latency_p50': round(percentile(sorted_lat, 50), 2),
        'latency_p90': round(percentile(sorted_lat, 90), 2),
        'latency_p95': round(percentile(sorted_lat, 95), 2),
        'latency_p99': round(percentile(sorted_lat, 99), 2),
        'jitter_avg': round(jitter_avg, 2),
        'jitter_max': round(jitter_max, 2),
        'latency_mdev': round(lat_mdev, 2),
        'ip_change_count': ip_changes,
        'last_resolved_ip': last_ip,
        'avg_ttl': round(avg_ttl, 1),
    }


def calculate_curl_stats(records: list[dict]) -> dict:
    """计算Curl/HTTP统计指标"""
    total = len(records)
    if total == 0:
        return {}

    success_records = [r for r in records if r['status'] == 'success']
    success_count = len(success_records)
    timeout_count = sum(1 for r in records if r.get('status') == 'timeout')
    tls_error_count = sum(1 for r in records if r.get('status') == 'tls_error')
    conn_error_count = sum(1 for r in records if r.get('status') == 'error')

    success_rate = (success_count / total) * 100 if total > 0 else 0

    # 各阶段耗时列表
    dns_times = [r['dns_ms'] for r in success_records if r.get('dns_ms') is not None]
    tcp_times = [r['tcp_ms'] for r in success_records if r.get('tcp_ms') is not None]
    tls_times = [r['tls_ms'] for r in success_records if r.get('tls_ms') is not None]
    ttfb_times = [r['ttfb_ms'] for r in success_records if r.get('ttfb_ms') is not None]
    total_times = [r['total_ms'] for r in success_records if r.get('total_ms') is not None]

    # HTTP 状态码分布
    http_codes = [r.get('http_code') for r in success_records if r.get('http_code') is not None]
    code_2xx = sum(1 for c in http_codes if 200 <= c < 300)
    code_3xx = sum(1 for c in http_codes if 300 <= c < 400)
    code_4xx = sum(1 for c in http_codes if 400 <= c < 500)
    code_5xx = sum(1 for c in http_codes if 500 <= c < 600)

    sorted_total = sorted(total_times) if total_times else []
    total_min = min(total_times) if total_times else 0
    total_max = max(total_times) if total_times else 0
    total_avg = sum(total_times) / len(total_times) if total_times else 0

    jitter_avg, jitter_max = calculate_jitter(total_times)

    return {
        'total_count': total,
        'success_count': success_count,
        'success_rate': round(success_rate, 2),
        'timeout_count': timeout_count,
        'tls_error_count': tls_error_count,
        'conn_error_count': conn_error_count,
        # DNS 阶段
        'dns_min': round(min(dns_times), 2) if dns_times else 0,
        'dns_max': round(max(dns_times), 2) if dns_times else 0,
        'dns_avg': round(sum(dns_times) / len(dns_times), 2) if dns_times else 0,
        # TCP 阶段
        'tcp_min': round(min(tcp_times), 2) if tcp_times else 0,
        'tcp_max': round(max(tcp_times), 2) if tcp_times else 0,
        'tcp_avg': round(sum(tcp_times) / len(tcp_times), 2) if tcp_times else 0,
        # TLS 阶段
        'tls_min': round(min(tls_times), 2) if tls_times else 0,
        'tls_max': round(max(tls_times), 2) if tls_times else 0,
        'tls_avg': round(sum(tls_times) / len(tls_times), 2) if tls_times else 0,
        # TTFB 阶段
        'ttfb_min': round(min(ttfb_times), 2) if ttfb_times else 0,
        'ttfb_max': round(max(ttfb_times), 2) if ttfb_times else 0,
        'ttfb_avg': round(sum(ttfb_times) / len(ttfb_times), 2) if ttfb_times else 0,
        # 总耗时
        'total_min': round(total_min, 2),
        'total_max': round(total_max, 2),
        'total_avg': round(total_avg, 2),
        'total_p50': round(percentile(sorted_total, 50), 2),
        'total_p90': round(percentile(sorted_total, 90), 2),
        'total_p95': round(percentile(sorted_total, 95), 2),
        'total_p99': round(percentile(sorted_total, 99), 2),
        # 抖动
        'jitter_avg': round(jitter_avg, 2),
        'jitter_max': round(jitter_max, 2),
        # HTTP 状态码分布
        'code_2xx': code_2xx,
        'code_3xx': code_3xx,
        'code_4xx': code_4xx,
        'code_5xx': code_5xx,
    }


def calculate_keepalive_stats(records: list[dict]) -> dict:
    """计算TCP长连接拨测统计指标"""
    total = len(records)
    if total == 0:
        return {}

    # ── 分类事件 ──
    connect_events = [r for r in records if r.get('event') == 'connect']
    connect_fail_events = [r for r in records if r.get('event') == 'connect_fail']
    heartbeat_events = [r for r in records if r.get('event') == 'heartbeat']
    disconnect_events = [r for r in records if r.get('event') == 'disconnect']
    reconnect_wait_events = [r for r in records if r.get('event') == 'reconnect_wait']

    # ── 建连统计 ──
    connect_ok_count = len([r for r in connect_events if r.get('status') == 'connect_ok'])
    connect_fail_count = len(connect_fail_events)
    total_connect_attempts = connect_ok_count + connect_fail_count
    connect_success_rate = (connect_ok_count / total_connect_attempts * 100) if total_connect_attempts > 0 else 0

    connect_rtts = [r['connect_rtt_ms'] for r in connect_events
                    if r.get('connect_rtt_ms') is not None]
    sorted_connect_rtts = sorted(connect_rtts) if connect_rtts else []
    connect_rtt_avg = sum(connect_rtts) / len(connect_rtts) if connect_rtts else 0
    connect_rtt_min = min(connect_rtts) if connect_rtts else 0
    connect_rtt_max = max(connect_rtts) if connect_rtts else 0

    # ── 心跳统计 ──
    hb_total = len(heartbeat_events)
    hb_success = [r for r in heartbeat_events if r.get('status') == 'success']
    hb_success_count = len(hb_success)
    hb_loss_count = hb_total - hb_success_count
    hb_loss_rate = (hb_loss_count / hb_total * 100) if hb_total > 0 else 0

    hb_rtts = [r['heartbeat_rtt_ms'] for r in hb_success
               if r.get('heartbeat_rtt_ms') is not None]
    sorted_hb_rtts = sorted(hb_rtts) if hb_rtts else []
    hb_rtt_avg = sum(hb_rtts) / len(hb_rtts) if hb_rtts else 0
    hb_rtt_min = min(hb_rtts) if hb_rtts else 0
    hb_rtt_max = max(hb_rtts) if hb_rtts else 0

    hb_jitter_avg, hb_jitter_max = calculate_jitter(hb_rtts)
    hb_rtt_mdev = calculate_std_dev(hb_rtts)

    # 最大连续心跳丢包
    hb_statuses = [r.get('status', '') for r in heartbeat_events]
    hb_max_burst_loss = max_consecutive_loss(hb_statuses)

    # ── 会话统计 ──
    disconnect_count = len(disconnect_events)
    session_durations = [r['session_duration_ms'] for r in disconnect_events
                         if r.get('session_duration_ms') is not None]
    # 如果没有断线事件，但有连接事件，最后一个会话可能还在持续
    # 这里只统计已结束的会话
    avg_session_duration = sum(session_durations) / len(session_durations) if session_durations else 0
    max_session_duration = max(session_durations) if session_durations else 0
    min_session_duration = min(session_durations) if session_durations else 0

    # ── 重连统计 ──
    reconnect_waits = [r.get('reconnect_wait_ms', 0) for r in reconnect_wait_events
                       if r.get('reconnect_wait_ms') is not None]
    avg_reconnect_wait = sum(reconnect_waits) / len(reconnect_waits) if reconnect_waits else 0
    max_reconnect_wait = max(reconnect_waits) if reconnect_waits else 0
    total_reconnect_count = len(reconnect_wait_events)

    return {
        # 建连统计
        'connect_attempts': total_connect_attempts,
        'connect_ok_count': connect_ok_count,
        'connect_fail_count': connect_fail_count,
        'connect_success_rate': round(connect_success_rate, 2),
        'connect_rtt_avg': round(connect_rtt_avg, 2),
        'connect_rtt_min': round(connect_rtt_min, 2),
        'connect_rtt_max': round(connect_rtt_max, 2),
        'connect_rtt_p50': round(percentile(sorted_connect_rtts, 50), 2),
        'connect_rtt_p90': round(percentile(sorted_connect_rtts, 90), 2),
        'connect_rtt_p95': round(percentile(sorted_connect_rtts, 95), 2),
        # 心跳统计
        'heartbeat_total': hb_total,
        'heartbeat_success': hb_success_count,
        'heartbeat_loss_count': hb_loss_count,
        'heartbeat_loss_rate': round(hb_loss_rate, 2),
        'heartbeat_max_burst_loss': hb_max_burst_loss,
        'hb_rtt_avg': round(hb_rtt_avg, 2),
        'hb_rtt_min': round(hb_rtt_min, 2),
        'hb_rtt_max': round(hb_rtt_max, 2),
        'hb_rtt_p50': round(percentile(sorted_hb_rtts, 50), 2),
        'hb_rtt_p90': round(percentile(sorted_hb_rtts, 90), 2),
        'hb_rtt_p95': round(percentile(sorted_hb_rtts, 95), 2),
        'hb_rtt_p99': round(percentile(sorted_hb_rtts, 99), 2),
        'hb_jitter_avg': round(hb_jitter_avg, 2),
        'hb_jitter_max': round(hb_jitter_max, 2),
        'hb_rtt_mdev': round(hb_rtt_mdev, 2),
        # 会话统计
        'disconnect_count': disconnect_count,
        'session_count': connect_ok_count,
        'avg_session_duration_ms': round(avg_session_duration, 2),
        'max_session_duration_ms': round(max_session_duration, 2),
        'min_session_duration_ms': round(min_session_duration, 2),
        # 重连统计
        'reconnect_count': total_reconnect_count,
        'avg_reconnect_wait_ms': round(avg_reconnect_wait, 2),
        'max_reconnect_wait_ms': round(max_reconnect_wait, 2),
    }


def quality_rating(loss_rate: float, avg_rtt: float, avg_jitter: float) -> tuple[str, str, str]:
    """
    根据丢包率、平均RTT、平均抖动计算质量评级
    返回 (枚举值, 显示文本, 星级)
    三项指标取最低评级
    """
    def rate_loss(lr):
        if lr == 0:
            return 5
        elif lr < 0.5:
            return 4
        elif lr < 1:
            return 3
        elif lr < 5:
            return 2
        else:
            return 1

    def rate_rtt(rtt):
        if rtt < 10:
            return 5
        elif rtt < 30:
            return 4
        elif rtt < 50:
            return 3
        elif rtt < 100:
            return 2
        else:
            return 1

    def rate_jitter(j):
        if j < 1:
            return 5
        elif j < 3:
            return 4
        elif j < 10:
            return 3
        elif j < 30:
            return 2
        else:
            return 1

    score = min(rate_loss(loss_rate), rate_rtt(avg_rtt), rate_jitter(avg_jitter))

    ratings = {
        5: ('EXCELLENT', '优秀', '★★★★★'),
        4: ('GOOD', '良好', '★★★★☆'),
        3: ('FAIR', '一般', '★★★☆☆'),
        2: ('POOR', '较差', '★★☆☆☆'),
        1: ('BAD', '极差', '★☆☆☆☆'),
    }
    return ratings.get(score, ratings[1])


def keepalive_quality_rating(stats: dict) -> tuple[str, str, str, str]:
    """
    TCP 长连接专用质量评级

    评价维度（纯 TCP 保活模式不产生心跳 RTT，因此不用 RTT/抖动作为评价指标）：
        1. 建连成功率    —— 能否连上
        2. 平均会话时长  —— 连接能保持多久
        3. 建连 RTT      —— 网络延迟水平
        4. 会话时长稳定性 —— 各次会话时长是否一致（区分随机断线 vs 服务端固定超时）

    评分规则：
        ★★★★★ 优秀：建连100%，平均会话≥5分钟，建连RTT<10ms
        ★★★★☆ 良好：建连≥95%，平均会话≥1分钟
        ★★★☆☆ 一般：建连≥90%，平均会话≥15秒
        ★★☆☆☆ 较差：建连≥50%，平均会话≥5秒
        ★☆☆☆☆ 极差：建连<50%，或平均会话<5秒

    返回 (枚举值, 显示文本, 星级, 评价说明)
    """
    connect_success_rate = stats.get('connect_success_rate', 0)
    avg_session_ms = stats.get('avg_session_duration_ms', 0)
    max_session_ms = stats.get('max_session_duration_ms', 0)
    min_session_ms = stats.get('min_session_duration_ms', 0)
    disconnect_count = stats.get('disconnect_count', 0)
    session_count = stats.get('session_count', 0)
    connect_rtt_avg = stats.get('connect_rtt_avg', 0)
    heartbeat_loss_rate = stats.get('heartbeat_loss_rate', 0)

    # ── 维度1：建连成功率 ──
    def rate_connect(cr):
        if cr >= 100:
            return 5
        elif cr >= 95:
            return 4
        elif cr >= 90:
            return 3
        elif cr >= 50:
            return 2
        else:
            return 1

    # ── 维度2：平均会话时长（ms） ──
    def rate_session_duration(dur_ms):
        if dur_ms >= 300000:       # ≥ 5 分钟
            return 5
        elif dur_ms >= 60000:      # ≥ 1 分钟
            return 4
        elif dur_ms >= 15000:      # ≥ 15 秒
            return 3
        elif dur_ms >= 5000:       # ≥ 5 秒
            return 2
        else:
            return 1

    # ── 维度3：建连 RTT ──
    def rate_connect_rtt(rtt):
        if rtt < 10:
            return 5
        elif rtt < 50:
            return 4
        elif rtt < 100:
            return 3
        elif rtt < 500:
            return 2
        else:
            return 1

    s1 = rate_connect(connect_success_rate)
    s2 = rate_session_duration(avg_session_ms)
    s3 = rate_connect_rtt(connect_rtt_avg)

    # 特殊情况：如果没有断线（只有 1 个会话且从未断线），直接评优秀
    if disconnect_count == 0 and session_count >= 1:
        s2 = 5  # 从未断线 = 会话时长无限

    # ── 判断是否为服务端固定超时行为 ──
    # 条件：多次断线、建连全部成功、建连RTT很低、且会话时长高度一致（极小标准差）
    is_server_timeout = False
    note = ''
    if disconnect_count >= 2 and session_count >= 2 and connect_success_rate >= 95 and connect_rtt_avg < 50:
        if max_session_ms > 0 and min_session_ms > 0:
            # 最长与最短会话时长之差 / 平均值 < 30%，说明非常稳定
            variation = (max_session_ms - min_session_ms) / avg_session_ms if avg_session_ms > 0 else 999
            if variation < 0.3:
                is_server_timeout = True
                timeout_sec = avg_session_ms / 1000
                note = f"检测到服务端固定超时断连（约{timeout_sec:.0f}秒），网络本身连通性良好"

    if is_server_timeout:
        # 服务端固定超时场景：会话时长维度提升1档（因为不是网络质量问题）
        s2 = min(s2 + 1, 4)  # 最多提到4（良好），不给5（因为确实在断线）
        if not note:
            note = "会话时长受限于服务端空闲超时策略，非网络质量问题"
    else:
        # 非服务端超时场景：生成常规说明
        reasons = []
        if s1 <= 2:
            reasons.append(f"建连成功率低({connect_success_rate:.0f}%)")
        if s2 <= 2 and disconnect_count > 0:
            reasons.append(f"平均会话时长短({avg_session_ms/1000:.1f}秒)")
        if s3 <= 2:
            reasons.append(f"建连延迟高({connect_rtt_avg:.1f}ms)")
        if heartbeat_loss_rate > 30:
            reasons.append(f"探活失败率高({heartbeat_loss_rate:.0f}%)")
        if reasons:
            note = '主要问题：' + '，'.join(reasons)

    score = min(s1, s2, s3)

    ratings = {
        5: ('EXCELLENT', '优秀', '★★★★★'),
        4: ('GOOD', '良好', '★★★★☆'),
        3: ('FAIR', '一般', '★★★☆☆'),
        2: ('POOR', '较差', '★★☆☆☆'),
        1: ('BAD', '极差', '★☆☆☆☆'),
    }
    enum_val, text, stars = ratings.get(score, ratings[1])
    return (enum_val, text, stars, note)
