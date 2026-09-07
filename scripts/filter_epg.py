import json
import requests
import xml.etree.ElementTree as ET

# 1. 读取配置文件
with open('config/config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

# 存储所有提取到的 EPG 节点
all_program_elements = []

# 2. 遍历每一个频道，精细化拉取对应的 EPG XML
for channel in config.get('keep_channels', []):
    xml_url = channel.get('xml_url')
    if not xml_url:
        continue
    
    try:
        response = requests.get(xml_url, timeout=10)
        if response.status_code == 200:
            # 解析单个频道的 XML
            root = ET.fromstring(response.content)
            # 提取所有的 <channel> 和 <programme> 标签
            for child in root:
                all_program_elements.append(child)
            print(f"✅ 成功抓取 [{channel['name']}] 的 EPG")
        else:
            print(f"⚠️ 抓取 [{channel['name']}] 失败，状态码: {response.status_code}")
    except Exception as e:
        print(f"❌ 请求 [{channel['name']}] EPG 出错: {e}")

# 3. 将所有频道合并为一个精简版 XML 并压缩保存为 Gather_epg.xml.gz
# （这样生成出来的文件可能只有几 KB 到几 MB，再也不用担心超过 GitHub 的 100MB 限制了！）
