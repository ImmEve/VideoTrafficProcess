import os
import shutil
import subprocess

filefolder = "../data/traffic/quic/pcap/"
quic_folder = "../data/traffic/quic/is_quic/"
udp_folder = "../data/traffic/quic/is_udp/"
pure_quic_folder = "../data/traffic/quic/pure_quic/"
tshark_folder = 'E:/Wireshark/tshark'

os.makedirs(pure_quic_folder, exist_ok=True)
os.makedirs(quic_folder, exist_ok=True)
os.makedirs(udp_folder, exist_ok=True)

filelist = os.listdir(filefolder)

for i in range(len(filelist)):
    input_file = os.path.join(filefolder, filelist[i])
    output_file = os.path.join(pure_quic_folder, filelist[i])

    command = f'"{tshark_folder}" -r "{input_file}" -Y "quic" -w "{output_file}"'
    subprocess.run(command, stdout=subprocess.PIPE, text=True, encoding='utf-8')

    original_size = os.path.getsize(input_file)
    pure_quic_size = os.path.getsize(output_file)
    ratio = pure_quic_size / original_size

    if ratio > 0.5:
        print("quic", ratio)
        shutil.copy(input_file, os.path.join(quic_folder, filelist[i]))
    else:
        print("not quic", ratio)
        shutil.copy(input_file, os.path.join(udp_folder, filelist[i]))
