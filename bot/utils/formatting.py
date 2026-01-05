"""Message formatting utilities."""

from core.schemas import LaptopDB, RecommendationResponse
from core.utils import format_source_link, format_phone_link


def format_laptop_short(laptop: LaptopDB, index: int) -> str:
    """Format laptop for list view."""
    price_str = f"{laptop.price_etb:,.0f} ETB" if laptop.price_etb else "Call"

    specs = []
    if laptop.ram_gb:
        specs.append(f"{laptop.ram_gb}GB")
    if laptop.storage_gb:
        if laptop.storage_gb >= 1000:
            specs.append(f"{laptop.storage_gb // 1000}TB")
        else:
            specs.append(f"{laptop.storage_gb}GB")
    if laptop.screen_size:
        specs.append(f'{laptop.screen_size}"')
    specs_str = " • ".join(specs)

    model = (laptop.model or "")[:20]
    channel, source_link = format_source_link(laptop.channel, laptop.message_id)

    line = f"{index}. [{laptop.brand} {model}]({source_link})\n"
    line += f"   💰 {price_str}"
    if specs_str:
        line += f" | {specs_str}"

    return line


def format_recommendations(response: RecommendationResponse) -> str:
    """Format recommendation response for Telegram."""
    message = f"📋 **{response.query_summary}**\n\n"

    if response.market_insight:
        message += f"💡 _{response.market_insight}_\n\n"

    message += "━━━━━━━━━━━━━━━━━━━━\n\n"

    for rec in response.recommendations:
        laptop = rec.laptop
        price_str = (
            f"{laptop.price_etb:,.0f} ETB" if laptop.price_etb else "Call for price"
        )

        # Header
        message += f"**#{rec.rank} {laptop.brand} {laptop.model or ''}**\n"
        message += f"💰 {price_str}\n\n"

        # Specs
        specs = []
        if laptop.cpu:
            specs.append(f"🔲 {laptop.cpu}")
        if laptop.ram_gb:
            specs.append(f"🧠 {laptop.ram_gb}GB RAM")
        if laptop.storage_gb:
            storage = f"💾 {laptop.storage_gb}GB"
            if laptop.storage_type:
                storage += f" {laptop.storage_type}"
            specs.append(storage)
        if laptop.screen_size:
            specs.append(f'🖥 {laptop.screen_size}"')
        if laptop.gpu:
            specs.append(f"🎮 {laptop.gpu}")
        if laptop.battery_life:
            specs.append(f"🔋 {laptop.battery_life}")

        if specs:
            message += "\n".join(specs) + "\n\n"

        # Pros & Cons
        message += "✅ **Pros:**\n"
        for pro in rec.pros[:3]:
            message += f"  • {pro}\n"

        message += "\n⚠️ **Cons:**\n"
        for con in rec.cons[:2]:
            message += f"  • {con}\n"

        # Verdict
        message += f"\n👤 **{rec.best_for}**\n"

        # Contact (clickable phone)
        if laptop.contact:
            display, tel_link = format_phone_link(laptop.contact)
            message += f"\n📞 [{display}]({tel_link})\n"

        # Source link (clickable)
        channel_name, source_link = format_source_link(
            laptop.channel, laptop.message_id
        )
        message += f"\nSource: [@{channel_name}]({source_link})\n"

        message += "\n━━━━━━━━━━━━━━━━━━━━\n\n"

    message += (
        "⚠️ **Disclaimer:** AI recommendations are a starting point, always "
        "verify specs, read reviews, and compare prices before purchasing.\n\n"
    )
    message += "Use /recommend to search again!"

    return message
