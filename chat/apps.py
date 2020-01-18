import logging
from django.apps import AppConfig

class ChatConfig(AppConfig):

    # This should be the path to YOUR app location, starting after BASE_DIR
    name='homepage.hosts.uni.chat'  

    def ready(self):

        logging.debug('Executing startup code from in chat/apps.py')
        
        # This should be the path to YOUR app location, starting after BASE_DIR
        from homepage.hosts.uni.chat.models import ChatLog
        from threading import Thread
        Thread(target=ChatLog.old_message_deleter, args=()).start()
        
