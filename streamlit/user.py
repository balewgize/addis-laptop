"""Public Streamlit app for browsing laptops (view only)."""

import streamlit as st
import pandas as pd

from core.config import setup_logging
from core.database import Database
from core.recommender import LLMRecommender
from core.schemas import RecommendationRequest, SearchFilters
from core.utils import format_source_link, format_phone_link

# Setup
logger = setup_logging()

st.set_page_config(
    page_title="Laptop Finder Ethiopia",
    page_icon="💻",
    layout="wide",
)


@st.cache_resource
def get_database() -> Database:
    return Database()


@st.cache_resource
def get_recommender() -> LLMRecommender:
    return LLMRecommender(get_database())


# Header
st.title("💻 Addis Laptop")
st.caption("Find the best laptop deals from Ethiopian Telegram channels")

# Stats
db = get_database()
stats = db.get_dashboard_stats()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Laptops", stats.total_laptops)
col2.metric("Channels", stats.total_channels)
col3.metric("New This Week", stats.laptops_last_7_days)
# col4.metric("Total Views", stats.total_views)

st.divider()

# Tabs
tab1, tab2, tab3 = st.tabs(
    ["🔍 Browse All", "🎯 Get Recommendations", "📊 Export Data"]
)


# Browse Tab
with tab1:
    st.header("Browse All Laptops")

    # Filters
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        filter_brand = st.text_input("Brand", placeholder="Dell, HP...")
    with col2:
        filter_max_price = st.number_input(
            "Max Price", min_value=0, value=0, step=10000
        )
    with col3:
        filter_min_ram = st.selectbox("Min RAM (GB)", [None, 8, 16, 32])
    with col4:
        filter_min_storage = st.selectbox("Min Storage (GB)", [None, 256, 512, 1000])

    # Build filters
    filters = SearchFilters(
        brand=filter_brand if filter_brand else None,
        max_price=filter_max_price if filter_max_price > 0 else None,
        min_ram=filter_min_ram,
        min_storage=filter_min_storage,
        posted_within_days=90,
    )

    # Search
    has_filters = any(
        [filter_brand, filter_max_price > 0, filter_min_ram, filter_min_storage]
    )
    if has_filters:
        laptops = db.search_laptops(filters)
    else:
        laptops = db.get_laptops(limit=100)

    st.caption(f"Showing {len(laptops)} laptops")

    if not laptops:
        st.info("No laptops found. Try adjusting your filters.")
    else:
        for laptop in laptops:
            price_str = (
                f"ETB {laptop.price_etb:,.0f}" if laptop.price_etb else "Call for price"
            )

            with st.expander(f"**{laptop.brand}** {laptop.model or ''} — {price_str}"):
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**Specifications**")
                    st.write(f"🔲 CPU: {laptop.cpu or 'N/A'}")
                    st.write(f"🧠 RAM: {laptop.ram_gb or 'N/A'} GB")
                    storage_info = f"{laptop.storage_gb or 'N/A'} GB"
                    if laptop.storage_type:
                        storage_info += f" {laptop.storage_type}"
                    st.write(f"💾 Storage: {storage_info}")
                    st.write(f"🖥️ Screen: {laptop.screen_size or 'N/A'} inches")
                    st.write(f"🎮 GPU: {laptop.gpu or 'N/A'}")

                with col2:
                    st.markdown("**Details**")
                    st.write(f"🔋 Battery: {laptop.battery_life or 'N/A'}")
                    st.write(f"📦 Condition: {laptop.condition or 'N/A'}")
                    if laptop.contact:
                        display, tel_link = format_phone_link(laptop.contact)
                        st.write(f"📞 Contact: [{display}]({tel_link})")
                    else:
                        st.write("📞 Contact: N/A")
                    st.write(f"📅 Posted: {laptop.posted_at.strftime('%Y-%m-%d')}")
                    channel_name, source_link = format_source_link(
                        laptop.channel, laptop.message_id
                    )
                    st.markdown(f"📢 Channel: [@{channel_name}]({laptop.channel})")
                    st.markdown(f"🔗 [View Original Post]({source_link})")

                if st.checkbox("📝 Show Original Message", key=f"raw_{laptop.id}"):
                    st.code(laptop.raw_text)

                # Track view
                db.increment_view_count(laptop.id)

# Recommendations Tab
with tab2:
    st.header("Get Personalized Recommendations")
    st.caption(
        "Our AI analyzes laptops and gives you the best options with pros and cons"
    )

    col1, col2 = st.columns(2)

    with col1:
        budget = st.number_input(
            "💰 Maximum Budget (ETB)",
            min_value=0,
            value=100000,
            step=10000,
            help="Enter 0 for no budget limit",
        )

        use_case = st.selectbox(
            "🎯 What will you use it for?",
            options=[
                ("General Use", "general"),
                ("Programming / Coding", "programming"),
                ("Gaming", "gaming"),
                ("Office / Business", "office"),
                ("Student / School", "student"),
                ("Video Editing", "video"),
            ],
            format_func=lambda x: x[0],
        )

    with col2:
        brand_pref = st.selectbox(
            "🏷️ Preferred Brand (optional)",
            options=[
                ("Any Brand", "any"),
                ("Dell", "dell"),
                ("HP", "hp"),
                ("Leonovo", "lenovo"),
                ("Asus", "asus"),
                ("Acer", "acer"),
            ],
            format_func=lambda x: x[0],
        )

        priorities = st.multiselect(
            "⭐ Priorities (optional)",
            options=[
                "Battery Life",
                "Lightweight",
                "Powerful",
                "Value for Money",
                "Build Quality",
            ],
        )

    if st.button("🔍 Get Recommendations", type="primary", use_container_width=True):
        with st.spinner("🤖 AI is analyzing laptops..."):
            request = RecommendationRequest(
                budget_max=budget if budget > 0 else None,
                use_case=use_case[1],
                brand_preference=brand_pref[1] if brand_pref[1] != "any" else None,
                priorities=[p.lower() for p in priorities],
            )

            recommender = get_recommender()
            response = recommender.recommend(request)

        if not response.recommendations:
            st.warning(
                "😔 No laptops match your criteria. Try adjusting your budget or requirements."
            )
        else:
            st.success(f"Found {len(response.recommendations)} great options!")

            # Summary
            st.markdown(f"### 📋 {response.query_summary}")
            if response.market_insight:
                st.info(f"💡 {response.market_insight}")

            st.divider()

            # Recommendations
            for rec in response.recommendations:
                laptop = rec.laptop
                price_str = (
                    f"ETB {laptop.price_etb:,.0f}"
                    if laptop.price_etb
                    else "📞 Call for price"
                )

                with st.container():
                    st.markdown(f"## #{rec.rank} {laptop.brand} {laptop.model or ''}")

                    cols = st.columns([2, 1])

                    with cols[0]:
                        # Specs
                        specs_md = ""
                        if laptop.cpu:
                            specs_md += f"- 🔲 **CPU:** {laptop.cpu}\n"
                        if laptop.ram_gb:
                            specs_md += f"- 🧠 **RAM:** {laptop.ram_gb} GB\n"
                        if laptop.storage_gb:
                            storage = f"{laptop.storage_gb} GB"
                            if laptop.storage_type:
                                storage += f" {laptop.storage_type}"
                            specs_md += f"- 💾 **Storage:** {storage}\n"
                        if laptop.screen_size:
                            specs_md += f'- 🖥️ **Screen:** {laptop.screen_size}"\n'
                        if laptop.gpu:
                            specs_md += f"- 🎮 **GPU:** {laptop.gpu}\n"
                        if laptop.battery_life:
                            specs_md += f"- 🔋 **Battery:** {laptop.battery_life}\n"

                        st.markdown(specs_md)

                    with cols[1]:
                        st.metric("Price", price_str)
                        if laptop.contact:
                            st.code(laptop.contact, language=None)
                        channel_name = laptop.channel.split("/")[-1]
                        st.caption(f"📢 From @{channel_name}")

                    # Pros & Cons
                    col_pro, col_con = st.columns(2)

                    with col_pro:
                        st.markdown("#### ✅ Pros")
                        for pro in rec.pros:
                            st.markdown(f"- {pro}")

                    with col_con:
                        st.markdown("#### ⚠️ Cons")
                        for con in rec.cons:
                            st.markdown(f"- {con}")

                    # Verdict
                    st.success(f"👤 **{rec.best_for}**")

                    # Track view
                    db.increment_view_count(laptop.id)

                st.divider()


# Export Tab
with tab3:
    st.header("Export Data")

    laptops = db.get_laptops(limit=1000)

    if not laptops:
        st.info("No data to export.")
    else:
        df = pd.DataFrame(
            [
                {
                    "Brand": l.brand,
                    "Model": l.model,
                    "CPU": l.cpu,
                    "RAM (GB)": l.ram_gb,
                    "Storage (GB)": l.storage_gb,
                    "Storage Type": l.storage_type,
                    "Screen Size": l.screen_size,
                    "GPU": l.gpu,
                    "Price (ETB)": l.price_etb,
                    "Condition": l.condition,
                    "Battery": l.battery_life,
                    "Contact": l.contact,
                    "Posted": l.posted_at.strftime("%Y-%m-%d"),
                    "Channel": l.channel.split("/")[-1],
                }
                for l in laptops
            ]
        )

        st.dataframe(df, use_container_width=True, hide_index=True)

        col1, col2 = st.columns(2)

        with col1:
            csv = df.to_csv(index=False)
            st.download_button(
                "📥 Download CSV",
                csv,
                "laptops.csv",
                "text/csv",
                use_container_width=True,
            )

        with col2:
            json_data = df.to_json(orient="records", indent=2)
            st.download_button(
                "📥 Download JSON",
                json_data,
                "laptops.json",
                "application/json",
                use_container_width=True,
            )


# Footer
st.divider()
st.caption(
    "💡 Data is collected from public Telegram channels. Prices may change. Contact sellers directly."
)
