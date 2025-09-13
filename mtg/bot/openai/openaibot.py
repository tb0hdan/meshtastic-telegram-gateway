# -*- coding: utf-8 -*-
""" OpenAI Bot module """

import os
from typing import Any, Optional
import openai


class OpenAIBot:
    """ OpenAI Bot container """

    def __init__(self, logger: Any) -> None:
        api_key = os.getenv("OPENAI_API_KEY", default='')
        openai.api_key = api_key
        self.logger = logger
        self.client = openai.OpenAI() if len(api_key) > 0 else None  # pylint:disable=no-member
        self.seed = (
                "The following is a conversation with an AI assistant. "
                + "The assistant is helpful, creative, clever, and very friendly.\n\n"
        )

    def run_query(self, user: str, query: str) -> Any:
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
        return self.client.chat.completions.create(model="gpt-3.5-turbo", messages=messages,
                                      temperature=0.9, top_p=1, presence_penalty=0.6,
                                      frequency_penalty=0, max_tokens=256, user=user,
                                      stop=[f" {user}:", " AI:"])

    def get_response(self, user: str, incoming: str) -> Optional[str]:
        """
        Get response from OpenAI API

        :param user:
        :param incoming:
        :return:
        """
        if self.client is None:
            self.logger.error('OpenAIBot not initialized...')
            return None
        response = self.run_query(user, incoming)
        self.logger.info(user, response)
        return response.get('choices')[0].get('message').get('content')
