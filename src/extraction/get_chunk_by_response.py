import configparser
import os

conf = configparser.ConfigParser()
conf.read('config.conf', encoding='UTF-8')
workdir = conf.get('global', 'workdir')
responsebody_path = workdir + conf.get('capture', 'responsebody_path')
fingerpath = workdir + conf.get('get_chunk', 'fingerpath')
if not os.path.exists(fingerpath):
    with open(fingerpath, 'a') as f:
        f.write('url,time,chunk\n')

responsebodys = os.listdir(responsebody_path)
for responsebody in responsebodys:
    time = responsebody.split(' ')[-1].split('.')[0]
    file_path = responsebody_path + responsebody
    url = 'https://www.youtube.com//watch?v=' + responsebody.split(' ')[0]
    with open(file_path, 'r', encoding='utf-8') as file:
        chunklist = '/'.join(line.strip() for line in file)
    with open(fingerpath, 'a') as f:
        f.write(f'{url},{time},{chunklist}\n')
