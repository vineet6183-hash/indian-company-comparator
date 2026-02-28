# ──────────────────────────────────────────────────────────────────────────────
# app.py  –  Indian Company Financial Comparator
# A beginner-friendly Streamlit app to compare two Indian companies
# side-by-side using key financial metrics.
#
# HOW TO RUN:
#   pip install streamlit pandas openpyxl matplotlib pdfplumber
#   streamlit run app.py
# ──────────────────────────────────────────────────────────────────────────────

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pdfplumber                          # for reading PDF files

# ── Page Configuration ────────────────────────────────────────────────────────
# This must be the very first Streamlit command in the script.
st.set_page_config(
    page_title="Indian Company Comparator",
    page_icon="📊",
    layout="wide"
)

# ── Inject a tiny bit of custom CSS for a cleaner look ───────────────────────
st.markdown(
    """
    <style>
        .metric-row  { padding: 6px 0; border-bottom: 1px solid #e0e0e0; }
        .section-hdr { font-size: 1.3rem; font-weight: 700; margin-top: 1rem; }
        .company-hdr {
            background: #1f4e79; color: white;
            padding: 10px 14px; border-radius: 8px;
            font-size: 1.1rem; font-weight: 700; text-align: center;
        }
        .metric-label { font-weight: 600; color: #444; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS & CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

# All columns the app expects in the uploaded file.
REQUIRED_COLUMNS = [
    "Company Name",
    "Sector",
    "Revenue",
    "Profit",
    "EPS",
    "P/E Ratio",
    "Market Cap",
    "1-Year Return",
    "52-Week High",
    "52-Week Low",
]

# Metrics where a HIGHER value means the company is doing BETTER.
# P/E Ratio is the exception — a LOWER P/E usually means better valuation.
METRIC_RULES = {
    "Revenue":       True,   # Higher Revenue  = Better
    "Profit":        True,   # Higher Profit   = Better
    "EPS":           True,   # Higher EPS      = Better
    "P/E Ratio":     False,  # Lower  P/E      = Better valuation
    "Market Cap":    True,   # Higher Mkt Cap  = Larger company
    "1-Year Return": True,   # Higher return   = Better performance
}

# Human-readable labels for each metric (shown in the comparison table).
METRIC_LABELS = {
    "Revenue":       "Revenue",
    "Profit":        "Net Profit",
    "EPS":           "EPS (Earnings per Share)",
    "P/E Ratio":     "P/E Ratio",
    "Market Cap":    "Market Cap",
    "1-Year Return": "1-Year Return",
    "52-Week High":  "52-Week High",
    "52-Week Low":   "52-Week Low",
}

# Metrics that are displayed but NOT colour-coded (informational only).
DISPLAY_ONLY_METRICS = ["52-Week High", "52-Week Low"]


# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def load_data(file) -> pd.DataFrame:
    """
    Load the uploaded CSV or Excel file into a pandas DataFrame.

    Parameters
    ----------
    file : UploadedFile  –  the file object returned by st.file_uploader

    Returns
    -------
    pd.DataFrame with the contents of the uploaded file.
    """
    if file.name.lower().endswith(".csv"):
        return pd.read_csv(file)
    else:
        # openpyxl is needed to read .xlsx files
        return pd.read_excel(file, engine="openpyxl")


def load_pdf(file) -> list:
    """
    Extract every table from a PDF file and return them as a list of dicts.

    Each dict contains:
        'label' : human-readable name shown in the dropdown
        'page'  : page number (1-based) where the table was found
        'df'    : the table as a pandas DataFrame

    pdfplumber scans each page for grid-like structures.
    If a page has no tables, it is skipped silently.
    """
    results = []

    with pdfplumber.open(file) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            page_tables = page.extract_tables()           # list of raw 2-D lists

            for tbl_num, raw in enumerate(page_tables, start=1):
                # Skip empty or single-row tables (no data rows)
                if not raw or len(raw) < 2:
                    continue

                # First row → column headers; clean up None / whitespace
                headers = [
                    str(h).strip() if h else f"Column {i}"
                    for i, h in enumerate(raw[0])
                ]

                # Remaining rows → data
                rows = raw[1:]

                try:
                    df_tbl = pd.DataFrame(rows, columns=headers)
                    df_tbl = df_tbl.dropna(how="all")    # drop fully empty rows

                    if len(df_tbl) == 0:
                        continue

                    results.append({
                        "label": f"Page {page_num}  –  Table {tbl_num}  "
                                 f"({len(df_tbl)} rows × {len(df_tbl.columns)} cols)",
                        "page": page_num,
                        "df":   df_tbl,
                    })
                except Exception:
                    # If pandas can't build a DataFrame from this table, skip it
                    continue

    return results


def validate_columns(df: pd.DataFrame) -> list:
    """
    Check whether all required columns are present in the DataFrame.

    Returns a list of column names that are MISSING (empty list = all good).
    """
    return [col for col in REQUIRED_COLUMNS if col not in df.columns]


def get_colors(val_a, val_b, higher_is_better: bool):
    """
    Compare two numeric values and return HTML colour strings.

    The 'winning' (better) value gets GREEN, the losing one gets RED.
    If they're equal, both get GREY.

    Parameters
    ----------
    val_a            : numeric value for Company A
    val_b            : numeric value for Company B
    higher_is_better : True if a higher number is better (e.g. Revenue),
                       False if a lower number is better (e.g. P/E Ratio)

    Returns
    -------
    (color_a, color_b) : tuple of CSS colour strings
    """
    if val_a == val_b:
        return "grey", "grey"

    if higher_is_better:
        return ("#27ae60", "#e74c3c") if val_a > val_b else ("#e74c3c", "#27ae60")
    else:
        # Lower is better
        return ("#27ae60", "#e74c3c") if val_a < val_b else ("#e74c3c", "#27ae60")


def format_value(col: str, val) -> str:
    """
    Format a raw number into a readable string with the right symbol/unit.

    Monetary values (Revenue, Profit, Market Cap) are assumed to be in ₹ Crores.
    Values ≥ 1 Lakh Crore (1,00,000 Cr) are shown as "X.XX L Cr" for readability.

    Parameters
    ----------
    col : column name (metric name)
    val : the raw numeric value

    Returns
    -------
    Formatted string representation.
    """
    try:
        val = float(val)
    except (TypeError, ValueError):
        return str(val)

    if col in ("Revenue", "Profit", "Market Cap"):
        if val >= 1_00_000:                         # ≥ 1 Lakh Crore
            return f"₹ {val / 1_00_000:,.2f} L Cr"
        return f"₹ {val:,.0f} Cr"

    if col == "EPS":
        return f"₹ {val:,.2f}"

    if col == "P/E Ratio":
        return f"{val:.2f}x"

    if col == "1-Year Return":
        sign = "+" if val >= 0 else ""
        return f"{sign}{val:.2f}%"

    if col in ("52-Week High", "52-Week Low"):
        return f"₹ {val:,.2f}"

    return str(val)


def colored_cell(text: str, color: str) -> str:
    """
    Wrap text in an HTML <span> with a given colour and bold style.
    Used with st.markdown(..., unsafe_allow_html=True).
    """
    return (
        f"<span style='color:{color}; font-weight:700; font-size:1rem;'>"
        f"{text}</span>"
    )


# ─────────────────────────────────────────────────────────────────────────────
# APP HEADER
# ─────────────────────────────────────────────────────────────────────────────

st.title("📊 Indian Company Financial Comparator")
st.markdown(
    "Upload a dataset and compare **two Indian companies** side-by-side "
    "across key financial metrics. Better values are highlighted in "
    "<span style='color:#27ae60;font-weight:700;'>Green</span> and "
    "weaker values in <span style='color:#e74c3c;font-weight:700;'>Red</span>.",
    unsafe_allow_html=True,
)
st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────────
# FILE UPLOAD
# ─────────────────────────────────────────────────────────────────────────────

uploaded_file = st.file_uploader(
    "📂 Upload your dataset (CSV, Excel .xlsx, or PDF)",
    type=["csv", "xlsx", "pdf"],
    help="CSV/Excel: must contain all required columns. PDF: tables are extracted automatically.",
)

# If no file is uploaded yet, show guidance and stop here.
if uploaded_file is None:
    st.info("👆 Please upload a CSV, Excel, or PDF file to get started.")

    with st.expander("📌 Click here to see the required file format & a sample"):
        st.markdown(
            "Your file **must** contain the following columns "
            "(column names must match exactly):"
        )
        st.code(
            "Company Name, Sector, Revenue, Profit, EPS, "
            "P/E Ratio, Market Cap, 1-Year Return, 52-Week High, 52-Week Low"
        )
        st.markdown("**Sample rows** (monetary values in ₹ Crores):")

        sample_data = {
            "Company Name":  ["Reliance Industries", "Infosys",        "TCS"],
            "Sector":        ["Energy",              "IT",              "IT"],
            "Revenue":       [862000,                146767,            240893],
            "Profit":        [73670,                 24108,             46483],
            "EPS":           [108.5,                 57.2,              125.3],
            "P/E Ratio":     [28.4,                  25.1,              29.6],
            "Market Cap":    [1720000,               608000,            1080000],
            "1-Year Return": [12.5,                  8.3,               14.2],
            "52-Week High":  [3024.90,               1953.90,           4592.25],
            "52-Week Low":   [2180.50,               1358.35,           3311.00],
        }
        st.dataframe(pd.DataFrame(sample_data), use_container_width=True)
        st.caption("Monetary values (Revenue, Profit, Market Cap) → ₹ Crores")

    st.stop()   # Do not run anything below until a file is uploaded.


# ─────────────────────────────────────────────────────────────────────────────
# LOAD DATA  –  branch on file type
# ─────────────────────────────────────────────────────────────────────────────

is_pdf = uploaded_file.name.lower().endswith(".pdf")

# ── PDF path ──────────────────────────────────────────────────────────────────
if is_pdf:
    st.markdown("### 📄 PDF detected — extracting tables…")

    with st.spinner("Scanning PDF for tables…"):
        pdf_tables = load_pdf(uploaded_file)

    if not pdf_tables:
        st.error(
            "❌ No tables were found in this PDF. "
            "Make sure the PDF contains grid/table data (not just plain text or images)."
        )
        st.stop()

    st.success(f"✅ Found **{len(pdf_tables)} table(s)** in the PDF.")

    # ── Step 1 : pick a table ─────────────────────────────────────────────────
    st.markdown("#### Step 1 — Select the table that contains company data")

    table_labels = [t["label"] for t in pdf_tables]
    chosen_label = st.selectbox("Choose a table:", table_labels, key="pdf_table_sel")
    chosen_table = next(t for t in pdf_tables if t["label"] == chosen_label)

    with st.expander("🔍 Preview selected table (first 10 rows)"):
        st.dataframe(chosen_table["df"].head(10), use_container_width=True)

    pdf_cols = list(chosen_table["df"].columns)

    # ── Step 2 : map PDF columns → required columns ───────────────────────────
    st.markdown("#### Step 2 — Map table columns to required fields")
    st.caption(
        "For each required field, choose the matching column from your PDF table. "
        "If the field doesn't exist in the PDF, leave it as **— skip —** "
        "(skipped numeric fields default to 0)."
    )

    SKIP = "— skip —"
    col_options = [SKIP] + pdf_cols   # allow skipping optional fields

    # Auto-match: if a PDF column name closely matches a required column, pre-select it.
    def best_match(required: str, candidates: list) -> str:
        req_lower = required.lower().replace(" ", "").replace("-", "")
        for c in candidates:
            if req_lower in c.lower().replace(" ", "").replace("-", ""):
                return c
        return SKIP

    mapping = {}      # required_col_name → pdf_col_name (or SKIP)

    # Lay out the mapping selectors in two columns for a tidier look
    left_fields  = REQUIRED_COLUMNS[:5]
    right_fields = REQUIRED_COLUMNS[5:]

    map_col_left, map_col_right = st.columns(2)

    for field in left_fields:
        auto = best_match(field, pdf_cols)
        default_idx = col_options.index(auto) if auto in col_options else 0
        with map_col_left:
            mapping[field] = st.selectbox(
                f"**{field}**", col_options,
                index=default_idx,
                key=f"pdfmap_{field}",
            )

    for field in right_fields:
        auto = best_match(field, pdf_cols)
        default_idx = col_options.index(auto) if auto in col_options else 0
        with map_col_right:
            mapping[field] = st.selectbox(
                f"**{field}**", col_options,
                index=default_idx,
                key=f"pdfmap_{field}",
            )

    # ── Step 3 : build the final DataFrame ────────────────────────────────────
    st.markdown("#### Step 3 — Build & review the mapped data")

    if st.button("✅ Apply mapping and load data", type="primary"):
        st.session_state["pdf_mapping_applied"] = True
        st.session_state["pdf_mapping"]         = mapping
        st.session_state["pdf_source_df"]       = chosen_table["df"]

    # Only proceed once the user has clicked Apply
    if not st.session_state.get("pdf_mapping_applied"):
        st.info("👆 Click **Apply mapping** above to continue.")
        st.stop()

    # Re-read confirmed mapping and source from session state
    mapping  = st.session_state["pdf_mapping"]
    raw_df   = st.session_state["pdf_source_df"]

    # Build a new DataFrame with the required column names
    rows_out = []
    for _, row in raw_df.iterrows():
        new_row = {}
        for req_col in REQUIRED_COLUMNS:
            src_col = mapping[req_col]
            if src_col == SKIP:
                # Text columns get empty string; numeric get 0
                new_row[req_col] = "" if req_col in ("Company Name", "Sector") else 0
            else:
                new_row[req_col] = row[src_col]
        rows_out.append(new_row)

    df = pd.DataFrame(rows_out, columns=REQUIRED_COLUMNS)

    # Convert numeric columns from strings to numbers (PDFs often return strings)
    numeric_cols = [c for c in REQUIRED_COLUMNS if c not in ("Company Name", "Sector")]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Drop rows where Company Name is blank / NaN
    df = df[df["Company Name"].astype(str).str.strip() != ""]
    df = df[df["Company Name"].astype(str).str.strip() != "nan"]

    if df.empty:
        st.error(
            "❌ No valid company rows found after mapping. "
            "Please check your column mapping and try again."
        )
        if st.button("🔄 Reset and re-map"):
            st.session_state["pdf_mapping_applied"] = False
        st.stop()

    with st.expander("🔍 Preview mapped data"):
        st.dataframe(df, use_container_width=True)

# ── CSV / Excel path ──────────────────────────────────────────────────────────
else:
    df = load_data(uploaded_file)

    # Check for missing columns
    missing_cols = validate_columns(df)
    if missing_cols:
        st.error(
            f"❌ Your file is missing these required columns: "
            f"**{', '.join(missing_cols)}**\n\n"
            f"Please fix the file and re-upload."
        )
        st.stop()

    with st.expander("🔍 Preview uploaded data"):
        st.dataframe(df, use_container_width=True)

# ── Common: strip whitespace from Company Name ────────────────────────────────
df["Company Name"] = df["Company Name"].astype(str).str.strip()

st.success(f"✅ Data ready — **{len(df)} companies** loaded.")

st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────────
# COMPANY SELECTION
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="section-hdr">🏢 Select Companies to Compare</div>',
            unsafe_allow_html=True)
st.markdown(" ")

company_list = df["Company Name"].dropna().unique().tolist()

col_sel_a, col_sel_b = st.columns(2)

with col_sel_a:
    company_a = st.selectbox(
        "Company A",
        options=company_list,
        index=0,
        key="company_a_selector",
    )

with col_sel_b:
    # Default Company B to the second item so both dropdowns start different
    default_b_index = 1 if len(company_list) > 1 else 0
    company_b = st.selectbox(
        "Company B",
        options=company_list,
        index=default_b_index,
        key="company_b_selector",
    )

# Guard: Both selections must be different
if company_a == company_b:
    st.warning("⚠️ Please select two **different** companies to compare.")
    st.stop()

# Fetch the data rows for the two selected companies
row_a = df[df["Company Name"] == company_a].iloc[0]
row_b = df[df["Company Name"] == company_b].iloc[0]

st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────────
# SIDE-BY-SIDE COMPARISON TABLE
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="section-hdr">📋 Side-by-Side Comparison</div>',
            unsafe_allow_html=True)
st.markdown(" ")

# ── Column headers ────────────────────────────────────────────────────────────
hdr_metric, hdr_a, hdr_b = st.columns([3, 2, 2])
hdr_metric.markdown("**Metric**")
hdr_a.markdown(
    f"<div class='company-hdr'>🔵 {company_a}</div>",
    unsafe_allow_html=True,
)
hdr_b.markdown(
    f"<div class='company-hdr'>🟠 {company_b}</div>",
    unsafe_allow_html=True,
)

st.markdown("---")

# ── Sector row (informational, no winner) ─────────────────────────────────────
c0, c1, c2 = st.columns([3, 2, 2])
c0.markdown("<span class='metric-label'>Sector</span>", unsafe_allow_html=True)
c1.write(str(row_a["Sector"]))
c2.write(str(row_b["Sector"]))

# ── Initialise win counters ───────────────────────────────────────────────────
wins_a = 0
wins_b = 0

# ── Comparable metrics (colour-coded) ────────────────────────────────────────
for metric in METRIC_RULES:
    val_a = row_a[metric]
    val_b = row_b[metric]
    higher_is_better = METRIC_RULES[metric]

    # Determine which company 'wins' this metric
    color_a, color_b = get_colors(val_a, val_b, higher_is_better)

    # Tally wins (green = winner)
    if color_a == "#27ae60":
        wins_a += 1
    elif color_b == "#27ae60":
        wins_b += 1

    # Render the row
    c0, c1, c2 = st.columns([3, 2, 2])
    c0.markdown(
        f"<span class='metric-label'>{METRIC_LABELS[metric]}</span>",
        unsafe_allow_html=True,
    )
    c1.markdown(
        colored_cell(format_value(metric, val_a), color_a),
        unsafe_allow_html=True,
    )
    c2.markdown(
        colored_cell(format_value(metric, val_b), color_b),
        unsafe_allow_html=True,
    )

# ── Display-only metrics (no colour, just info) ───────────────────────────────
for metric in DISPLAY_ONLY_METRICS:
    c0, c1, c2 = st.columns([3, 2, 2])
    c0.markdown(
        f"<span class='metric-label'>{METRIC_LABELS[metric]}</span>",
        unsafe_allow_html=True,
    )
    c1.write(format_value(metric, row_a[metric]))
    c2.write(format_value(metric, row_b[metric]))

st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────────
# SCORING SYSTEM
# Each metric where a company has the better value awards it 1 point.
# wins_a and wins_b were tallied in the comparison loop above.
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="section-hdr">🏆 Final Score</div>', unsafe_allow_html=True)
st.markdown(" ")

total_possible = len(METRIC_RULES)   # Maximum points either company can earn

# ── Score card HTML ──────────────────────────────────────────────────────────
# Build a styled card for each company showing "X points" prominently.
# The winner card gets a gold/green accent; the loser gets a muted red accent.

def score_card_html(company_name: str, points: int, total: int,
                    is_winner: bool, is_tie: bool) -> str:
    """
    Return an HTML string for a styled score card.

    Parameters
    ----------
    company_name : display name of the company
    points       : number of metrics this company won
    total        : total comparable metrics (max possible points)
    is_winner    : True if this company has more points
    is_tie       : True if both companies are equal
    """
    if is_tie:
        border_color = "#f39c12"   # amber for a tie
        badge_color  = "#f39c12"
        label        = "🤝 Tied"
    elif is_winner:
        border_color = "#27ae60"   # green for winner
        badge_color  = "#27ae60"
        label        = "🥇 Winner"
    else:
        border_color = "#e74c3c"   # red for loser
        badge_color  = "#e74c3c"
        label        = "Runner-up"

    return f"""
    <div style="
        border: 3px solid {border_color};
        border-radius: 12px;
        padding: 20px 16px;
        text-align: center;
        background: #fafafa;
    ">
        <div style="font-size:0.85rem; color:#888; margin-bottom:4px;">
            {company_name}
        </div>
        <div style="font-size:3rem; font-weight:800; color:{border_color}; line-height:1.1;">
            {points}
        </div>
        <div style="font-size:1rem; color:#555; margin-bottom:8px;">
            point{"s" if points != 1 else ""} out of {total}
        </div>
        <span style="
            background:{badge_color}; color:white;
            padding:3px 10px; border-radius:20px; font-size:0.8rem; font-weight:600;
        ">{label}</span>
    </div>
    """

# Determine winner / tie flags
is_tie      = (wins_a == wins_b)
a_is_winner = (wins_a > wins_b)
b_is_winner = (wins_b > wins_a)

# Render both score cards side by side
card_col_a, card_col_b = st.columns(2)

with card_col_a:
    st.markdown(
        score_card_html(company_a, wins_a, total_possible, a_is_winner, is_tie),
        unsafe_allow_html=True,
    )

with card_col_b:
    st.markdown(
        score_card_html(company_b, wins_b, total_possible, b_is_winner, is_tie),
        unsafe_allow_html=True,
    )

st.markdown(" ")

# ── Plain-text score line (easy to read at a glance) ─────────────────────────
st.markdown(
    f"**{company_a}:** {wins_a} point{'s' if wins_a != 1 else ''}  &nbsp;|&nbsp;  "
    f"**{company_b}:** {wins_b} point{'s' if wins_b != 1 else ''}",
    unsafe_allow_html=True,
)

st.markdown(" ")

# ── Verdict message ───────────────────────────────────────────────────────────
if a_is_winner:
    st.success(
        f"✅ **Based on the selected metrics, {company_a} appears stronger overall** "
        f"with **{wins_a} point{'s' if wins_a != 1 else ''}** vs "
        f"{company_b}'s {wins_b} point{'s' if wins_b != 1 else ''}."
    )
elif b_is_winner:
    st.success(
        f"✅ **Based on the selected metrics, {company_b} appears stronger overall** "
        f"with **{wins_b} point{'s' if wins_b != 1 else ''}** vs "
        f"{company_a}'s {wins_a} point{'s' if wins_a != 1 else ''}."
    )
else:
    st.info(
        f"🤝 It's a tie! Both **{company_a}** and **{company_b}** scored "
        f"**{wins_a} point{'s' if wins_a != 1 else ''}** each."
    )

st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────────
# BAR CHART  –  Revenue & Profit Comparison
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="section-hdr">📈 Revenue & Profit Chart</div>',
            unsafe_allow_html=True)
st.markdown("*(Values in ₹ Crores)*")
st.markdown(" ")

companies_labels = [company_a, company_b]
bar_colors       = ["#2980b9", "#e67e22"]   # Blue for A, Orange for B

revenue_vals = [float(row_a["Revenue"]), float(row_b["Revenue"])]
profit_vals  = [float(row_a["Profit"]),  float(row_b["Profit"])]

# Create a figure with two side-by-side bar charts
fig, (ax_rev, ax_prof) = plt.subplots(1, 2, figsize=(11, 5))
fig.patch.set_facecolor("#f9f9f9")

# ── Revenue chart ─────────────────────────────────────────────────────────────
bars_rev = ax_rev.bar(
    companies_labels, revenue_vals,
    color=bar_colors, edgecolor="white", linewidth=1.2, width=0.5
)
ax_rev.set_title("Revenue Comparison", fontsize=14, fontweight="bold", pad=12)
ax_rev.set_ylabel("₹ Crores", fontsize=11)
ax_rev.tick_params(axis="x", labelsize=10, rotation=10)
ax_rev.set_facecolor("#f9f9f9")
ax_rev.spines[["top", "right"]].set_visible(False)

# Add value labels on top of each bar
for bar, val in zip(bars_rev, revenue_vals):
    ax_rev.text(
        bar.get_x() + bar.get_width() / 2,
        bar.get_height() * 1.015,
        format_value("Revenue", val),
        ha="center", va="bottom", fontsize=8.5, fontweight="bold"
    )

# ── Profit chart ──────────────────────────────────────────────────────────────
bars_prof = ax_prof.bar(
    companies_labels, profit_vals,
    color=bar_colors, edgecolor="white", linewidth=1.2, width=0.5
)
ax_prof.set_title("Net Profit Comparison", fontsize=14, fontweight="bold", pad=12)
ax_prof.set_ylabel("₹ Crores", fontsize=11)
ax_prof.tick_params(axis="x", labelsize=10, rotation=10)
ax_prof.set_facecolor("#f9f9f9")
ax_prof.spines[["top", "right"]].set_visible(False)

for bar, val in zip(bars_prof, profit_vals):
    ax_prof.text(
        bar.get_x() + bar.get_width() / 2,
        bar.get_height() * 1.015,
        format_value("Profit", val),
        ha="center", va="bottom", fontsize=8.5, fontweight="bold"
    )

# ── Legend ────────────────────────────────────────────────────────────────────
legend_patches = [
    mpatches.Patch(color=bar_colors[0], label=company_a),
    mpatches.Patch(color=bar_colors[1], label=company_b),
]
fig.legend(
    handles=legend_patches,
    loc="upper center",
    ncol=2,
    fontsize=10,
    frameon=False,
    bbox_to_anchor=(0.5, 1.02),
)

plt.tight_layout()
st.pyplot(fig)

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────────────────────

st.caption(
    "⚠️ **Disclaimer:** This app is for **educational purposes only** and does "
    "not constitute financial advice. All data is sourced from your uploaded file. "
    "Always consult a certified financial advisor before making investment decisions."
)
