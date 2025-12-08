import configparser
import csv
import json
import os
import re
import subprocess
import time
import argparse
from concurrent.futures import ThreadPoolExecutor
from itertools import accumulate
import requests
from bs4 import BeautifulSoup


class Reference():
    def __init__(self, Reference_Type, Reference_Size, Subsegment_Duration, Starts_with_SAP, SAP_Type):
        self.Reference_Type = Reference_Type
        self.Reference_Size = Reference_Size
        self.Subsegment_Duration = Subsegment_Duration
        self.Starts_with_SAP = Starts_with_SAP
        self.SAP_Type = SAP_Type


class Track():
    def __init__(self, Track_Time, Track_Number, Track_Position):
        self.Track_Time = Track_Time
        self.Track_Number = Track_Number
        self.Track_Position = Track_Position


class Box():
    def __init__(self, filetype, start, end, videopath):
        self.filetype = filetype
        self.start = start
        self.end = end
        if self.filetype == 'mp4':
            self.get_metedata_mp4(videopath)
        elif self.filetype == 'webm':
            self.get_metedata_webm(videopath)
        else:
            raise ValueError('Filetype Wrong')

    def get_metedata_mp4(self, videopath):
        with open(videopath, 'rb') as f:
            header_data = f.read(10000)
        sidx = header_data[self.start:self.end + 1]

        self.Box_Siz = int.from_bytes(sidx[:4], byteorder='big')
        sidx = sidx[4:]
        self.Box_Type = int.from_bytes(sidx[:4], byteorder='big')
        sidx = sidx[4:]
        self.Version = int.from_bytes(sidx[:1], byteorder='big')
        sidx = sidx[1:]
        self.Flags = int.from_bytes(sidx[:3], byteorder='big')
        sidx = sidx[3:]
        self.Reference_ID = int.from_bytes(sidx[:4], byteorder='big')
        sidx = sidx[4:]
        self.Timescale = int.from_bytes(sidx[:4], byteorder='big')
        sidx = sidx[4:]
        if self.Version == 0:
            self.Earliest_Presentation_Time = int.from_bytes(sidx[:4], byteorder='big')
            sidx = sidx[4:]
            self.First_Offset = int.from_bytes(sidx[:4], byteorder='big')
            sidx = sidx[4:]
        elif self.Version == 1:
            self.Earliest_Presentation_Time = int.from_bytes(sidx[:8], byteorder='big')
            sidx = sidx[8:]
            self.First_Offset = int.from_bytes(sidx[:8], byteorder='big')
            sidx = sidx[8:]
        else:
            raise Exception('Version Inexistence')
        self.Reserved = int.from_bytes(sidx[:2], byteorder='big')
        sidx = sidx[2:]
        self.Reference_Count = int.from_bytes(sidx[:2], byteorder='big')
        sidx = sidx[2:]

        self.reference = []
        self.reference_list = []
        self.duration_list = []
        while len(sidx) != 0:
            Reference_Type = int.from_bytes(sidx[:1], byteorder='big')
            sidx = sidx[1:]
            Reference_Size = int.from_bytes(sidx[:3], byteorder='big')
            sidx = sidx[3:]
            Subsegment_Duration = int.from_bytes(sidx[:4], byteorder='big')
            sidx = sidx[4:]
            Starts_with_SAP = int.from_bytes(sidx[:1], byteorder='big')
            sidx = sidx[1:]
            SAP_Type = int.from_bytes(sidx[:3], byteorder='big')
            sidx = sidx[3:]

            ref = Reference(Reference_Type, Reference_Size, Subsegment_Duration, Starts_with_SAP, SAP_Type)
            self.reference.append(ref)
            self.reference_list.append(Reference_Size)
            self.duration_list.append(Subsegment_Duration)

    def get_metedata_webm(self, videopath):
        with open(videopath, 'rb') as f:
            header_data = f.read(10000)
        cues = header_data[self.start:self.end + 1]

        self.Cues_Header = int.from_bytes(cues[:6], byteorder='big')
        cues = cues[6:]

        self.track = []
        self.track_list = []
        self.timeline = []
        while len(cues) != 0:
            Track_Time_Flag = int.from_bytes(cues[3:4], byteorder='big')
            cues = cues[4:]
            Track_Time_Length = Track_Time_Flag - 0x80
            Track_Time = int.from_bytes(cues[:Track_Time_Length], byteorder='big')
            cues = cues[Track_Time_Length:]
            Track_Number_Flag = int.from_bytes(cues[3:4], byteorder='big')
            cues = cues[4:]
            Track_Number_Length = Track_Number_Flag - 0x80
            Track_Number = int.from_bytes(cues[:Track_Number_Length], byteorder='big')
            cues = cues[Track_Number_Length:]
            Track_Position_Flag = int.from_bytes(cues[1:2], byteorder='big')
            cues = cues[2:]
            Track_Position_Length = Track_Position_Flag - 0x80
            Track_Position = int.from_bytes(cues[:Track_Position_Length], byteorder='big')
            cues = cues[Track_Position_Length:]

            tra = Track(Track_Time, Track_Number, Track_Position)
            self.track.append(tra)
            if len(self.track) > 1:
                self.track_list.append(self.track[-1].Track_Position - self.track[-2].Track_Position)
            self.timeline.append(Track_Time)


class Video():
    def __init__(self, video_url, videofile_path, fingerprint_path):
        conf = configparser.ConfigParser()
        conf.read('src/extraction/config.conf', encoding='UTF-8')
        workdir = os.getcwd() + os.sep
        self.videofile_path = videofile_path
        os.makedirs(self.videofile_path, exist_ok=True)
        os.makedirs(f'{self.videofile_path}websource', exist_ok=True)
        os.makedirs(f'{self.videofile_path}videoheader', exist_ok=True)
        self.fingerprint_path = fingerprint_path
        os.makedirs(self.fingerprint_path, exist_ok=True)
        self.errorlog = workdir + conf.get('path', 'errorlog')
        self.video_mp4_itag = conf.get('parameter', 'video_mp4_itag').split(',')
        self.video_webm_itag = conf.get('parameter', 'video_webm_itag').split(',')
        self.audio_mp4_itag = conf.get('parameter', 'audio_mp4_itag').split(',')
        self.audio_webm_itag = conf.get('parameter', 'audio_webm_itag').split(',')
        self.video_url = video_url
        self.video_name = self.video_url.split('=')[1]

    def get_websource(self):
        # if os.path.exists(f'{self.videofile_path}websource/{self.video_name}.html'):
        #     return 1
        for i in range(5):
            try:
                response = requests.get(self.video_url)
                # if 'adaptiveFormats' in response.text:
                with open(f'{self.videofile_path}websource/{self.video_name}.html', 'w', encoding='utf-8') as f:
                    f.write(response.text)
                return 1
            except:
                pass
        print(f'{self.video_name}: get websource error')
        with open(self.errorlog, 'a') as f:
            f.write(f'{self.video_name}: get websource error\n')
        return 0

    def analyse_websource(self):
        try:
            with open(f'{self.videofile_path}websource/{self.video_name}.html', 'r', encoding='utf-8') as f:
                html_content = f.read()
            soup = BeautifulSoup(html_content, 'html.parser')
            # 找到所有的 <script> 标签
            script_tags = soup.find_all('script')
            # 定义正则表达式来匹配 JavaScript 变量
            pattern = re.compile(r'var\s+ytInitialPlayerResponse\s*=\s*({.*?});', re.DOTALL)

            # 在每个 <script> 标签中搜索匹配的内容
            for script_tag in script_tags:
                # 获取 <script> 标签的所有内容，并将其合并为一个字符串
                script_content = ''.join(map(str, script_tag.contents))
                # 使用正则表达式匹配 JavaScript 变量
                match = pattern.search(script_content)
                if match:
                    # 提取匹配的 JavaScript 变量内容
                    javascript_code = match.group(1)
            data = json.loads(javascript_code)
            service_tracking_params = data.get('streamingData', {}).get('adaptiveFormats', [])

            self.itag_list = []
            self.itag_filetype = {}
            self.itag_mimetype = {}
            self.itag_vcodec = {}
            self.itag_indexrange = {}
            self.itag_contentlength = {}
            self.itag_quality = {}
            self.itag_durationMs = {}
            for param in service_tracking_params:
                itag = str(param.get('itag'))
                if param.get('isDrc'):
                    itag = itag + '-drc'
                if itag in self.itag_list:
                    continue
                if itag in (self.video_mp4_itag + self.video_webm_itag + self.audio_mp4_itag + self.audio_webm_itag):
                    self.itag_list.append(itag)
                    self.itag_filetype[itag] = param['mimeType'].split('/')[1].split(';')[0]
                    self.itag_mimetype[itag] = param['mimeType'].split('/')[0]
                    self.itag_vcodec[itag] = param['mimeType'].split('\"')[1].split('.')[0]
                    indexRange = param.get('indexRange')
                    indexRange['start'] = int(indexRange['start'])
                    indexRange['end'] = int(indexRange['end'])
                    self.itag_indexrange[itag] = indexRange
                    self.itag_contentlength[itag] = int(param.get('contentLength'))
                    if self.itag_mimetype[itag] == 'video':
                        self.itag_quality[itag] = param.get('qualityLabel')
                    elif self.itag_mimetype[itag] == 'audio':
                        self.itag_quality[itag] = param.get('audioQuality')
                    self.itag_durationMs[itag] = param.get('approxDurationMs')
            return 1
        except:
            print(f'{self.video_name}: analyse websource error')
            with open(self.errorlog, 'a') as f:
                f.write(f'{self.video_name}: analyse websource error\n')
            return 0

    def download_video(self):
        for itag in self.itag_list:
            videopath = f'{self.videofile_path}videoheader/{self.video_name}/{self.video_name}_{self.itag_mimetype[itag]}_{itag}.{self.itag_filetype[itag]}'
            flag = 0
            for i in range(5):
                if os.path.exists(videopath):
                    if os.path.getsize(videopath) > 2 * 1024:
                        flag = 1
                        break
                    else:
                        os.remove(videopath)
                
                command = f'yt-dlp --limit-rate 10K -f {itag} {self.video_url} -o {videopath}'.split(' ')
                try:
                    
                    process = subprocess.Popen(command)
                    time.sleep(30)
                    process.kill()
                except:
                    pass
                time.sleep(3)
                if os.path.exists(videopath + '.part'):
                    os.rename(videopath + '.part', videopath)
            if flag == 0:
                print(f'{self.video_name}: download video {itag} error')
                with open(self.errorlog, 'a') as f:
                    f.write(f'{self.video_name}: download video {itag} error\n')

    def get_video_fingerprint(self):
        for itag in self.itag_list:
            try:
                start, end = self.itag_indexrange[itag]['start'], self.itag_indexrange[itag]['end']
                videopath = f'{self.videofile_path}videoheader/{self.video_name}/{self.video_name}_{self.itag_mimetype[itag]}_{itag}.{self.itag_filetype[itag]}'
                box = Box(self.itag_filetype[itag], start, end, videopath)

                fingerprint_csv = self.fingerprint_path + 'video0.csv'
                if not os.path.exists(fingerprint_csv):
                    with open(fingerprint_csv, 'a') as f:
                        f.write('vid,itag,mimetype/filetype,quality,vcodec,contentlength,seg_num,seg_list,time_list\n')
                with open(fingerprint_csv, 'a') as f:
                    vid = self.video_name
                    if self.itag_mimetype[itag] == 'video' and box.filetype == 'mp4':
                        seg_list = box.reference_list[:-1]
                        dura_list = [1000 * x // box.Timescale for x in box.duration_list[:-1]]
                        time_list = list(accumulate(dura_list))
                    elif self.itag_mimetype[itag] == 'video' and box.filetype == 'webm':
                        seg_list = box.track_list
                        time_list = box.timeline[1:]
                    elif self.itag_mimetype[itag] == 'audio' and box.filetype == 'mp4':
                        seg_list = box.reference_list
                        dura_list = [1000 * x // box.Timescale for x in box.duration_list[:-1]]
                        time_list = [0] + list(accumulate(dura_list))
                    elif self.itag_mimetype[itag] == 'audio' and box.filetype == 'webm':
                        seg_list = box.track_list
                        time_list = box.timeline[:-1]
                    seg_str = '/'.join([str(seg) for seg in seg_list])
                    time_str = '/'.join([str(tim) for tim in time_list])
                    f.write(f'{vid},{itag},{self.itag_mimetype[itag]}/{self.itag_filetype[itag]},{self.itag_quality[itag]},{self.itag_vcodec[itag]},{str(self.itag_contentlength[itag])},{str(len(seg_list))},{seg_str},{time_str}\n')
            except:
                print(f'{self.video_name}: get video fingerprint {itag} error')
                with open(self.errorlog, 'a') as f:
                    f.write(f'{self.video_name}: get video fingerprint {itag} error\n')
                # return 0
        return 1

    def get_video_fusion_fingerprint(self):
        video_itags = list(set(self.itag_list) & set(self.video_mp4_itag + self.video_webm_itag))
        audio_itags = list(set(self.itag_list) & set(self.audio_mp4_itag + self.audio_webm_itag))
        for video_itag in video_itags:
            for audio_itag in audio_itags:
                try:
                    video_start, video_end = self.itag_indexrange[video_itag]['start'], self.itag_indexrange[video_itag]['end']
                    audio_start, audio_end = self.itag_indexrange[audio_itag]['start'], self.itag_indexrange[audio_itag]['end']
                    videopath = f'{self.videofile_path}videoheader/{self.video_name}/{self.video_name}_{self.itag_mimetype[video_itag]}_{video_itag}.{self.itag_filetype[video_itag]}'
                    audiopath = f'{self.videofile_path}videoheader/{self.video_name}/{self.video_name}_{self.itag_mimetype[audio_itag]}_{audio_itag}.{self.itag_filetype[audio_itag]}'
                    try:
                        video_box = Box(self.itag_filetype[video_itag], video_start, video_end, videopath)
                        audio_box = Box(self.itag_filetype[audio_itag], audio_start, audio_end, audiopath)
                    except:
                        continue

                    if not os.path.exists(self.fingerprint_path + 'video.csv'):
                        with open(self.fingerprint_path + 'video.csv', 'a') as f:
                            f.write('vid,itag,contentlength,seg_num,seg_list\n')
                    with open(self.fingerprint_path + 'video.csv', 'a') as f:
                        vid = self.video_name
                        if video_box.filetype == 'mp4':
                            video_seg_list = video_box.reference_list[:-1]
                            video_dura_list = [1000 * x // video_box.Timescale for x in video_box.duration_list[:-1]]
                            video_time_list = list(accumulate(video_dura_list))
                        elif video_box.filetype == 'webm':
                            video_seg_list = video_box.track_list
                            video_time_list = video_box.timeline[1:]
                        if audio_box.filetype == 'mp4':
                            audio_seg_list = audio_box.reference_list
                            audio_dura_list = [1000 * x // audio_box.Timescale for x in audio_box.duration_list[:-1]]
                            audio_time_list = [0] + list(accumulate(audio_dura_list))
                        elif audio_box.filetype == 'webm':
                            audio_seg_list = audio_box.track_list
                            audio_time_list = audio_box.timeline[:-1]
                        com_dict = dict(zip(video_time_list + audio_time_list, video_seg_list + audio_seg_list))
                        com_time = list(com_dict.keys())
                        com_time.sort()
                        com_seg = [str(com_dict[i]) for i in com_time]
                        seg_str = '/'.join([str(seg) for seg in com_seg])
                        f.write(f'{vid},{video_itag}/{audio_itag},{str(self.itag_contentlength[video_itag] + self.itag_contentlength[audio_itag])},{str(len(video_seg_list) + len(audio_seg_list))},{seg_str}\n')
                except:
                    print(f'{self.video_name}: get video fusion fingerprint {video_itag}/{audio_itag} error')
                    with open(self.errorlog, 'a') as f:
                        f.write(f'{self.video_name}: get video fusion fingerprint {video_itag}/{audio_itag} error\n')
                    return 0
        return 1
                

def batch_download(video_urls, videofile_path, fingerprint_path):
    with ThreadPoolExecutor(max_workers=3) as executor:
        for video_url in video_urls:
            video = Video(video_url, videofile_path, fingerprint_path)
            if video.get_websource() == 0:
                continue
            if video.analyse_websource() == 0:
                continue
            executor.submit(video.download_video)


def batch_get_video_fingerprint(video_urls, videofile_path, fingerprint_path):
    for video_url in video_urls:
        video = Video(video_url, videofile_path, fingerprint_path)
        if video.analyse_websource() == 0:
            continue
        video.get_video_fingerprint()


def batch_get_video_fusion_fingerprint(video_urls, videofile_path, fingerprint_path):
    for video_url in video_urls:
        video = Video(video_url, videofile_path, fingerprint_path)
        if video.analyse_websource() == 0:
            continue
        video.get_video_fusion_fingerprint()


def get_video_urls(if_use_url_list, url_list_path, videofile_path):
    if if_use_url_list:
        with open(url_list_path, 'r') as f:
            reader = csv.reader(f)
            txt = list(reader)
        video_urls = [i[0] for i in txt]
    else:
        files = os.listdir(videofile_path + 'videoheader')
        video_urls = ['https://www.youtube.com//watch?v=' + i for i in files]
    return video_urls


def main():
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(
        description='视频指纹提取工具 - 用于下载YouTube视频和提取视频指纹',
        formatter_class=argparse.RawDescriptionHelpFormatter)

    # 读取配置文件
    conf = configparser.ConfigParser()
    conf.read('src/extraction/config.conf', encoding='utf-8')
    workdir = os.getcwd() + os.sep
    
    # 运行模式
    parser.add_argument('--mode', type=str, 
                        choices=['download', 'fingerprint', 'fusion'],
                        required=True,
                        help='运行模式: download=批量下载, fingerprint=批量提取视频指纹, fusion=批量提取视频融合指纹')
    
    # URL来源参数
    parser.add_argument('--if-use-url-list', type=int, choices=[0, 1],
                        default=conf.getint('mode', 'if_use_url_list'),
                        help='是否使用URL列表 (0=使用已下载的视频文件夹, 1=使用URL列表文件, 默认: 从配置文件读取)')
    
    # 路径参数
    parser.add_argument('--url-list-path', type=str,
                        default=workdir + conf.get('path', 'url_list_path') + 'url.csv',
                        help='URL列表文件路径 (默认: 从配置文件读取)')
    parser.add_argument('--videofile-path', type=str,
                        default=workdir + conf.get('path', 'videofile_path'),
                        help='视频文件存储路径 (默认: 从配置文件读取)')
    parser.add_argument('--fingerprint-path', type=str,
                        default=workdir + conf.get('path', 'fingerprint_path'),
                        help='指纹文件保存路径 (默认: 从配置文件读取)')
    
    args = parser.parse_args()
    
    # 显示运行信息
    print('=' * 60)
    print('视频指纹提取工具')
    print('=' * 60)
    print(f'运行模式: {args.mode}')
    print(f'URL来源: {"URL列表文件" if args.if_use_url_list else "本地视频文件夹"}')
    print(f'URL列表路径: {args.url_list_path}' if args.if_use_url_list else f'视频文件路径: {args.videofile_path}')
    print('=' * 60)
    
    # 获取视频URL列表
    try:
        video_urls = get_video_urls(args.if_use_url_list, args.url_list_path, args.videofile_path)
        print(f'\n找到 {len(video_urls)} 个视频')
        
        # 根据模式执行相应操作
        if args.mode == 'download':
            print('\n开始批量下载视频...')
            batch_download(video_urls, args.videofile_path, args.fingerprint_path)
            print('\n批量下载完成!')
            
        elif args.mode == 'fingerprint':
            print('\n开始批量提取视频指纹...')
            batch_get_video_fingerprint(video_urls, args.videofile_path, args.fingerprint_path)
            print('\n视频指纹提取完成!')
            
        elif args.mode == 'fusion':
            print('\n开始批量提取视频融合指纹...')
            batch_get_video_fusion_fingerprint(video_urls, args.videofile_path, args.fingerprint_path)
            print('\n视频融合指纹提取完成!')
            
    except KeyboardInterrupt:
        print('\n\n用户中断处理')
    except Exception as e:
        print(f'\n处理过程中出现错误: {str(e)}')
        raise


if __name__ == '__main__':
    main()
    """
    python src/extraction/get_segment.py --mode download
    python src/extraction/get_segment.py --mode fusion
    """