import configparser
import os
import time

conf = configparser.ConfigParser()
conf.read('config.conf', encoding='UTF-8')
workdir = conf.get('global', 'workdir')
responsebody_path = workdir + conf.get('capture', 'responsebody_path')
fingerpath = workdir + conf.get('get_chunk', 'fingerpath')
t_time = time.strftime('%Y_%m_%d_%H_%M')
fingerpath = f'{fingerpath.split(".")[0]}_{t_time}.csv'
if not os.path.exists(fingerpath):
    with open(fingerpath, 'a') as f:
        f.write('vid,time,chunk\n')

responsebodys = os.listdir(responsebody_path)
for responsebody in responsebodys:
    t = responsebody.split(' ')[-1].split('.')[0]
    file_path = responsebody_path + responsebody
    vid = responsebody.split(' ')[0]
    with open(file_path, 'r', encoding='utf-8') as file:
        chunklist = '/'.join(line.strip() for line in file)
    with open(fingerpath, 'a') as f:
        f.write(f'{vid},{t},{chunklist}\n')
