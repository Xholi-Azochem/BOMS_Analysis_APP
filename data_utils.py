import pandas as pd

def clean_data(df, numeric_columns):
    """Clean and convert numeric columns."""
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

def optimize_memory(df):
    """Optimize memory usage of a DataFrame."""
    for col in df.select_dtypes(include=["float64", "int64"]).columns:
        df[col] = pd.to_numeric(df[col], downcast="float" if df[col].dtype == "float64" else "integer")
    return df
