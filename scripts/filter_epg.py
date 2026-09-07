import json
import re
import requests
import gzip
from datetime import datetime
import xml.etree.ElementTree as ET

def clean_str(s):
    """去除特殊字符并转换为小写，提升匹配成功率"""
    return re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', s).lower()

def fetch_m3u(url):
    """拉取上游 M3U 并解析频道列表 [(title, link)]"""
    channels = []
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            lines = resp.text.splitlines()
            current_title = ""
            for line in lines:
                line = line.strip()
                if line.startswith("#EXTINF:"):
                    # 提取频道名称
                    parts = line.split(",")
                    current_title = parts[-1].strip() if len(parts) > 1 else ""
                elif line and not line.startswith("#") and current_title:
                    channels.append((current_title, line))
                    current_title = ""
            print(f"✅ 成功从 {url} 抓取到 {len(channels)} 个频道")
    except Exception as e:
        print(f"❌ 拉取上游 M3U 失败 [{url}]: {e}")
    return channels

def main():
    # 1. 读取配置文件
    with open('config/config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    # 2. 拉取所有上游频道源
    all_raw_channels = []
    for upstream in config.get('upstream_urls', []):
        all_raw_channels.extend(fetch_m3u(upstream))

    print(f"\n📡 上游合并完成，共计 {len(all_raw_channels)} 条原始线路")

    # 3. 根据 keep_channels 过滤并保留对应频道
    final_m3u_items = []
    keep_channels = config.get('keep_channels', [])

    for target in keep_channels:
        t_name = target.get('name')
        t_group = target.get('group', 'Default')
        keywords = target.get('keywords', [])
        
        matched_urls = []
        for raw_title, raw_url in all_raw_channels:
            clean_raw_title = clean_str(raw_title)
            # 关键词模糊匹配
            for kw in keywords:
                if clean_str(kw) in clean_raw_title:
                    matched_urls.append(raw_url)
                    break
        
        if matched_urls:
            print(f"🎯 [{t_name}] 匹配到 {len(matched_urls)} 条有效线路")
            # 写入 M3U 节点信息
            for idx, url in enumerate(matched_urls, 1):
                final_m3u_items.append(f'#EXTINF:-1 tvg-name="{t_name}" group-title="{t_group}",{t_name}\n{url}')
        else:
            print(f"⚠️ [{t_name}] 未匹配到任何线路，请尝试放宽 keywords！")

    # 4. 生成并写出 Gather.m3u
    m3u_content = "#EXTM3U\n" + "\n".join(final_m3u_items)
    with open('Gather.m3u', 'w', encoding='utf-8') as f:
        f.write(m3u_content)
    print(f"\n🎉 M3U 写入完成！最终文件共保留 {len(final_m3u_items)} 条频道线路。")

    # 5. 抓取并合成 EPG 节目单
    today_str = datetime.now().strftime("%Y%m%d")
    root_epg = ET.Element("tv")

    print("\n📺 开始抓取并合成精简版 EPG 数据...")
    for target in keep_channels:
        xml_url = target.get('xml_url')
        if not xml_url:
            continue
        
        # 动态替换死板的 date=2026xxxx 参数为当天日期
        xml_url = re.sub(r'date=\d{8}', f'date={today_str}', xml_url)
        
        try:
            resp = requests.get(xml_url, timeout=10)
            if resp.status_code == 200:
                channel_xml = ET.fromstring(resp.content)
                for elem in channel_xml:
                    root_epg.append(elem)
                print(f"  └─ ✅ [{target['name']}] EPG 抓取成功")
            else:
                print(f"  └─ ⚠️ [{target['name']}] EPG HTTP 状态码: {resp.status_code}")
        except Exception as e:
            print(f"  └─ ❌ [{target['name']}] EPG 抓取失败: {e}")

    # 保存为 Gather_epg.xml.gz
    epg_data = ET.tostring(root_epg, encoding='utf-8', xml_declaration=True)
    with gzip.open("Gather_epg.xml.gz", "wb") as f:
        f.write(epg_data)
    print("📦 EPG 打包完成，已导出为 Gather_epg.xml.gz！")

if __name__ == '__main__':
    main()
