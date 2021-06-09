from django.db import models
from django.db.utils import OperationalError
from threading import Lock, Thread
import time
import logging
import datetime
import rpyc

classifier_host = 'classifier'
classifier_port = '18861'

class Author(models.Model):

    class AuthorManager(models.Manager):
        pass

    authors = AuthorManager()  # renames entries from 'objects' to 'messages'

    AUTHOR_NAME_CHOICES = (('Anonymous', 'Anonymous'),
                           ('Bush', 'Bush'),
                           ('Clinton', 'Clinton'),
                           ('Ghandi', 'Ghandi'),
                           ('Kennedy', 'Kennedy'),
                           ('Merkel', 'Merkel'),
                           ('Obama', 'Obama'),
                           ('Putin', 'Putin'),
                           ('Trump', 'Trump'))

    ip = models.GenericIPAddressField(primary_key=True)
    name = models.CharField(max_length=15, choices=AUTHOR_NAME_CHOICES,
                            default='Anonymous')

    def __str__(self):
        return f"{self.name} ({self.ip}), pk: {self.pk}"

    @staticmethod
    def get_author(ip, create=False):
        ''' Retrieves or creates new author based on unique ip address'''
        try:
            return Author.authors.get(ip=ip)
        except models.ObjectDoesNotExist:
            if create:
                # TODO: Lock this to avoid race conditions
                all_names = set(choice[0] for choice
                                in Author.AUTHOR_NAME_CHOICES)
                taken_names = set(author.name for author
                                  in list(Author.authors.all()))
                available_names = (all_names - taken_names)
                available_names.remove('Anonymous')  # Save this one for last
                try:
                    designated_name = available_names.pop()
                except KeyError:  # No more name available
                    designated_name = "Anonymous"
                return Author.authors.create(name=designated_name, ip=ip)


CONC_COUNT = 4

class ChatLog(models.Model):

    class ChatLogManager(models.Manager):
        pass

    messages = ChatLogManager()  # renames entries from 'objects' to 'messages'

    MESSAGE_CLASS_CHOICES = (('H', 'HATESPEECH'),
                             ('U', 'UNCLASSIFIED'),
                             ('O', 'OFFENSIVE'),
                             ('N', 'NORMAL'))

    author = models.ForeignKey(Author, on_delete=models.CASCADE,
                               related_name='authored')
    message_string = models.CharField(max_length=200)
    message_class = models.CharField(max_length=1,
                                     choices=MESSAGE_CLASS_CHOICES)
    time_stamp = models.DateTimeField(default=datetime.datetime.utcnow)
    """
    concatenated_classes:
        This was added due to the request of the supervisor to be able to
        reclassify previous messages based on subsequent ones.
        example: 'RRNN' means that:
            this_message+the_previous_message_from_the_same_author -> 'R'
            this_message+the_previous2_messages_from_the_same_author -> 'R'
            this_message+the_previous3_messages_from_the_same_author -> 'N'
            this_message+the_previous4_messages_from_the_same_author -> 'N'
        This in combination with self.n_previous_messages() allows for figuring
        out which messages actually were concatenated.
        This can then be interpreted on the front-end (like relabeling,
        explaining current label in tooltip, etc.)
        The reclassification is only manifested on the client-side to more
        easily make the reasoning for reclassifications visible to the user and
        to keep it flexible.
        The implementation tries to make the additional code fit in without
        making the whole system infinitely complicated because of this new
        feature's existence.
        It is limited to CONC_COUNT concatenations as this was found to be the
        most resonable value for cohesive message content after testing it.
    """
    concatenated_classes = models.CharField(max_length=10)

    def __str__(self):
        return '[{}] {} - {}'.format(self.message_class, self.time_stamp,
                                     self.message_string)

    def n_previous_messages(self):
        previous_messages = list(ChatLog.messages.
                filter(author=self.author, pk__lt=self.pk).
                order_by('-id')[:CONC_COUNT])
        return previous_messages

    @staticmethod
    def labeler(message_record):

        def classify(string):
            rpc_connection = rpyc.connect(classifier_host, classifier_port).root
            return rpc_connection.classify(string)

        # Get label of single message classification
        record_query = ChatLog.messages.filter(id__exact=message_record.id)
        new_message_string = message_record.message_string
        single_classification = classify(new_message_string)

        # Get labels from classification of concatenated messages
        concatenated_classifications = ''

        previous_messages = message_record.n_previous_messages()

        for i in range(1, min(CONC_COUNT, len(previous_messages))+1):
            messages = previous_messages[:i]
            messages.reverse()
            concatenated_string = ''.join(
                [m.message_string + ' ' for m in messages]
            ) + new_message_string
            classification = classify(concatenated_string)
            print(f"Conc string:{concatenated_string}, Class: {classification}")
            concatenated_classifications += classification

        """Update single and concatenated classifications at the same time
        to make coordination with clientside easier"""
        record_query.update(
                message_class=single_classification,
                concatenated_classes=concatenated_classifications
                )

    @staticmethod
    def log_message(message_string, ip, message_class='U'):
        """ Log a submitted message and give back a name (eg. 'Trump') """
        if 0 < len(str(message_string)) <= 200:
            author = Author.get_author(ip, create=True)
            created_message_record = \
                    ChatLog.messages.create(message_string=str(message_string),
                                            author=author,
                                            message_class='U')
            t = Thread(target=ChatLog.labeler, args=(created_message_record,))
            t.start()
            return created_message_record.author.name

    @staticmethod
    def old_message_deleter():
        """ Delete old messages and free up unused authors
        WARNING: Changes during development apply only at server restart,
        because threads do not get autoreloaded depending on cli arguments"""
        one_hour = datetime.timedelta(seconds=60*60)
        try:
            while True:
                # Delete messages older than one hour from the chat
                now = datetime.datetime.utcnow()
                ChatLog.messages.filter(time_stamp__lt=now-one_hour).delete()

                # Delete authors with zero messages in chat to free them up
                for author in list(Author.authors.all()):
                    if author.authored.count() == 0:
                        Author.authors.filter(pk=author.pk).delete()
                time.sleep(2)
        except OperationalError as e:
            print(f'Old chat message deleter failed: {e}')
            #logging.critical(f'Old chat message deleter failed: {e}', exc_info=True)

