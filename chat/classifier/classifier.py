"""
This is a 3-class classifier made from the hatespeech-offensive-none dataset.

The "trained_model.pkl" has been exported at the end of the training phase
on jupyter notebook. 
It contains the trained classifier model with all parameters and weights.
This file is then used to rebuild the classifier on the server with all of the 
weights that have already been learned during training (On a google server with
highly performent GPUs)

The "classifier.py" is there to provide an RPC interface to the django chat app 
for classifying the messages. It is started on the server as a service separate
from the django web application.

The classifier is not directly integrated into the django app, because the 
multiple workers of the django web server would all spawn their own instances of
it and use up a multiple of the memory on the server. Around 200MB per worker.
"""

from fastai.text import * 
import rpyc

# Load the trained model from file
learn = load_learner('./', 'trained_model.pkl')

# Define an RPC service, so that the classifier can be used from outside
class ClassifierService(rpyc.Service):

    def exposed_classify(self, message): # this is an outwardly exposed method
        label = str(learn.predict(message)[0])
        if label == 'none':
            return 'N'
        if label == 'hatespeech':
            return 'H'
        if label == 'offensive':
            return 'O'
        print('Unexpected label: ', label)


if __name__ == "__main__":
    from rpyc.utils.server import ThreadedServer
    ThreadedServer(ClassifierService, port=18861).start()

