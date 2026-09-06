import os
import re
import json
import time
import gzip
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# 项目基础路径配置
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, 'config', 'config.json')
M3U_OUTPUT_PATH = os.path.join(BASE_DIR, 'Gather.m3u')
EPG_OUTPUT_PATH = os.path.join(BASE_DIR, 'Gather_epg.xml.gz')

def clean_name(str_val):
    """清洗频道名称：统一小写并剔除特殊字符"""
    if not str_val:
        return ''
    str_val = str_val.lower()
    str_val = re.sub(r'\(.*?\)|\[.*?\]|「.*?」|（.*?）', '', str_val)
    return re.sub(r'[^a-z0-9\u4e00-\u9fa5]', '', str_val)

def test_url_latency(url, timeout=3):
    """检测 URL 连通性并返回响应延迟（毫秒）"""
    start_time = time.time()
    try:
        if HAS_REQUESTS:
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
    """拉取并解析上游全量 M3U 数据"""
    channel_candidates = []
    
    for url in urls:
        print(f"📡 正在拉取上游源: {url}")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode('utf-8', errors='ignore')
                
                curr_meta = {}
                for line in content.splitlines():
                    line = line.strip()
                    if line.startswith('#EXTINF:'):
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

def generate_custom_epg(config):
    """根据独立 xml_url 对齐频道 ID，生成 Gather_epg.xml.gz"""
    print("\n📅 开始抓取并生成专属 Gather_epg.xml.gz...")
    
    tv_root = ET.Element('tv')
    tv_root.set('generator-info-name', 'Gather-IPTV-EPG')
    
    keep_channels = config.get('keep_channels', [])
    
    # 写入 <channel> 基础节点
    for item in keep_channels:
        channel_name = item['name']
        channel_node = ET.SubElement(tv_root, 'channel', id=channel_name)
        display_node = ET.SubElement(channel_node, 'display-name')
        display_node.text = channel_name

    # 抓取并合并 <programme> 节点
    for item in keep_channels:
        channel_name = item['name']
        xml_url = item.get('xml_url')
        
        if not xml_url:
            print(f"⚠️ 频道 [{channel_name}] 未配置 xml_url，跳过 EPG 抓取")
            continue
            
        print(f"📥 正在抓取 [{channel_name}] 的 EPG 数据: {xml_url}")
        try:
            req = urllib.request.Request(xml_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=8) as resp:
                xml_data = resp.read()
                
                # 若为 .gz 压缩格式，自动解压
                if xml_url.endswith('.gz') or xml_data[:2] == b'\x1f\x8b':
                    xml_data = gzip.decompress(xml_data)
                    
                sub_tree = ET.fromstring(xml_data)
                
                prog_count = 0
                for prog in sub_tree.findall('programme'):
                    # 强制重写 channel 属性，确保与 M3U 完美匹配
                    prog.set('channel', channel_name)
                    tv_root.append(prog)
                    prog_count += 1
                
                print(f"  └─ 已成功对齐导入 {prog_count} 条节目记录")
                
        except Exception as e:
            print(f"❌ 抓取 [{channel_name}] EPG 失败: {e}")

    # 压缩保存到根目录
    xml_string = ET.tostring(tv_root, encoding='utf-8', xml_declaration=True)
    with gzip.open(EPG_OUTPUT_PATH, 'wb') as f:
        f.write(xml_string)
        
    print(f"✅ EPG 电子节目单成功生成至: {EPG_OUTPUT_PATH}")

def main():
    if not os.path.exists(CONFIG_PATH):
        print(f"❌ 未找到配置文件: {CONFIG_PATH}")
        return

    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # 1. 抓取与测速 M3U 直播源
    candidates = parse_upstream_m3u(config.get('upstream_urls', []))
    print(f"\n🚀 共解析到 {len(candidates)} 个候选源，开始多线程测速筛选...")

    m3u_lines = ["#EXTM3U"]

    for item in config.get('keep_channels', []):
        display_name = item['name']
        group_name = item.get('group', '精选频道')
        keywords = [clean_name(kw) for kw in item.get('keywords', [])]

        matched_candidates = []
        for cand in candidates:
            if any(kw == cand['clean_name'] or kw in cand['clean_name'] for kw in keywords):
                matched_candidates.append(cand)

        if not matched_candidates:
            print(f"⚠️ 未找到匹配源: {display_name}")
            continue

        print(f"🔍 频道 [{display_name}] 匹配到 {len(matched_candidates)} 个源，正在测速...")

        tested_results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_cand = {executor.submit(test_url_latency, cand['url']): cand for cand in matched_candidates}
            for future in as_completed(future_to_cand):
                cand = future_to_cand[future]
                latency = future.result()
                if latency < float('inf'):
                    tested_results.append({'cand': cand, 'latency': latency})

        tested_results.sort(key=lambda x: x['latency'])

        if not tested_results:
            print(f"❌ 频道 [{display_name}] 的所有提供源均不可用")
            continue

        # 生成 Backup Links 并组装 M3U 标签
        for idx, res in enumerate(tested_results):
            cand = res['cand']
            latency = res['latency']

            line_title = display_name if idx == 0 else f"{display_name} (线路{idx+1})"
            
            tvg_id_attr = f'tvg-id="{display_name}"'
            tvg_name_attr = f'tvg-name="{display_name}"'
            tvg_logo_attr = f'tvg-logo="{cand["tvg_logo"]}"' if cand["tvg_logo"] else ''

            extinf_line = f'#EXTINF:-1 {tvg_id_attr} {tvg_name_attr} {tvg_logo_attr} group-title="{group_name}",{line_title}'
            
            m3u_lines.append(extinf_line)
            m3u_lines.append(cand['url'])
            
            print(f"  └─ [{line_title}] 接入成功 | 延迟: {latency:.1f}ms")

    # 2. 输出 Gather.m3u
    with open(M3U_OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(m3u_lines))
    print(f"\n🎉 专属直播源已生成至: {M3U_OUTPUT_PATH}")

    # 3. 输出 Gather_epg.xml.gz
    generate_custom_epg(config)

if __name__ == '__main__':
    main()
