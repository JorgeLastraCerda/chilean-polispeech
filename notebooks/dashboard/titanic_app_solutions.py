# Import required packages
import streamlit as st
import seaborn as sns
import pandas as pd

# Load Titanic dataset
df = sns.load_dataset("titanic")

# Task a)
st.title("🚢 Titanic Dashboard")

st.subheader("First look into the data")
st.write(df.head(5))

# Task a + b)
sex = st.selectbox("Select passenger sex", df["sex"].unique())
filtered_df = df[df["sex"] == sex]

st.subheader(f"Age Distribution for {sex.capitalize()}s")
st.bar_chart(filtered_df["age"].value_counts())

# Task c + d)
st.subheader("Guess fate of passengers")
passenger = df.sample(n=1).iloc[0]
st.write(f"👤 Passenger: Age {passenger['age']}, Class {passenger['class']}, Sex {passenger['sex']}")

if "count" not in st.session_state:
    st.session_state.count = 0
if "annotations" not in st.session_state:
    st.session_state.annotations = []

# Task c, d + e
def classify(label):
    st.session_state.annotations.append({
        "age": passenger["age"],
        "class": passenger["class"],
        "sex": passenger["sex"],
        "label": label,
        "true_label": "survived" if passenger["survived"] == 1 else "not survived"})
    st.session_state.count += 1

col1, col2 = st.columns(2)
with col1:
    st.button("🟩 Survived", on_click=classify, args=("survived",))
with col2:
    st.button("🟥 Did not survive", on_click=classify, args=("not survived",))

st.write(f"Total annotations: {st.session_state.count}")

# Task f
if st.session_state.annotations:
    st.subheader("Annotation Accuracy")
    annotations_df = pd.DataFrame(st.session_state.annotations)
    annotations_df["correct"] = annotations_df["label"] == annotations_df["true_label"]
    accuracy = annotations_df["correct"].mean()
    st.write(f"✅ Accuracy: **{accuracy:.2%}**")
