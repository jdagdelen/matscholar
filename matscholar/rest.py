import requests
import json
import warnings
from os import environ

"""
This module provides classes to interface with the MatScholar REST
API.

To make use of the MatScholar API, you need to obtain an API key by 
contacting John Dagdelen at jdagdelen@berkeley.edu.
"""

__author__ = "John Dagdelen"
__credits__ = "Shyue Ping Ong, Shreyas Cholia, Anubhav Jain"
__copyright__ = "Copyright 2018, Materials Intelligence"
__version__ = "0.1"
__maintainer__ = "John Dagdelen"
__email__ = "jdagdelen@berkeley.edu"
__date__ = "October 3, 2018"


class Rester(object):
    """
    A class to conveniently interface with the Mastract REST interface.
    The recommended way to use MatstractRester is with the "with" context
    manager to ensure that sessions are properly closed after usage::

        with MatstractRester("API_KEY") as m:
            do_something

    MatstractRester uses the "requests" package, which provides for HTTP connection
    pooling. All connections are made via https for security.

    Args:
        api_key (str): A String API key for accessing the MaterialsProject
            REST interface. Please obtain your API key by emailing
            John Dagdelen at jdagdelen@berkeley.edu. If this is None,
            the code will check if there is a "MATSTRACT_API_KEY" environment variable.
            If so, it will use that environment variable. This makes
            easier for heavy users to simply add this environment variable to
            their setups and MatstractRester can then be called without any arguments.
        endpoint (str): Url of endpoint to access the Matstract REST
            interface. Defaults to the standard address, but can be changed to other
            urls implementing a similar interface.
    """

    def __init__(self, api_key=None,
                 endpoint="http://0.0.0.0:8080"):
        if api_key is not None:
            self.api_key = api_key
        else:
            self.api_key = environ['MATERIALS_SCHOLAR_API_KEY']
        self.preamble = endpoint
        self.session = requests.Session()
        self.session.headers = {"x-api-key": self.api_key}

    def __enter__(self):
        """
        Support for "with" context.
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Support for "with" context.
        """
        self.session.close()

    def _make_request(self, sub_url, payload=None, method="GET"):
        response = None
        url = self.preamble + sub_url
        try:
            if method == "POST":
                response = self.session.post(url, json=payload, verify=True)
            else:
                response = self.session.get(url, params=payload, verify=True)
            if response.status_code in [200, 400]:
                data = json.loads(response.text)
                if data["valid_response"]:
                    if data.get("warning"):
                        warnings.warn(data["warning"])
                    return data["response"]
                else:
                    raise MatScholarRestError(data["error"])

            raise MatScholarRestError("REST query returned with error status code {}"
                                     .format(response.status_code))

        except Exception as ex:
            msg = "{}. Content: {}".format(str(ex), response.content) \
                if hasattr(response, "content") else str(ex)
            raise MatScholarRestError(msg)

    def materials_search(self, positive, negative=None, ignore_missing=True, top_k=10):
        """
        Given input strings or lists of positive and negative words / phrases, returns a ranked list of materials with
        corresponding scores and numbers of mentions
        :param positive: a string or a list of strings used as a positive search criterion
        :param negative: a string or a list of strings used as a negative search criterion
        :param ignore_missing: if True, ignore words missing from the embedding vocabulary, otherwise generate "guess"
        embeddings
        :param top_k: number of top results to return (10 by default)
        :return: a dictionary with the following keys ["materials", "counts", "scores", "positive", "negative",
                                                                    "original_negative", "original_positive"]
        """

        if not isinstance(positive, list):
            positive = [positive]
        if negative and not isinstance(negative, list):
            negative = [negative]
        method = "GET"
        sub_url = '/embeddings/matsearch/{}'.format(",".join(positive))
        payload = {'top_k': top_k, 'negative': ",".join(negative) if negative else None, 'ignore_missing': ignore_missing}

        return self._make_request(sub_url, payload=payload, method=method)

    def close_words(self, positive, negative=None, ignore_missing=True, top_k=10):
        """
        Given input strings or lists of positive and negative words / phrases, returns a list of most similar words /
        phrases according to cosine similarity
        :param positive: a string or a list of strings used as positive contributions to the cumulative embedding
        :param negative: a string or a list of strings used as negative contributions to the cumulative embedding
        :param ignore_missing: if True, ignore words missing from the embedding vocabulary, otherwise generate "guess"
        embeddings
        :param top_k: number of top results to return (10 by default)
        :return: a dictionary with the following keys ["close_words", "scores", "positive", "negative",
                                                                    "original_negative", "original_positive"]
        """

        if not isinstance(positive, list):
            positive = [positive]
        if negative and not isinstance(negative, list):
            negative = [negative]

        method = "GET"
        sub_url = '/embeddings/close_words/{}'.format(",".join(positive))
        payload = {'top_k': top_k, 'negative': ",".join(negative) if negative else None, 'ignore_missing': ignore_missing}

        return self._make_request(sub_url, payload=payload, method=method)

    def mentioned_with(self, material, words):
        """
        Given a material formula and a list of words, returns True if the material was mentioned with any of the words
        in our corpus of abstracts, otherwise returns False
        :param material: the material formula as a string
        :param words: a list of words and phrases (pre-processed, phrases separated by _, words lower cased, etc.)
        :return: True or False
        """

        method = "GET"
        sub_url = '/search/mentioned_with'
        payload = {
            'material': material,
            'words': " ".join(words)
        }

        return self._make_request(sub_url, payload=payload, method=method)["mentioned_with"]

    def process_text(self, text, exclude_punct=False, phrases=False):
        """
        Chemistry and Materials Science-aware pre-processing of text. Keeps the sentence structure, so returns a list
        of lists of strings, with each string corresponding to a single token.
        :param text: The input text
        :param exclude_punct: If True, will remove punctuation (False by default)
        :param phrases: If True, will convert single words to common materials science phrases separated by _
        (False by default)
        :return: processed text as a list of lists of strings
        """

        method = "GET"
        sub_url = '/embeddings/preprocess/{}'.format(text)
        payload = {
            'exclude_punct': exclude_punct,
            'phrases': phrases
        }

        return self._make_request(sub_url, payload=payload, method=method)["processed_text"]

    def get_embedding(self, wordphrases, ignore_missing=True):
        """
        Returns the embedding(s) for the supplied wordphrase. If the wordphrase is a string, returns a single embedding
        vector as a list. If the wordphrase is a list of string, returns a matrix with each row corresponding to a single
        (potentially cumulative) embedding. If the words (after pre-processing) do not have embeddings and
        ignore_missing is set to True, a list of all 0s is returned
        :param wordphrases: a string or a list of strings
        :param ignore_missing: if True, will ignore missing words, otherwise will guess embeddings based on
        string similarity
        :return: a dictionary with following keys ["original_wordphrases", "processed_wordphrases", "embeddings"]
        """

        if isinstance(wordphrases, list):
            method = "POST"
            sub_url = '/embeddings'
            payload = {
                'wordphrases': wordphrases,
                'ignore_missing': ignore_missing
            }
        else:
            method = "GET"
            sub_url = '/embeddings/{}'.format(wordphrases)
            payload = {
                'ignore_missing': ignore_missing
            }

        return self._make_request(sub_url, payload=payload, method=method)


class MatScholarRestError(Exception):
    """
    Exception class for MatstractRester.
    Raised when the query has problems, e.g., bad query format.
    """
    pass
