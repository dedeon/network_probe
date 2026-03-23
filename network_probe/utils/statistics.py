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
