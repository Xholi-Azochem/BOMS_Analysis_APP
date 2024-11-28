import pandas as pd
import streamlit as st
from calculate_requirements import calculate_requirements,calculate_custom_requirements
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
#Modify the search_and_requirements_page function to include more error logging
@st.cache_resource
def search_and_requirements_page(analysis_results, bom_a_l, bom_m_z, dispensing_data, raw_materials):
    """Render the Search & Requirements page."""
    st.title("Search & Requirements")

    # User inputs for product search
    product = st.text_input("Enter Product Code")
    quantity_desired = st.number_input("Enter Desired Quantity", min_value=0, step=1)

    if product and quantity_desired > 0:
        st.subheader(f"Requirements for Producing {quantity_desired} Units of {product}")

        # Calculate requirements with custom method
        try:
            # Log input parameters
            logger.info(f"Calculating requirements for Product: {product}, Quantity: {quantity_desired}")
            
            # Use custom requirements calculation
            requirements = calculate_custom_requirements(
                product, 
                quantity_desired, 
                bom_a_l, 
                bom_m_z, 
                analysis_results
            )

            # Fallback to original method if custom method fails
            if requirements.empty:
                logger.warning("Custom requirements calculation failed. Falling back to original method.")
                requirements = calculate_requirements(
                    product, 
                    quantity_desired, 
                    analysis_results, 
                    dispensing_data, 
                    raw_materials
                )

            if not requirements.empty:
                st.dataframe(requirements)
            else:
                st.warning(f"No requirements found for product: {product}")
        except Exception as e:
            # Log the full error
            logger.error(f"Error calculating requirements: {e}", exc_info=True)
            st.error(f"Error calculating requirements: {e}")
