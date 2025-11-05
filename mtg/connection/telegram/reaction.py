# -*- coding: utf-8 -*-
"""Helpers for handling Telegram message reaction updates."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional

from telegram import Chat, Update, User, constants
from telegram.ext import CallbackContext, Handler


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReactionType:  # pragma: no cover - simple data container
    """Base representation of a Telegram reaction."""

    type: str
    is_big: bool = False


@dataclass(frozen=True)
class EmojiReaction(ReactionType):
    """Representation of a standard emoji reaction."""

    emoji: str = ''

    def __init__(self, emoji: str, *, is_big: bool = False):
        super().__init__('emoji', is_big=is_big)
        object.__setattr__(self, 'emoji', emoji)


@dataclass(frozen=True)
class CustomEmojiReaction(ReactionType):
    """Representation of a custom emoji reaction."""

    custom_emoji_id: str = ''

    def __init__(self, custom_emoji_id: str, *, is_big: bool = False):
        super().__init__('custom_emoji', is_big=is_big)
        object.__setattr__(self, 'custom_emoji_id', custom_emoji_id)


@dataclass(frozen=True)
class UnknownReaction(ReactionType):  # pragma: no cover - debugging helper
    """Representation for reaction types we do not explicitly support."""

    raw: object = None

    def __init__(self, reaction_type: str, raw: object):
        super().__init__(reaction_type)
        object.__setattr__(self, 'raw', raw)


def _parse_reaction_list(data: Optional[Iterable[dict]]) -> List[ReactionType]:
    """Return a list of ReactionType instances parsed from raw data."""

    reactions: List[ReactionType] = []
    if not data:
        return reactions
    for item in data:
        if not isinstance(item, dict):
            reactions.append(UnknownReaction('unknown', item))
            continue
        reaction_type = item.get('type')
        is_big = bool(item.get('is_big', False))
        if reaction_type == 'emoji' and item.get('emoji'):
            reactions.append(EmojiReaction(item['emoji'], is_big=is_big))
        elif reaction_type == 'custom_emoji' and item.get('custom_emoji_id'):
            reactions.append(CustomEmojiReaction(item['custom_emoji_id'], is_big=is_big))
        else:  # pragma: no cover - defensive logging branch
            reactions.append(UnknownReaction(reaction_type or 'unknown', item))
    return reactions


@dataclass
class MessageReactionUpdate:
    """Minimal structure describing a Telegram message reaction update."""

    chat: Optional[Chat]
    message_id: Optional[int]
    user: Optional[User]
    actor_chat: Optional[Chat]
    date: Optional[int]
    old_reaction: List[ReactionType]
    new_reaction: List[ReactionType]

    @classmethod
    def from_raw(cls, data: Optional[dict], bot) -> Optional['MessageReactionUpdate']:
        """Parse raw JSON payload into a MessageReactionUpdate instance."""

        if not data:
            return None
        chat = Chat.de_json(data.get('chat'), bot)
        actor_chat = Chat.de_json(data.get('actor_chat'), bot)
        user = User.de_json(data.get('user'), bot)
        message_id = data.get('message_id')
        date = data.get('date')
        old_reaction = _parse_reaction_list(data.get('old_reaction'))
        new_reaction = _parse_reaction_list(data.get('new_reaction'))
        return cls(
            chat=chat,
            message_id=message_id,
            user=user,
            actor_chat=actor_chat,
            date=date,
            old_reaction=old_reaction,
            new_reaction=new_reaction,
        )


def ensure_reaction_update_support() -> None:
    """Monkey patch python-telegram-bot to expose message reaction updates."""

    # Avoid reapplying the patch if another instance already did so.
    if getattr(Update, 'MESSAGE_REACTION', None):
        return

    constants.UPDATE_MESSAGE_REACTION = 'message_reaction'
    if constants.UPDATE_MESSAGE_REACTION not in constants.UPDATE_ALL_TYPES:
        constants.UPDATE_ALL_TYPES.append(constants.UPDATE_MESSAGE_REACTION)

    Update.MESSAGE_REACTION = constants.UPDATE_MESSAGE_REACTION
    if hasattr(Update, 'ALL_TYPES') and constants.UPDATE_MESSAGE_REACTION not in Update.ALL_TYPES:
        Update.ALL_TYPES.append(constants.UPDATE_MESSAGE_REACTION)

    if 'message_reaction' not in getattr(Update, '__slots__', ()):  # pragma: no branch
        Update.__slots__ = tuple(Update.__slots__) + ('message_reaction',)

    original_de_json = Update.de_json.__func__  # type: ignore[attr-defined]

    @classmethod
    def patched_de_json(cls, data, bot):  # pragma: no cover - exercised indirectly
        raw_reaction = None
        if isinstance(data, dict):
            raw_reaction = data.get('message_reaction')
        update = original_de_json(cls, data, bot)
        if update is None:
            return None
        if raw_reaction is not None:
            reaction = MessageReactionUpdate.from_raw(raw_reaction, bot)
            try:
                update.message_reaction = reaction
            except AttributeError:  # pragma: no cover - defensive
                LOGGER.debug('Unable to attach message reaction to update', exc_info=True)
            else:
                if reaction is not None:
                    if update._effective_chat is None and reaction.chat is not None:  # pylint:disable=protected-access
                        update._effective_chat = reaction.chat
                    if update._effective_user is None and reaction.user is not None:  # pylint:disable=protected-access
                        update._effective_user = reaction.user
        return update

    Update.de_json = patched_de_json  # type: ignore[assignment]


class MessageReactionHandler(Handler[Update, CallbackContext]):
    """Dispatcher handler that triggers on Telegram message reaction updates."""

    def __init__(self, callback: Callable[[Update, CallbackContext], object]):
        super().__init__(callback)

    def check_update(self, update: object):  # type: ignore[override]
        if isinstance(update, Update) and getattr(update, 'message_reaction', None):
            return update.message_reaction
        return None
