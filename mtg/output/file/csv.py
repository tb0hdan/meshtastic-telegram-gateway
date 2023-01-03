import csv
import time

class CSVFileWriter:
    def __init__(self, dst='logfile.csv'):
        self.logger = None
        self.dst = dst

    def set_logger(self, logger):
        self.logger = logger

    def write(self, packet):
        decoded = packet.get('decoded', {})
        position = decoded.get('position', {})
        # local node
        snr = packet.get('rxSnr', 10)
        latitude = position.get('latitude')
        longitude = position.get('longitude')
        rx_time = time.strftime('%d.%m.%y %H:%M:%S')
        fields = [rx_time, packet.get('fromId'), packet.get('toId'), snr, latitude, longitude]
        with open(self.dst, 'a') as f:
            writer = csv.writer(f)
            writer.writerow(fields)
