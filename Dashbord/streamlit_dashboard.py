import os
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# 1. Page Setup
st.set_page_config(page_title="Uber Trips Dashboard", layout="wide")
st.title("Uber Trips Analytics Dashboard")


# 2. Load and Clean the CSV File (Cached so filters stay fast)
@st.cache_data
def load_data():
    # Look for trips_reviewed.csv in the same folder as this script first
    script_folder = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_folder, "trips_reviewed.csv")

    if not os.path.exists(file_path):
        file_path = "trips_reviewed.csv"

    df = pd.read_csv(file_path)

    # Remove exact duplicate rows
    df = df.drop_duplicates()

    # Clean column names
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

    # Clean extra spaces from text columns
    df["city"] = df["city"].astype(str).str.strip()
    df["status"] = df["status"].astype(str).str.strip()
    df["payment_method"] = df["payment_method"].astype(str).str.strip()

    # Convert date/time columns
    df["pickup_time"] = pd.to_datetime(df["pickup_time"], errors="coerce")
    df["drop_time"] = pd.to_datetime(df["drop_time"], errors="coerce")

    # Create useful time columns
    df["trip_duration_min"] = (df["drop_time"] - df["pickup_time"]).dt.total_seconds() / 60
    df["pickup_hour"] = df["pickup_time"].dt.hour
    df["pickup_day"] = df["pickup_time"].dt.day_name()

    # Create basic sanity check flags
    df["zero_distance_flag"] = df["distance_km"] == 0
    df["negative_distance_flag"] = df["distance_km"] < 0
    df["invalid_duration_flag"] = df["trip_duration_min"] <= 0
    df["high_fare_flag"] = df["fare_amount"] > 40

    return df


# Load data safely (show a friendly error if the CSV is missing)
try:
    df = load_data()
except FileNotFoundError:
    st.error("Could not find `trips_reviewed.csv`. Please put it in the same folder as this Python file.")
    st.stop()

# 3. Sidebar Filters
st.sidebar.header("Filters")

# Choose between all trips or only clean completed trips
view_option = st.sidebar.radio(
    "Choose Data View",
    ["All Trips", "Clean Completed Trips Only"]
)

if view_option == "Clean Completed Trips Only":
    data = df[
        (df["status"] == "Completed")
        & (df["distance_km"] > 0)
        & (df["trip_duration_min"] > 0)
        & (df["fare_amount"] >= 0)
    ].copy()
    if "flag_recorded_distance_less_than_straight_line_plus_10m" in data.columns:
        data = data[data["flag_recorded_distance_less_than_straight_line_plus_10m"] == False]
else:
    data = df.copy()

# Filter by City
cities = sorted(df["city"].dropna().unique().tolist())
selected_cities = st.sidebar.multiselect("Select City", cities, default=cities)

# Filter by Status (only shown when viewing All Trips so switching views never errors)
if view_option == "All Trips":
    statuses = sorted(df["status"].dropna().unique().tolist())
    selected_statuses = st.sidebar.multiselect("Select Status", statuses, default=statuses)
else:
    selected_statuses = ["Completed"]
    st.sidebar.info("Status is locked to 'Completed' in Clean Completed Trips mode.")

# Filter by Payment Method
payments = sorted(df["payment_method"].dropna().unique().tolist())
selected_payments = st.sidebar.multiselect("Select Payment Method", payments, default=payments)

# Apply all sidebar filters
filtered_df = data[
    (data["city"].isin(selected_cities))
    & (data["status"].isin(selected_statuses))
    & (data["payment_method"].isin(selected_payments))
].copy()

# Stop cleanly if no rows match
if len(filtered_df) == 0:
    st.warning("No trips match your selected filters. Please select at least one option.")
    st.stop()

# Separate Completed trips for revenue metrics
completed_df = filtered_df[filtered_df["status"] == "Completed"]

# 4. Key Metrics (Top Row)
total_trips = len(filtered_df)
completed_count = len(completed_df)
total_revenue = completed_df["fare_amount"].sum() if completed_count > 0 else 0.0
avg_fare = completed_df["fare_amount"].mean() if completed_count > 0 else 0.0
avg_distance = completed_df["distance_km"].mean() if completed_count > 0 else 0.0

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Trips", f"{total_trips:,}")
col2.metric("Completed Trips", f"{completed_count:,}")
col3.metric("Total Revenue", f"${total_revenue:,.2f}")
col4.metric("Average Fare", f"${avg_fare:.2f}")
col5.metric("Average Distance", f"{avg_distance:.2f} km")

# 5. Dashboard Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Overview",
    "City & Drivers",
    "Time Trends",
    "Fare vs Distance",
    "Data Quality & Export"
])

# --- TAB 1: Overview ---
with tab1:
    st.subheader("Trips by Status and Payment Method")

    left_col, right_col = st.columns(2)

    with left_col:
        status_counts = filtered_df["status"].value_counts()
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(status_counts.index, status_counts.values, color="steelblue")
        ax.set_title("Trips by Status")
        ax.set_ylabel("Number of Trips")
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    with right_col:
        payment_counts = filtered_df["payment_method"].value_counts()
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(payment_counts.index, payment_counts.values, color="teal")
        ax.set_title("Trips by Payment Method")
        ax.set_ylabel("Number of Trips")
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    st.write("Status vs. Payment Method Table")
    status_payment_table = pd.crosstab(
        filtered_df["status"],
        filtered_df["payment_method"],
        margins=True
    )
    st.dataframe(status_payment_table)

# --- TAB 2: City & Drivers ---
with tab2:
    st.subheader("City Performance (Completed Trips)")

    if completed_count == 0:
        st.info("No Completed trips in the current filter.")
    else:
        city_summary = completed_df.groupby("city").agg(
            completed_trips=("trip_id", "count"),
            total_revenue=("fare_amount", "sum"),
            avg_fare=("fare_amount", "mean"),
            avg_distance_km=("distance_km", "mean")
        ).sort_values("total_revenue", ascending=False).round(2)

        left_col, right_col = st.columns(2)

        with left_col:
            fig, ax = plt.subplots(figsize=(6, 4))
            ax.bar(city_summary.index, city_summary["total_revenue"], color="steelblue")
            ax.set_title("Total Revenue by City ($)")
            ax.set_ylabel("Total Revenue ($)")
            plt.xticks(rotation=25)
            plt.tight_layout()
            st.pyplot(fig)
            plt.close(fig)

        with right_col:
            fig, ax = plt.subplots(figsize=(6, 4))
            ax.bar(city_summary.index, city_summary["avg_fare"], color="seagreen")
            ax.set_title("Average Fare by City ($)")
            ax.set_ylabel("Average Fare ($)")
            plt.xticks(rotation=25)
            plt.tight_layout()
            st.pyplot(fig)
            plt.close(fig)

        st.write("City Summary Table")
        st.dataframe(city_summary)

        st.subheader("Top 10 Drivers by Revenue")
        top_drivers = completed_df.groupby("driver_id").agg(
            completed_trips=("trip_id", "count"),
            total_revenue=("fare_amount", "sum"),
            avg_fare=("fare_amount", "mean")
        ).sort_values("total_revenue", ascending=False).head(10).round(2)
        st.dataframe(top_drivers)

# --- TAB 3: Time Trends ---
with tab3:
    st.subheader("Hourly and Daily Demand")

    left_col, right_col = st.columns(2)

    with left_col:
        hourly_trips = filtered_df.groupby("pickup_hour")["trip_id"].count()
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(hourly_trips.index, hourly_trips.values, marker="o", color="steelblue")
        ax.set_title("Trips by Pickup Hour (0 to 23)")
        ax.set_xlabel("Hour of Day")
        ax.set_ylabel("Number of Trips")
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    with right_col:
        day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        daily_trips = filtered_df["pickup_day"].value_counts().reindex(day_order).fillna(0)
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(daily_trips.index, daily_trips.values, color="mediumpurple")
        ax.set_title("Trips by Day of Week")
        ax.set_ylabel("Number of Trips")
        plt.xticks(rotation=25)
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

# --- TAB 4: Fare vs Distance ---
with tab4:
    st.subheader("Fare Amount vs. Trip Distance (Completed Trips)")

    if completed_count == 0:
        st.info("No Completed trips in the current filter.")
    else:
        left_col, right_col = st.columns(2)

        with left_col:
            fig1, ax1 = plt.subplots(figsize=(6, 4))
            sns.histplot(completed_df["distance_km"], bins=30, ax=ax1, color="steelblue")
            ax1.set_title("Distance Distribution (km)")
            ax1.set_xlabel("Distance (km)")
            plt.tight_layout()
            st.pyplot(fig1)
            plt.close(fig1)

        with right_col:
            fig2, ax2 = plt.subplots(figsize=(6, 4))
            sns.histplot(completed_df["fare_amount"], bins=30, ax=ax2, color="seagreen")
            ax2.set_title("Fare Amount Distribution ($)")
            ax2.set_xlabel("Fare Amount ($)")
            plt.tight_layout()
            st.pyplot(fig2)
            plt.close(fig2)

        # Scatter plot on a 2,000-row sample so it loads fast
        sample_size = min(2000, len(completed_df))
        sample_df = completed_df.sample(n=sample_size, random_state=42)

        fig3, ax3 = plt.subplots(figsize=(8, 4.5))
        sns.scatterplot(data=sample_df, x="distance_km", y="fare_amount", alpha=0.4, ax=ax3)
        ax3.set_title("Fare Amount vs. Distance (Sample of Completed Trips)")
        ax3.set_xlabel("Distance (km)")
        ax3.set_ylabel("Fare Amount ($)")
        plt.tight_layout()
        st.pyplot(fig3)
        plt.close(fig3)

# --- TAB 5: Data Quality & Export ---
with tab5:
    st.subheader("Basic Sanity Check Counts")

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Zero Distance", int(filtered_df["zero_distance_flag"].sum()))
    s2.metric("Negative Distance", int(filtered_df["negative_distance_flag"].sum()))
    s3.metric("Invalid Duration (<= 0)", int(filtered_df["invalid_duration_flag"].sum()))
    s4.metric("High Fare (> $40)", int(filtered_df["high_fare_flag"].sum()))

    st.subheader("Review Flag Counts from trips_reviewed.csv")

    flag_list = []
    for col in filtered_df.columns:
        if col.startswith("flag_"):
            flag_count = int(filtered_df[col].sum())
            flag_percent = round((flag_count / len(filtered_df)) * 100, 2)
            flag_list.append({
                "Flag Name": col,
                "Flagged Trips": flag_count,
                "Percent (%)": flag_percent
            })

    if len(flag_list) > 0:
        flag_table = pd.DataFrame(flag_list).sort_values("Flagged Trips", ascending=False)
        flag_table = flag_table.set_index("Flag Name")
        st.dataframe(flag_table)

    st.subheader("Data Preview & Download")
    st.dataframe(filtered_df.head(50))

    csv_data = filtered_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download Filtered Data as CSV",
        data=csv_data,
        file_name="trips_cleaned_output.csv",
        mime="text/csv"
    )