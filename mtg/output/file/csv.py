# -*- coding: utf-8 -*-
""" CSV file writer module """


import csv
import time

class CSVFileWriter:
    """
    CSVFileWriter - CSV file writer. Stores node coordinates
    """
    def __init__(self, dst='logfile.csv'):
        self.logger = None
        self.dst = dst

    def set_logger(self, logger):
        """
        set_logger - logger setter
        """
        self.logger = logger

    def write(self, packet):
        """
        write - writes node position to file
        """
        decoded = packet.get('decoded', {})
        position = decoded.get('position', {})
        # local node
        snr = packet.get('rxSnr', 10)
        latitude = position.get('latitude')
        longitude = position.get('longitude')
        rx_time = time.strftime('%d.%m.%y %H:%M:%S')
        fields = [rx_time, packet.get('fromId'), packet.get('toId'), snr, latitude, longitude]
        with open(self.dst, 'a', encoding='utf-8') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(fields)
