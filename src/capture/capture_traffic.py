import configparser
import os.path
import subprocess
import time
import argparse
from winproxy import ProxySetting
from web_driver import Webdriver


class Capture():
    def __init__(self, if_tshark, if_mitm, if_vpn, responsebody_path, pcap_path, url_list_path, time_duration, chose_resolution):
        conf = configparser.ConfigParser()
        conf.read('src/capture/config.conf', encoding='utf-8')
        workdir = os.getcwd() + os.sep
        self.if_tshark = if_tshark
        self.if_mitm = if_mitm
        self.if_vpn = if_vpn
        if self.if_tshark:
            self.tshark_interface = conf.get('tshark', 'tshark_interface')
            self.tshark_path = conf.get('tshark', 'tshark_path')
        if self.if_mitm:
            self.mitmdump_path = conf.get('mitmdump', 'mitmdump_path')
            self.capture_responsebody_path = workdir + 'src/capture/capture_responsebody.py'
            self.responsebody_path = responsebody_path
            os.makedirs(self.responsebody_path, exist_ok=True)
        self.pcap_path = pcap_path
        os.makedirs(self.pcap_path, exist_ok=True) 
        self.url_list_path = url_list_path
        self.time_duration = time_duration
        self.chose_resolution = chose_resolution
        self.error_log = workdir + conf.get('path', 'errorlog')

    def cleanup(self):
        if hasattr(self, 'wd'):
            del self.wd
        time.sleep(3)

    # 开始记录网络流量
    def begin_tshark_mitm(self):
        tsharkOut, tsharkProc, mitmProc = None, None, None
        if self.if_tshark:
            print('start tshark...')
            tsharkOut = open(self.pcap_path + 'log.pcap', 'wb')
            tsharkCall = [self.tshark_path, '-F', 'pcap', '-i', self.tshark_interface, '-w', self.pcap_path + 'log.pcap']
            tsharkProc = subprocess.Popen(tsharkCall, stdout=tsharkOut, executable=self.tshark_path)
        if self.if_mitm:
            print('start mitm...')
            if self.if_vpn:
                mitmCall = [self.mitmdump_path, '-q', '-s', self.capture_responsebody_path, '--mode', 'upstream:http://127.0.0.1:7890']
            else:
                mitmCall = [self.mitmdump_path, '-q', '-s', self.capture_responsebody_path]
            mitmProc = subprocess.Popen(mitmCall, executable=self.mitmdump_path)
        time.sleep(10)
        return tsharkOut, tsharkProc, mitmProc

    # 结束流量采集
    def end_tshark_mitm(self, tsharkOut, tsharkProc, mitmProc):
        if self.if_tshark:
            print('end tshark...')
            tsharkProc.terminate()
            try:
                tsharkProc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                tsharkProc.kill()
                tsharkProc.wait()
            tsharkOut.close()
        if self.if_mitm:
            print('end mitm...')
            mitmProc.terminate()
            try:
                mitmProc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                mitmProc.kill()
                mitmProc.wait()
        time.sleep(10)

    # 如果提前退出流量采集，则清理记录文件
    def drop_out(self, tsharkOut, tsharkProc, mitmProc):
        self.end_tshark_mitm(tsharkOut, tsharkProc, mitmProc)
        if self.if_tshark:
            if os.path.exists(self.pcap_path + 'log.pcap'):
                for _ in range(5):
                    try:
                        os.remove(self.pcap_path + 'log.pcap')
                        break
                    except PermissionError:
                        time.sleep(3)
        if self.if_mitm:
            if os.path.exists(self.responsebody_path + 'log.csv'):
                for _ in range(5):
                    try:
                        os.remove(self.responsebody_path + 'log.csv')
                        break
                    except PermissionError:
                        time.sleep(3)

    # 更改记录文件名
    def change_record_filename(self, video_url, video_itag, audio_itag):
        t_time = time.strftime('%Y_%m_%d_%H_%M')
        video_name = video_url.split('=')[-1]
        if self.if_tshark:
            pcap_filename = f'{video_name} {video_itag}_{audio_itag} {str(self.time_duration)}s TLS {t_time}.pcap'
            pcap_filepath = self.pcap_path + pcap_filename
            for _ in range(5):
                try:
                    os.rename(self.pcap_path + 'log.pcap', pcap_filepath)
                    break
                except PermissionError:
                    time.sleep(3)
        if self.if_mitm:
            responsebody_filename = f'{video_name} {video_itag}_{audio_itag} {str(self.time_duration)}s TLS {t_time}.csv'
            responsebody_filepath = self.responsebody_path + responsebody_filename        
            for _ in range(5):
                try:
                    os.rename(self.responsebody_path + 'log.csv', responsebody_filepath)
                    break
                except PermissionError:
                    time.sleep(3)

    # 采集视频流量并记录解密响应
    def single_video_capture(self, video_url):
        # 开始记录网络流量
        tsharkOut, tsharkProc, mitmProc = self.begin_tshark_mitm()
        
        # 播放视频
        self.wd = Webdriver()
        if self.wd.loop_get_url(video_url) == 0:
            self.drop_out(tsharkOut, tsharkProc, mitmProc)
            return 0
        if self.wd.play_video(video_url) == 0:
            self.drop_out(tsharkOut, tsharkProc, mitmProc)
            return 0

        # 切换分辨率
        if self.chose_resolution != '0':
            if self.wd.change_video_resolution(video_url, self.chose_resolution) == 0:
                self.drop_out(tsharkOut, tsharkProc, mitmProc)
                return 0
        video_itag, audio_itag = self.wd.get_itag(video_url)
        if video_itag == 0 and audio_itag == 0:
            self.drop_out(tsharkOut, tsharkProc, mitmProc)
            return 0
        
        # 等待视频播放结束
        time.sleep(self.time_duration + 10)
        self.cleanup()
        # 结束流量采集
        self.end_tshark_mitm(tsharkOut, tsharkProc, mitmProc)
        # 更改记录文件名
        self.change_record_filename(video_url, video_itag, audio_itag)

    # 批量采集
    def batch_video_capture(self, turn):
        csv_file = open(self.url_list_path + 'url.csv', 'r', encoding='utf-8')
        csv_data = csv_file.read()
        video_urls = csv_data.split('\n')

        for i in range(0, len(video_urls)):
            for t in range(turn):
                try:
                    self.single_video_capture(video_urls[i])
                except Exception as e:
                    print(f'{video_urls[i]}: capture error: {e}')
                    with open(self.error_log, 'a') as f:
                        f.write(f'{video_urls[i]}: capture error\n')
                finally:
                    self.cleanup()


def main():
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(
        description='视频流量采集工具 - 用于采集和记录YouTube视频的网络流量',
        formatter_class=argparse.RawDescriptionHelpFormatter)

    conf = configparser.ConfigParser()
    conf.read('src/capture/config.conf', encoding='utf-8')
    workdir = os.getcwd() + os.sep
    
    # 运行模式
    parser.add_argument('--mode', type=str, choices=['single', 'batch'], required=True,
                        help='运行模式: single=单个视频采集, batch=批量视频采集')
    parser.add_argument('--url', type=str, default=None,
                        help='视频URL (single模式必需)')
    parser.add_argument('--turn', type=int, default=1,
                        help='批量采集时每个视频采集的轮次 (默认: 1)')
    
    # 模式参数
    parser.add_argument('--if-tshark', type=int, choices=[0, 1], default=int(conf.get('mode', 'if_tshark')),
                        help='是否启用tshark抓包 (0=否, 1=是, 默认: 从配置文件读取)')
    parser.add_argument('--if-mitm', type=int, choices=[0, 1], default=int(conf.get('mode', 'if_mitm')),
                        help='是否启用mitmdump抓包 (0=否, 1=是, 默认: 从配置文件读取)')
    parser.add_argument('--if-vpn', type=int, choices=[0, 1], default=int(conf.get('mode', 'if_vpn')),
                        help='是否使用VPN上游代理 (0=否, 1=是, 默认: 从配置文件读取)')
    
    # 路径参数
    parser.add_argument('--pcap-path', type=str, default=workdir + conf.get('path', 'pcap_path'),
                        help='PCAP文件保存路径 (默认: 从配置文件读取)')
    parser.add_argument('--responsebody-path', type=str, default=workdir + conf.get('path', 'responsebody_path'),
                        help='响应体CSV文件保存路径 (默认: 从配置文件读取)')
    parser.add_argument('--url-list-path', type=str, default=workdir + conf.get('path', 'url_list_path'),
                        help='URL列表文件路径 (默认: 从配置文件读取)')
    
    # 采集参数
    parser.add_argument('--time-duration', type=int, default=conf.getint('parameter', 'time_duration'),
                        help='视频播放时长(秒) (默认: 从配置文件读取)')
    parser.add_argument('--resolution', type=str, default=conf.get('parameter', 'chose_resolution'),
                        help='视频分辨率 (如: 720p, 480p, 0表示不切换, 默认: 从配置文件读取)')
    
    args = parser.parse_args()
    
    # 创建Capture实例
    print('=' * 60)
    print('视频流量采集工具')
    print('=' * 60)
    print(f'运行模式: {args.mode}')
    print(f'Tshark: {"启用" if args.if_tshark else "禁用"}')
    print(f'Mitmdump: {"启用" if args.if_mitm else "禁用"}')
    print(f'VPN上游代理: {"启用" if args.if_vpn else "禁用"}')
    print(f'监听视频时长: {args.time_duration}秒')
    print(f'采集分辨率: {args.resolution}')
    print('=' * 60)
    
    capture = Capture(
        if_tshark=args.if_tshark,
        if_mitm=args.if_mitm,
        if_vpn=args.if_vpn,
        responsebody_path=args.responsebody_path,
        pcap_path=args.pcap_path,
        url_list_path=args.url_list_path,
        time_duration=args.time_duration,
        chose_resolution=args.resolution
    )
    
    # 如果启用mitm，自动设置系统代理为127.0.0.1:8080
    if args.if_mitm:
        print('\n正在设置系统代理: 127.0.0.1:8080')
        p = ProxySetting()
        p.enable = True
        p.server = '127.0.0.1:8080'
        p.registry_write()
        print('代理设置完成')
    
    # 执行采集
    try:
        if args.mode == 'single':
            # 单个视频采集
            if not args.url:
                parser.error('single模式必须指定--url参数')
            print(f'\n开始采集视频: {args.url}，采集{args.turn}轮')
            for i in range(args.turn):
                print(f'采集第{i+1}轮开始')
                capture.single_video_capture(args.url)
                print(f'采集第{i+1}轮完成')
            print('\n视频采集完成!')
        elif args.mode == 'batch':
            # 批量视频采集
            print(f'\n开始批量采集，每个视频采集{args.turn}轮')
            capture.batch_video_capture(args.turn)
            print('\n批量采集完成!')
    except KeyboardInterrupt:
        print('\n\n用户中断采集')
        capture.cleanup()
    except Exception as e:
        print(f'\n采集过程中出现错误: {str(e)}')
        capture.cleanup()
        raise
    finally:
        # 如果启用了mitm，需要处理代理设置
        if args.if_mitm:
            p = ProxySetting()
            if args.if_vpn:
                # VPN模式：将代理改回127.0.0.1:7890
                print('\n恢复VPN代理设置: 127.0.0.1:7890')
                p.enable = True
                p.server = '127.0.0.1:7890'
                p.registry_write()
                print('代理已恢复为VPN上游代理')
            else:
                # 非VPN模式：关闭代理
                print('\n关闭系统代理')
                p.enable = False
                p.registry_write()
                print('系统代理已关闭')


if __name__ == '__main__':
    main()
    """
    python src/capture/capture_traffic.py --mode single --url "https://www.youtube.com/watch?v=01GCYVvJLRY" --turn 3
    python src/capture/capture_traffic.py --mode batch
    """