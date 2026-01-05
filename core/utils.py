"""Utility functions"""

import json


def parse_json_from_llm(content: str) -> dict | None:
    """
    Parse JSON from LLM response.

    Handles:
    - Raw JSON
    - JSON wrapped in markdown code blocks
    - JSON embedded in other text

    Args:
        content: Raw LLM response text

    Returns:
        Parsed dict or None if parsing fails
    """
    content = content.strip()

    # Remove markdown code blocks
    if content.startswith("```"):
        lines = content.split("\n")
        lines = [line for line in lines if not line.startswith("```")]
        content = "\n".join(lines)

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Try to extract JSON object from text
        start = content.find("{")
        end = content.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(content[start:end])
            except json.JSONDecodeError:
                return None
        return None


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
