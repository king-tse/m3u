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

---

## 节目单
配置文件写法

### 单一频道直接xml文件的
```
  "xml_url": "https://epg.pw/api/epg.xml?channel_id=76735"
```

### 集合多个频道在一个gz文件的
```
  "xml_gz": "https://example.com/epg/whole_epg.xml.gz",
  "xml_gz_match": ["凤凰香港台", "Phoenix Hong Kong"]
```

在需要从 gz 包提取的频道上，把原来的 xml_url 换成 xml_gz，并增加 xml_gz_match 指定要匹配的频道标识：

```
{
  "name": "凤凰香港台",
  "group": "港澳台",
  "keywords": ["凤凰香港台"],
  "xml_gz": "https://example.com/epg/whole_epg.xml.gz",
  "xml_gz_match": ["凤凰香港台", "Phoenix Hong Kong"]
}
```

xml_gz：gz 包地址

xml_gz_match：在 gz 解压出来的 XML 里，用这些字符串去匹配 <channel> 的 id 或 <display-name>（清洗后精确匹配，和 m3u 那边逻辑一致）

如果不写 xml_gz_match，就默认用频道的 name 去匹配

同时，原来的 xml_url 逻辑保留不变，两个可以同时存在（先处理 xml_url，再处理 xml_gz）。
