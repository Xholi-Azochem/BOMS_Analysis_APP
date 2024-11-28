import pandas as pd
import streamlit as st


@st.cache_resource
def clean_data(df, numeric_columns):
    """Clean and convert numeric columns."""
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

# Existing memory optimization function, enhance with more techniques
@st.cache_resource
def optimize_memory(df):
    # Convert object columns to categorical where appropriate
    for col in df.select_dtypes(include=['object']).columns:
        if df[col].nunique() / len(df) < 0.5:  # Only convert if low cardinality
            df[col] = df[col].astype('category')
    
    # Downcast numeric columns
    float_cols = df.select_dtypes(include=['float64']).columns
    int_cols = df.select_dtypes(include=['int64']).columns
    
    df[float_cols] = df[float_cols].apply(pd.to_numeric, downcast='float')
    df[int_cols] = df[int_cols].apply(pd.to_numeric, downcast='integer')
    
    return df
