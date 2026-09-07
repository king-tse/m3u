import json
import re
import requests
import gzip
from datetime import datetime
import xml.etree.ElementTree as ET

def clean_str(s):
    """去除特殊字符并转小写，极大提高匹配率"""
    return re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', s).lower()

def fetch_m3u(url):
    """拉取上游 M3U 列表"""
    channels = []
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            lines = resp.text.splitlines()
            current_title = ""
            for line in lines:
                line = line.strip()
                if line.startswith("#EXTINF:"):
                    parts = line.split(",")
                    current_title = parts[-1].strip() if len(parts) > 1 else ""
                elif line and not line.startswith("#") and current_title:
                    channels.append((current_title, line))
                    current_title = ""
            print(f"✅ 从 [{url}] 成功拉取到 {len(channels)} 条原始线路")
    except Exception as e:
        print(f"❌ 拉取 [{url}] 失败: {e}")
    return channels

def main():
    # 1. 读取配置
    with open('config/config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    # 2. 获取所有上游线路
    all_raw_channels = []
    for upstream in config.get('upstream_urls', []):
        all_raw_channels.extend(fetch_m3u(upstream))

    print(f"\n📡 上游合并完成，总计 {len(all_raw_channels)} 条线路")

    # 3. 筛选 M3U 频道
    final_m3u_items = []
    keep_channels = config.get('keep_channels', [])

    for target in keep_channels:
        t_name = target.get('name')
        t_group = target.get('group', 'NEWS')
        keywords = target.get('keywords', [])
        
        matched_urls = []
        for raw_title, raw_url in all_raw_channels:
            clean_raw_title = clean_str(raw_title)
            for kw in keywords:
                if clean_str(kw) in clean_raw_title:
                    matched_urls.append(raw_url)
                    break
        
        if matched_urls:
            print(f"🎯 [{t_name}] 成功匹配到 {len(matched_urls)} 条线路")
            for url in matched_urls:
                final_m3u_items.append(f'#EXTINF:-1 tvg-name="{t_name}" group-title="{t_group}",{t_name}\n{url}')
        else:
            print(f"⚠️ [{t_name}] 未能匹配到线路")

    # 4. 强制写入 Gather.m3u
    m3u_content = "#EXTM3U\n" + "\n".join(final_m3u_items)
    with open('Gather.m3u', 'w', encoding='utf-8') as f:
        f.write(m3u_content)
    print(f"\n🎉 Gather.m3u 生成成功！包含 {len(final_m3u_items)} 条播放源。")

    # 5. 合成并压缩生成 Gather_epg.xml.gz
    today_str = datetime.now().strftime("%Y%m%d")
    root_epg = ET.Element("tv")

    print("\n📺 开始拼接 EPG xml 数据...")
    for target in keep_channels:
        xml_url = target.get('xml_url')
        if not xml_url:
            continue
        
        # 自动将 url 中的 date=2026xxxx 替换为当天的年月日
        xml_url = re.sub(r'date=\d{8}', f'date={today_str}', xml_url)
        
        try:
            resp = requests.get(xml_url, timeout=10)
            if resp.status_code == 200:
                channel_xml = ET.fromstring(resp.content)
                for elem in channel_xml:
                    root_epg.append(elem)
                print(f"  └─ ✅ 成功拼接 [{target['name']}]")
        except Exception as e:
            print(f"  └─ ❌ 拼接 [{target['name']}] 失败: {e}")

    # 将 XML 转换为 bytes 并通过 gzip 写入 Gather_epg.xml.gz
    xml_data = ET.tostring(root_epg, encoding='utf-8', xml_declaration=True)
    with gzip.open("Gather_epg.xml.gz", "wb") as f:
        f.write(xml_data)
    print("📦 Gather_epg.xml.gz 压缩打包完毕！")

if __name__ == '__main__':
    main()
