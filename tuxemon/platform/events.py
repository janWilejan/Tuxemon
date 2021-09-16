#
# Tuxemon
# Copyright (c) 2014-2017 William Edwards <shadowapex@gmail.com>,
#                         Benjamin Bean <superman2k5@gmail.com>,
#                         Leif Theden <leif.theden@gmail.com>
#
# This file is part of Tuxemon
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
from __future__ import annotations
from typing import Sequence, Mapping, Optional, Generator
import pygame


class EventQueueHandler:
    """Event QueueHandler for different platforms.

    * Only one per game
    * Sole manager of platform events of type
    """

    _inputs: Mapping[int, Sequence[InputHandler]]

    def release_controls(self) -> Generator[PlayerInput, None, None]:
        """
        Send virtual input events which release held buttons/axis.

        After this frame, held/triggered inputs will return to previous state.

        Yields:
            Inputs to release all buttons.

        """
        for value in self._inputs.values():
            for inp in value:
                yield from inp.virtual_stop_events()

    def process_events(self) -> None:
        raise NotImplementedError


class InputHandler:
    """
    Enables basic input device with discrete inputs.

    Parameters:
        event_map: Mapping of pygame identifiers to button identifiers.

    """

    event_type = None
    default_input_map: Mapping[int, int]

    def __init__(self, event_map: Optional[Mapping[int, int]] = None):
        if event_map is None:
            event_map = self.default_input_map
        self.buttons = dict()
        self.event_map = event_map
        for button in event_map.values():
            self.buttons[button] = PlayerInput(button)

    def process_event(self, pg_event: pygame.event.Event) -> None:
        raise NotImplementedError

    def virtual_stop_events(self) -> Generator[PlayerInput, None, None]:
        """
        Send virtual input events simulating released buttons/axis.

        This is used to force a state to release inputs without changing input
        state.

        Yields:
            Inputs to release all buttons of this handler.

        """
        for inp in self.buttons.values():
            if inp.held:
                yield PlayerInput(inp.button, 0, 0)

    def get_events(self) -> Generator[PlayerInput, None, None]:
        """
        Update the input state (holding time, etc) and return player inputs.

        Yields:
            Player inputs (before updating their state).

        """
        for inp in self.buttons.values():
            if inp.held:
                yield inp
                inp.hold_time += 1
            elif inp.triggered:
                yield inp
                inp.triggered = False

    def press(self, button: int, value: float = 1) -> None:
        """
        Press a button managed by this handler.

        Parameters:
            button: Identifier of the button to press.
            value: Intensity value used for pressing the button.

        """
        inp = self.buttons[button]
        inp.value = value
        if not inp.hold_time:
            inp.hold_time = 1

    def release(self, button: int) -> None:
        """
        Release a button managed by this handler.

        Parameters:
            button: Identifier of the button to release.

        """
        inp = self.buttons[button]
        inp.value = 0
        inp.hold_time = 0
        inp.triggered = True


class PlayerInput:
    """
    Represents a single player input.

    Each instance represents the state of a single input:
    * have float value 0-1
    * are "pressed" when value is above 0, for exactly one frame
    * are "held" when "pressed" for longer than zero frames

    Do not manipulate these values.
    Once created, these objects will not be destroyed.
    Input managers will set values on these objects.
    These objects are reused between frames, do not hold references to
    them.

    Parameters:
        button: Identifier of the button that caused this input.
        value: Intensity of the press in the range [0, 1]. 0 is not pressed
            and 1 is fully pressed. Some inputs, such as analog sticks may
            support intermediate values.
        hold_time: The number of frames this input has been hold.

    """

    __slots__ = ("button", "value", "hold_time", "triggered")

    def __init__(
        self,
        button: int,
        value: float = 0,
        hold_time: int = 0,
    ) -> None:
        self.button = button
        self.value = value
        self.hold_time = hold_time
        self.triggered = False

    def __str__(self) -> str:
        return (
            f"<PlayerInput: {self.button} {self.value} {self.pressed} "
            f"{self.held} {self.hold_time}>"
        )

    @property
    def pressed(self) -> bool:
        """
        This is edge triggered, meaning it will only be true once!

        Returns:
            Whether the input has been pressed.

        """
        return bool(self.value) and self.hold_time == 1

    @property
    def held(self) -> bool:
        """
        This will be true as long as button is held down.

        Returns:
            Whether the input is being hold.

        """
        return bool(self.value)
