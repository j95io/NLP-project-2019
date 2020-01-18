import os
import sys

"""
Prevent from running apps.py twice in development without --noreload set,
because it would duplicate the threads.
Also dont run apps.py when making migrations or when migrating, as it will
start threads.
"""

is_thread_restarted = os.environ.get('RUN_MAIN', None) == 'true'
is_local_testing_runserver = sys.argv[1] == 'runserver'
is_production_runserver = 'gunicorn' in sys.argv[0]

if is_production_runserver or \
        (is_local_testing_runserver and not is_thread_restarted):
        
    default_app_config = 'homepage.hosts.uni.chat.apps.ChatConfig'

