import os
import re
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

# 尝试导入 requests 库，若环境没有则使用 urllib 备用
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# 项目根目录路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, 'config', 'config.json')
OUTPUT_PATH = os.path.join(BASE_DIR, 'Gather.m3u')

def clean_name(str_val):
    """字符串清洗：转小写，去除中英文括号及特殊字符"""
    if not str_val:
        return ''
    str_val = str_val.lower()
    str_val = re.sub(r'\(.*?\)|\[.*?\]|「.*?」|（.*?）', '', str_val)
    return re.sub(r'[^a-z0-9\u4e00-\u9fa5]', '', str_val)

def test_url_latency(url, timeout=3):
    """
    对直链进行网络连通性测试并打分（测量延迟，单位：毫秒）
    若超时或返回非 200 状态，返回 float('inf') 表示不可用
    """
    start_time = time.time()
    try:
        if HAS_REQUESTS:
            # 优先使用 HEAD 快速请求；若 405/403，回退至 GET 流式请求
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            resp = requests.head(url, headers=headers, timeout=timeout, allow_redirects=True)
            if resp.status_code >= 400:
                resp = requests.get(url, headers=headers, timeout=timeout, stream=True)
            if resp.status_code == 200:
                return (time.time() - start_time) * 1000
        else:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status in [200, 301, 302]:
                    return (time.time() - start_time) * 1000
    except Exception:
        pass
    return float('inf')

def parse_upstream_m3u(urls):
    """解析上游 M3U，获取频道列表及其完整的 EPG 元数据"""
    channel_candidates = [] # 保存格式: {clean_name, raw_name, url, tvg_id, tvg_name, tvg_logo}
    
    for url in urls:
        print(f"正在拉取上游源: {url}")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode('utf-8', errors='ignore')
                
                curr_meta = {}
                for line in content.splitlines():
                    line = line.strip()
                    if line.startswith('#EXTINF:'):
                        # 提取 EPG 相关标签
                        tvg_id_m = re.search(r'tvg-id="([^"]*)"', line, re.I)
                        tvg_name_m = re.search(r'tvg-name="([^"]*)"', line, re.I)
                        tvg_logo_m = re.search(r'tvg-logo="([^"]*)"', line, re.I)
                        
                        raw_name = line.split(',')[-1].strip()
                        curr_meta = {
                            'raw_name': raw_name,
                            'clean_name': clean_name(raw_name),
                            'tvg_id': tvg_id_m.group(1) if tvg_id_m else '',
                            'tvg_name': tvg_name_m.group(1) if tvg_name_m else '',
                            'tvg_logo': tvg_logo_m.group(1) if tvg_logo_m else ''
                        }
                    elif line.startswith('http') and curr_meta:
                        curr_meta['url'] = line
                        channel_candidates.append(curr_meta)
                        curr_meta = {}
        except Exception as e:
            print(f"⚠️ 读取上游 {url} 失败: {e}")
            
    return channel_candidates

def main():
    # 1. 读取配置
    if not os.path.exists(CONFIG_PATH):
        print(f"❌ 找不到配置文件: {CONFIG_PATH}")
        return

    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # 2. 获取上游所有候选源
    candidates = parse_upstream_m3u(config.get('upstream_urls', []))
    print(f"共解析到 {len(candidates)} 个候选链接，准备开始测速匹配...")

    m3u_lines = ["#EXTM3U"]

    # 3. 逐个匹配精选频道并做连通性测试/打分
    for item in config.get('keep_channels', []):
        display_name = item['name']
        group_name = item.get('group', '精选频道')
        keywords = [clean_name(kw) for kw in item.get('keywords', [])]

        # 找出上游中符合关键词的所有候选源
        matched_candidates = []
        for cand in candidates:
            # 只要候选频道名字匹配任意一个关键词即可
            if any(kw == cand['clean_name'] or kw in cand['clean_name'] for kw in keywords):
                matched_candidates.append(cand)

        if not matched_candidates:
            print(f"⚠️ 无法在任何上游中找到频道: {display_name}")
            continue

        print(f"🔍 频道 [{display_name}] 找到 {len(matched_candidates)} 个潜在来源，开始多线程并发测速...")

        # 多线程对匹配到的候选源做测速打分
        tested_results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_cand = {executor.submit(test_url_latency, cand['url']): cand for cand in matched_candidates}
            for future in as_completed(future_to_cand):
                cand = future_to_cand[future]
                latency = future.result()
                if latency < float('inf'): # 过滤掉超时的不可用源
                    tested_results.append({
                        'cand': cand,
                        'latency': latency
                    })

        # 按延迟低到高升序排序（延迟越低越好）
        tested_results.sort(key=lambda x: x['latency'])

        if not tested_results:
            print(f"❌ 频道 [{display_name}] 的所有提供源均测速超时（失效）")
            continue

        # 4. 生成多源备用（Backup Links），并自动对齐 EPG 元数据
        for idx, res in enumerate(tested_results):
            cand = res['cand']
            latency = res['latency']

            # 第一条主线路保留原频道名，备用线路追加 (线路2)、(线路3) 等后缀
            line_title = display_name if idx == 0 else f"{display_name} (线路{idx+1})"
            
            # EPG 属性组装
            tvg_id_attr = f'tvg-id="{cand["tvg_id"]}"' if cand["tvg_id"] else f'tvg-id="{display_name}"'
            tvg_name_attr = f'tvg-name="{cand["tvg_name"]}"' if cand["tvg_name"] else f'tvg-name="{display_name}"'
            tvg_logo_attr = f'tvg-logo="{cand["tvg_logo"]}"' if cand["tvg_logo"] else ''

            extinf_line = f'#EXTINF:-1 {tvg_id_attr} {tvg_name_attr} {tvg_logo_attr} group-title="{group_name}",{line_title}'
            
            m3u_lines.append(extinf_line)
            m3u_lines.append(cand['url'])
            
            print(f"  └─ 接入 [{line_title}] | 响应延迟: {latency:.1f}ms")

    # 5. 写入最终文件 Gather.m3u 到根目录
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(m3u_lines))

    print(f"\n🎉 处理完毕！完全版直播源已生成至: {OUTPUT_PATH}")

if __name__ == '__main__':
    main()
