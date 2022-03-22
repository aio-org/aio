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

from ..interactions import Interaction
from .core import Event


class OnInteraction(Event):
    """A event which processes interactions, not to be normally used

    Returns
    -------
    interaction: :class:`Interaction`
    """

    async def process(self):
        for component in self.state.components.values():
            if component['id'] == self.data['data']['custom_id']:
                self.loop.create_task(
                    component['self']._run_callback(component['callback'], self.data, self.state)
                )
        try:
            for application_command in self.state.application_commands.values():
                cog = application_command['cog']
                if application_command['d']['id'] == self.data['data']['id']:
                    self.loop.create_task(
                        application_command['self'].run(
                            application_command['callback'],
                            self.data,
                            self.state,
                            cog=cog,
                        )
                    )
        except KeyError:
            # components
            pass

        await self.dispatch('INTERACTION', Interaction(self.data, self.state))
