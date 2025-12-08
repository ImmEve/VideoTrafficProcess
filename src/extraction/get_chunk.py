import configparser
import os
import socket
import subprocess
import dpkt
import argparse

conf = configparser.ConfigParser()
conf.read('src/extraction/config.conf', encoding='UTF-8')
workdir = os.getcwd() + os.sep

class Traffic:
    def __init__(self, pcap, fingerprint_path):
        self.tshark_path = conf.get('tshark', 'tshark_path')
        self.fingerprint_path = workdir + fingerprint_path
        os.makedirs(self.fingerprint_path, exist_ok=True)
        self.pcap = pcap
        self.time = pcap.split(' ')[-1].split('.')[0]
        self.vid = self.pcap.split('/')[-1].split(' ')[0]

    def get_videoflows(self):
        self.videoflows = {}
        with open(self.pcap, 'rb') as f:
            r = dpkt.pcap.Reader(f)
            for ts, buf in r:
                packet = dpkt.ethernet.Ethernet(buf)
                if isinstance(packet.data, dpkt.ip.IP) and isinstance(packet.data.data, dpkt.tcp.TCP):
                    ip = packet.data
                    tcp = ip.data
                    src_ip = socket.inet_ntoa(ip.src)
                    dst_ip = socket.inet_ntoa(ip.dst)
                    src_port = tcp.sport
                    dst_port = tcp.dport
                    if (src_ip, dst_ip, src_port, dst_port) in self.videoflows:
                        self.videoflows[(src_ip, dst_ip, src_port, dst_port)].append(packet)
                    elif (dst_ip, src_ip, dst_port, src_port) in self.videoflows:
                        self.videoflows[(dst_ip, src_ip, dst_port, src_port)].append(packet)
                    else:
                        if tcp.dport == 443 or tcp.sport == 443:
                            if hasattr(tcp, 'data') and len(tcp.data) > 0:
                                try:
                                    ssl = dpkt.ssl.TLSRecord(tcp.data).data
                                except dpkt.dpkt.NeedData:
                                    continue
                                hex_data = ssl.hex()
                                str_data = ''.join(chr(int(hex_data[i:i + 2], 16)) if 32 <= int(hex_data[i:i + 2], 16) <= 126 else ' ' for i in range(0, len(hex_data), 2))
                                if 'googlevideo.com' in str_data:
                                    self.videoflows[(src_ip, dst_ip, src_port, dst_port)] = [packet]

    def clean_flows(self):
        videoflows_list = self.videoflows.keys()
        tmp = {}
        for videoflow in videoflows_list:
            sumlen = 0
            for packet in self.videoflows[videoflow]:
                sumlen = sumlen + len(packet.data.data)
            if sumlen > 5 * 1024 * 1024:
                tmp[videoflow] = self.videoflows[videoflow]
        self.videoflows = tmp

    def get_tls_downlink_flows(self):
        fingerprint_csv = os.path.join(self.fingerprint_path, 'traffic.csv')
        if not os.path.exists(fingerprint_csv):
            with open(fingerprint_csv, 'w') as f:
                f.write('vid,time,flow,chunk\n')
        
        videoflows_list = self.videoflows.keys()
        for videoflow in videoflows_list:
            tsharkCall = [
                self.tshark_path,
                '-r', self.pcap,
                '-Y',
                f'ip.dst=={videoflow[0]} && tcp.dstport=={videoflow[2]} && ip.src=={videoflow[1]} && tcp.srcport=={videoflow[3]} && tls',
                '-T', 'fields',
                '-e', 'tls.record.length'
            ]
            tsharkProc = subprocess.Popen(tsharkCall, stdout=subprocess.PIPE, executable=self.tshark_path)
            tsharkOut = tsharkProc.stdout.read().decode('utf-8')
            record_length_list = tsharkOut.replace('\r\n', ',').split(',')
            record_length_list = [int(i) - 16 - 1 for i in record_length_list if i != '']

            record2chunk_list = []
            record2chunk = []
            for record_length in record_length_list:
                if record_length == 953:
                    record2chunk_list.append(record2chunk)
                    record2chunk = []
                else:
                    record2chunk.append(record_length)
            record2chunk_list = record2chunk_list[1:]

            chunk_list = []
            for record2chunk in record2chunk_list:
                chunk = []
                record_list = []
                for record in record2chunk:
                    if record == 2:
                        chunk.append(record_list)
                        record_list = []
                    else:
                        record_list.append(record)
                chunk.append(record_list)
                chunk_list.append(chunk)

            chunksize = []
            for chunk in chunk_list:
                chunksize.append(sum([sum(record[1:]) for record in chunk]))
            chunksize_str = '/'.join([str(i) for i in chunksize if i > 1000])
            with open(fingerprint_csv, 'a') as f:
                f.write(f'{self.vid},{self.time},{videoflow[0]}:{videoflow[2]}-{videoflow[1]}:{videoflow[3]},{chunksize_str}\n')


def batch_get_chunk_from_pcap(pcap_path, fingerprint_path):
    pcaps = os.listdir(pcap_path)
    for pcap in pcaps:
        traffic = Traffic(pcap_path + pcap, fingerprint_path)
        traffic.get_videoflows()
        traffic.clean_flows()
        traffic.get_tls_downlink_flows()


def batch_get_chunk_from_response(responsebody_path, fingerprint_path):
    fingerprint_csv = fingerprint_path + 'traffic.csv'
    if not os.path.exists(fingerprint_csv):
        with open(fingerprint_csv, 'a') as f:
            f.write('vid,itag,chunk_list\n')
    responsebodys = os.listdir(responsebody_path)
    for responsebody in responsebodys:
        vid = responsebody.split(' ')[0]
        itag = responsebody.split(' ')[1].replace('_', '/')
        file_path = responsebody_path + responsebody
        with open(file_path, 'r', encoding='utf-8') as file:
            chunklist = '/'.join(line.strip() for line in file)
        with open(fingerprint_csv, 'a') as f:
            f.write(f'{vid},{itag},{chunklist}\n')


def main():
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(
        description='视频流量 Chunk 提取工具 - 从 PCAP 或 ResponseBody 文件中提取 chunk 信息',
        formatter_class=argparse.RawDescriptionHelpFormatter)

    # 读取配置文件
    conf = configparser.ConfigParser()
    conf.read('src/extraction/config.conf', encoding='utf-8')
    workdir = os.getcwd() + os.sep
    
    # 运行模式
    parser.add_argument('--mode', type=str, 
                        choices=['pcap', 'response'],
                        required=True,
                        help='运行模式: pcap=从PCAP文件提取, response=从ResponseBody文件提取')
    
    # 路径参数
    parser.add_argument('--pcap-path', type=str,
                        default=workdir + conf.get('path', 'pcap_path'),
                        help='PCAP文件目录路径 (默认: 从配置文件读取)')
    parser.add_argument('--responsebody-path', type=str,
                        default=workdir + conf.get('path', 'responsebody_path'),
                        help='ResponseBody文件目录路径 (默认: 从配置文件读取)')
    parser.add_argument('--fingerprint-path', type=str,
                        default=workdir + conf.get('path', 'fingerprint_path'),
                        help='指纹文件保存路径 (默认: 从配置文件读取)')
    
    args = parser.parse_args()
    
    # 显示运行信息
    print('=' * 60)
    print('视频流量 Chunk 提取工具')
    print('=' * 60)
    print(f'运行模式: {args.mode}')
    print(f'指纹保存路径: {args.fingerprint_path}')
    print('=' * 60)
    
    # 根据模式执行相应操作
    try:
        if args.mode == 'pcap':
            print(f'\n正在从 PCAP 文件提取 chunk...')
            print(f'PCAP 路径: {args.pcap_path}')
            print(f'Tshark 路径: {conf.get("tshark", "tshark_path")}')
            batch_get_chunk_from_pcap(args.pcap_path, args.fingerprint_path)
            print('\nPCAP 文件处理完成!')
            
        elif args.mode == 'response':
            print(f'\n正在从 ResponseBody 文件提取 chunk...')
            print(f'ResponseBody 路径: {args.responsebody_path}')
            batch_get_chunk_from_response(args.responsebody_path, args.fingerprint_path)
            print('\nResponseBody 文件处理完成!')
            
    except KeyboardInterrupt:
        print('\n\n用户中断处理')
    except Exception as e:
        print(f'\n处理过程中出现错误: {str(e)}')
        raise


if __name__ == '__main__':
    main()
    """
    python src/extraction/get_chunk.py --mode pcap
    python src/extraction/get_chunk.py --mode response
    """
