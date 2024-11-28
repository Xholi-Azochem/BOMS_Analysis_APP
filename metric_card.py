import pandas as pd
import streamlit as st


@st.cache_resource
def create_metric_card(title, value, delta=None):
    """Create a styled metric card."""
    col1, col2 = st.columns([1, 1])
    with col1:
        st.metric(label=title, value=value, delta=delta)
