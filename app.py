"""Streamlit UI for the expense tracker. Run: uv run streamlit run app.py"""

import asyncio
from datetime import date, datetime, timedelta, timezone
from html import escape

import altair as alt
import pandas as pd
import streamlit as st

import db
import llm_client

# Brand palette
PRIMARY = "#F3BD00"
DARK = "#1C1C1E"
LIGHT = "#F5F5F5"
MUTED = "#6B6B70"
DANGER = "#D93025"
CHART_COLORS = [PRIMARY, DARK, "#8E8E93", "#F7D55C", "#C7C7CC", "#A67F00"]

PAYMENT_METHODS = ["Cash", "UPI", "Card", "Net Banking", "Other"]
PAGES = {
    "Expenses": ":material/receipt_long:",
    "Categories": ":material/category:",
    "Dashboard": ":material/insights:",
}
SUGGESTIONS = [
    ("Log an expense", "I spent 250 on lunch today with UPI"),
    ("Monthly summary", "Summarise my spending this month"),
    ("Top category", "Which category did I spend the most on this month?"),
    ("Recent expenses", "Show my last 5 expenses"),
]
AVATARS = {"user": ":material/person:", "assistant": ":material/account_balance_wallet:"}

st.set_page_config(
    page_title="Expense Tracker",
    page_icon=":material/account_balance_wallet:",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.html(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* Hide Streamlit's own menu so ours is the only one in the top-right */
[data-testid="stMainMenu"], [data-testid="stAppDeployButton"] {{ display: none; }}
header[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stMainBlockContainer"] {{ padding-top: 2.2rem; max-width: 1240px; }}

/* Page header */
.page-title {{ font-size: 1.65rem; font-weight: 800; color: {DARK}; margin: 0; letter-spacing: -0.02em; }}
.page-sub {{ color: {MUTED}; margin: 2px 0 0; font-size: 0.95rem; }}

/* Three-dot menu */
.st-key-topmenu {{ position: relative; align-items: flex-end; overflow: visible; }}
.st-key-menu_toggle button {{
    width: 44px; height: 44px; border-radius: 999px; padding: 0;
    background: #FFFFFF; border: 1px solid #E4E4E7;
    box-shadow: 0 1px 2px rgba(28,28,30,.06);
}}
.st-key-menu_toggle button:hover {{ border-color: {PRIMARY}; color: {DARK}; }}
.st-key-navmenu {{
    position: absolute !important; top: 52px; right: 0; z-index: 1000; gap: 2px;
    width: 230px !important; min-width: 230px !important; max-width: none !important;
    background: #FFFFFF; border: 1px solid #E4E4E7; border-radius: 14px; padding: 10px;
    box-shadow: 0 12px 32px rgba(28,28,30,.14);
}}
.st-key-navmenu button {{ padding-left: 12px; }}
.st-key-navmenu button > div {{ justify-content: flex-start; width: 100%; }}
[class*="st-key-sugg_"] button > div,
[data-testid="stSidebar"] [class*="st-key-chat_"] button > div {{ justify-content: flex-start; width: 100%; }}
.menu-label {{ font-size: .72rem; font-weight: 700; text-transform: uppercase; letter-spacing: .06em;
              color: {MUTED}; margin: 0 0 4px 6px; }}

/* Cards */
[class*="st-key-card"] {{
    background: #FFFFFF; border: 1px solid #E4E4E7; border-radius: 16px; padding: 20px 22px;
    box-shadow: 0 1px 2px rgba(28,28,30,.04), 0 8px 24px rgba(28,28,30,.04);
}}
.card-title {{ font-weight: 700; font-size: 1.02rem; color: {DARK}; margin: 0 0 2px; }}
.card-sub {{ color: {MUTED}; font-size: .85rem; margin: 0 0 8px; }}

/* KPI tiles */
.kpi {{
    background: #FFFFFF; border: 1px solid #E4E4E7; border-radius: 16px; padding: 18px 20px;
    box-shadow: 0 1px 2px rgba(28,28,30,.04), 0 8px 24px rgba(28,28,30,.04); height: 100%;
}}
.kpi-label {{ font-size: .74rem; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; color: {MUTED}; }}
.kpi-value {{ font-size: 1.6rem; font-weight: 800; color: {DARK}; margin-top: 6px; letter-spacing: -0.02em;
              white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.kpi-sub {{ font-size: .8rem; color: {MUTED}; margin-top: 2px; }}
.kpi.accent {{ background: {DARK}; border-color: {DARK}; }}
.kpi.accent .kpi-label {{ color: #A1A1A6; }}
.kpi.accent .kpi-value {{ color: {PRIMARY}; }}
.kpi.accent .kpi-sub {{ color: #A1A1A6; }}

/* Primary buttons: dark text on yellow for contrast */
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {{
    color: {DARK} !important; font-weight: 600; border: none;
}}
[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover {{
    background: #DCAA00 !important; color: {DARK} !important;
}}

/* Sidebar */
.brand {{ display: flex; align-items: center; gap: 12px; margin: 4px 0 18px; }}
.brand-logo {{
    width: 40px; height: 40px; border-radius: 12px; background: {PRIMARY}; color: {DARK};
    display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 1.1rem;
}}
.brand-name {{ font-weight: 800; font-size: 1.08rem; color: {LIGHT}; line-height: 1.1; }}
.brand-tag {{ font-size: .75rem; color: #8E8E93; }}
.side-group {{ font-size: .7rem; font-weight: 700; text-transform: uppercase; letter-spacing: .08em;
              color: #8E8E93; margin: 18px 0 2px 8px; }}
.side-empty {{ color: #8E8E93; font-size: .85rem; margin: 18px 8px; line-height: 1.5; }}
.side-footer {{ color: #8E8E93; font-size: .75rem; margin-top: 28px; padding: 12px 8px 0;
               border-top: 1px solid #3A3A3C; }}
[class*="st-key-row_"] {{ flex-wrap: nowrap !important; gap: 2px !important; }}
[class*="st-key-row_"] > div:first-child {{ flex: 1 1 auto; min-width: 0; }}
[data-testid="stSidebar"] [class*="st-key-chat_"] button {{
    justify-content: flex-start; border-radius: 10px; padding: 6px 10px; min-height: 36px;
    color: #D1D1D6; border: 1px solid transparent; background: transparent;
}}
[data-testid="stSidebar"] [class*="st-key-chat_"] button:hover {{ background: #2C2C2E; color: {LIGHT}; }}
[data-testid="stSidebar"] [class*="st-key-chat_"] button p {{
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; text-align: left; font-size: .9rem;
}}
[data-testid="stSidebar"] [class*="st-key-chat_"] [data-testid="stBaseButton-secondary"] {{
    background: #2C2C2E; color: {LIGHT}; border-left: 3px solid {PRIMARY};
}}
[data-testid="stSidebar"] [class*="st-key-del_"] button {{ color: #636366; min-height: 36px; padding: 0 6px; }}
[data-testid="stSidebar"] [class*="st-key-del_"] button:hover {{ color: {DANGER}; }}

/* Chat */
.hero {{
    background: {DARK}; color: {LIGHT}; border-radius: 20px; padding: 34px 36px; margin: 8px 0 18px;
    background-image: radial-gradient(circle at 92% 10%, rgba(243,189,0,.28), transparent 42%);
}}
.hero-badge {{ display: inline-block; background: rgba(243,189,0,.15); color: {PRIMARY}; font-weight: 700;
              font-size: .74rem; letter-spacing: .06em; text-transform: uppercase; padding: 5px 10px;
              border-radius: 999px; }}
.hero-title {{ color: {LIGHT}; font-weight: 800; font-size: 1.9rem; margin: 14px 0 6px; letter-spacing: -0.02em; }}
.hero-title span {{ color: {PRIMARY}; }}
.hero-text {{ color: #C7C7CC; margin: 0; max-width: 620px; }}
[class*="st-key-sugg_"] button {{
    background: #FFFFFF; border: 1px solid #E4E4E7; border-radius: 14px; padding: 14px 16px;
    justify-content: flex-start; text-align: left; min-height: 74px;
}}
[class*="st-key-sugg_"] button:hover {{ border-color: {PRIMARY}; box-shadow: 0 6px 18px rgba(243,189,0,.15); color: {DARK}; }}
[data-testid="stChatMessage"] {{
    background: #FFFFFF; border: 1px solid #E4E4E7; border-radius: 16px; padding: 14px 18px; margin-bottom: 8px;
}}
[data-testid="stChatMessageAvatarCustom"] {{ background: {PRIMARY}; color: {DARK}; }}

/* Category cards */
.cat-head {{ display: flex; align-items: center; gap: 10px; }}
.cat-dot {{ width: 12px; height: 12px; border-radius: 999px; flex: none; }}
.cat-name {{ font-weight: 700; font-size: 1.02rem; color: {DARK}; }}
.cat-desc {{ color: {MUTED}; font-size: .85rem; margin: 4px 0 14px; min-height: 1.2em; }}
.cat-amount {{ font-weight: 800; font-size: 1.3rem; color: {DARK}; }}
.cat-meta {{ color: {MUTED}; font-size: .8rem; }}
.bar {{ height: 8px; background: #EFEFF1; border-radius: 999px; overflow: hidden; margin: 10px 0 6px; }}
.bar > div {{ height: 100%; border-radius: 999px; }}
.pill {{ display: inline-block; font-size: .72rem; font-weight: 700; padding: 3px 9px; border-radius: 999px; }}
.pill.ok {{ background: #FFF6D6; color: #8A6A00; }}
.pill.over {{ background: #FDE7E5; color: {DANGER}; }}
.pill.none {{ background: #F0F0F2; color: {MUTED}; }}
[data-testid="stButtonGroup"] button[aria-checked="true"] {{
    background: {DARK} !important; color: {PRIMARY} !important; border-color: {DARK} !important;
}}
.empty {{ text-align: center; color: {MUTED}; padding: 36px 12px; }}
.empty b {{ color: {DARK}; display: block; font-size: 1.05rem; margin-bottom: 4px; }}
</style>
""")

ss = st.session_state
ss.setdefault("page", "Chat")
ss.setdefault("chat_id", None)
ss.setdefault("messages", [])
ss.setdefault("table_ver", 0)
ss.setdefault("menu_open", False)


# ---------- helpers ----------

def tool(name: str, args: dict | None = None):
    """Call an MCP tool synchronously; show errors in the UI."""
    try:
        return asyncio.run(llm_client.call_tool(name, args))
    except Exception as e:
        st.error(str(e))
        return None


def money(value: float | None) -> str:
    return f"₹{value or 0:,.2f}"


def flash(message: str) -> None:
    """Show a toast on the next run (toasts don't survive st.rerun)."""
    ss.flash = message


def kpi(col, label: str, value: str, sub: str = "", accent: bool = False) -> None:
    col.markdown(
        f'<div class="kpi{" accent" if accent else ""}"><div class="kpi-label">{escape(label)}</div>'
        f'<div class="kpi-value">{escape(value)}</div><div class="kpi-sub">{escape(sub) or "&nbsp;"}</div></div>',
        unsafe_allow_html=True,
    )


def empty_state(title: str, text: str) -> None:
    st.markdown(f'<div class="empty"><b>{escape(title)}</b>{escape(text)}</div>', unsafe_allow_html=True)


def date_bounds(value) -> tuple[date | None, date | None]:
    """st.date_input range can briefly hold one date while the user picks."""
    if not value:
        return None, None
    if isinstance(value, date):
        return value, value
    value = tuple(value)
    return value[0], value[-1]


def style_chart(chart: alt.Chart, height: int = 280) -> alt.Chart:
    return (
        chart.properties(height=height, background="#FFFFFF")
        .configure_view(strokeWidth=0)
        .configure_axis(
            labelColor=MUTED, titleColor=MUTED, gridColor="#EEEEF0", domain=False,
            ticks=False, labelFont="Inter", titleFont="Inter", labelFontSize=11, titlePadding=10,
        )
        .configure_legend(labelFont="Inter", labelColor=DARK, titleFont="Inter", titleColor=MUTED)
    )


def go(page: str) -> None:
    ss.page = page
    ss.menu_open = False


def toggle_menu() -> None:
    ss.menu_open = not ss.menu_open


def new_chat() -> None:
    ss.chat_id, ss.messages = None, []
    go("Chat")


def open_chat(chat_id: int) -> None:
    ss.chat_id, ss.messages = chat_id, db.fetch_chat_messages(chat_id)
    go("Chat")


def remove_chat(chat_id: int) -> None:
    db.delete_chat(chat_id)
    if ss.chat_id == chat_id:
        new_chat()


def header(title: str, subtitle: str) -> None:
    """Page title on the left, three-dot navigation menu on the right."""
    left, right = st.columns([12, 1], vertical_alignment="center")
    with left:
        if ss.page != "Chat":
            st.button("Back to chat", icon=":material/arrow_back:", type="tertiary", on_click=go, args=("Chat",))
        st.markdown(f'<div class="page-title">{escape(title)}</div><div class="page-sub">{escape(subtitle)}</div>',
                    unsafe_allow_html=True)
    with right, st.container(key="topmenu"):
        st.button("", icon=":material/more_vert:", key="menu_toggle", help="Menu", on_click=toggle_menu)
        if ss.menu_open:
            with st.container(key="navmenu"):
                st.markdown('<div class="menu-label">Go to</div>', unsafe_allow_html=True)
                for name, icon in PAGES.items():
                    st.button(
                        name, icon=icon, key=f"nav_{name}", width="stretch",
                        type="primary" if ss.page == name else "tertiary",
                        on_click=go, args=(name,),
                    )
    st.write("")


def group_chats(chats: list[dict]) -> list[tuple[str, list[dict]]]:
    today = date.today()
    groups: dict[str, list[dict]] = {"Today": [], "Yesterday": [], "Previous 7 days": [], "Older": []}
    for c in chats:
        try:
            day = (datetime.strptime(c["updated_at"], "%Y-%m-%d %H:%M:%S")
                   .replace(tzinfo=timezone.utc).astimezone().date())
        except (TypeError, ValueError):
            day = today
        age = (today - day).days
        key = "Today" if age <= 0 else "Yesterday" if age == 1 else "Previous 7 days" if age <= 7 else "Older"
        groups[key].append(c)
    return [(name, items) for name, items in groups.items() if items]


# ---------- sidebar: chat history ----------

def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            '<div class="brand"><div class="brand-logo">₹</div><div>'
            '<div class="brand-name">Expense Tracker</div>'
            '<div class="brand-tag">AI-powered spending assistant</div></div></div>',
            unsafe_allow_html=True,
        )
        st.button("New chat", icon=":material/add:", type="primary", width="stretch", on_click=new_chat)

        chats = db.fetch_chats()
        if not chats:
            st.markdown('<div class="side-empty">No conversations yet.<br>Start a new chat to log or '
                        'explore your expenses.</div>', unsafe_allow_html=True)
        for group, items in group_chats(chats):
            st.markdown(f'<div class="side-group">{group}</div>', unsafe_allow_html=True)
            for c in items:
                active = ss.page == "Chat" and ss.chat_id == c["id"]
                row = st.container(horizontal=True, vertical_alignment="center", key=f"row_{c['id']}")
                row.button(
                    c["title"], key=f"chat_{c['id']}", width="stretch",
                    type="secondary" if active else "tertiary",
                    icon=":material/chat_bubble:", on_click=open_chat, args=(c["id"],),
                )
                row.button("", icon=":material/delete:", key=f"del_{c['id']}", type="tertiary", width="content",
                         help="Delete chat", on_click=remove_chat, args=(c["id"],))

        st.markdown(f'<div class="side-footer">{escape(llm_client.PROVIDER.title())} · {escape(llm_client.MODEL)}</div>',
                    unsafe_allow_html=True)


# ---------- chat page ----------

def page_chat(categories: list[dict]) -> None:
    header("AI Assistant", "Log and explore your expenses in plain English.")

    prompt = st.chat_input("Ask anything, e.g. I spent 250 on lunch today with UPI")
    prompt = prompt or ss.pop("pending", None)
    visible = [m for m in ss.messages if m["role"] in ("user", "assistant") and m.get("content")]

    if not visible and not prompt:
        st.markdown(
            '<div class="hero"><span class="hero-badge">AI expense assistant</span>'
            '<div class="hero-title">What did you <span>spend</span> on today?</div>'
            "<div class=\"hero-text\">Tell me in plain English. I'll log it, put it in the right category and "
            "summarise your spending whenever you ask.</div></div>",
            unsafe_allow_html=True,
        )
        cols = st.columns(2)
        for i, (label, text) in enumerate(SUGGESTIONS):
            cols[i % 2].button(f"**{label}**  \n{text}", key=f"sugg_{i}", width="stretch",
                               on_click=lambda t=text: ss.update(pending=t))
        return

    for m in visible:
        st.chat_message(m["role"], avatar=AVATARS[m["role"]]).markdown(m["content"])

    if prompt:
        st.chat_message("user", avatar=AVATARS["user"]).markdown(prompt)
        with st.chat_message("assistant", avatar=AVATARS["assistant"]):
            with st.spinner("Thinking..."):
                try:
                    reply, messages = asyncio.run(llm_client.chat(prompt, ss.messages))
                except Exception as e:
                    if "429" in str(e) or "quota" in str(e).lower():
                        st.error(f"The {llm_client.PROVIDER.title()} usage limit has been reached. Wait for it to "
                                 "reset, or switch LLM_PROVIDER / the model in your .env file.")
                    else:
                        st.error(f"LLM error: {e}")
                    return
        ss.messages = messages
        title = prompt if len(prompt) <= 40 else prompt[:40].rstrip() + "…"
        ss.chat_id = db.save_chat(ss.chat_id, title, messages)
        st.rerun()


# ---------- expenses page ----------

def expense_form(key: str, categories: list[str], expense: dict | None = None) -> dict | None:
    """Form shared by add and edit. Returns the submitted values or None."""
    e = expense or {}
    with st.form(key, border=False):
        c1, c2 = st.columns([2, 1])
        title = c1.text_input("Title *", e.get("title", ""), placeholder="e.g. Lunch at Café")
        amount = c2.number_input("Amount *", min_value=0.0, step=10.0, value=float(e.get("amount", 0.0)))

        c1, c2, c3 = st.columns(3)
        expense_date = c1.date_input(
            "Date", date.fromisoformat(e["expense_date"]) if e.get("expense_date") else date.today()
        )
        cat = e.get("category") or "Other"
        category = c2.selectbox("Category", categories, index=categories.index(cat) if cat in categories else 0)
        pm = e.get("payment_method") or "Cash"
        payment_method = c3.selectbox(
            "Payment method", PAYMENT_METHODS, index=PAYMENT_METHODS.index(pm) if pm in PAYMENT_METHODS else 0
        )

        c1, c2, c3 = st.columns(3)
        merchant = c1.text_input("Merchant", e.get("merchant") or "")
        subcategory = c2.text_input("Subcategory", e.get("subcategory") or "")
        currency = c3.text_input("Currency", e.get("currency", "INR"))

        tags = st.text_input("Tags", e.get("tags") or "", placeholder="Comma-separated, e.g. work, team")
        notes = st.text_area("Notes", e.get("notes") or "", height=80)
        is_recurring = st.toggle("Recurring expense", bool(e.get("is_recurring")))

        if not st.form_submit_button("Save changes" if expense else "Add expense", type="primary", width="stretch"):
            return None
        if not title or amount <= 0:
            st.warning("Title and an amount greater than 0 are required.")
            return None
        return {
            "title": title, "amount": amount, "currency": currency,
            "expense_date": expense_date.isoformat(), "category": category,
            "subcategory": subcategory, "payment_method": payment_method,
            "merchant": merchant, "tags": tags, "notes": notes, "is_recurring": is_recurring,
        }


def _expense_saved(message: str) -> None:
    ss.table_ver += 1  # clears the table selection
    flash(message)
    st.rerun()


@st.dialog("Add expense", width="large")
def add_expense_dialog(categories: list[str]) -> None:
    data = expense_form("add_form", categories)
    if data and tool("add_expense", data):
        _expense_saved("Expense added")


@st.dialog("Edit expense", width="large")
def edit_expense_dialog(expense: dict, categories: list[str]) -> None:
    data = expense_form(f"edit_form_{expense['id']}", categories, expense)
    if data and tool("update_expense", {"expense_id": expense["id"], **data}):
        _expense_saved("Expense updated")


@st.dialog("Delete expense")
def delete_expense_dialog(expense: dict) -> None:
    st.markdown(f"Delete **{escape(expense['title'])}** ({money(expense['amount'])}) "
                f"from {expense['expense_date']}? This can't be undone.")
    c1, c2 = st.columns(2)
    if c1.button("Cancel", width="stretch"):
        st.rerun()
    if c2.button("Delete", type="primary", width="stretch", icon=":material/delete:"):
        if tool("delete_expense", {"expense_id": expense["id"]}):
            _expense_saved("Expense deleted")


def page_expenses(categories: list[dict]) -> None:
    header("Expenses", "Track, search and manage every transaction.")
    names = [c["name"] for c in categories]
    today = date.today()

    with st.container(key="card_filters"):
        c1, c2, c3, c4 = st.columns([2, 1.5, 2.2, 1.3], vertical_alignment="bottom")
        start, end = date_bounds(c1.date_input("Date range", (today.replace(day=1), today), key="exp_range"))
        category = c2.selectbox("Category", ["All"] + names, key="exp_cat")
        search = c3.text_input("Search", placeholder="Title, merchant, notes…", key="exp_search")
        if c4.button("Add expense", icon=":material/add:", type="primary", width="stretch"):
            add_expense_dialog(names)

    expenses = tool("list_expenses", {
        "start_date": start.isoformat() if start else None,
        "end_date": end.isoformat() if end else None,
        "category": None if category == "All" else category,
        "search": search or None,
        "limit": 500,
    }) or []

    st.write("")
    amounts = [e["amount"] for e in expenses]
    k1, k2, k3, k4 = st.columns(4)
    kpi(k1, "Total spent", money(sum(amounts)), "Selected period", accent=True)
    kpi(k2, "Transactions", str(len(expenses)), "Matching filters")
    kpi(k3, "Average", money(sum(amounts) / len(amounts) if amounts else 0), "Per transaction")
    kpi(k4, "Largest", money(max(amounts) if amounts else 0),
        max(expenses, key=lambda e: e["amount"])["title"] if expenses else "")
    st.write("")

    with st.container(key="card_table"):
        st.markdown('<div class="card-title">Transactions</div>'
                    '<div class="card-sub">Select a row to edit or delete it.</div>', unsafe_allow_html=True)
        if not expenses:
            empty_state("No expenses found", "Try a different date range or add a new expense.")
            return

        df = pd.DataFrame(expenses)
        df["expense_date"] = pd.to_datetime(df["expense_date"])
        df = df[["expense_date", "title", "category", "amount", "payment_method", "merchant", "tags"]]
        df = df.fillna({"category": "Uncategorised", "payment_method": "", "merchant": "", "tags": ""})
        event = st.dataframe(
            df, hide_index=True, width="stretch", height=min(42 + 35 * len(df), 460),
            on_select="rerun", selection_mode="single-row", key=f"exp_table_{ss.table_ver}",
            column_config={
                "expense_date": st.column_config.DateColumn("Date", format="DD MMM YYYY"),
                "title": st.column_config.TextColumn("Title", width="medium"),
                "category": "Category",
                "amount": st.column_config.NumberColumn("Amount", format="₹%.2f"),
                "payment_method": "Payment",
                "merchant": "Merchant",
                "tags": "Tags",
            },
        )
        rows = event.selection.rows
        if rows:
            selected = expenses[rows[0]]
            c1, c2, _ = st.columns([1, 1, 4])
            if c1.button("Edit", icon=":material/edit:", width="stretch"):
                edit_expense_dialog(selected, names)
            if c2.button("Delete", icon=":material/delete:", width="stretch"):
                delete_expense_dialog(selected)


# ---------- categories page ----------

def category_form(key: str, category: dict | None = None) -> dict | None:
    c = category or {}
    with st.form(key, border=False):
        name = st.text_input("Name *", c.get("name", ""))
        description = st.text_input("Description", c.get("description") or "")
        c1, c2 = st.columns([1, 3])
        color = c1.color_picker("Colour", c.get("color") or PRIMARY)
        budget = c2.number_input("Monthly budget (0 = no budget)", min_value=0.0, step=500.0,
                                 value=float(c.get("budget_limit") or 0))
        if not st.form_submit_button("Save changes" if category else "Add category", type="primary", width="stretch"):
            return None
        if not name.strip():
            st.warning("Name is required.")
            return None
        return {"name": name.strip(), "description": description, "color": color, "budget_limit": budget or None}


@st.dialog("New category")
def add_category_dialog() -> None:
    data = category_form("add_category")
    if data and tool("add_category", data):
        flash("Category added")
        st.rerun()


@st.dialog("Edit category")
def edit_category_dialog(category: dict) -> None:
    data = category_form(f"edit_category_{category['id']}", category)
    if data:
        data["budget_limit"] = data["budget_limit"] or 0
        if tool("update_category", {"category_id": category["id"], **data}):
            flash("Category updated")
            st.rerun()


@st.dialog("Delete category")
def delete_category_dialog(category: dict) -> None:
    st.markdown(f"Delete **{escape(category['name'])}**? Its expenses will become uncategorised.")
    c1, c2 = st.columns(2)
    if c1.button("Cancel", width="stretch"):
        st.rerun()
    if c2.button("Delete", type="primary", width="stretch", icon=":material/delete:"):
        if tool("delete_category", {"category_id": category["id"]}):
            flash("Category deleted")
            st.rerun()


def page_categories(categories: list[dict]) -> None:
    header("Categories", "Organise your spending and set monthly budgets.")
    today = date.today()
    report = tool("monthly_summary", {"year": today.year, "month": today.month}) or []
    spent_by = {r["category"]: r["spent"] for r in report}

    left, right = st.columns([5, 1.3], vertical_alignment="center")
    left.markdown(f'<div class="card-sub" style="margin:0">{len(categories)} categories · '
                  f'spending shown for {today.strftime("%B %Y")}</div>', unsafe_allow_html=True)
    if right.button("New category", icon=":material/add:", type="primary", width="stretch"):
        add_category_dialog()
    st.write("")

    if not categories:
        empty_state("No categories yet", "Create one to start organising your expenses.")
        return

    cols = st.columns(3)
    for i, c in enumerate(categories):
        spent = spent_by.get(c["name"], 0) or 0
        budget = c.get("budget_limit") or 0
        if budget:
            pct = spent / budget * 100
            over = spent > budget
            bar_color = DANGER if over else PRIMARY
            meta = f"of {money(budget)} budget"
            pill = (f'<span class="pill over">Over by {money(spent - budget)}</span>' if over
                    else f'<span class="pill ok">{pct:.0f}% used</span>')
            bar = f'<div class="bar"><div style="width:{min(pct, 100):.1f}%;background:{bar_color}"></div></div>'
        else:
            meta, pill = "spent this month", '<span class="pill none">No budget</span>'
            bar = '<div class="bar"><div style="width:0"></div></div>'

        with cols[i % 3], st.container(key=f"card_cat_{c['id']}"):
            st.markdown(
                f'<div class="cat-head"><span class="cat-dot" style="background:{escape(c["color"] or "#888")}"></span>'
                f'<span class="cat-name">{escape(c["name"])}</span></div>'
                f'<div class="cat-desc">{escape(c.get("description") or "")}</div>'
                f'<div class="cat-amount">{money(spent)}</div><div class="cat-meta">{meta}</div>'
                f'{bar}{pill}',
                unsafe_allow_html=True,
            )
            b1, b2, _ = st.columns([1, 1, 3])
            if b1.button("", icon=":material/edit:", key=f"edit_cat_{c['id']}", help="Edit", type="tertiary"):
                edit_category_dialog(c)
            if b2.button("", icon=":material/delete:", key=f"delete_cat_{c['id']}", help="Delete", type="tertiary"):
                delete_category_dialog(c)


# ---------- dashboard page ----------

def period_bounds(period: str) -> tuple[date | None, date]:
    today = date.today()
    first = today.replace(day=1)
    if period == "Last month":
        end = first - timedelta(days=1)
        return end.replace(day=1), end
    if period == "Last 30 days":
        return today - timedelta(days=29), today
    if period == "This year":
        return today.replace(month=1, day=1), today
    if period == "All time":
        return None, today
    return first, today


def page_dashboard(categories: list[dict]) -> None:
    header("Dashboard", "A clear view of where your money goes.")
    period = st.segmented_control(
        "Period", ["This month", "Last month", "Last 30 days", "This year", "All time"],
        default="This month", key="dash_period", label_visibility="collapsed",
    ) or "This month"
    start, end = period_bounds(period)
    args = {"start_date": start.isoformat() if start else None, "end_date": end.isoformat()}

    summary = tool("summarize_expenses", args) or {}
    expenses = tool("list_expenses", {**args, "limit": 5000}) or []
    by_category = summary.get("by_category", [])
    by_date = summary.get("by_date", [])
    total = summary.get("total", 0) or 0

    first_day = start or (date.fromisoformat(by_date[0]["date"]) if by_date else end)
    days = max((end - first_day).days + 1, 1)

    st.write("")
    k1, k2, k3, k4 = st.columns(4)
    kpi(k1, "Total spent", money(total), period, accent=True)
    kpi(k2, "Transactions", str(summary.get("count", 0)), f"Across {len(by_category)} categories")
    kpi(k3, "Daily average", money(total / days), f"Over {days} days")
    kpi(k4, "Top category", by_category[0]["category"] if by_category else "—",
        money(by_category[0]["total"]) if by_category else "")
    st.write("")

    if not by_category:
        with st.container(key="card_empty_dash"):
            empty_state("No spending in this period", "Add expenses or pick a different period.")
    else:
        c1, c2 = st.columns([3, 2])
        with c1, st.container(key="card_trend"):
            st.markdown('<div class="card-title">Spending over time</div>'
                        '<div class="card-sub">Daily totals</div>', unsafe_allow_html=True)
            df = pd.DataFrame(by_date)
            df["date"] = pd.to_datetime(df["date"])
            gradient = alt.Gradient(
                gradient="linear", x1=1, x2=1, y1=1, y2=0,
                stops=[alt.GradientStop(color="rgba(243,189,0,0.02)", offset=0),
                       alt.GradientStop(color="rgba(243,189,0,0.45)", offset=1)],
            )
            base = alt.Chart(df).encode(
                x=alt.X("date:T", title=None, axis=alt.Axis(format="%d %b", grid=False)),
                y=alt.Y("total:Q", title=None, axis=alt.Axis(format="~s")),
                tooltip=[alt.Tooltip("date:T", title="Date", format="%d %b %Y"),
                         alt.Tooltip("total:Q", title="Spent (₹)", format=",.2f")],
            )
            chart = (base.mark_area(color=gradient, interpolate="monotone")
                     + base.mark_line(color=PRIMARY, strokeWidth=2.5, interpolate="monotone")
                     + base.mark_circle(color=DARK, size=40))
            st.altair_chart(style_chart(chart), width="stretch", theme=None)

        with c2, st.container(key="card_cats"):
            st.markdown('<div class="card-title">By category</div>'
                        '<div class="card-sub">Where the money went</div>', unsafe_allow_html=True)
            df = pd.DataFrame(by_category).head(8)
            chart = alt.Chart(df).mark_bar(color=PRIMARY, cornerRadiusEnd=6, height=18).encode(
                y=alt.Y("category:N", sort="-x", title=None, axis=alt.Axis(labelLimit=110)),
                x=alt.X("total:Q", title=None, axis=alt.Axis(format="~s")),
                tooltip=[alt.Tooltip("category:N", title="Category"),
                         alt.Tooltip("total:Q", title="Spent (₹)", format=",.2f"),
                         alt.Tooltip("count:Q", title="Transactions")],
            )
            st.altair_chart(style_chart(chart), width="stretch", theme=None)

        st.write("")
        c1, c2 = st.columns([2, 3])
        with c1, st.container(key="card_payments"):
            st.markdown('<div class="card-title">Payment methods</div>'
                        '<div class="card-sub">Share of total spend</div>', unsafe_allow_html=True)
            pay = (pd.DataFrame(expenses).fillna({"payment_method": "Other"})
                   .groupby("payment_method", as_index=False)["amount"].sum())
            chart = alt.Chart(pay).mark_arc(innerRadius=62, cornerRadius=4, padAngle=0.02).encode(
                theta="amount:Q",
                color=alt.Color("payment_method:N", title=None,
                                scale=alt.Scale(range=CHART_COLORS), legend=alt.Legend(orient="bottom")),
                tooltip=[alt.Tooltip("payment_method:N", title="Method"),
                         alt.Tooltip("amount:Q", title="Spent (₹)", format=",.2f")],
            )
            st.altair_chart(style_chart(chart, height=260), width="stretch", theme=None)

        with c2, st.container(key="card_recent"):
            st.markdown('<div class="card-title">Recent transactions</div>'
                        '<div class="card-sub">Latest in this period</div>', unsafe_allow_html=True)
            recent = pd.DataFrame(expenses[:6])[["expense_date", "title", "category", "amount"]]
            recent["expense_date"] = pd.to_datetime(recent["expense_date"])
            st.dataframe(recent, hide_index=True, width="stretch", column_config={
                "expense_date": st.column_config.DateColumn("Date", format="DD MMM"),
                "title": "Title", "category": "Category",
                "amount": st.column_config.NumberColumn("Amount", format="₹%.2f"),
            })

    st.write("")
    month = end
    with st.container(key="card_budget"):
        st.markdown(f'<div class="card-title">Budget vs. actual</div>'
                    f'<div class="card-sub">{month.strftime("%B %Y")}</div>', unsafe_allow_html=True)
        report = tool("monthly_summary", {"year": month.year, "month": month.month}) or []
        if not report:
            empty_state("Nothing to compare yet", "Set budgets on the Categories page to track them here.")
            return
        df = pd.DataFrame(report)
        df["used"] = df.apply(
            lambda r: min(r["spent"] / r["budget_limit"] * 100, 100) if r["budget_limit"] else None, axis=1)
        df["status"] = df.apply(
            lambda r: "No budget" if not r["budget_limit"] else "Over budget" if r["over_budget"] else "On track",
            axis=1)
        st.dataframe(df[["category", "spent", "budget_limit", "remaining", "used", "status"]],
                     hide_index=True, width="stretch", column_config={
                         "category": "Category",
                         "spent": st.column_config.NumberColumn("Spent", format="₹%.2f"),
                         "budget_limit": st.column_config.NumberColumn("Budget", format="₹%.2f"),
                         "remaining": st.column_config.NumberColumn("Remaining", format="₹%.2f"),
                         "used": st.column_config.ProgressColumn("Used", min_value=0, max_value=100, format="%.0f%%"),
                         "status": "Status",
                     })


# ---------- router ----------

if message := ss.pop("flash", None):
    st.toast(message, icon=":material/check_circle:")

render_sidebar()
all_categories = tool("list_categories") or []
{
    "Chat": page_chat,
    "Expenses": page_expenses,
    "Categories": page_categories,
    "Dashboard": page_dashboard,
}[ss.page](all_categories)
