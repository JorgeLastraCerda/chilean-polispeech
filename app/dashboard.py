# Import required packages
import streamlit as st
import pandas as pd
import sqlite3
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from pathlib import Path

#from wordcloud import WordCloud #not used yet!!!

####### Title configuration

# title and description
st.set_page_config(
    page_title="Chilean PoliSpeech Dashboard",
    page_icon=":bar_chart:",
    layout="wide"
    )
st.subheader("An interactive dashboard to explore speech patterns of Chilean deputies")
st.write("Explore Chilean parliamentary speeches with filters, query search, term analysis, group comparison, and simple time dynamics.")
st.write("This version is still a work in progress, therefore it has some limitations. Actually is only possible to use with the [LVI period of the Deputies Chamber](https://www.bcn.cl/historiapolitica/corporaciones/periodo_detalle?inicio=2022-03-11&fin=2026-03-10&periodo=1990-2026&cam=Diputados#:~:text=Parlamentarios) (2022-2026), but in the future I hope to be able to include more periods, elections and also the Senate, also to add more complex NLP methods.")
st.markdown("Use the sidebar to control the analysis methods and parameters. And the expander directly below to control the the corpus to analyze.")



####### LOADING DATA

APP_DIRECTORY = Path(__file__).parent
PROJECT_ROOT = APP_DIRECTORY.parent
DB_PATH = PROJECT_ROOT / "data" / "chilean_polispeech2.db"
#"notebooks\\intake\\chilean_polispeech.db"

@st.cache_data # this will cache the results of the function, meaning it won't load it again.
def load_data(db_path):
    #db_path = "notebooks\\intake\\chilean_polispeech.db"
    con = sqlite3.connect(db_path)
    
    analysis_df = pd.read_sql_query("""
    SELECT
        s.speech_id,
        s.speech_raw,
        s.speech_clean,
        s.dipid,
        ls.law_title,
        ls.law_number,
        ls.section_key,
        ls.discussion_date,
        dip.name,
        dip.lastname_1,
        dip.lastname_2,
        dip.sex_value,
        p.party_id,
        p.party_name, 
        dist.region                            
    FROM speeches AS s
    JOIN law_sections AS ls
        ON s.law_section_id = ls.law_section_id
    LEFT JOIN deputies AS dip
        ON s.dipid = dip.dipid
    LEFT JOIN militancies AS m
        ON s.dipid = m.dipid
       AND date(m.date_end) >= date('2026-03-10')
    LEFT JOIN parties AS p
        ON m.party_id = p.party_id
    LEFT JOIN districts AS dist
        ON dip.dipid = dist.dipid
""", con)
    con.close()
    # prepare datasets
    analysis_df["discussion_date"] = pd.to_datetime(analysis_df["discussion_date"])

    analysis_df["year"] = analysis_df["discussion_date"].dt.year

    # deputy full name 
    analysis_df["full_name"] = analysis_df["name"] + " " + analysis_df["lastname_1"] + " " + analysis_df["lastname_2"]

    return analysis_df


## load the data
analysis_df = load_data(DB_PATH)

# create the sex_label colum to have a easier understanding
analysis_df["sex_value"] = pd.to_numeric(analysis_df["sex_value"])
sex_map = {0: "Women", 1: "Men"}
analysis_df["sex_label"] = analysis_df["sex_value"].map(sex_map)



####### Sidebar (for methods of analysis) and expander (for corpus slicing) configuration
# Sidebar configuration (to control filters and analysis)
with st.sidebar.header("1. Choose the type of analysis to perform"):
    analysis_type = st.sidebar.selectbox("Choose analysis type",
                    ["Top terms", "TF-IDF comparison", "Raw count comparison", "Relative comparison"])

if analysis_type != "Top terms":
    group_col = st.sidebar.selectbox("Group by",["sex_label", "region", "party_name"])

    # get the unique values of the selected group column to populate the group selection dropdowns
    group_values = sorted(analysis_df[group_col].dropna().astype(str).unique().tolist()) # dropna() to avoid the problem of the Na caused by the wrong transcription (explained in the written report)

    group_a = st.sidebar.selectbox("Group A", group_values)
    group_b = st.sidebar.selectbox("Group B", group_values,
        index=1 if len(group_values) > 1 else 0) # if there is more than one group, we set the default selection of group B to the second option

    if group_a == group_b:
        st.warning("Group A and Group B must be different.")
        st.stop()

# Query configuration
with st.sidebar.header("2. Query configuration"):
    st.sidebar.caption("Search in the selected corpus")
    query_text = st.sidebar.text_input("Query terms", help="Type one or more terms separated by spaces.")
    query_mode = st.sidebar.selectbox(
        "Query mode",
        ["AND", "OR"]
    )


with st.sidebar.header("3. Advanced configuration for analysis"):
    
    # Choose the amount of top terms to show
    top_k = st.sidebar.slider("Number of (top) terms to show", min_value=1, max_value=50, value=10)

    # How many times the term must appear to be included in the analysis
    min_df = st.sidebar.slider("Minimum documents in which terms appear", min_value=1, max_value=10, value=2)

    # N-gram range, by default unigrams (single words)
    ngram_size = st.sidebar.slider("N-Gram size", min_value=1, max_value=3, value=1)

    # word window for the context snippet
    word_window = st.sidebar.slider("Number of words before and after the query term(s) (context window)", min_value=1, max_value=10, value=6)

    text_choice = st.sidebar.selectbox("Text version", ["Cleaned text", "Raw text"])

text_col = "speech_clean" if text_choice == "Cleaned text" else "speech_raw"
# because sklearn need a tuple for the ngram_size
ngram_range = (ngram_size, ngram_size)


#### Expander configuration (to configurate the corpus slice)
# main filters first
# filter by law number
with st.expander("Corpus slice configuration", icon=":material/settings:", expanded=False):
    all_laws = sorted(analysis_df["law_number"].astype(str).unique().tolist())
    selected_laws = st.multiselect("Filter by law number", all_laws)

    selected_sexes = st.multiselect("Filter by sex",analysis_df["sex_label"].dropna().unique().tolist()) # here we add the dropna() to cover the wrongly written lastname of Sagardia and Guzman (more in the report)

    all_deputies = analysis_df["full_name"].dropna().unique().tolist()    
    selected_deputies = st.multiselect("Filter by deputy", all_deputies)

    all_parties = analysis_df["party_name"].dropna().unique().tolist()
    selected_parties = st.multiselect("Filter by party", all_parties)

slice_df = analysis_df.copy()


######## ANALYSIS

## corpus stats, to have a general idea of the size of the corpus we are working with.

def corpus_stats(df, text_col="speech_clean"):
    """
    Print basic statistics about the corpus.
    """
    word_counts = df[text_col].str.len()
    
    total_words = df[text_col].str.split().str.len().sum()

    return {
        "n_speeches": len(df),
        "n_unique_speakers": df["full_name"].nunique(),
        "total_words": int(word_counts.sum()),
        "total_laws": df["law_number"].nunique(),
}


## top terms, this allows to see the most frequent words and n-grams

def top_terms(df, text_col, top_k, min_df, ngram_range):

    vec = CountVectorizer(
        min_df=min_df,
        ngram_range=ngram_range
    )

    X = vec.fit_transform(df[text_col])

    terms = vec.get_feature_names_out()
    counts = X.sum(axis=0).A1

    result = pd.DataFrame({
        "term": terms,
        "count": counts
    })

    return result.sort_values("count", ascending=False).head(top_k)


## tf-idf keywords, this allows to see the most important words and n-grams in a group compared to another group.

def compare_tfidf_groups(df, group_col, group_a, group_b, text_col, top_k, min_df, ngram_range):
    # build the TF-IDF representation of the texts
    vec = TfidfVectorizer( # split into terms, a term is a word or n-gram depending on the ngram_range
        min_df=min_df, 
        ngram_range=ngram_range # this decides if it is n-gram or just a word
    )

    # fit the vectorizer and transform the texts into a matrix
    X = vec.fit_transform(df[text_col])

    # get the actual words (or n-grams) used
    words = vec.get_feature_names_out()

    # turn the matrix into a normal dataframe
    tfidf_df = pd.DataFrame(X.toarray(), columns=words, index=df.index)

    # add the group label to each row
    tfidf_df[group_col] = df[group_col].values

    # average the TF-IDF score of each term inside each group
    grouped = tfidf_df.groupby(group_col).mean()

    result = pd.DataFrame({
        "term": grouped.columns,
        f"{group_a}_tfidf": grouped.loc[group_a].values,
        f"{group_b}_tfidf": grouped.loc[group_b].values
    })

    # positive difference = more characteristic of group_a
    # negative difference = more characteristic of group_b
    result["difference"] = result[f"{group_a}_tfidf"] - result[f"{group_b}_tfidf"]
    # absolute difference helps sort the strongest contrasts
    result["abs_difference"] = result["difference"].abs()

    # here we select the top_k terms with the biggest difference in usage between the two groups
    return result.sort_values("abs_difference", ascending=False).head(top_k)


## raw count comparison: this allows to compare which words have a higher frequency in one group versus the other.


def compare_groups_totalwords(df, group_col, group_a, group_b, text_col, top_k, min_df, ngram_range):
     
    copy = df[df[group_col].isin([group_a, group_b])].copy()
    
    vec = CountVectorizer(
        ngram_range=ngram_range,
        min_df=min_df
    )

    X = vec.fit_transform(copy[text_col])
    words = vec.get_feature_names_out()

    # convert matrix to dataframe
    term_df = pd.DataFrame(X.toarray(), columns=words, index=copy.index)

    # add the group label back
    term_df[group_col] = copy[group_col].values

    # sum counts inside each group
    grouped = term_df.groupby(group_col).sum()

    # create a comparison table
    result = pd.DataFrame({
        "term": grouped.columns,
        f"{group_a}_count": grouped.loc[group_a].values,
        f"{group_b}_count": grouped.loc[group_b].values
    })

    # difference alow us to check which group uses more the term
    result["difference"] = result[f"{group_a}_count"] - result[f"{group_b}_count"]
    result["abs_difference"] = result["difference"].abs()

    return result.sort_values("abs_difference", ascending=False).head(top_k)


## Compare the ratio of term usage between two groups, this allows to see which words are disproportionately more frequent in one group compared to the other.
# This is similar to the raw count comparison, but instead of looking at the absolute difference in counts, we look at the ratio of counts (with smoothing to avoid division by zero). This can help identify terms that are much more characteristic of one group compared to the other, even if their absolute counts are not very high. For example, a term that appears 10 times in group A and 1 time in group B would have a ratio of 10, indicating it is much more characteristic of group A, even though the absolute difference is only 9.

def compare_groups_ratio(df, group_col, group_a, group_b, text_col, top_k, min_df, ngram_range):
    # get many rows first, then sort and cut later
    result = compare_groups_totalwords(
        df=df,
        group_col=group_col,
        group_a=group_a,
        group_b=group_b,
        text_col=text_col,
        top_k=100000,
        min_df=min_df,
        ngram_range=ngram_range
    ).copy()

    # add 1 to avoid division by zero
    result[f"{group_a}_count_smooth"] = result[f"{group_a}_count"] + 1
    result[f"{group_b}_count_smooth"] = result[f"{group_b}_count"] + 1

    # ratios for both directions
    result["ratio_a_over_b"] = result[f"{group_a}_count_smooth"] / result[f"{group_b}_count_smooth"]
    result["ratio_b_over_a"] = result[f"{group_b}_count_smooth"] / result[f"{group_a}_count_smooth"]

    return result.sort_values("ratio_a_over_b", ascending=False).head(top_k)


## Extract context snippet: this allows to show a short snippet of text around the first occurrence of a query term, which can help understand how the term is being used in the speech. The function takes in the full text, a list of query terms, and a word window size, and returns a snippet of text that includes the first found term and some words before and after it for context. If no term is found, it returns an empty string.

def extract_context_snippet(text, query_terms, word_window=7):
    """
    Return a short snippet around the first matching query term.

    Parameters
    ----------
    text : str
        The speech text.
    query_terms : list[str]
        List of terms typed by the user.
    word_window : int
        Number of words to show before and after the match.

    Returns
    -------
    str
        A short snippet with context around the first found term.
        If no term is found, return an empty string.
    """
    if pd.isna(text):
        return ""

    words = str(text).split() # split the text into words by spaces

    # search word by word
    for i, word in enumerate(words): # with enumerate  we get the index and the word itself
        clean_word = word.lower().strip(",.()\"'")

        # if this word matches one of the query terms
        if any(q in clean_word for q in query_terms): # we check if any of the query terms is in the cleaned word
            
            # get the words that are before and after the found term
            start = max(0, i - word_window) # max to avoid going below index 0
            end = min(len(words), i + word_window + 1) # min to avoid going beyond the last index of the words list

            snippet = " ".join(words[start:end])
            return snippet

    return ""



# apply law filter only if the user selected something
if selected_laws:
    slice_df = slice_df[slice_df["law_number"].astype(str).isin(selected_laws)]

# apply sex filter only if selected
if selected_sexes:
    slice_df = slice_df[slice_df["sex_label"].isin(selected_sexes)]

# apply deputy filter by readable full name
if selected_deputies:
    slice_df = slice_df[slice_df["full_name"].isin(selected_deputies)]

# apply party filter by readable party name
if selected_parties:
    slice_df = slice_df[slice_df["party_name"].isin(selected_parties)]

# apply AND / OR query search, only if the user typed something
if query_text.strip():

    # split the query into terms and make them lowercase
    query_terms = query_text.lower().split()

    # select the text column to search in
    text_series = slice_df[text_col]

    # AND mode
    if query_mode == "AND":
        mask = pd.Series(True, index=slice_df.index) # start with all a table of only True with the length of the analysis_df and then filter down
        
        for term in query_terms: # for each term we update the mask to keep only rows that contain this term
            mask = mask & text_series.str.contains(term, regex=False) # we use & ((bitwise) for AND logic , meaning that the row must contain all terms to be True.
            # str.contains() returns False for the rows that not contain the term, in this way we "knock down" the True in the mask to discover only the rows that contain all the terms (goes through the filter for each term)

    # OR mode
    else:
        mask = pd.Series(False, index=slice_df.index) # we start with False this time, to mark with True the rows that contain at last one of the terms
        for term in query_terms:
            mask = mask | text_series.str.contains(term, regex=False) # regex=False so special symbols don't clash in the search

    # we make a copy, to not alter the original. But we select only the ones that are True (with AND all terms present, with OR at least one)
    slice_df = slice_df[mask].copy()

    # in a new column we create the context snippet, going to every row and getting the context surrounding the first term
    slice_df["context_snippet"] = slice_df[text_col].apply(lambda x: extract_context_snippet(x, query_terms, word_window=word_window)) # assumes the text as x and then applies the function

# warning in case the sliced corpus is too small
if len(slice_df) == 0:
    st.warning("No speeches match the current filters/query.")
    st.stop()

# warning if the corpus is smallr than min_df
if len(slice_df) < min_df:
    st.warning("The current corpus slice has fewer speeches than the minimum document frequency required for the analysis.")
    st.stop()

######## (actual) Corpus metrics, so we can have an idea of the size of the corspus we are working with
def corpus_stats(df, text_col="speech_clean"):
    # count words in each speech
    word_counts = df[text_col].str.split().str.len()

    # return a small summary
    return pd.Series({
        "n_speeches": len(df),
        "n_unique_speakers": df["dipid"].nunique(),
        "total_words": word_counts.sum(),
        "avg_words_per_speech": round(word_counts.mean(), 2),
        "total_laws": df["law_number"].nunique()
    })

stats = corpus_stats(slice_df, text_col=text_col)

# create columns to show the corpus metrics
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Speeches", stats["n_speeches"])
col2.metric("Unique speakers", stats["n_unique_speakers"])
col3.metric("Total words", stats["total_words"])
col4.metric("Avg words / speech", stats["avg_words_per_speech"])
col5.metric("Total laws", stats["total_laws"])

##### running the analysis

# initialize the results dataframe
results_df = None 

if analysis_type == "Top terms":
    results_df = top_terms(
        df=slice_df,
        text_col=text_col,
        top_k=top_k,
        min_df=min_df,
        ngram_range=ngram_range
    )

elif analysis_type == "TF-IDF comparison":
    results_df = compare_tfidf_groups(
        df=slice_df,
        group_col=group_col,
        group_a=group_a,
        group_b=group_b,
        text_col=text_col,
        top_k=top_k,
        min_df=min_df,
        ngram_range=ngram_range
    )

elif analysis_type == "Raw count comparison":
    results_df = compare_groups_totalwords(
        df=slice_df,
        group_col=group_col,
        group_a=group_a,
        group_b=group_b,
        text_col=text_col,
        top_k=top_k,
        min_df=min_df,
        ngram_range=ngram_range
    )

elif analysis_type == "Relative comparison":
    results_df = compare_groups_ratio(
        df=slice_df,
        group_col=group_col,
        group_a=group_a,
        group_b=group_b,
        text_col=text_col,
        top_k=top_k,
        min_df=min_df,
        ngram_range=ngram_range
    )

# to show the result table
st.subheader("Analysis result")
st.dataframe(results_df, width="stretch")


#### Charts to visualize the results
st.subheader("Quick chart")

if analysis_type == "Top terms":
    chart_col = "count"
elif analysis_type == "TF-IDF comparison":
    chart_col = "abs_difference"
elif analysis_type == "Raw count comparison":
    chart_col = "abs_difference"
else:
    chart_col = "ratio_a_over_b"

if chart_col in results_df.columns:
    chart_df = results_df.set_index("term")[[chart_col]].head(10)
    st.bar_chart(chart_df)


### Time distribution of query terms
# if there is a query it will show how many times the query term appears in speeches over time, otherwise it will show the number of speeches over time.

st.subheader("Time dynamics")

# If there is a query written, we show how often the first query term appears over time in the already filtered speeches.
if query_text.strip():

    # Split the query into words and take the first one for plotting.
    first_term = query_text.lower().split()[0]

    if query_mode == "AND":
        st.info("The speeches shown here were filtered with AND logic, but the time plot counts only the first query term.")
    
    else:
        st.info("The speeches shown here were filtered with OR logic but the time plot counts only the first query term.")

    # Work on a copy
    temp_df = slice_df.copy()

    # Count how many times the first query term appears in each speech
    temp_df["term_count"] = (temp_df[text_col].str.lower().str.count(first_term))

    # Keep only speeches where the term appears at least once
    temp_df = temp_df[temp_df["term_count"] > 0]

    # Group by year and sum the number of occurrences
    yearly_counts = (temp_df.groupby("year")["term_count"].sum().reset_index().sort_values("year"))

    # Plot only if there is something to show
    if len(yearly_counts) > 0:
        yearly_counts = yearly_counts.set_index("year")
        st.line_chart(yearly_counts)
    else:
        st.info("The first query term does not appear in speeches of the current time selection.")

# If there is no query, show number of speeches per year
else:
    yearly_speeches = (slice_df.groupby("year")["speech_id"].count().reset_index().rename(columns={"speech_id": "n_speeches"}).sort_values("year"))

    # Plot only if there is something to show
    if len(yearly_speeches) > 0:
        yearly_speeches = yearly_speeches.set_index("year")
        st.line_chart(yearly_speeches)


### Speech preview: allow the user to inspect the acutal speeches

st.subheader("Speech preview")

# if there was a context snippet created (which means a query) we show it, otherwise we show the full text
if "context_snippet" in slice_df.columns:
    preview_text_col = "context_snippet"
else:
    preview_text_col = text_col


preview_cols = [
    "full_name",
    "sex_label",
    "law_number",
    preview_text_col,
    "discussion_date",
    "party_name",
    "law_title"
]

# preview_cols = [col for col in preview_cols if col in slice_df.columns]

st.dataframe(slice_df[preview_cols].head(20),use_container_width=True)

st.markdown("This dashboard was created by *Jorge Lastra Cerda* as part of the course [*Introduction to Computer Sciences for Social Scientists*](https://github.com/dgarcia-eu/ICSS).")

