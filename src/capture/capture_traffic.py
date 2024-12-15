import configparser
import csv
import os.path
import subprocess
import time
from winproxy import ProxySetting
from webdriver import Webdriver


class Capture():
    def __init__(self):
        conf = configparser.ConfigParser()
        conf.read('src/config.conf', encoding='UTF-8')
        self.capture_responsebody_path = 'src/capture/capture_responsebody.py'
        self.pcap_path = conf.get('capture', 'pcap_path')
        os.makedirs(self.pcap_path, exist_ok=True)
        self.responsebody_path = conf.get('capture', 'responsebody_path')
        os.makedirs(self.responsebody_path, exist_ok=True)
        self.url_list_path = conf.get('capture', 'url_list_path')
        self.url_class_path = conf.get('capture', 'url_class_path')
        self.tshark_interface = conf.get('capture', 'tshark_interface')
        self.tshark_path = conf.get('capture', 'tshark_path')
        self.mitmdump_path = conf.get('capture', 'mitmdump_path')
        self.time_duration = int(conf.get('capture', 'time_duration'))
        self.check_resolution = ['720p']
        self.webdriver = Webdriver()

    # 检查视频信息
    def check_video_info(self, video_url):
        print('start checking...')
        # 打开视频
        if self.webdriver.loop_get_url(video_url) == 0:
            self.webdriver.driver.close()
            return 0
        time.sleep(10)
        # 获取视频时长
        video_duration = self.webdriver.get_video_duration(video_url)
        if video_duration == 0:
            self.webdriver.driver.close()
            return 0
        # 获取视频时长（秒）
        duration_of_the_video = self.webdriver.get_video_duration_second(video_duration)
        # 获取视频分辨率信息
        video_resolution = self.webdriver.get_video_resolution(video_url)
        if video_resolution == 0:
            self.webdriver.driver.close()
            return 0
        # 检查视频时长
        if duration_of_the_video < self.time_duration:
            print(f'{video_url}: duration too short')
            with open(self.webdriver.errorlog, 'a') as f:
                f.write(f'{video_url}: duration too short\n')
            self.webdriver.driver.close()
            return 0
        # 检查分辨率
        if (set(self.check_resolution) & set(video_resolution)) == set():
            print(f'{video_url}: resolution not include')
            with open(self.webdriver.errorlog, 'a') as f:
                f.write(f'{video_url}: resolution not include\n')
            self.webdriver.driver.close()
            return 0
        self.webdriver.driver.close()
        return 1

    # 采集视频流量并记录解密响应
    def capture_traffic(self, video_url, turn):
        for t in range(turn):
            # 新建文件
            t_time = time.strftime('%Y_%m_%d_%H_%M')
            video_name = video_url.split('=')[-1]
            pcap_filename = f'{video_name} TLS {self.check_resolution[0]} {str(self.time_duration)}s {t_time}.pcap'
            responsebody_filename = f'{video_name} TLS {self.check_resolution[0]} {str(self.time_duration)}s {t_time}.csv'
            pcap_filepath = self.pcap_path + pcap_filename
            responsebody_filepath = self.responsebody_path + responsebody_filename

            # 开始记录网络流量
            print('start capturing...')
            tsharkOut = open(pcap_filepath, 'wb')
            tsharkCall = [self.tshark_path, '-F', 'pcap', '-i', self.tshark_interface, '-w', pcap_filepath]
            tsharkProc = subprocess.Popen(tsharkCall, stdout=tsharkOut, executable=self.tshark_path)
            # mitmCall = [self.mitmdump_path, '-s', self.capture_responsebody_path, '--mode', 'upstream:http://127.0.0.1:7890']
            mitmCall = [self.mitmdump_path, '-s', self.capture_responsebody_path]
            mitmProc = subprocess.Popen(mitmCall, executable=self.mitmdump_path)
            time.sleep(10)

            # 播放视频
            self.webdriver.loop_get_url(video_url)
            time.sleep(self.time_duration + 10)
            # 结束流量采集
            tsharkProc.kill()
            mitmProc.kill()
            try:
                os.rename(self.responsebody_path + 'log.csv', responsebody_filepath)
            except:
                print(f'{video_url}: log error')
                with open(self.webdriver.errorlog, 'a') as f:
                    f.write(f'{video_url}: log error\n')
            # 关闭视频
            self.webdriver.driver.close()
            time.sleep(10)

    # 批量采集
    def batch_capture(self, turn):
        csv_file = open(self.url_list_path, 'r', encoding='utf-8')
        csv_data = csv_file.read()
        video_urls = csv_data.split('\n')

        for i in range(0, len(video_urls)):
            try:
                self.capture_traffic(video_urls[i], turn)
            except:
                print(f'{video_urls[i]}: capture error')
                with open(self.webdriver.errorlog, 'a') as f:
                    f.write(f'{video_urls[i]}: capture error\n')

    # 批量检查
    def batch_check(self):
        with open(self.url_list_path, 'r', encoding='utf-8') as f:
            csv_data = f.read()
            video_urls = csv_data.split('\n')

        t_time = time.strftime('%Y_%m_%d_%H_%M')
        for i in range(len(video_urls)):
            try:
                if self.check_video_info(video_urls[i]) == 1:
                    with open(f'{self.url_list_path.split(".")[0]}_check_{t_time}.csv', 'a') as f:
                        f.write(video_urls[i] + '\n')
            except:
                print(f'{video_urls[i]}: check error')
                with open(self.webdriver.errorlog, 'a') as f:
                    f.write(f'{video_urls[i]}: check error\n')

    # 抓取url
    def clawer_url(self):
        with open(self.url_class_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            class_list = list(reader)
        urllist = []
        for class_url in range(len(class_list)):
            # 打开视频
            if self.webdriver.loop_get_url(class_list[class_url][1]) == 0:
                self.webdriver.driver.close()
                return 0
            time.sleep(10)
            urls = self.webdriver.get_urllist()
            self.webdriver.driver.close()
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


if __name__ == '__main__':
    capture = Capture()
    # capture.clawer_url()
    # capture.batch_check()
    # capture.clean_response()

    # 更改端口
    p = ProxySetting()
    p.enable = True
    p.server = '127.0.0.1:8080'
    p.registry_write()

    capture.batch_capture(10)