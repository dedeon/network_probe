"""输入验证工具"""
import re
import ipaddress


def validate_ipv4(address: str) -> bool:
    """校验IPv4地址格式"""
    try:
        ipaddress.IPv4Address(address)
        return True
    except ipaddress.AddressValueError:
        return False


def validate_ipv6(address: str) -> bool:
    """校验IPv6地址格式"""
    try:
        ipaddress.IPv6Address(address)
        return True
    except ipaddress.AddressValueError:
        return False


def validate_domain(domain: str) -> bool:
    """校验域名格式（符合DNS命名规范）"""
    if not domain or len(domain) > 253:
        return False
    # 域名正则：支持常规域名和国际化域名
    pattern = r'^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})*\.[A-Za-z]{2,}$'
    return bool(re.match(pattern, domain))


def validate_port(port_str: str) -> tuple[bool, int]:
    """校验端口号，返回 (是否合法, 端口值)"""
    try:
        port = int(port_str)
        if 1 <= port <= 65535:
            return True, port
        return False, 0
    except (ValueError, TypeError):
        return False, 0


def parse_target_with_port(raw_input: str) -> tuple[str, int, str]:
    """
    解析 目标地址:端口 格式的输入
    支持格式:
        域名:端口         如 www.baidu.com:443
        IPv4:端口         如 8.8.8.8:53
        [IPv6]:端口       如 [::1]:80
    返回 (host, port, error_msg)
    error_msg 为空字符串表示无错误
    """
    raw_input = raw_input.strip()
    if not raw_input:
        return '', 0, '请输入目标地址和端口'

    host = ''
    port_str = ''

    # IPv6 格式: [addr]:port
    if raw_input.startswith('['):
        bracket_end = raw_input.find(']')
        if bracket_end == -1:
            return '', 0, 'IPv6 地址格式错误，请使用 [IPv6地址]:端口'
        host = raw_input[1:bracket_end]
        remainder = raw_input[bracket_end + 1:]
        if not remainder.startswith(':') or len(remainder) < 2:
            return '', 0, '请在IPv6地址后输入端口，格式：[IPv6地址]:端口'
        port_str = remainder[1:]
    else:
        # IPv4 或域名: host:port
        # 注意可能有多个冒号（IPv6 无方括号 不支持）
        colon_count = raw_input.count(':')
        if colon_count == 0:
            return '', 0, '请输入端口，格式：地址:端口'
        elif colon_count == 1:
            host, port_str = raw_input.rsplit(':', 1)
        else:
            # 多个冒号，可能是无方括号的 IPv6，不支持
            return '', 0, 'IPv6 地址请使用 [IPv6地址]:端口 格式'

    if not host:
        return '', 0, '目标地址不能为空'

    if not port_str:
        return '', 0, '端口不能为空'

    port_valid, port = validate_port(port_str)
    if not port_valid:
        return '', 0, f'端口号无效（需为1-65535的整数），当前输入：{port_str}'

    # 校验 host 部分
    if validate_ipv4(host):
        return host, port, ''
    if validate_ipv6(host):
        return host, port, ''
    if validate_domain(host):
        return host, port, ''

    return '', 0, f'目标地址无效：{host}'


def validate_target(target: str) -> tuple[bool, str]:
    """
    校验目标地址（不含端口），返回 (是否合法, 地址类型)
    地址类型: 'ipv4' / 'ipv6' / 'domain' / 'invalid'
    """
    target = target.strip()
    if not target:
        return False, 'empty'
    if validate_ipv4(target):
        return True, 'ipv4'
    if validate_ipv6(target):
        return True, 'ipv6'
    if validate_domain(target):
        return True, 'domain'
    return False, 'invalid'


def is_ip_address(target: str) -> bool:
    """判断目标是否为纯IP地址"""
    return validate_ipv4(target) or validate_ipv6(target)


def validate_duration(value: str) -> tuple[bool, str]:
    """校验拨测时长"""
    try:
        minutes = int(value)
        if minutes < 1:
            return False, '拨测时长最小值为1分钟'
        if minutes > 1440:
            return False, '拨测时长最大值为1440分钟（24小时）'
        return True, ''
    except ValueError:
        return False, '请输入有效的整数'
