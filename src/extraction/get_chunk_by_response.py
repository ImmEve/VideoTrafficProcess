import configparser
import os
import time

conf = configparser.ConfigParser()
conf.read('config.conf', encoding='UTF-8')
workdir = conf.get('global', 'workdir')
responsebody_path = workdir + conf.get('capture', 'responsebody_path')
fingerpath = workdir + conf.get('extraction', 'fingerpath')
url_list_path = workdir + conf.get('capture', 'url_list_path')
if not os.path.exists(fingerpath + 'traffic.csv'):
    with open(fingerpath + 'traffic.csv', 'a') as f:
        f.write('vid,itag,chunk\n')

with open(url_list_path + 'url_10min.csv', 'r') as f:
    datas = f.readlines()
urls = [i.strip() for i in datas]
responsebodys = os.listdir(responsebody_path)
for responsebody in responsebodys:
    vid = responsebody.split(' ')[0]
    if 'https://www.youtube.com/watch?v=' + vid not in urls:
        continue
    itag = responsebody.split(' ')[1]
    # t = responsebody.split(' ')[-1].split('.')[0]
    file_path = responsebody_path + responsebody
    with open(file_path, 'r', encoding='utf-8') as file:
        chunklist = '/'.join(line.strip() for line in file)
    with open(fingerpath + 'traffic.csv', 'a') as f:
        f.write(f'{vid},{itag},{chunklist}\n')