import urllib.request
import re
import json

# 1. 读取配置
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

# 用于存储清洗后的上游全部频道数据 { clean_name: url }
upstream_channels = {}

def clean_name(name):
    # 复用你播放器里的清洗逻辑：转小写，去括号，去特殊字符
    name = re.sub(r'\(.*?\)|\[.*?\]|「.*?」', '', name)
    return re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', name).lower()

# 2. 拉取所有上游 M3U 并解析
for url in config['upstream_urls']:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            content = response.read().decode('utf-8')
            
            current_name = ""
            for line in content.splitlines():
                line = line.strip()
                if line.startswith('#EXTINF:'):
                    # 提取频道名字
                    current_name = line.split(',')[-1].strip()
                elif line.startswith('http') and current_name:
                    c_name = clean_name(current_name)
                    # 优先保留先匹配到的有效源
                    if c_name not in upstream_channels:
                        upstream_channels[c_name] = line
                    current_name = ""
    except Exception as e:
        print(f"读取上游 {url} 失败: {e}")

# 3. 按照你的精选清单生成新的 M3U 文件
m3u_output = ["#EXTM3U"]

for item in config['keep_channels']:
    custom_display_name = item['name']
    matched_url = None
    
    # 尝试匹配关键字
    for kw in item['keywords']:
        clean_kw = clean_name(kw)
        if clean_kw in upstream_channels:
            matched_url = upstream_channels[clean_kw]
            break
            
    # 如果匹配成功，写入 M3U
    if matched_url:
        m3u_output.append(f'#EXTINF:-1 group-title="我的精选",{custom_display_name}')
        m3u_output.append(matched_url)
    else:
        print(f"⚠️ 匹配失败: {custom_display_name}")

# 4. 保存为你的专属 playlist.m3u
with open("my_list.m3u", "w", encoding="utf-8") as f:
    f.write("\n".join(m3u_output))

print("✅ 精选 M3U 列表生成完成！")
