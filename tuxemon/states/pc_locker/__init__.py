# SPDX-License-Identifier: GPL-3.0
# Copyright (c) 2014-2023 William Edwards <shadowapex@gmail.com>, Benjamin Bean <superman2k5@gmail.com>
from __future__ import annotations

import logging
import uuid
from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Optional, Sequence, Tuple

import pygame_menu
from pygame_menu import baseimage, locals, widgets

from tuxemon import graphics, prepare
from tuxemon.db import db
from tuxemon.item import item
from tuxemon.locale import T
from tuxemon.menu.interface import MenuItem
from tuxemon.menu.menu import PygameMenuState
from tuxemon.menu.quantity import QuantityMenu
from tuxemon.menu.theme import get_theme
from tuxemon.session import local_session
from tuxemon.states.items import ItemMenuState
from tuxemon.tools import open_choice_dialog, open_dialog

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from tuxemon.animation import Animation
    from tuxemon.item.item import Item


MenuGameObj = Callable[[], object]

HIDDEN_LOCKER = "hidden_locker"
HIDDEN_LIST_LOCKER = [HIDDEN_LOCKER]


class ItemTakeState(PygameMenuState):
    """
    Shows all items currently in a storage locker, and selecting one puts it
    into your bag.
    """

    def add_menu_items(
        self,
        menu: pygame_menu.Menu,
        items: Sequence[Item],
    ) -> None:
        # it regroups kennel operations: pick up, move and release
        def locker_options(instance_id: uuid.UUID) -> None:

            # retrieves the item from the iid
            iid = uuid.UUID(instance_id)
            itm = self.player.find_item_in_storage(iid)

            # list with all the lockers and removes where we are
            lockers = list(local_session.player.item_boxes.keys())
            lockers.remove(self.box_name)

            # updates the kennel and executes operation
            def update_locker(itm: Item, box: str) -> None:
                self.client.pop_state()
                self.client.pop_state()
                if len(lockers) >= 2:
                    self.client.pop_state()
                self.player.remove_item_from_storage(itm)
                self.player.item_boxes[box].append(itm)

            # opens choice dialog (move item)
            def change_locker(itm: Item) -> None:
                var_menu = []
                for box in lockers:
                    text = T.translate(box).upper()
                    var_menu.append(
                        (text, text, partial(update_locker, itm, box))
                    )
                open_choice_dialog(
                    local_session,
                    menu=(var_menu),
                    escape_key_exits=True,
                )

            # picks up the item
            def take(itm: Item, quantity: int) -> None:
                self.client.pop_state()
                self.client.pop_state()
                diff = itm.quantity - quantity
                if diff <= 0:
                    self.player.remove_item_from_storage(itm)
                    if self.player.find_item(itm.slug):
                        self.player.find_item(itm.slug).quantity += quantity
                    else:
                        self.player.add_item(itm)
                else:
                    itm.quantity = diff
                    if self.player.find_item(itm.slug):
                        self.player.find_item(itm.slug).quantity += quantity
                    else:
                        # item deposited
                        new_item = item.Item()
                        new_item.load(itm.slug)
                        new_item.quantity = quantity
                        self.player.add_item(new_item)
                open_dialog(
                    local_session,
                    [
                        T.format(
                            "menu_storage_take_item",
                            {"name": itm.name, "nr": quantity},
                        )
                    ],
                )

            def take_item(itm: Item) -> None:
                self.client.push_state(
                    QuantityMenu(
                        callback=partial(take, itm),
                        max_quantity=itm.quantity,
                        quantity=1,
                        shrink_to_items=True,
                    )
                )

            # confirms release operation
            def disband(itm: Item, quantity: int) -> None:
                self.client.pop_state()
                self.client.pop_state()
                diff = itm.quantity - quantity
                if diff <= 0:
                    self.box.remove(itm)
                else:
                    itm.quantity = diff
                open_dialog(
                    local_session,
                    [
                        T.format(
                            "item_disbanded",
                            {"name": itm.name, "nr": quantity},
                        )
                    ],
                )

            # disband the item
            def disband_item(itm: Item) -> None:
                self.client.push_state(
                    QuantityMenu(
                        callback=partial(disband, itm),
                        max_quantity=itm.quantity,
                        quantity=1,
                        shrink_to_items=True,
                    )
                )

            # continues locker_options
            var_menu = []
            # picking up option
            var_menu.append(
                (
                    "pick",
                    T.translate("pick_up").upper(),
                    partial(take_item, itm),
                )
            )
            # ifs because choice dialog works only with >= 2 elements
            # moving option
            if len(lockers) >= 2:
                var_menu.append(
                    (
                        "move",
                        T.translate("monster_menu_move").upper(),
                        partial(change_locker, itm),
                    )
                )
            elif len(lockers) == 1:
                msg = T.format(
                    "move_to_kennel",
                    {
                        "box": T.translate(lockers[0]),
                    },
                ).upper()
                var_menu.append(
                    ("move", msg, partial(update_locker, itm, lockers[0]))
                )
            # releasing option
            var_menu.append(
                (
                    "disband",
                    T.translate("item_menu_disband").upper(),
                    partial(disband_item, itm),
                ),
            )
            # creates the choice dialog
            open_choice_dialog(
                local_session,
                menu=(var_menu),
                escape_key_exits=True,
            )

        # it prints items inside the screen: image + button
        sum_total = []
        for itm in items:
            sum_total.append(itm.quantity)
            label = T.translate(itm.name).upper() + " x " + str(itm.quantity)
            iid = itm.instance_id.hex
            results = db.lookup(itm.slug, table="item").dict()
            new_image = pygame_menu.BaseImage(
                graphics.transform_resource_filename(results["sprite"]),
                drawing_position=baseimage.POSITION_CENTER,
            )
            new_image.scale(prepare.SCALE, prepare.SCALE)
            menu.add.banner(
                new_image,
                partial(locker_options, iid),
                selection_effect=widgets.HighlightSelection(),
            )
            menu.add.label(label, selectable=True)

        # menu
        menu.set_title(
            T.format(
                "locker_label_long",
                {
                    "box": T.translate(self.box_name).upper(),
                    "qty1": len(self.box),
                    "qty2": sum(sum_total),
                },
            )
        ).center_content()

    def __init__(self, box_name: str) -> None:
        width, height = prepare.SCREEN_SIZE

        background = pygame_menu.BaseImage(
            image_path=graphics.transform_resource_filename(
                "gfx/ui/item/bg_pcstate.png"
            ),
            drawing_position=baseimage.POSITION_CENTER,
        )
        theme = get_theme()
        theme.scrollarea_position = locals.POSITION_EAST
        theme.background_color = background
        theme.widget_alignment = locals.ALIGN_CENTER

        # menu
        theme.title = True
        theme.title_background_color = (197, 232, 234)
        theme.title_font_size = round(0.025 * width)
        theme.title_font_color = (10, 10, 10)
        theme.title_close_button = False
        theme.title_bar_style = widgets.MENUBAR_STYLE_ADAPTIVE

        columns = 3

        self.box_name = box_name
        self.player = local_session.player
        self.box = self.player.item_boxes[self.box_name]

        num_itms = len(self.box)
        # Widgets are like a pygame_menu label, image, etc.
        num_widgets_per_item = 2
        rows = int(num_itms * num_widgets_per_item / columns) + 1
        # Make sure rows are divisible by num_widgets
        while rows % num_widgets_per_item != 0:
            rows += 1

        super().__init__(
            height=height, width=width, columns=columns, rows=rows
        )

        menu_items_map = []
        for item in self.box:
            menu_items_map.append(item)

        self.add_menu_items(self.menu, menu_items_map)
        self.repristinate()

    def repristinate(self) -> None:
        """Repristinate original theme (color, alignment, etc.)"""
        theme = get_theme()
        theme.scrollarea_position = locals.SCROLLAREA_POSITION_NONE
        theme.background_color = PygameMenuState.background_color
        theme.widget_alignment = locals.ALIGN_LEFT
        theme.title = False


class ItemBoxChooseState(PygameMenuState):
    """Menu to choose an item box."""

    def __init__(self) -> None:
        _, height = prepare.SCREEN_SIZE

        super().__init__(height=height)

        self.animation_offset = 0

        menu_items_map = self.get_menu_items_map()
        self.add_menu_items(self.menu, menu_items_map)

    def add_menu_items(
        self,
        menu: pygame_menu.Menu,
        items: Sequence[Tuple[str, MenuGameObj]],
    ) -> None:

        menu.add.vertical_fill()
        for key, callback in items:
            num_itms = local_session.player.item_boxes[key]
            sum_total = []
            for ele in num_itms:
                sum_total.append(ele.quantity)
            label = T.format(
                "locker_label_short",
                {
                    "box": T.translate(key).upper(),
                    "qty1": len(num_itms),
                    "qty2": sum(sum_total),
                },
            )
            menu.add.button(label, callback)
            menu.add.vertical_fill()

        width, height = prepare.SCREEN_SIZE
        widgets_size = menu.get_size(widget=True)
        b_width, b_height = menu.get_scrollarea().get_border_size()
        menu.resize(
            widgets_size[0],
            height - 2 * b_height,
            position=(width + b_width, b_height, False),
        )

    def get_menu_items_map(self) -> Sequence[Tuple[str, MenuGameObj]]:
        """
        Return a list of menu options and callbacks, to be overridden by
        class descendents.
        """
        return []

    def change_state(self, state: str, **kwargs: Any) -> Callable[[], object]:
        return partial(self.client.replace_state, state, **kwargs)

    def update_animation_position(self) -> None:
        self.menu.translate(-self.animation_offset, 0)

    def animate_open(self) -> Animation:
        """
        Animate the menu sliding in.

        Returns:
            Sliding in animation.

        """

        width = self.menu.get_width(border=True)
        self.animation_offset = 0

        ani = self.animate(self, animation_offset=width, duration=0.50)
        ani.update_callback = self.update_animation_position

        return ani

    def animate_close(self) -> Animation:
        """
        Animate the menu sliding out.

        Returns:
            Sliding out animation.

        """
        ani = self.animate(self, animation_offset=0, duration=0.50)
        ani.update_callback = self.update_animation_position

        return ani


class ItemBoxChooseStorageState(ItemBoxChooseState):
    """Menu to choose a box, which you can then take an item from."""

    def get_menu_items_map(self) -> Sequence[Tuple[str, MenuGameObj]]:
        player = local_session.player
        menu_items_map = []
        for box_name, items in player.item_boxes.items():
            if box_name not in HIDDEN_LIST_LOCKER:
                if not items:
                    menu_callback = partial(
                        open_dialog,
                        local_session,
                        [T.translate("menu_storage_empty_locker")],
                    )
                else:
                    menu_callback = self.change_state(
                        "ItemTakeState", box_name=box_name
                    )
                menu_items_map.append((box_name, menu_callback))
        return menu_items_map


class ItemBoxChooseDropOffState(ItemBoxChooseState):
    """Menu to choose a box, which you can then drop off an item into."""

    def get_menu_items_map(self) -> Sequence[Tuple[str, MenuGameObj]]:
        player = local_session.player
        menu_items_map = []
        for box_name, items in player.item_boxes.items():
            if box_name not in HIDDEN_LIST_LOCKER:
                menu_callback = self.change_state(
                    "ItemDropOffState", box_name=box_name
                )
            menu_items_map.append((box_name, menu_callback))
        return menu_items_map


class ItemDropOffState(ItemMenuState):
    """Shows all items in player's bag, puts it into box if selected."""

    def __init__(self, box_name: str) -> None:
        super().__init__()

        self.box_name = box_name

    def on_menu_selection(
        self,
        menu_item: MenuItem[Optional[Item]],
    ) -> None:
        player = local_session.player
        game_object = menu_item.game_object
        assert game_object

        def deposit(itm: Item, quantity: int) -> None:
            self.client.pop_state(self)
            if not quantity:
                return

            # item deposited
            new_item = item.Item()
            new_item.load(itm.slug)
            diff = itm.quantity - quantity

            box = player.item_boxes[self.box_name]

            def find_monster_box(itm: Item, box: list) -> Optional[Item]:
                for ele in box:
                    if ele.slug == itm.slug:
                        return ele

            if box:
                if find_monster_box(itm, box):
                    if diff <= 0:
                        stored = player.find_item_in_storage(
                            find_monster_box(itm, box).instance_id
                        )
                        stored.quantity += quantity
                        player.remove_item(itm)
                    else:
                        stored = player.find_item_in_storage(
                            find_monster_box(itm, box).instance_id
                        )
                        stored.quantity += quantity
                        itm.quantity = diff
                else:
                    if diff <= 0:
                        new_item.quantity = quantity
                        player.item_boxes[self.box_name].append(new_item)
                        player.remove_item(itm)
                    else:
                        itm.quantity = diff
                        new_item.quantity = quantity
                        player.item_boxes[self.box_name].append(new_item)
            else:
                if diff <= 0:
                    new_item.quantity = quantity
                    player.item_boxes[self.box_name].append(new_item)
                    player.remove_item(itm)
                else:
                    itm.quantity = diff
                    new_item.quantity = quantity
                    player.item_boxes[self.box_name].append(new_item)

        self.client.push_state(
            QuantityMenu(
                callback=partial(deposit, game_object),
                max_quantity=game_object.quantity,
                quantity=1,
                shrink_to_items=True,
            )
        )