import configparser
import os
import socket
import subprocess
import dpkt


class Traffic:
    def __init__(self, pcap):
        conf = configparser.ConfigParser()
        conf.read('src/config.conf', encoding='UTF-8')
        self.tshark_path = conf.get('capture', 'tshark_path')
        self.fingerpath = conf.get('get_chunk', 'fingerpath')
        os.makedirs(os.path.dirname(self.fingerpath), exist_ok=True)
        self.pcap = pcap
        self.time = pcap.split(' ')[-1].split('.')[0]
        self.url = 'https://www.youtube.com//watch?v=' + self.pcap.split('/')[-1].split(' ')[0]

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
        if not os.path.exists(self.fingerpath):
            with open(self.fingerpath, 'a') as f:
                f.write('url,time,flow,chunk\n')
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
            record_length_list = [int(i) - 17 for i in record_length_list if i != '']

            record2chunk_list = []
            record2chunk = []
            for reocrd_length in record_length_list:
                if reocrd_length == 953:
                    record2chunk_list.append(record2chunk)
                    record2chunk = []
                else:
                    record2chunk.append(reocrd_length)
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
            chunsize_str = '/'.join([str(i) for i in chunksize if i > 1000])
            with open(self.fingerpath, 'a') as f:
                f.write(f'{self.url},{self.time},{videoflow[0]}:{videoflow[2]}-{videoflow[1]}:{videoflow[3]},{chunsize_str}\n')


def batch_get_chunk():
    conf = configparser.ConfigParser()
    conf.read('src/config.conf', encoding='UTF-8')
    pcap_path = conf.get('capture', 'pcap_path')
    pcaps = os.listdir(pcap_path)
    for pcap in pcaps:
        traffic = Traffic(pcap_path + pcap)
        traffic.get_videoflows()
        traffic.clean_flows()
        traffic.get_tls_downlink_flows()


if __name__ == '__main__':
    batch_get_chunk()
