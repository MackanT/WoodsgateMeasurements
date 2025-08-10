from nicegui import ui


import sqlite3
import pandas as pd

ACCENT = "#006400"


def get_data(start, end, granularity):
    con = sqlite3.connect("data.db")
    df = pd.read_sql_query(
        "SELECT time, level, volume FROM data WHERE time BETWEEN ? AND ?",
        con,
        params=(start, end),
    )
    con.close()

    df["time"] = pd.to_datetime(df["time"])

    if granularity != "raw":
        freq_map = {
            "minute": "T",
            "hour": "H",
            "day": "D",
            "week": "W",
            "month": "M",
        }
        df = df.set_index("time").resample(freq_map[granularity]).mean().reset_index()

    return df


from datetime import datetime, timedelta
from statistics import mean, stdev


def create_pump_tab():
    with ui.column().classes("w-full items-center"):
        with ui.card().classes("w-full max-w-3xl"):
            ui.label("Well Water Level Over Time").classes("text-2xl font-bold mb-4")

            plot_container = ui.element("div").classes("w-full mt-4")
            stats_container = ui.element("div").classes("w-full mt-4")

            with ui.row().classes("w-full justify-center"):
                update_button = ui.button("Update Graph").classes("mt-4")

            # Date pickers below the graph, centered horizontally
            with ui.row().classes("w-full justify-center gap-8 mt-6 wrap"):
                with ui.column().classes("items-center"):
                    ui.label("Start Date")
                    start_input = ui.date(
                        value=(datetime.now() - timedelta(days=365)).date()
                    )

                with ui.column().classes("items-center"):
                    ui.label("End Date")
                    end_input = ui.date(value=datetime.now().date())

            # Global stats and granularity selector side-by-side below date pickers
            with stats_container:
                with ui.row().classes("items-end justify-between w-full flex-wrap"):
                    with ui.column():
                        ui.label("Global Stats (Selected Date Range)").classes(
                            "text-lg font-semibold"
                        )
                        global_stats_level = ui.label()
                        global_stats_volume = ui.label()
                        global_stats_count = ui.label()
                    with ui.column().classes("items-end"):
                        ui.label("Data Granularity")
                        granularity_input = ui.select(
                            ["raw", "minute", "hour", "day", "week", "month"],
                            value="day",
                        ).classes("w-48")

            def update_graph():
                start = str(start_input.value)
                end = str(end_input.value)
                granularity = granularity_input.value

                con = sqlite3.connect("data.db")
                df = pd.read_sql_query(
                    "SELECT time, level, volume FROM data WHERE time BETWEEN ? AND ?",
                    con,
                    params=(start, end),
                )
                con.close()

                if df.empty:
                    plot_container.clear()
                    with plot_container:
                        ui.label("No data available for the selected range.").classes(
                            "text-red-500"
                        )
                    global_stats_level.set_text("")
                    global_stats_volume.set_text("")
                    global_stats_count.set_text("")
                    return

                df["time"] = pd.to_datetime(df["time"])
                raw_df = df.copy()

                import plotly.graph_objs as go

                fig = go.Figure()

                if granularity != "raw":
                    freq_map = {
                        "minute": "T",
                        "hour": "H",
                        "day": "D",
                        "week": "W",
                        "month": "M",
                    }
                    df.set_index("time", inplace=True)
                    groups = df.groupby(pd.Grouper(freq=freq_map[granularity]))

                    data = []
                    for time_val, group in groups:
                        if group.empty:
                            continue
                        l_vals = group["level"].dropna().tolist()
                        v_vals = group["volume"].dropna().tolist()
                        if not l_vals or not v_vals:
                            continue
                        n = min(len(l_vals), len(v_vals))
                        l_min, l_max = min(l_vals), max(l_vals)
                        v_min, v_max = min(v_vals), max(v_vals)
                        l_mean_val = mean(l_vals)
                        v_mean_val = mean(v_vals)
                        l_std = stdev(l_vals) if len(l_vals) > 1 else 0
                        v_std = stdev(v_vals) if len(v_vals) > 1 else 0

                        tooltip = (
                            f"Time: {time_val.strftime('%Y-%m-%d %H:%M')}<br>"
                            f"Level: [{l_min:.2f}↓, {l_max:.2f}↑] ({l_mean_val:.2f} ± {l_std:.2f})<br>"
                            f"Volume: [{v_min:.2f}↓, {v_max:.2f}↑] ({v_mean_val:.2f} ± {v_std:.2f})<br>"
                            f"Number of data points: {n}"
                        )

                        data.append((time_val.to_pydatetime(), l_mean_val, tooltip))

                    if not data:
                        plot_container.clear()
                        with plot_container:
                            ui.label("No data after aggregation.").classes(
                                "text-red-500"
                            )
                        global_stats_level.set_text("")
                        global_stats_volume.set_text("")
                        global_stats_count.set_text("")
                        return

                    times, levels, tooltips = zip(*data)
                    fig.add_trace(
                        go.Scatter(
                            x=times,
                            y=levels,
                            mode="lines+markers",
                            hoverinfo="text",
                            text=tooltips,
                            name="Water Level (Aggregated)",
                        )
                    )
                else:
                    df.dropna(inplace=True)
                    fig.add_trace(
                        go.Scatter(
                            x=df["time"],
                            y=df["level"],
                            mode="lines+markers",
                            hoverinfo="text",
                            text=[
                                f"Time: {t.strftime('%Y-%m-%d %H:%M')}<br>Level: {l:.2f}<br>Volume: {v:.2f}"
                                for t, l, v in zip(
                                    df["time"], df["level"], df["volume"]
                                )
                            ],
                            name="Water Level",
                            marker=dict(color=ACCENT),
                        )
                    )

                fig.update_layout(
                    xaxis_title="Time",
                    yaxis_title="Level",
                    title="Water Level Over Time",
                    yaxis=dict(range=[0, 3.3]),
                    margin=dict(l=20, r=20, t=40, b=20),
                    height=400,
                )

                plot_container.clear()
                with plot_container:
                    ui.plotly(fig).classes("w-full")

                # Update global stats below
                level_vals = raw_df["level"].dropna().tolist()
                volume_vals = raw_df["volume"].dropna().tolist()

                if level_vals and volume_vals:
                    n = min(len(level_vals), len(volume_vals))
                    l_min, l_max = min(level_vals), max(level_vals)
                    v_min, v_max = min(volume_vals), max(volume_vals)
                    l_mean_val = mean(level_vals)
                    v_mean_val = mean(volume_vals)
                    l_std = stdev(level_vals) if len(level_vals) > 1 else 0
                    v_std = stdev(volume_vals) if len(volume_vals) > 1 else 0

                    global_stats_level.set_text(
                        f"Level: [{l_min:.2f}↓, {l_max:.2f}↑] ({l_mean_val:.2f} ± {l_std:.2f})"
                    )
                    global_stats_volume.set_text(
                        f"Volume: [{v_min:.2f}↓, {v_max:.2f}↑] ({v_mean_val:.2f} ± {v_std:.2f})"
                    )
                    global_stats_count.set_text(f"Number of data points: {n}")
                else:
                    global_stats_level.set_text("No data")
                    global_stats_volume.set_text("")
                    global_stats_count.set_text("")

            update_button.on("click", update_graph)
            update_graph()


@ui.page("/")
def index():
    ui.colors(primary=ACCENT)

    with ui.tabs().classes("w-full justify-center") as tabs:
        pump_tab = ui.tab("Pump")
        temp_tab = ui.tab("Temp")

    with ui.tab_panels(tabs, value=pump_tab).classes("w-full"):
        with ui.tab_panel(pump_tab):
            create_pump_tab()

        with ui.tab_panel(temp_tab):
            ui.label("Temperature Data Coming Soon...").classes("text-lg text-gray-500")

    ui.add_head_html("""
    <style>
        body {
            font-family: 'Segoe UI', sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f9fafb;
        }
        .nicegui-content {
            padding: 1rem;
        }
    </style>
    """)


def run():
    ui.run(host="0.0.0.0", port=8080, reload=False)
