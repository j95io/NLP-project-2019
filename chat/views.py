from django.shortcuts import render
from django.http import HttpResponse
from homepage.hosts.uni.chat.models import ChatLog, Author
from datetime import timedelta  # TODO: remove after time zone fix
import json
import ast
import logging
# NOTE: requires Python 3.6+ due to use of f-strings in this file

# Function based views

def index(request):
    # This is the page that contains the chat application
    jinja_vars = {
        'content_file': 'chat/index_content.html',
        'title': 'Chat',
        'navbar_home': 'active',
    }
    return render(request, "chat/chat_template.html", jinja_vars)

def chat_api(request):

    def get_ip():
        '''Get the requesting client's IP address'''
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def json_serializable_chat_log(latest_seen_message_id):
        messages = []
        if not latest_seen_message_id:
            message_records = list(ChatLog.messages.all())
        else:
            message_records = \
                    list(ChatLog.messages.filter(id__gt=latest_seen_message_id))
        for message in message_records:
            CEST_time = message.time_stamp + timedelta(seconds=2*60*60)
            CET_time = message.time_stamp + timedelta(seconds=1*60*60)
            #time_stamp = CEST_time.strftime('%H:%M')  # TODO: clientside fix
            time_stamp = CET_time.strftime('%H:%M')  # TODO: clientside fix
            messages.append({'time_stamp': time_stamp, 
                             'message_string': message.message_string, 
                             'author_name': message.author.name, 
                             'message_id': message.id,
                             'message_class': message.message_class,
                             'concatenated_classes': \
                                     [c for c in message.concatenated_classes],
                            'previous_messages': [m.pk for m in message.
                                    n_previous_messages()]
                            })
        return messages

    def get_classifications(unclassified_messages):
        ''' Get classifications for messages in the given list (by id) '''
        if not unclassified_messages:
            return []
        message_records = \
                list(ChatLog.messages.filter(id__in=unclassified_messages).
                                      exclude(message_class='U'))
        single_classified = {}
        concatenated_classified = {}
        previous_messages = {}
        for message in message_records:
            single_classified[message.id] = message.message_class
            concatenated_classified[message.id] = message.concatenated_classes
            previous_messages[message.id] = \
                    [m.pk for m in message.n_previous_messages()]
        """
        For each message that is still unclassified, deliver
        - the classification of the single message, 
        - the classifications of the concatenations with the previous messages
        - the ids of the previous messages from the same author with which the
            concatenataions were made
        given in a JSON object, organized by message_id as keys
        """
        result = {
                'single_classified': single_classified,
                'previous_messages': previous_messages,
                'concatenated_classified': concatenated_classified
                }
        return result

    # This is the server interface with which makes the site responsive
    if request.method == 'GET':
        if request.GET.get('type') == 'update_chat_log':

            latest_seen_message_id = request.GET.get('latest_seen_message_id')
            unclassified_messages = request.GET.get('unclassified_messages')
            unclassified_messages = ast.literal_eval(unclassified_messages)
            json_chat_log = json_serializable_chat_log(latest_seen_message_id)
            classified_messages = get_classifications(unclassified_messages)
            oldest = ChatLog.messages.order_by('id').first()
            oldest_message = None if oldest is None else oldest.id
            return HttpResponse(
                    json.dumps({'chat_log': json_chat_log, 
                                'classified_messages': classified_messages,
                                'oldest_message': oldest_message})
                    )

        if request.GET.get('type') == 'full_update':

            client_author = Author.get_author(get_ip(), create=False)
            client_name = None if client_author is None else client_author.name
            json_chat_log = json_serializable_chat_log(None)
            oldest = ChatLog.messages.order_by('id').first()
            oldest_message = None if oldest is None else oldest.id
            return HttpResponse(json.dumps({'client_name': client_name,
                                            'chat_log': json_chat_log,
                                            'oldest_message': oldest_message}))
        else:
            logging.error(f'Invalid GET request: {request}')
    if request.method == 'POST':
        if 'message' in request.POST:
            author_name = ChatLog.log_message(
                    message_string=request.POST['message'], ip=get_ip())
            return HttpResponse(json.dumps({'client_name': author_name}))
        else:
            logging.error(f'Invalid POST request: {request}')

    return HttpResponse('Invalid request')

