"""Utility functions"""


def format_source_link(channel: str, message_id: int) -> tuple[str, str]:
    """
    Generate source link and channel name from channel URL.

    Returns:
        (channel_name, full_link)
    """
    # Handle various channel URL formats
    channel = channel.rstrip("/")

    if channel.startswith("https://t.me/"):
        channel_name = channel.replace("https://t.me/", "")
    elif channel.startswith("t.me/"):
        channel_name = channel.replace("t.me/", "")
    elif channel.startswith("@"):
        channel_name = channel[1:]
    else:
        channel_name = channel.split("/")[-1]

    full_link = f"https://t.me/{channel_name}/{message_id}"

    return channel_name, full_link


def format_phone_link(phone: str) -> tuple[str, str]:
    """
    Format phone number for display and tel: link.

    Returns:
        (display_number, tel_link)
    """
    # Clean the number
    clean = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

    # TODO: handle more than one contacts available

    # Convert to international format for Ethiopia
    if clean.startswith("0") and len(clean) == 10:
        international = "+251" + clean[1:]
    elif clean.startswith("251"):
        international = "+" + clean
    elif clean.startswith("+"):
        international = clean
    else:
        international = clean  # Unknown format, use as-is

    return phone, f"tel:{international}"
