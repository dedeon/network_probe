#!/usr/bin/env python3
"""详细检查搜索引擎返回内容"""
import httpx
import re

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

client = httpx.Client(timeout=20, follow_redirects=True, verify=False, headers=HEADERS)

# 测试bing
print("=== BING 测试 ===")
try:
    r = client.get('https://www.bing.com/search?q=com.ss.android.lark.greentown+下载', timeout=15)
    print(f"状态码: {r.status_code}, 长度: {len(r.text)}")
    print(f"URL: {r.url}")
    # 保存完整HTML以便分析
    with open('/tmp/bing_test.html', 'w') as f:
        f.write(r.text)
    print("已保存到 /tmp/bing_test.html")
    # 检查各种可能的结果标记
    for pat_name, pat in [
        ('b_algo', r'class="b_algo"'),
        ('b_results', r'id="b_results"'),
        ('b_content', r'class="b_content"'),
        ('h2标签', r'<h2'),
        ('搜索结果数', r'b_algo'),
    ]:
        count = len(re.findall(pat, r.text))
        print(f"  {pat_name}: {count}处")
    # 看标题
    titles = re.findall(r'<title>(.*?)</title>', r.text)
    print(f"  页面标题: {titles}")
    # 打印前3000字符看结构
    clean = re.sub(r'<script[^>]*>.*?</script>', '', r.text, flags=re.DOTALL)
    clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL)
    clean = re.sub(r'\s+', ' ', clean)
    print(f"\n  Clean HTML前2000字符:")
    print(clean[:2000])
except Exception as e:
    print(f"Bing失败: {e}")

print("\n\n=== 百度 测试 ===")
try:
    r2 = client.get('https://www.baidu.com/s?wd=com.ss.android.lark.greentown', timeout=15)
    print(f"状态码: {r2.status_code}, 长度: {len(r2.text)}")
    print(f"URL: {r2.url}")
    with open('/tmp/baidu_test.html', 'w') as f:
        f.write(r2.text)
    # 看标题
    titles = re.findall(r'<title>(.*?)</title>', r2.text)
    print(f"  页面标题: {titles}")
    # 百度可能需要cookie
    if '百度安全验证' in r2.text or len(r2.text) < 5000:
        print("  !! 百度返回了验证页面或空结果")
    print(f"\n  前500字符: {r2.text[:500]}")
except Exception as e:
    print(f"百度失败: {e}")

# 测试Google搜索
print("\n\n=== Google 测试 ===")
try:
    r3 = client.get('https://www.google.com/search?q=com.ss.android.lark.greentown', timeout=15)
    print(f"状态码: {r3.status_code}, 长度: {len(r3.text)}")
    print(f"URL: {r3.url}")
except Exception as e:
    print(f"Google失败: {e}")

# 测试搜狗搜索
print("\n\n=== 搜狗 测试 ===")
try:
    r4 = client.get('https://www.sogou.com/web?query=com.ss.android.lark.greentown', timeout=15)
    print(f"状态码: {r4.status_code}, 长度: {len(r4.text)}")
    print(f"URL: {r4.url}")
    titles = re.findall(r'<title>(.*?)</title>', r4.text)
    print(f"  页面标题: {titles}")
    # 搜狗结果结构
    results = re.findall(r'<h3[^>]*>(.*?)</h3>', r4.text, re.DOTALL)
    print(f"  h3结果数: {len(results)}")
    for i, res in enumerate(results[:5]):
        title = re.sub(r'<.*?>', '', res).strip()
        print(f"  [{i+1}] {title}")
except Exception as e:
    print(f"搜狗失败: {e}")

client.close()
