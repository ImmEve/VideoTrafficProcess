import configparser
import os

conf = configparser.ConfigParser()
conf.read('src/config.conf', encoding='UTF-8')
responsebody_path = conf.get('capture', 'responsebody_path')
fingerpath = conf.get('get_chunk', 'fingerpath')
if not os.path.exists(fingerpath):
    with open(fingerpath, 'a') as f:
        f.write('url,chunk\n')

responsebodys = os.listdir(responsebody_path)
for responsebody in responsebodys:
    file_path = responsebody_path + responsebody
    url = 'https://www.youtube.com//watch?v=' + responsebody.split(' ')[0]
    with open(file_path, 'r', encoding='utf-8') as file:
        chunklist = '/'.join(line.strip() for line in file)
    with open(fingerpath, 'a') as f:
        f.write(url + ',' + chunklist + '\n')
