"""Streamlit UI for Telegram Laptop Scraper."""

import streamlit as st
import httpx
import pandas as pd
from datetime import datetime

# API base URL
API_URL = "http://localhost:8000"

st.set_page_config(
    page_title="Laptop Scraper",
    page_icon="💻",
    layout="wide",
)

st.title("💻 Telegram Laptop Scraper")
st.caption("Find the best laptop deals from Ethiopian Telegram channels")


def api_request(method: str, endpoint: str, **kwargs):
    """Make API request with error handling."""
    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.request(method, f"{API_URL}{endpoint}", **kwargs)
            response.raise_for_status()
            return response.json()
    except httpx.ConnectError:
        st.error(
            "❌ Cannot connect to API. Make sure the server is running: `uvicorn telegram_laptop_scraper.api:app`"
        )
        return None
    except httpx.HTTPStatusError as e:
        st.error(f"❌ API Error: {e.response.status_code}")
        return None


# Sidebar
with st.sidebar:
    st.header("⚙️ Actions")

    # Sync button
    st.subheader("Sync Channels")
    channels_input = st.text_area(
        "Channels (one per line)",
        placeholder="https://t.me/Linktechcomputers",
        height=100,
    )
    sync_limit = st.slider("Messages per channel", 10, 200, 50)

    if st.button("🔄 Sync Now", type="primary"):
        channels = [c.strip() for c in channels_input.split("\n") if c.strip()]

        with st.spinner("Syncing channels..."):
            result = api_request(
                "POST",
                "/sync",
                params={"limit": sync_limit},
                json=channels if channels else None,
            )

        if result:
            for r in result:
                st.success(
                    f"**{r['channel']}**: {r['laptops_extracted']} laptops extracted"
                )

    st.divider()

    # Stats
    st.subheader("📊 Stats")
    stats = api_request("GET", "/stats")
    if stats:
        st.metric("Total Laptops", stats["total_laptops"])


# Main content tabs
tab1, tab2, tab3 = st.tabs(["🔍 Browse", "🎯 Recommend", "📋 Raw Data"])


# Browse tab
with tab1:
    st.header("Browse Laptops")

    # Filters
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        brand_filter = st.text_input("Brand", placeholder="Dell, Asus...")
    with col2:
        max_price = st.number_input("Max Price (ETB)", min_value=0, value=0, step=10000)
    with col3:
        min_ram = st.selectbox("Min RAM (GB)", [None, 8, 16, 32], index=0)
    with col4:
        min_storage = st.selectbox("Min Storage (GB)", [None, 256, 512, 1000], index=0)

    # Build search params
    params = {}
    if brand_filter:
        params["brand"] = brand_filter
    if max_price > 0:
        params["max_price"] = max_price
    if min_ram:
        params["min_ram"] = min_ram
    if min_storage:
        params["min_storage"] = min_storage

    # Fetch and display
    if params:
        laptops = api_request("GET", "/laptops/search/", params=params)
    else:
        laptops = api_request("GET", "/laptops", params={"limit": 100})

    if laptops:
        if not laptops:
            st.info("No laptops found. Try syncing some channels!")
        else:
            st.caption(f"Showing {len(laptops)} laptops")

            for laptop in laptops:
                with st.expander(
                    f"**{laptop['brand']}** {laptop['model'] or ''} - "
                    f"{'ETB {:,.0f}'.format(laptop['price_etb']) if laptop['price_etb'] else 'Price N/A'}"
                ):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown("**Specifications**")
                        st.write(f"🔲 CPU: {laptop['cpu'] or 'N/A'}")
                        st.write(f"🧠 RAM: {laptop['ram_gb'] or 'N/A'} GB")
                        st.write(
                            f"💾 Storage: {laptop['storage_gb'] or 'N/A'} GB {laptop['storage_type'] or ''}"
                        )
                        st.write(f"🖥️ Screen: {laptop['screen_size'] or 'N/A'} inches")
                        st.write(f"🎮 GPU: {laptop['gpu'] or 'N/A'}")

                    with col2:
                        st.markdown("**Details**")
                        st.write(f"📦 Condition: {laptop['condition'] or 'N/A'}")
                        st.write(f"📞 Contact: {laptop['contact'] or 'N/A'}")
                        st.write(f"📅 Posted: {laptop['posted_at'][:10]}")
                        st.write(f"📢 Channel: {laptop['channel']}")

                    st.markdown("**Original Message**")
                    st.code(
                        laptop["raw_text"][:500] + "..."
                        if len(laptop["raw_text"]) > 500
                        else laptop["raw_text"]
                    )


# Recommend tab
with tab2:
    st.header("Get Recommendations")

    col1, col2 = st.columns(2)

    with col1:
        budget = st.number_input(
            "Budget (ETB)",
            min_value=0,
            value=100000,
            step=10000,
            help="Maximum price you're willing to pay",
        )

        use_case = st.selectbox(
            "Use Case",
            [None, "programming", "gaming", "office", "general"],
            help="What will you use the laptop for?",
        )

    with col2:
        rec_brand = st.text_input("Preferred Brand (optional)")
        rec_min_ram = st.selectbox("Minimum RAM (GB)", [None, 8, 16, 32], key="rec_ram")
        rec_min_storage = st.selectbox(
            "Minimum Storage (GB)", [None, 256, 512, 1000], key="rec_storage"
        )

    if st.button("🎯 Get Recommendations", type="primary"):
        query = {
            "budget_max": budget if budget > 0 else None,
            "use_case": use_case,
            "brand": rec_brand if rec_brand else None,
            "min_ram": rec_min_ram,
            "min_storage": rec_min_storage,
        }

        with st.spinner("Finding best matches..."):
            recommendations = api_request("POST", "/recommend", json=query)

        if recommendations:
            if not recommendations:
                st.warning(
                    "No laptops match your criteria. Try adjusting your filters."
                )
            else:
                st.success(f"Found {len(recommendations)} recommendations!")

                for i, laptop in enumerate(recommendations, 1):
                    st.markdown(f"### #{i} {laptop['brand']} {laptop['model'] or ''}")

                    cols = st.columns([2, 1])

                    with cols[0]:
                        specs = []
                        if laptop["cpu"]:
                            specs.append(f"🔲 {laptop['cpu']}")
                        if laptop["ram_gb"]:
                            specs.append(f"🧠 {laptop['ram_gb']}GB RAM")
                        if laptop["storage_gb"]:
                            specs.append(
                                f"💾 {laptop['storage_gb']}GB {laptop['storage_type'] or 'Storage'}"
                            )

                        st.write(" | ".join(specs))

                    with cols[1]:
                        if laptop["price_etb"]:
                            st.metric("Price", f"ETB {laptop['price_etb']:,.0f}")
                        if laptop["contact"]:
                            st.write(f"📞 {laptop['contact']}")

                    st.divider()


# Raw Data tab
with tab3:
    st.header("Raw Data")

    laptops = api_request("GET", "/laptops", params={"limit": 500})

    if laptops:
        # Convert to DataFrame
        df = pd.DataFrame(laptops)

        # Select columns to display
        display_cols = [
            "id",
            "brand",
            "model",
            "cpu",
            "ram_gb",
            "storage_gb",
            "price_etb",
            "condition",
            "contact",
            "posted_at",
            "channel",
        ]
        display_cols = [c for c in display_cols if c in df.columns]

        st.dataframe(
            df[display_cols],
            use_container_width=True,
            hide_index=True,
        )

        # Download button
        csv = df.to_csv(index=False)
        st.download_button(
            "📥 Download CSV",
            csv,
            "laptops.csv",
            "text/csv",
        )
