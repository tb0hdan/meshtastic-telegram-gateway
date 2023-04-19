# -*- coding: utf-8 -*-
""" OpenAI Bot module """

import os
import openai

# fallback:
# I'm sorry, I'm not able to help you with that request.
# I'm sorry, I can't do that.
# I apologize, I'm not sure I can help you with that.
# I'm sorry, but I cannot help with that request.
# I'm sorry, but I do not have access to that kind of content.
# I'm sorry, I don't understand the request.
class OpenAIDavinci:
    """ OpenAI Bot container """
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY", default='')
        openai.api_key = api_key
        self.completion = openai.Completion() if len(api_key) > 0 else None
        self.seed = (
            "The following is a conversation with an AI assistant. "
            + "The assistant is helpful, creative, clever, and very friendly.\n\n"
        )


    def run_query(self, user, query):
        """
        Run OpenAI query with user info

        user: user name
        query: user query
        :return: response from OpenAI
        """
        seed = f"{self.seed}{user}: Hello, who are you?\nAI: I am an AI created by OpenAI. How can I help you today?\n"
        return self.completion.create(
            model="text-davinci-003",
            prompt=f"{seed}{user}: {query}\nAI:\n",
            temperature=0.9,
            top_p=1,
            presence_penalty=0.6,
            frequency_penalty=0,
            max_tokens=256,
            user=user,
            best_of=4,
            stop=[f" {user}:", " AI:"],
        )

    def get_response(self, user, incoming):
        """
        Get response from OpenAI API

        :param user:
        :param incoming:
        :return:
        """
        if self.completion is None:
            print('OpenAIBot not initialized...')
            return None
        response = self.run_query(user, incoming)
        print(user, response)
        return response.get('choices')[0].get('text').lstrip('!').lstrip('\n')

class OpenAIBot:
    """ OpenAI Bot container """
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY", default='')
        openai.api_key = api_key
        self.completion = openai.ChatCompletion() if len(api_key) > 0 else None
        self.seed = (
            "The following is a conversation with an AI assistant. "
            + "The assistant is helpful, creative, clever, and very friendly.\n\n"
        )


    def run_query(self, user, query):
        """
        Run OpenAI query with user info

        :param user:
        :param query:
        :return:
        """
        messages = [{"role": "system", "content": self.seed},
                    {"role": "user", "content": f"{user}: Hello, who are you?"},
                    {"role": "assistant", "content": "AI: I am an AI created by OpenAI. How can I help you today?"},
                    {"role": "user", "content": query},
                    ]
        return self.completion.create(model="gpt-3.5-turbo", messages=messages,
                                      temperature=0.9, top_p=1, presence_penalty=0.6,
                                      frequency_penalty=0, max_tokens=256, user=user,
                                      stop=[f" {user}:", " AI:"])

    def get_response(self, user, incoming):
        """
        Get response from OpenAI API

        :param user:
        :param incoming:
        :return:
        """
        if self.completion is None:
            print('OpenAIBot not initialized...')
            return None
        response = self.run_query(user, incoming)
        print(user, response)
        return response.get('choices')[0].get('message').get('content')
