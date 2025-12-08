# VideoTrafficProcess

YouTube 视频流量采集与指纹提取工具

## 命令行使用说明

### 1. 视频流量采集 (capture_traffic.py)

```bash
# 批量采集
python src/capture/capture_traffic.py --mode batch

# 单个视频采集
python src/capture/capture_traffic.py --mode single --url "https://www.youtube.com/watch?v=xxxxx"

# 自定义参数
python src/capture/capture_traffic.py --mode batch --turn 3 --time-duration 60 --resolution 480p
python src/capture/capture_traffic.py --mode batch --if-tshark 1 --if-mitm 0
```

### 2. 视频指纹提取 (get_segment.py)

```bash
# 批量下载视频
python src/extraction/get_segment.py --mode download

# 提取视频指纹
python src/extraction/get_segment.py --mode fingerprint

# 提取融合指纹
python src/extraction/get_segment.py --mode fusion

# 自定义参数
python src/extraction/get_segment.py --mode download --if-use-url-list 1
python src/extraction/get_segment.py --mode fingerprint --if-use-url-list 0
```

### 3. 流量 Chunk 提取 (get_chunk.py)

```bash
# 从 PCAP 提取
python src/extraction/get_chunk.py --mode pcap

# 从 ResponseBody 提取
python src/extraction/get_chunk.py --mode response

# 自定义路径
python src/extraction/get_chunk.py --mode pcap --pcap-path "data/traffic/"
```

### 4. Chunk 到 Segment 标注 (label_chunk2seg.py)

```bash
# 使用默认配置执行标注
python src/other/label_chunk2seg.py

# 自定义输入文件路径
python src/other/label_chunk2seg.py --video-path data/fingerprint/video.csv --traffic-path data/fingerprint/traffic.csv

# 自定义输出路径
python src/other/label_chunk2seg.py --label-path data/fingerprint/my_label.csv
```

**功能说明**：
- 将流量指纹中的 chunk 与视频指纹中的 segment 进行对齐标注
- 输出每个 chunk 对应的 segment 范围和 segment 大小列表
- 标注结果包含：流ID、视频ID、itag、chunk大小、segment范围、segment列表

## 典型工作流程

```bash
# 1. 准备 URL 列表（编辑 data/url/url.csv）

# 2. 采集流量
python src/capture/capture_traffic.py --mode batch

# 3. 下载视频
python src/extraction/get_segment.py --mode download

# 4. 提取视频指纹
python src/extraction/get_segment.py --mode fingerprint

# 5. 提取流量 Chunk
python src/extraction/get_chunk.py --mode pcap
python src/extraction/get_chunk.py --mode response

# 6. 融合流量指纹
python src/extraction/get_segment.py --mode fusion

# 7. Chunk 到 Segment 标注
python src/other/label_chunk2seg.py
```

## 输出文件说明

### 指纹文件
- `data/fingerprint/video.csv`: 视频指纹文件，包含每个视频的 segment 大小序列
- `data/fingerprint/traffic.csv`: 流量指纹文件，包含每个采集流的 chunk 大小序列
- `data/fingerprint/label.csv`: 标注文件，包含 chunk 到 segment 的对应关系

### 标注文件格式 (label.csv)
| 字段 | 说明 |
|------|------|
| flow_id | 流ID（对应 traffic.csv 的行索引） |
| vid | 视频ID |
| itag | 视频流标签（格式：视频itag/音频itag） |
| chunk | chunk 大小（字节） |
| subseg | 对应的 segment 范围（格式：起始索引-结束索引） |
| subseg_list | 对应的 segment 大小列表（格式：大小1/大小2/...） |
