# 配置文件示例（含 source 字段）
### 在你现有配置基础上，只加了一个可选字段 source。写法有两种：

### 写法 A：只从一个源匹配

```
{
  "name": "CCTV1",
  "group": "央视",
  "keywords": ["CCTV1"],
  "source": "https://iptv-org.github.io/iptv/index.m3u",
  "xml_url": "https://epg.pw/api/epg.xml?channel_id=561309"
}
```

### 写法 B：从多个指定源匹配

```
{
  "name": "凤凰中文台",
  "group": "港澳台",
  "keywords": ["凤凰中文台"],
  "source": [
    "https://iptv.yang-1989.xyz/playlist.m3u",
    "https://iptv-org.github.io/iptv/index.m3u"
  ],
  "xml_url": "https://epg.pw/api/epg.xml?channel_id=410378"
}
```

### 不写 source 时

```
{
  "name": "Al Jazeera",
  "group": "NEWS",
  "keywords": ["AlJazeera.qa@Arabic"],
  "xml_url": "https://epg.pw/api/epg.xml?channel_id=76735"
}
```

→ 行为跟现在一样：在所有 upstream_urls 里匹配。
