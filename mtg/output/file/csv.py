import csv
import time

class CSVLogWriter:
    def __init__(self, dst='logfile.csv'):
        self.logger = None
        self.dst = dst

    def set_logger(self, logger):
        self.logger = logger

    def write(self, packet):
        position = packet.get('decoded', {}).get('position', {})
        latitude = position.get('latitude')
        longitude = position.get('longitude')
        rx_time = time.strftime('%d.%m.%y %H:%M:%S')
        fields = [rx_time, packet.get('fromId'), packet.get('toId'), latitude, longitude]
        with open(self.dst, 'a') as f:
            writer = csv.writer(f)
            writer.writerow(fields)
