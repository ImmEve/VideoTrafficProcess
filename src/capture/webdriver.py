import configparser
import time
from lxml import etree
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


class Webdriver():
    def __init__(self):
        conf = configparser.ConfigParser()
        conf.read('src/config.conf', encoding='UTF-8')
        self.chrome_driver_path = conf.get('capture', 'chrome_driver_path')
        self.chrome_user_data_path = conf.get('capture', 'chrome_user_data_path')
        self.errorlog = conf.get('capture', 'errorlog')
        self.loop_count = 10

    # 初始化chrom driver
    def chrome_driver_init(self):
        options = webdriver.ChromeOptions()
        service = Service(self.chrome_driver_path)
        options.add_argument('--user-data-dir=' + self.chrome_user_data_path)
        options.add_argument('--disable-cache')
        options.add_argument('--disk-cache-size=0')
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_window_size(1000, 30000)
        wait = WebDriverWait(driver, 100)
        return driver

    # 持续访问URL直到成功
    def loop_get_url(self, video_url):
        self.driver = self.chrome_driver_init()
        for i in range(0, self.loop_count):
            try:
                time.sleep(3)
                self.driver.get(video_url)
                print(f'video: {video_url}')
                return 1
            except:
                pass
        print(f'{video_url}: playback error')
        with open(self.errorlog, 'a') as f:
            f.write(f'{video_url}: playback error\n')
        return 0

    # 获取视频时长
    def get_video_duration(self, video_url):
        duration_xpath = '//span[starts-with(@class,"ytp-time-duration")]/text()'
        for i in range(0, self.loop_count):
            try:
                time.sleep(3)
                html = self.driver.page_source.encode('utf-8', 'ignore')
                parseHtml = etree.HTML(html)
                video_duration = parseHtml.xpath(duration_xpath)
                print(f'video_duration: {video_duration[0]}')
                return video_duration
            except:
                pass
        print(f'{video_url}: duration error')
        with open(self.errorlog, 'a') as f:
            f.write(f'{video_url}: duration error\n')
        return 0

    # 获取视频时长（秒）
    def get_video_duration_second(self, video_duration):
        video_duration_s = -1
        if len(video_duration) > 0 and video_duration != -1:
            time_data = str(video_duration[0]).split(':')
            if len(time_data) == 2:
                video_duration_s = int(time_data[0]) * 60 + int(time_data[1])
            else:
                video_duration_s = int(time_data[0]) * 3600 + int(time_data[1]) * 60 + int(time_data[2])
        duration_of_the_video = video_duration_s
        return duration_of_the_video

    # 获取视频分辨率信息
    def get_video_resolution(self, video_url):
        for i in range(0, self.loop_count):
            try:
                time.sleep(3)
                # 点击设置
                self.driver.find_element(By.XPATH, '//*[@class="ytp-button ytp-settings-button"]').click()
                # 点击画质
                self.driver.find_element(By.XPATH,
                                         '//*[@class="ytp-popup ytp-settings-menu"]//*[@class="ytp-menu-label-secondary"]').click()
                time.sleep(3)
                # 获取分辨率信息
                html = self.driver.page_source.encode('utf-8', 'ignore')
                parseHtml = etree.HTML(html)
                video_resolution = parseHtml.xpath(
                    '//*[@class="ytp-popup ytp-settings-menu"]//*[@class="ytp-menuitem-label"]/div/span/text()')
                # 复原
                self.driver.find_element(By.XPATH, '//*[@class="ytp-button ytp-settings-button"]').click()
                print(f'video_resolution: {video_resolution}')
                return video_resolution
            except:
                pass
        print(f'{video_url}: resolution error')
        with open(self.errorlog, 'a') as f:
            f.write(f'{video_url}: resolution error\n')
        return 0

    def get_urllist(self):
        for i in range(0, 100):
            self.driver.execute_script('window.scrollBy(0,1000)')
            time.sleep(1)
        # 从索引页批量获取视频URL
        video_urls = []
        html = self.driver.page_source.encode("utf-8", "ignore")
        parseHtml = etree.HTML(html)
        index_page_xpath = '//a[@id="thumbnail"]/@href'
        raw_video_urls = parseHtml.xpath(index_page_xpath)
        # 跳过短视频
        for url in raw_video_urls:
            if str(url).__contains__('watch'):
                video_urls.append("https://www.youtube.com/" + str(url))
        return video_urls
