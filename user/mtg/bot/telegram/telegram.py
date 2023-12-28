

class Telegram:
    def __init__(self):
        tempo_handler =  CommandHandler('tempo', self.tempo)
        update_handler =  CommandHandler('update', self.update)
        dispatcher.add_handler(tempo_handler)
        dispatcher.add_handler(update_handler)

    @check_room
    def tempo(self, update: Update, context: CallbackContext) -> None:
        """
        Telegram /tempo command handler.

        :param update:
        :param context:
        :return:
        """
        chat_id = update.effective_chat.id
        os.system('/usr/bin/python3 /home/meshtasticpt/scripts/meteo/all.py > /tmp/tempo.txt')
        os.system('/usr/bin/cat /tmp/tempo.txt')

        out2 = subprocess.check_output(["/usr/bin/cat /tmp/tempo.txt"], shell=True)
        out2 = ou2.decode('utf-8')
        print(type(out2))

        #    try:
        #		encoded = out2.encode('utf-8')
        # 		print(encoded) # 👉️ b'bobbyhadz.com'
        #		print(type(encoded))  # 👉️ <class 'bytes'>
        #	except AttributeError:
        #   		pass
        def json_serializer(obj):
            if isinstance(obj, bytes):
                return obj.decode('utf-8')

            return obj

        json_str = json.dumps(out2, default=json_serializer)

        print(json_str)  # "hello world"
        print(type(json_str))  # <class 'str'>
        print('DOne')

        #        proc = subprocess.Popen(['/usr/bin/cat', '/tmp/tempo.txt'],stdout=subprocess.PIPE, shell=True)
        #        (out, err) = proc.communicate()
        #        print("program output:", out)

        self.logger.info(f"Got /tempo from {chat_id}")
        context.bot.send_message(chat_id=chat_id, text=json_str)
        context.bot.send_message(chat_id=chat_id, text=type(json_str))

    @check_room
    def map_link(self, update: Update, context: CallbackContext) -> None:
        """
        Returns map link to user

        :param update:
        :param context:
        :return:
        """
        msg = 'Map link not enabled'
        map = '''Mapa Principal
http://map.meshtastic.pt

Mapa do Bot
'''
        map2 = '''

Mapa Grafana
http://grafana.meshtastic.pt:3000/
(Username/Password: meshtastic)'''

        if self.config.enforce_type(bool, self.config.Telegram.MapLinkEnabled):
            msg = self.config.enforce_type(str, self.config.Telegram.MapLink)
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=map+msg+map2)

    @check_room
    def update(self, update: Update, context: CallbackContext) -> None:
            url = 'https://github.com/meshtastic/firmware/releases/latest'
            r = requests.get(url)
            version = r.url.split('/')[-1]
            os.system("""curl --silent https://github.com/meshtastic/firmware/tags | more | grep -A 1 /meshtastic/firmware/releases/tag/v | head -1| grep -o -P '(?<=href="/).*(?=" data-view-component="true" class="Link--primary)' | sed  's/meshtastic\/firmware\/releases\/tag\///g' > /tmp/firmware.vrs""")
            os.system("""curl --silent https://github.com/meshtastic/Meshtastic-Android/tags | more | grep -A 1 /meshtastic/Meshtastic-Android/releases/tag/ | head -1| grep -o -P '(?<=href="/).*(?=" data-view-component="true" class="Link--primary)' | sed  's/meshtastic\/Meshtastic-Android\/releases\/tag\///g' > /tmp/Meshtastic-Android.vrs""")
            #sm1 = os.system('cat /tmp/firmware.vrs')
            p = subprocess.Popen('cat /tmp/firmware.vrs', stdout=subprocess.PIPE, shell=True)
            (output, err) = p.communicate()
            p_status = p.wait()
            sm2 = f'Meshtastic Firmware Beta: ' + version + ''' (Versão Estável)\n'''
            output = output.decode("utf-8")
#https://github.com/meshtastic/firmware/releases/latest


            sm3 = f'Ultima Versão: ' + str(output) + '''https://github.com/meshtastic/firmware/releases

'''
            sms = sm2+sm3

            url = 'https://github.com/meshtastic/Meshtastic-Android/releases/latest'
            r = requests.get(url)
            version = r.url.split('/')[-1]
            sms2A = f'Meshtastic App Android Beta: ' + version + ''' (Versão Estável)\n'''
            p = subprocess.Popen('cat /tmp/Meshtastic-Android.vrs', stdout=subprocess.PIPE, shell=True)
            (output, err) = p.communicate()
            p_status = p.wait()
            output = output.decode("utf-8")
            sm3 = f'Ultima Versão: ' + str(output) + '''https://github.com/meshtastic/Meshtastic-Android/releases

'''
            smsA = sms2A+sm3

            print(str(output))
            print(str(output))
            print(str(output))

#https://github.com/meshtastic/Meshtastic-Android/releases/latest


            url = 'https://github.com/meshtastic/python/releases/latest'
            r = requests.get(url)
            version = r.url.split('/')[-1]
            sms3 = f'Meshtastic Python CLI: ' + version + ''' (Versão Estável)
https://github.com/meshtastic/python/releases

'''

#https://github.com/meshtastic/python/releases/latest


            url = 'https://github.com/meshtastic/c-sharp/releases/latest'
            r = requests.get(url)
            version = r.url.split('/')[-1]
            sms4 = f'Meshtastic CLI Preview: ' + version + ''' (Versão Estável)
https://github.com/meshtastic/c-sharp/releases
'''

#https://github.com/meshtastic/c-sharp/releases/latest
            context.bot.send_message(chat_id=update.effective_chat.id,text=sms+smsA+sms3+sms4)

            self.meshtastic_connection.send_text(sms, destinationId=from_id)
            self.meshtastic_connection.send_text(smsA, destinationId=from_id)
            self.meshtastic_connection.send_text(sms3, destinationId=from_id)
            self.meshtastic_connection.send_text(sms4, destinationId=from_id)

