# Import required packages
import streamlit as st
import pandas as pd
import sqlite3

# Load dataset, this one  is built in
db_path = "notebooks\intake\chilean_polispeech.db"

# configurate the page
st.set_page_config(page_title="Chilean PoliSpeech Dashboard", layout="wide")

# Create a connection to the SQLite database
conn = sqlite3.connect(db_path)
# Load the dataset into a pandas DataFrame
df = pd.read_sql_query("SELECT * FROM deputies", conn)
conn.close()

# learn how and when to use cache date
# Caching stores the results of slow function calls, so they only need to run once. This makes your app much faster and helps with persisting objects across reruns. Cached values are available to all users of your app. If you need to save results that should only be accessible within a session, use Session State instead.
# @st.cache_data

st.title("Chilean PoliSpeech Dashboard")



