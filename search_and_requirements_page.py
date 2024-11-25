import pandas as pd
import streamlit as st
from calculate_requirements import calculate_requirements

def search_and_requirements_page(analysis_results, dispensing_data, raw_materials):
    """
    Search page to analyze product requirements and stock availability.
    """
    st.title("Search & Requirements")

    # User inputs
    product = st.text_input("Enter Product Code")
    quantity_desired = st.number_input("Desired Quantity", min_value=0, step=1)

    if product and quantity_desired > 0:
        st.subheader(f"Requirements for Producing {quantity_desired} Units of {product}")

        # Calculate requirements
        try:
            requirements = calculate_requirements(
                product, quantity_desired, analysis_results, dispensing_data, raw_materials
            )

            # Display requirements
            if not requirements.empty:
                st.table(requirements)
            else:
                st.warning(f"No requirements found for product: {product}")
        except Exception as e:
            st.error(f"Error calculating requirements: {e}")

