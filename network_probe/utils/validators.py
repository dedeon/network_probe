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


def validate_target(target: str) -> tuple[bool, str]:
    """
    校验目标地址，返回 (是否合法, 地址类型)
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
