"""Keyboard builders for Telegram bot."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .pagination import PaginationState


def build_pagination_keyboard(
    state: PaginationState, prefix: str
) -> InlineKeyboardMarkup:
    """Build pagination keyboard with prev/next buttons."""
    buttons = []

    # Previous
    if state.has_prev:
        buttons.append(InlineKeyboardButton("◀️ Prev", callback_data=f"{prefix}:prev"))
    else:
        buttons.append(InlineKeyboardButton("◀️", callback_data="noop"))

    # Page indicator
    buttons.append(
        InlineKeyboardButton(f"{state.page}/{state.total_pages}", callback_data="noop")
    )

    # Next
    if state.has_next:
        buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"{prefix}:next"))
    else:
        buttons.append(InlineKeyboardButton("▶️", callback_data="noop"))

    return InlineKeyboardMarkup([buttons])
