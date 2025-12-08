from itertools import accumulate
import pandas as pd
import os
import argparse
import configparser


class Label():
    def __init__(self, video_fingerprint_path, traffic_fingerprint_path, label_path):
        self.video_fingerprint_path = video_fingerprint_path
        self.traffic_fingerprint_path = traffic_fingerprint_path
        self.label_path = label_path

    def single_label_chunk2seg(self, seg_list, chunk_list):
        seg_list_accum = list(accumulate(seg_list))
        label = {}
        for sidx_chunk in range(len(chunk_list)):
            sub_chunk_list = chunk_list[sidx_chunk:]
            tmp_label = {}
            leidx_seg = 0
            for i in range(len(sub_chunk_list)):
                flag = 0
                for sidx_seg in range(leidx_seg, len(seg_list_accum)):
                    for j in range(sidx_seg, len(seg_list_accum)):
                        if 0 <= sub_chunk_list[i] - seg_list_accum[j] <= 1200:
                            tmp_label[sub_chunk_list[i]] = [[sidx_seg, j+1], seg_list[sidx_seg: j+1]]
                            seg_list_accum = [x - seg_list_accum[j] for x in seg_list_accum]
                            leidx_seg = j + 1
                            flag = 1
                            break
                    if flag:
                        break
                    seg_list_accum = [x - seg_list_accum[sidx_seg] for x in seg_list_accum]
            if len(tmp_label) >= len(label):
                label = tmp_label.copy()
        return label

    def batch_label_chunk2seg(self):
        if not os.path.exists(self.label_path):
            with open(self.label_path, 'w') as f:
                f.write('flow_id,vid,itag,chunk,subseg,subseg_list\n')
        self.video_fingerprint = pd.read_csv(self.video_fingerprint_path)
        self.traffic_fingerprint = pd.read_csv(self.traffic_fingerprint_path)
        for idx, row in self.traffic_fingerprint.iterrows():
            vid = row['vid']
            itag = row['itag']
            flow_id = idx
            # 寻找video_fingerprint中对应的seg_list
            vf_row = self.video_fingerprint[(self.video_fingerprint['vid'] == vid) & (self.video_fingerprint['itag'] == itag)]
            if vf_row.empty:
                print(f"Cannot find video fingerprint for vid: {vid}, itag: {itag}")
                continue
            seg_list = [int(s) for s in vf_row.iloc[0]['seg_list'].split('/')]
            chunk_list = [int(s) for s in row['chunk_list'].split('/')]
            label = self.single_label_chunk2seg(seg_list, chunk_list)
            # 组装新的结果记录到列表
            for chunk, ([start_idx, end_idx], subseg_list) in label.items():
                subseg = f"{start_idx}-{end_idx}"
                subseg_list_str = '/'.join([str(s) for s in subseg_list])
                with open(self.label_path, 'a') as f:
                    f.write(f'{flow_id},{vid},{itag},{chunk},{subseg},{subseg_list_str}\n')


def main():
    # 读取配置文件
    conf = configparser.ConfigParser()
    conf.read('src/extraction/config.conf', encoding='utf-8')
    workdir = os.getcwd() + os.sep
    
    # 创建参数解析器
    parser = argparse.ArgumentParser(
        description='视频 Chunk 到 Segment 标注工具',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    
    # 路径参数
    parser.add_argument('--video-path', type=str, 
                        default=workdir + conf.get('path', 'fingerprint_path') + 'video.csv',
                        help='视频指纹文件路径')
    parser.add_argument('--traffic-path', type=str,
                        default=workdir + conf.get('path', 'fingerprint_path') + 'traffic.csv',
                        help='流量指纹文件路径')
    parser.add_argument('--label-path', type=str,
                        default=workdir + conf.get('path', 'fingerprint_path') + 'label.csv',
                        help='标注结果输出路径')
    
    args = parser.parse_args()
    
    # 打印配置信息
    print('=' * 60)
    print('Chunk to Segment 标注工具')
    print('=' * 60)
    print(f'视频指纹文件: {args.video_path}')
    print(f'流量指纹文件: {args.traffic_path}')
    print(f'输出标签文件: {args.label_path}')
    print('=' * 60)
    
    # 检查输入文件是否存在
    if not os.path.exists(args.video_path):
        print(f'\n错误: 视频指纹文件不存在: {args.video_path}')
        return
    if not os.path.exists(args.traffic_path):
        print(f'\n错误: 流量指纹文件不存在: {args.traffic_path}')
        return
    
    # 创建输出目录
    output_dir = os.path.dirname(args.label_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        print(f'\n已创建输出目录: {output_dir}')
    
    try:
        # 创建标注器并执行标注
        print('\n开始 Chunk 到 Segment 的对齐标注...')
        labeler = Label(
            video_fingerprint_path=args.video_path,
            traffic_fingerprint_path=args.traffic_path,
            label_path=args.label_path
        )
        labeler.batch_label_chunk2seg()
        print(f'\n标注完成! 结果已保存到: {args.label_path}')
        
        # 读取并显示结果摘要
        result_df = pd.read_csv(args.label_path)
        print(f'\n标注结果摘要:')
        print(f'  总标注条数: {len(result_df)}')
        print(f'  涉及视频数: {result_df["vid"].nunique()}')
        print(f'  涉及流数: {result_df["flow_id"].nunique()}')
        print(f'\n前5条标注结果:')
        print(result_df.head().to_string(index=False))
        
    except Exception as e:
        print(f'\n标注过程中出现错误: {str(e)}')
        raise


if __name__ == '__main__':
    main()
    """
    python src/other/label_chunk2seg.py
    """