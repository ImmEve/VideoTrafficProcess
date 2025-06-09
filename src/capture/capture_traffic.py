import configparser
import csv
import os.path
import subprocess
import time
from winproxy import ProxySetting
from web_driver import Webdriver

conf = configparser.ConfigParser()
conf.read('config.conf', encoding='UTF-8')
workdir = conf.get('global', 'workdir')

class Capture():
    def __init__(self):
        self.capture_responsebody_path = workdir + 'src/capture/capture_responsebody.py'
        self.pcap_path = workdir + conf.get('capture', 'pcap_path')
        os.makedirs(self.pcap_path, exist_ok=True)
        self.responsebody_path = workdir + conf.get('capture', 'responsebody_path')
        os.makedirs(self.responsebody_path, exist_ok=True)
        self.url_list_path = workdir + conf.get('capture', 'url_list_path')
        self.url_class_path = workdir + conf.get('capture', 'url_class_path')
        self.tshark_interface = conf.get('capture', 'tshark_interface')
        self.tshark_path = conf.get('capture', 'tshark_path')
        self.mitmdump_path = conf.get('capture', 'mitmdump_path')
        self.time_duration = conf.getint('capture', 'time_duration')
        self.chose_resolution = conf.get('capture', 'chose_resolution')
        self.wd = Webdriver()

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

    # 提前退出流量采集
    def drop_out(self, tsharkProc, mitmProc, tsharkOut):
        self.end_tshark_mitm(tsharkProc, mitmProc, tsharkOut)
        if os.path.exists(self.responsebody_path + 'log.csv'):
            for _ in range(5):
                try:
                    os.remove(self.responsebody_path + 'log.csv')
                    break
                except PermissionError:
                    time.sleep(3)

    # 采集视频流量并记录解密响应
    def capture_traffic(self, video_url, turn):
        for t in range(turn):
            # 开始记录网络流量
            self.wd.loop_get_url('about:blank')
            time.sleep(3)
            tsharkProc, mitmProc, tsharkOut = self.begin_tshark_mitm()
            
            # 播放视频
            if self.wd.loop_get_url(video_url) == 0:
                self.drop_out(tsharkProc, mitmProc, tsharkOut)
                continue
            if self.wd.play_video(video_url) == 0:
                self.drop_out(tsharkProc, mitmProc, tsharkOut)
                continue

            # 切换分辨率
            if self.chose_resolution != '0':
                if self.wd.change_video_resolution(video_url, self.chose_resolution) == 0:
                    self.drop_out(tsharkProc, mitmProc, tsharkOut)
                    continue
            video_itag, audio_itag = self.wd.get_itag(video_url)
            if video_itag == 0 and audio_itag == 0:
                self.drop_out(tsharkProc, mitmProc, tsharkOut)
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
        csv_file = open(self.url_list_path + 'url.csv', 'r', encoding='utf-8')
        csv_data = csv_file.read()
        video_urls = csv_data.split('\n')

        for i in range(0, len(video_urls)):
            try:
                self.capture_traffic(video_urls[i], turn)
            except:
                print(f'{video_urls[i]}: capture error')
                with open(self.wd.errorlog, 'a') as f:
                    f.write(f'{video_urls[i]}: capture error\n')

    # 清楚多余响应
    def clean_response(self):
        dir_response = os.listdir(self.responsebody_path)
        for file in dir_response:
            filename = file.split('.')[0]
            if not os.path.exists(f'{self.pcap_path}{filename}.pcap'):
                print(f'{self.responsebody_path}{file}')
                os.remove(f'{self.responsebody_path}{file}')

if __name__ == '__main__':
    capture = Capture()
    # capture.clean_response()

    # 更改端口
    # p = ProxySetting()
    # p.enable = True
    # p.server = '127.0.0.1:8080'
    # p.registry_write()
    # capture.batch_capture(1)

    capture.capture_traffic('https://www.youtube.com/watch?v=uYlH3SAIXUQ', 1)