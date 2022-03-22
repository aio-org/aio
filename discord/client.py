# -*- coding: utf-8 -*-
# cython: language_level=3
# Copyright (c) 2021-present VincentRPS

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE

import asyncio
import importlib
import importlib.machinery
import importlib.util
import logging
import sys
import time
from threading import Event
from typing import Callable, Dict, List, Literal, Optional, TypeVar

from discord.channels import VoiceChannel

from .api.gateway import Gateway
from .ext.cogs import Cog, ExtensionLoadError
from .flags import Intents
from .guild import Guild
from .http import RESTFactory
from .interactions import ApplicationCommandRegistry
from .internal import dispatcher
from .state import ConnectionState
from .user import User

_log = logging.getLogger(__name__)
__all__: List[str] = ['Client']
CFT = TypeVar('CFT', bound='dispatcher.CoroFunc')


class Client:
    """Represents a Discord bot.

    .. versionadded:: 0.4.0

    Attributes
    ----------
    factory
        The instance of RESTFactory
    state
        The client's connection state
    dispatcher
        The dispatcher
    gateway
        The Gateway
    p
        The presence
    cogs
        A :class:`dict` of all Cogs.
    intents: :class:`int`
        Your current Gateway intents.

    Parameters
    ----------
    token
        The bot token
    intents
        The bot intents, defaults `32509`
    status
        The bot status, defaults to online
    afk
        If the bot is afk, default to False
    loop
        The loop you want to use, defaults to :class:`asyncio.new_event_loop`
    module
        The module with a `banner.txt` to print
    voice
        If to enable the voice gateway or not, defaults False.
    logs
        A :class:`int`, :class:`str` or :class:`dict`.
    debug
        To show debug logs or not.
    state: :class:`ConnectionState`
        Allow's for custom ConnectionStates,
        and soforth custom db caches.
    command_prefix: :class:`str`
        The prefix for prefixed commands,
        defaults to ''.
    chunk_guild_members
        If to cache guild members,
        this allows the before argument on member events,
        aswell as faster fetching times.
    api_version: :class:`int`
        The Discord API Version to use,
        normally defaults to the newest version.
    """

    def __init__(
        self,
        intents: Optional[int] = Intents.ALL_UNPRIVLEDGED,
        shards: Optional[int] = None,
        mobile: Optional[bool] = False,
        proxy: Optional[str] = None,
        proxy_auth: Optional[str] = None,
        state: Optional[ConnectionState] = None,
        chunk_guild_members: Optional[bool] = False,
        api_version: Optional[int] = 10,
        cache_timeout: Optional[int] = 10000,
    ):
        self.state = state or ConnectionState(
            intents=intents, bot=self, shard_count=shards, timeout=cache_timeout
        )
        self.dispatcher = dispatcher.Dispatcher(state=self.state)
        self.factory = RESTFactory(state=self.state, proxy=proxy, proxy_auth=proxy_auth, version=api_version)
        self.application = ApplicationCommandRegistry(self.factory, self.state)
        self.gateway = Gateway(
            state=self.state,
            dispatcher=self.dispatcher,
            factory=self.factory,
            mobile=mobile,
        )
        self._got_gateway_bot: Event = Event()
        self.cogs: Dict[str, Cog] = {}
        self._extensions = {}
        self.chunk_guild_members = chunk_guild_members
        self.intents = intents

    async def login(self, token: str):
        """Starts the bot connection

        .. versionadded:: 0.4.0

        """
        self.token = token
        r = await self.factory.login(token)
        self.state._bot_id = r['id']
        return r

    def voice(self, channel: VoiceChannel):
        return DeprecationWarning('This has been deprecated.')

    @property
    def latency(self) -> float:
        return self.gateway.latency

    async def connect(self, token: str):
        """Starts the WebSocket(Gateway) connection with Discord.

        .. versionadded:: 0.4.0
        """

        await self.gateway.connect(token=token)
        if self.chunk_guild_members is not False:
            # this makes sure we are already
            # connected when asking for the chunk
            await asyncio.sleep(30)
            await self.gateway._chunk_members()

    def run(self, token: str, **kwargs):
        """A blocking function to start your bot

        Parameters
        ----------
        token: :class:`str`
            Your bot token
        asyncio_debug: :class:`bool`
        """

        async def runner():
            await self.login(token=token)
            await self.dispatcher.dispatch('login')
            await self.connect(token=token)

        debug = kwargs.get('asyncio_debug', False)

        if not debug:
            asyncio.run(runner())
        else:
            asyncio.run(runner(), debug=True)

    def fetch_guild(self, guild_id):
        """Fetches the guild from the cache

        Parameters
        ----------
        guild_id: :class:`int`
            The guild to fetch

        Returns
        -------
        :class:`Guild`
        """
        raw = self.state.guilds.get(guild_id)
        return Guild(raw, self.factory)

    def fetch_raw_guild(self, guild_id):
        return self.state.guilds.get(guild_id)

    async def get_guild(self, guild_id):
        """Gets a guild by requesting to the API

        Parameters
        ----------
        guild_id: :class:`int`
            The guild to get

        Returns
        -------
        :class:`Guild`
        """
        raw = await self.factory.guilds.get_guild(guild_id=guild_id)
        return Guild(raw, self.factory)

    async def get_voice_channel(self, channel_id: int):
        raw = await self.factory.channels.get_channel(channel=channel_id)
        return VoiceChannel(raw, self.state)

    @property
    def is_ready(self):
        """Returns if the bot is ready or not."""
        return self.state._ready.is_set()

    @property
    def presence(self) -> List[str]:
        return self.state._bot_presences

    def change_presence(
        self,
        name: str,
        type: int,
        status: Literal['online', 'dnd', 'idle', 'invisible', 'offline'] = 'online',
        stream_url: Optional[str] = None,
        afk: Optional[bool] = False,
        shard: Optional[int] = None,
    ):
        """Changes the bot's presence

        Parameters
        ----------
        name
            The presence name
        type
            The presence type
        status
            The presence status

            .. note::

                can be 'online', 'dnd',
                invisible and offline.
        stream_url
            Used with the streaming presence type
        afk
            If to be afk or not
        """
        if type == 1 and stream_url is None:
            raise NotImplementedError('Streams need to be provided a url!')
        elif type == 1 and stream_url is not None:
            ret = {
                'name': name,
                'type': 1,
                'url': stream_url,
            }
        else:
            # another type
            ret = {
                'name': name,
                'type': type,
            }
        json = {'op': 3, 'd': {'activities': [ret]}}

        if afk is True:
            json['d']['afk'] = True
            json['d']['since'] = time()
        else:
            json['d']['afk'] = False
            json['d']['since'] = None

        json['d']['status'] = status

        return self.gateway.send(json, shard)

    def event(self, coro: dispatcher.Coro) -> dispatcher.Coro:
        """Register an event"""
        return self.dispatcher.listen(coro)

    def listen(self, name: str = None) -> Callable[[CFT], CFT]:
        """Listen to a event

        like :meth:`Client.event` but you can have a event split into multiple coroutines.

        Parameters
        ----------
        name
            The event to listen to
        """

        def decorator(func: CFT) -> CFT:
            self.dispatcher.add_listener(func, name)
            return func

        return decorator

    @property
    def user(self):
        """Returns the bot user

        Returns
        -------
        :class:`User`
        """
        return User(self.state.bot_info[self])

    def slash_command(
        self,
        name: Optional[str] = None,
        options: List[dict] = None,
        guild_ids: List[int] = None,
        default_permission: bool = True,
    ):
        """Creates a slash command

        Parameters
        ----------
        name: :class:`str`
            The slash command name
        callback
            The slash command callback
        options: :class:`List`
            A list of slash command options
        guild_ids: List[:class:`int`]
            A list of guild ids
        description: :class:`str`
            The application command description
        default_permission: :class:`bool`
            If this slash command should have default permissions
        """
        def decorator(func: CFT) -> CFT:
            loop = asyncio.get_running_loop()
            _name = func.__name__ if name is None else name
            description = "No description provided" if func.__doc__ is None else func.__doc__

            if guild_ids is not None:
                for guild in guild_ids:
                    loop.create_task(
                        self.application.register_guild_slash_command(
                            guild_id=guild,
                            name=_name,
                            description=description,
                            callback=func,
                            options=options,
                            default_permission=default_permission,
                        )
                    )
            else:
                loop.create_task(
                    self.application.register_global_slash_command(
                        name=_name,
                        description=description,
                        callback=func,
                        options=options,
                        default_permission=default_permission,
                    )
                )

            return func

        return decorator

    async def add_cog(self, cog: Cog, *, override: bool = False):
        if not isinstance(cog, Cog):
            raise TypeError('ALL cogs must subclass Cog.')

        name = cog.__cog_name__
        current = self.cogs.get(name)

        if current is not None:
            if not override:
                raise TypeError('There is already another Cog with this name!')
            self.remove_cog(current)

        cog = cog._inject(self)

        for name, func in cog.listeners.items():
            self.dispatcher.add_listener(func, name, cog=cog)

        await self._register_cog_commands(real=cog)
        self.cogs[name] = cog

    async def remove_cog(self, cog: Cog):
        self.cogs.pop(cog.__cog_name__)
        cog._eject(self)

    def _resolver(self, name: str, *, package: str):
        try:
            return importlib.util.resolve_name(name=name, package=package)
        except ImportError:
            raise TypeError('Cog is not found!')

    async def _extension_loader(self, spec: importlib.machinery.ModuleSpec, key: str):
        lib = importlib.util.module_from_spec(spec)
        sys.modules[key] = lib
        try:
            spec.loader.exec_module(lib)
        except Exception as exc:
            del sys.modules[key]
            raise ExtensionLoadError(key, exc) from exc

        try:
            setup = getattr(lib, 'setup')
        except Exception as exc:
            del sys.modules[key]
            raise TypeError('There is no setup function inside your cog file!')

        try:
            await setup(self)
        except Exception as exc:
            del sys.modules[key]
            raise ExtensionLoadError(key, exc) from exc
        else:
            self._extensions[key] = lib

    async def add_extension(self, name: str, *, package: Optional[str] = None):
        name = self._resolver(name=name, package=package)
        if name in self._extensions.items():
            raise TypeError('Module is already loaded')

        spec = importlib.util.find_spec(name)
        if spec is None:
            raise TypeError(f'Extension {name} is not found!')

        await self._extension_loader(spec, name)

    async def remove_extension(self, name: str, *, package: Optional[str] = None):
        name = self._resolver(name=name, package=package)
        lib = self._extensions.get(name)
        if lib is None:
            raise TypeError('That Module isnt loaded')
        else:
            await self.remove_cog(name)
            self._extensions.pop(lib)

    async def _register_cog_commands(self, real: Cog):
        await asyncio.sleep(20)

        for command in real.guild_commands.values():
            for guild_id in command['guild_id']:
                await self.application.register_guild_slash_command(
                    guild_id=guild_id,
                    name=command['name'],
                    description=command['description'],
                    callback=command['callback'],
                    options=command['options'],
                    default_permission=command['default_permission'],
                    cog=real,
                )
        for command in real.global_commands.values():
            await self.application.register_global_slash_command(
                name=command['name'],
                description=command['description'],
                callback=command['callback'],
                options=command['options'],
                default_permission=command['default_permission'],
                cog=real,
            )

    def wait_for(self, event: str):
        return self.dispatcher.wait_for(event)

    @property
    def guilds(self) -> List[Guild]:
        return [Guild(guild, self.factory) for guild in self.state.guilds.view()]
