import re
import pandas as pd
import calendar
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import streamlit as st

def check_password():
    """Returns True if the user entered the correct password."""
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if st.session_state.password_correct:
        return True

    st.subheader("🔐 Login Required")
    pwd = st.text_input("Enter password:", type="password")

    if pwd == st.secrets["app_password"]:
        st.session_state.password_correct = True
        return True
    else:
        if pwd:
            st.error("Incorrect password")
        return False


# Require authentication before showing the calendar
if not check_password():
    st.stop()

# ==============================
# 1. Load Calendar Data (unchanged except “source” added)
# ==============================
def load_calendar_data(filepath,
                       source_label,
                       ofci_equipment_category_col="OFCI Equipment Category",
                       unit_tag_col="Unit Tag",
                       date_column="Vendor On Site Delivery Date"):
    """Load and preprocess delivery data from Excel."""
    deliveries = pd.read_excel(filepath)
    deliveries.columns = deliveries.columns.str.strip()

    deliveries = deliveries[[ofci_equipment_category_col, unit_tag_col, date_column]].copy()
    deliveries = deliveries.dropna(subset=[ofci_equipment_category_col, unit_tag_col, date_column])

    deliveries[unit_tag_col] = deliveries[unit_tag_col].replace("ALL UNITS", "")
    
    deliveries["TaskLabel"] = (
    deliveries[ofci_equipment_category_col].astype(str)
    + " "
    + deliveries[unit_tag_col].astype(str)
    )

    # ⭐ Clean it
    deliveries["TaskLabel"] = deliveries["TaskLabel"].apply(clean_label)
    deliveries = deliveries[~deliveries["TaskLabel"].str.match(r"(?i)^Phase\s+\d+$")]

    deliveries["Source"] = source_label  # ⭐ New

    deliveries[date_column] = pd.to_datetime(deliveries[date_column], errors="coerce")
    deliveries = deliveries.dropna(subset=[date_column])

    return deliveries

def clean_label(label: str) -> str:
    """Clean and simplify equipment labels."""

    if not isinstance(label, str):
        return label

    replacements = {
        r"\bSWITCHGEAR\b": "SWGR",
        r"\bLV SWITCHGEAR\b": "LV SWGR",
        r"\bMV SWITCHGEAR\b": "MV SWGR",
        r"\bGENERATOR\b": "",       # remove the word entirely
        r"\bGEN\b": "GEN",          # keep GEN numbers like 1.3A
        r"\bTRANSFORMER\b": "",       # remove the word entirely
        r"\bPANELS\b": "",       # remove the word entirely
        r"\bSWGR SWGR\b": "SWGR",
        r"\bLV LV\b": "LV",
        r"\bMARS\b": "Racking",
    }

    for pattern, repl in replacements.items():
        label = re.sub(pattern, repl, label, flags=re.IGNORECASE)

    # Remove extra whitespace created by deletions
    label = re.sub(r"\s+", " ", label).strip()

    return label

# ==============================
# 2. Load BOTH Excel files into one merged dataframe
# ==============================
def load_all_sources():
    df1 = load_calendar_data("03. CMH116 OFCI Log REV2.0.xlsx", source_label="CMH116")
    df2 = load_calendar_data("03. CMH120 OFCI Log REV2.0.xlsx", source_label="CMH120")
    return pd.concat([df1, df2], ignore_index=True)


# ==============================
# 3. Draw blank calendar background + legend
# ==============================
def draw_calendar_base_dynamic(
    ax,
    df,
    year,
    month,
    date_column="Vendor On Site Delivery Date",
    default_height=1.0,
    line_height=0.15,
    date_padding=0.12,
    weekday_padding=0.12,
    title_padding=0.25,
):
    calendar.setfirstweekday(calendar.SUNDAY)
    month_days = calendar.monthcalendar(year, month)
    weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

    # 1) Compute tasks_per_day + max per week
    tasks_per_day = {}
    max_tasks_per_week = []

    for w_idx, week in enumerate(month_days):
        week_max = 0
        for d_idx, day in enumerate(week):
            if day != 0:
                day_date = pd.Timestamp(year, month, day)
                n = df[df[date_column] == day_date].shape[0]
                tasks_per_day[(w_idx, d_idx)] = n
                week_max = max(week_max, n)
        max_tasks_per_week.append(week_max)

    # 2) Compute week heights
    week_heights = []
    for week_max in max_tasks_per_week:
        needed = date_padding + (max(0, week_max - 1)) * line_height + 0.1
        h = max(default_height, needed)
        week_heights.append(h)

    # 3) Compute week top y-positions (tight layout)
    week_tops = []
    cumulative = 0
    for h in week_heights:
        y_top = -(cumulative + 0.02)    # much smaller gap than old -0.5
        week_tops.append(y_top)
        cumulative += h

    # 4) Tight Title
    ax.set_axis_off()
    title_y = week_tops[0] + week_heights[0] + title_padding
    ax.set_title(
        f"{calendar.month_name[month]} {year}",
        fontsize=20,
        fontweight="bold",
        pad=2
    )

    # 5) Weekday row – just above first row of boxes
    weekday_y = week_tops[0] + 0.05   # small gap above first row
    for i, name in enumerate(weekdays):
        ax.text(i + 0.5, weekday_y, name,
                ha="center", va="bottom",
                fontsize=14, fontweight="bold")

    # 6) Legend – just above weekday names (small gap)
    legend_y = weekday_y + 0.18
    ax.text(0,    legend_y, "CMH116", color="darkblue", fontsize=12)
    ax.text(0.35,  legend_y, "CMH120", color="darkred",  fontsize=12)


    # 7) Draw calendar boxes
    for w_idx, week in enumerate(month_days):
        y_top = week_tops[w_idx]
        h = week_heights[w_idx]

        for d_idx, day in enumerate(week):
            if day == 0:
                continue

            x = d_idx
            bg = "#ffffff" if d_idx % 2 == 0 else "#e6f2ff"
            rect = Rectangle((x, y_top), 1, -h,
                             facecolor=bg, edgecolor="black")
            ax.add_patch(rect)

            ax.text(
                x + 0.05,
                y_top - 0.05,
                str(day),
                fontsize=14,
                fontweight="bold",
                ha="left",
                va="top"
            )

    # 8) Axis Limits
    bottom = week_tops[-1] - week_heights[-1] - 0.3
    ax.set_xlim(0, 7)
    ax.set_ylim(bottom, legend_y + 0.25)


    return month_days, week_tops, week_heights, line_height, date_padding


# ==============================
# 4. Add all labels to an already drawn calendar
# ==============================
def draw_calendar_labels_dynamic(
    ax,
    df,
    year,
    month,
    month_days,
    week_tops,
    week_heights,
    line_height,
    date_padding,
    date_column="Vendor On Site Delivery Date",
    colors=None,
):
    if colors is None:
        colors = {"CMH116": "darkblue", "CMH120": "darkred"}

    for w_idx, week in enumerate(month_days):
        y_top = week_tops[w_idx]

        for d_idx, day in enumerate(week):
            if day == 0:
                continue

            x = d_idx
            day_date = pd.Timestamp(year, month, day)
            tasks = df[df[date_column] == day_date]

            for i, row in enumerate(tasks.itertuples()):
                label_y = y_top - date_padding - i * line_height
                ax.text(
                    x + 0.17,
                    label_y + 0.08,
                    row.TaskLabel,
                    fontsize=9,
                    ha="left",
                    va="top",
                    color=colors.get(row.Source, "black")
                )

# ==============================
# 5. Combine into the original single-function workflow
# ==============================
def generate_calendar(df, year, month):
    fig, ax = plt.subplots(figsize=(18, 10))

    (
        month_days,
        week_tops,
        week_heights,
        line_height,
        date_padding,
    ) = draw_calendar_base_dynamic(ax, df, year, month)

    draw_calendar_labels_dynamic(
        ax, df, year, month, month_days,
        week_tops, week_heights,
        line_height, date_padding
    )

    plt.tight_layout()
    st.pyplot(fig, width='stretch')

# ==============================
# 6. Streamlit App (UNCHANGED)
# ==============================
def calendar_app(filepath):
    st.header("📅 Calendar View")

    # This now loads BOTH files regardless of UI
    df = load_all_sources()

    col1, col2 = st.columns(2)
    with col1:
        year = st.number_input("Year", value=pd.Timestamp.today().year, step=1)
    with col2:
        month = st.selectbox("Month", list(range(1, 13)), index=pd.Timestamp.today().month - 1)

    if st.button("Generate Calendar"):
        generate_calendar(df, year, month)


# ==============================
# Run standalone
# ==============================
if __name__ == "__main__":
    st.set_page_config(page_title="Construction Dashboard", layout="wide")
    calendar_app("03. CMH116 OFCI Log REV2.0.xlsx")
