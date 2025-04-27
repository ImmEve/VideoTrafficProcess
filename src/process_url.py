import configparser
from capture.web_driver import Webdriver
from extraction.get_segment import *

conf = configparser.ConfigParser()
conf.read('config.conf', encoding='UTF-8')
workdir = conf.get('global', 'workdir')

class ProcessUrl():
    def __init__(self):
        self.url_list_path = workdir + conf.get('capture', 'url_list_path')
        with open(self.url_list_path + 'url.csv', 'r', encoding='utf-8') as f:
            self.url_list = f.readlines()
        self.url_list = list(set([url.strip() for url in self.url_list if url.strip()]))
        self.url_list.sort()
        self.video_itag = conf.get('filter', 'video_mp4_itag').split(',') + conf.get('filter', 'video_webm_itag').split(',')
        self.audio_itag = conf.get('filter', 'audio_mp4_itag').split(',') + conf.get('filter', 'audio_webm_itag').split(',')
        self.filter_duration = conf.get('filter', 'filter_duration').split(',')
        self.filter_url_list = []
        self.errorlog = workdir + conf.get('capture', 'errorlog')
        self.pcap_path = workdir + conf.get('capture', 'pcap_path')
        self.datapath = workdir + conf.get('get_segment', 'datapath')
        self.loop_count = 5

    def batch_get_websource(self):
        for url in self.url_list:
            video = Video(url)
            flag = 0
            for i in range(0, self.loop_count):
                try:
                    video.get_websource()
                    flag = 1
                    break
                except:
                    time.sleep(1)
            if flag == 0:
                print(f'{url}: get websource error')
                with open(self.errorlog, 'a') as f:
                    f.write(f'{url}: get websource error\n')

    def check(self, url):
        video = Video(url)
        vid = url.split('=')[-1]
        try:
            video.analyse_websource()
        except:
            print(f'{vid}: analyse websource error')
            with open(self.errorlog, 'a') as f:
                f.write(f'{vid}: analyse websource error\n')
            return 0
        itag_list = video.itag_list
        if set(itag_list) & set(self.video_itag) != set() and set(itag_list) & set(self.audio_itag) != set():
            if int(self.filter_duration[0]) * 1000 <= int(video.itag_durationMs[itag_list[0]]) <= int(self.filter_duration[1]) * 1000:
                return 1
        return 0
    
    def batch_check(self):
        with open(self.url_list_path + 'url_check.csv', 'w', encoding='utf-8') as f:
            for url in self.url_list:
                if self.check(url) == 1:
                    f.write(url + '\n')

    def clawer_url(self):
        wd = Webdriver()
        with open(self.url_class_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            class_list = list(reader)
        urllist = []
        for class_url in range(len(class_list)):
            if wd.loop_get_url(class_list[class_url][1]) == 0:
                continue
            time.sleep(10)
            urls = wd.get_urllist()
            urllist = urllist + urls
        urllist = list(set(urllist))
        with open(self.url_list_path + 'url_clawer.csv', 'w') as f:
            for url in urllist:
                f.write(url[:44] + '\n')

    # 获取采集完毕的url
    def captured_url(self):
        urls = ['https://www.youtube.com/watch?v=' + vid.split(' ')[0] for vid in os.listdir(self.pcap_path)]
        urls = list(set(urls))
        urls.sort()
        with open(self.url_list_path + 'url_captured.csv', 'w') as f:
            f.write('\n'.join(urls))

    # 需要重新处理的url
    def redo_url(self):
        reurls = {}
        with open(self.errorlog, 'r', encoding='utf-8') as f:
            datas = f.readlines()
        for data in datas:
            data = data.split('\n')[0]
            url = 'https://www.youtube.com/watch?v=' + data.split(': ')[0]
            error = data.split(': ')[1]
            if url in reurls.keys():
                reurls[url].append(error)
            else:
                reurls[url] = [error]
        urls = list(reurls.keys())
        with open(self.url_list_path + 'url_redo.csv', 'w') as f:
            f.write('\n'.join(urls))

    def remove_error(self):
        with open(self.errorlog, 'r') as f:
            datas = f.readlines()
        error_urls = ['https://www.youtube.com/watch?v=' + i.split(':')[0] for i in datas]
        new_urls = list(set(self.url_list) - set(error_urls))
        new_urls.sort()
        with open(self.url_list_path + 'url_new.csv', 'w') as f:
            f.write('\n'.join(new_urls))

        # dir_response = os.listdir(self.responsebody_path)
        # dir_pcap = os.listdir(self.pcap_path)
        dir_websource = os.listdir(self.datapath + 'websource/')
        dir_videoheader = os.listdir(self.datapath + 'videoheader/')
        for file in dir_websource:
            vid = file.split('.')[0]
            if 'https://www.youtube.com/watch?v=' + vid not in new_urls:
                if os.path.exists(f'{self.datapath}websource/{vid}.html'):
                    try:
                        os.remove(f'{self.datapath}websource/{vid}.html')
                    except:
                        print(f'{vid}: remove websource error')
        for file in dir_videoheader:
            vid = file
            if 'https://www.youtube.com/watch?v=' + vid not in new_urls:
                if os.path.exists(f'{self.datapath}videoheader/{vid}'):
                    try:
                        shutil.rmtree(f'{self.datapath}videoheader/{vid}')
                    except Exception as e:
                        print(e)
                        print(f'{vid}: remove videoheader error')


if __name__ == '__main__':
    process_url = ProcessUrl()
    # process_url.clawer_url()
    process_url.batch_check()
    # process_url.batch_get_websource()
    # process_url.captured_url()
    # process_url.redo_url()
    # process_url.remove_error()