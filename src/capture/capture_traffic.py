import configparser
import csv
import os.path
import subprocess
import time
from winproxy import ProxySetting
from web_driver import Webdriver


class Capture():
    def __init__(self):
        conf = configparser.ConfigParser()
        conf.read('config.conf', encoding='UTF-8')
        self.workdir = conf.get('global', 'workdir')
        self.capture_responsebody_path = self.workdir + 'src/capture/capture_responsebody.py'
        self.pcap_path = self.workdir + conf.get('capture', 'pcap_path')
        os.makedirs(self.pcap_path, exist_ok=True)
        self.responsebody_path = self.workdir + conf.get('capture', 'responsebody_path')
        os.makedirs(self.responsebody_path, exist_ok=True)
        self.url_list_path = self.workdir + conf.get('capture', 'url_list_path')
        self.url_class_path = self.workdir + conf.get('capture', 'url_class_path')
        self.tshark_interface = conf.get('capture', 'tshark_interface')
        self.tshark_path = conf.get('capture', 'tshark_path')
        self.mitmdump_path = conf.get('capture', 'mitmdump_path')
        self.time_duration = int(conf.get('capture', 'time_duration'))
        self.check_resolution = conf.get('capture', 'check_resolution').split(',')
        self.if_auto_playback = int(conf.get('capture', 'if_auto_playback'))
        self.chose_resolution = conf.get('capture', 'chose_resolution')
        self.wd = Webdriver()

    # 检查视频信息
    def check_video_info(self, video_url):
        print('start checking...')
        # 打开视频
        if self.wd.loop_get_url(video_url) == 0:
            return 0
        time.sleep(10)
        # 获取视频时长
        video_duration = self.wd.get_video_duration(video_url)
        if video_duration == 0:
            return 0
        # 获取视频时长（秒）
        duration_of_the_video = self.wd.get_video_duration_second(video_duration)
        # 获取视频分辨率信息
        video_resolution = self.wd.get_video_resolution(video_url)
        if video_resolution == 0:
            return 0
        # 检查视频时长
        if duration_of_the_video < self.time_duration:
            print(f'{video_url}: duration too short')
            with open(self.wd.errorlog, 'a') as f:
                f.write(f'{video_url}: duration too short\n')
            return 0
        # 检查分辨率
        if not (set(video_resolution) >= set(self.check_resolution)):
            print(f'{video_url}: resolution not include')
            with open(self.wd.errorlog, 'a') as f:
                f.write(f'{video_url}: resolution not include\n')
            return 0
        return 1

    # 开始记录网络流量
    def begin_tshark_mitm(self):
        print('start tshark and mitm...')
        tsharkOut = open(self.pcap_path + 'log.pcap', 'wb')
        tsharkCall = [self.tshark_path, '-F', 'pcap', '-i', self.tshark_interface, '-w', self.pcap_path + 'log.pcap']
        tsharkProc = subprocess.Popen(tsharkCall, stdout=tsharkOut, executable=self.tshark_path)
        # mitmCall = [self.mitmdump_path, '-s', self.capture_responsebody_path, '--mode', 'upstream:http://127.0.0.1:7890']
        mitmCall = [self.mitmdump_path, '-q', '-s', self.capture_responsebody_path]
        mitmProc = subprocess.Popen(mitmCall, executable=self.mitmdump_path)
        time.sleep(10)
        return tsharkProc, mitmProc, tsharkOut

    # 结束流量采集
    def end_tshark_mitm(self, tsharkProc, mitmProc, tsharkOut):
        tsharkProc.terminate()
        mitmProc.terminate()
        try:
            tsharkProc.wait(timeout=3)
            mitmProc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            tsharkProc.kill()
            mitmProc.kill()
            tsharkProc.wait()
            mitmProc.wait()
        tsharkOut.close()
        time.sleep(3)

    # 采集视频流量并记录解密响应
    def capture_traffic(self, video_url, turn):
        for t in range(turn):
            # 开始记录网络流量
            self.wd.loop_get_url('about:blank')
            time.sleep(3)
            tsharkProc, mitmProc, tsharkOut = self.begin_tshark_mitm()

            # 播放视频
            self.wd.loop_get_url(video_url)
            # 切换分辨率
            if self.if_auto_playback == 0:
                self.wd.change_video_resolution(video_url, self.chose_resolution)
            video_itag, audio_itag = self.wd.get_itag(video_url)
            if video_itag == 0 and audio_itag == 0:
                self.end_tshark_mitm(tsharkProc, mitmProc, tsharkOut)
                if os.path.exists(self.responsebody_path + 'log.csv'):
                    for _ in range(5):
                        try:
                            os.remove(self.responsebody_path + 'log.csv')
                            break
                        except PermissionError:
                            time.sleep(3)
                continue
            time.sleep(self.time_duration + 10)

            # 结束流量采集
            self.end_tshark_mitm(tsharkProc, mitmProc, tsharkOut)

            t_time = time.strftime('%Y_%m_%d_%H_%M')
            video_name = video_url.split('=')[-1]
            flag = -1
            
            # 更改解密响应文件名
            responsebody_filename = f'{video_name} {video_itag}_{audio_itag} {str(self.time_duration)}s TLS {t_time}.csv'
            responsebody_filepath = self.responsebody_path + responsebody_filename        
            for _ in range(5):
                try:
                    os.rename(self.responsebody_path + 'log.csv', responsebody_filepath)
                    flag = flag + 1
                    break
                except PermissionError:
                    time.sleep(3)

            # 更改pcap文件名
            pcap_filename = f'{video_name} {video_itag}_{audio_itag} {str(self.time_duration)}s TLS {t_time}.pcap'
            pcap_filepath = self.pcap_path + pcap_filename
            for _ in range(5):
                try:
                    os.rename(self.pcap_path + 'log.pcap', pcap_filepath)
                    flag = flag + 1
                    break
                except PermissionError:
                    time.sleep(3)

            if flag != 1:
                print(f'{video_url}: log error')
                with open(self.wd.errorlog, 'a') as f:
                    f.write(f'{video_url}: log error\n')

    # 批量采集
    def batch_capture(self, turn):
        csv_file = open(self.url_list_path, 'r', encoding='utf-8')
        csv_data = csv_file.read()
        video_urls = csv_data.split('\n')

        for i in range(0, len(video_urls)):
            try:
                self.capture_traffic(video_urls[i], turn)
            except Exception as e:
                print(f'{video_urls[i]}: capture error')
                with open(self.wd.errorlog, 'a') as f:
                    f.write(f'{video_urls[i]}: capture error\n')
                    f.write(str(e) + '\n')

    # 批量检查
    def batch_check(self):
        with open(self.url_list_path, 'r', encoding='utf-8') as f:
            csv_data = f.read()
            video_urls = csv_data.split('\n')

        t_time = time.strftime('%Y_%m_%d_%H_%M')
        for i in range(0, len(video_urls)):
            try:
                if self.check_video_info(video_urls[i]) == 1:
                    with open(f'{self.url_list_path.split(".")[0]}_check_{t_time}.csv', 'a') as f:
                        f.write(video_urls[i] + '\n')
            except Exception as e:
                print(f'{video_urls[i]}: check error')
                with open(self.wd.errorlog, 'a') as f:
                    f.write(f'{video_urls[i]}: check error\n')

    # 抓取url
    def clawer_url(self):
        with open(self.url_class_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            class_list = list(reader)
        urllist = []
        for class_url in range(len(class_list)):
            # 打开视频
            if self.wd.loop_get_url(class_list[class_url][1]) == 0:
                continue
            time.sleep(10)
            urls = self.wd.get_urllist()
            urllist = urllist + urls
        urllist = list(set(urllist))
        t_time = time.strftime('%Y_%m_%d_%H_%M')
        with open(f'{self.url_list_path.split(".")[0]}_{t_time}.csv', 'w') as f:
            for url in urllist:
                f.write(url[:44] + '\n')

    def clean_response(self):
        dir_response = os.listdir(self.responsebody_path)
        for file in dir_response:
            filename = file.split('.')[0]
            if not os.path.exists(f'{self.pcap_path}{filename}.pcap'):
                print(f'{self.responsebody_path}{file}')
                os.remove(f'{self.responsebody_path}{file}')


def recheck():
    capture = Capture()
    video_urls = {}
    with open('D:/VideoTrafficProcess/data/url/recheck.txt', 'r', encoding='utf-8') as f:
        datas = f.readlines()
    for data in datas:
        data = data.split('\n')[0]
        url = data.split(': ')[0]
        title = data.split(': ')[1]
        if url in video_urls.keys():
            video_urls[url].append(title)
        else:
            video_urls[url] = [title]

    t_time = time.strftime('%Y_%m_%d_%H_%M')
    urls = list(video_urls.keys())
    for url in urls:
        if {'duration too short', 'resolution not include', 'duration error', 'resolution error'} & set(video_urls[url]) == set():
            try:
                if capture.check_video_info(url) == 1:
                    with open(f'{capture.url_list_path.split(".")[0]}_check_{t_time}.csv', 'a') as f:
                        f.write(url + '\n')
            except Exception as e:
                print(f'{url}: check error')
                with open(capture.wd.errorlog, 'a') as f:
                    f.write(f'{url}: check error\n')

if __name__ == '__main__':
    # recheck()
    capture = Capture()
    # capture.clawer_url()
    # capture.batch_check()
    # capture.clean_response()

    # 更改端口
    p = ProxySetting()
    p.enable = True
    p.server = '127.0.0.1:8080'
    p.registry_write()
    capture.batch_capture(1)

    # capture.capture_traffic('https://www.youtube.com/watch?v=uYlH3SAIXUQ', 1)
    # print(capture.check_video_info('https://www.youtube.com/watch?v=06D_ckhFa88'))