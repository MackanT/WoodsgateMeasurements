from nicegui import ui

import pandas as pd

from datetime import datetime, timedelta, date
from statistics import mean, stdev
from webgui.repository import WaterDataRepository

ACCENT: str = "#006400"

# Global repository instance - will be initialized in run()
_repository: WaterDataRepository | None = None


def _convert_ui_date_to_date(ui_date_value) -> date:
    """Convert NiceGUI date input value to date object.

    Args:
        ui_date_value: Value from NiceGUI date input (could be string or date object)

    Returns:
        date object
    """
    if isinstance(ui_date_value, date):
        return ui_date_value
    elif isinstance(ui_date_value, datetime):
        return ui_date_value.date()
    elif isinstance(ui_date_value, str):
        return datetime.strptime(ui_date_value, "%Y-%m-%d").date()
    else:
        # Fallback - convert to string first
        return datetime.strptime(str(ui_date_value), "%Y-%m-%d").date()


def get_data(
    start: datetime | date,
    end: datetime | date,
    granularity: str,
    repository: WaterDataRepository,
) -> pd.DataFrame:
    df = repository.get_data_by_date_range(start, end)

    # Always apply resampling based on granularity
    freq_map: dict[str, str] = {
        "minute": "T",
        "hour": "H",
        "day": "D",
        "week": "W",
        "month": "M",
    }
    df = df.set_index("time").resample(freq_map[granularity]).mean().reset_index()

    return df


def create_pump_tab() -> None:
    if _repository is None:
        raise RuntimeError("Repository not initialized. Call run() first.")

    repository = _repository
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
                        value=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
                    )

                with ui.column().classes("items-center"):
                    ui.label("End Date")
                    end_input = ui.date(value=datetime.now().strftime("%Y-%m-%d"))

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
                            ["minute", "hour", "day", "week", "month"],
                            value="day",
                        ).classes("w-48")
                        ui.label("Note: 'minute' auto-limited to 7 days").classes(
                            "text-xs text-gray-500 mt-1"
                        )

            def update_graph() -> None:
                # Convert string values from NiceGUI to datetime objects immediately
                start_date: date = _convert_ui_date_to_date(start_input.value)
                end_date: date = _convert_ui_date_to_date(end_input.value)
                granularity = granularity_input.value

                # Check time range limits for performance-sensitive granularities
                date_range = (end_date - start_date).days
                max_days_for_granularity = {"minute": 7}

                if granularity in max_days_for_granularity:
                    max_allowed_days = max_days_for_granularity[granularity]
                    if date_range > max_allowed_days:
                        # Automatically adjust the date range to the last week
                        new_start_date = end_date - timedelta(days=max_allowed_days)

                        # Update the date pickers
                        start_input.set_value(new_start_date.strftime("%Y-%m-%d"))

                        # Update our local variables
                        start_date = new_start_date

                        # Notify the user about the automatic adjustment
                        ui.notify(
                            f"Date range automatically limited to {max_allowed_days} days for '{granularity}' granularity "
                            f"(was {date_range} days). Start date adjusted to {new_start_date.strftime('%Y-%m-%d')}.",
                            type="warning",
                            timeout=5000,
                        )

                df = repository.get_data_by_date_range(start_date, end_date)

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

                # Always apply resampling based on granularity
                freq_map: dict[str, str] = {
                    "minute": "min",
                    "hour": "h",
                    "day": "d",
                    "week": "W",
                    "month": "ME",
                }
                df.set_index("time", inplace=True)
                groups = df.groupby(pd.Grouper(freq=freq_map[granularity]))

                data: list[tuple[datetime, float, str]] = []
                for time_val, group in groups:
                    if group.empty:
                        continue
                    l_vals: list[float] = group["level"].dropna().tolist()
                    v_vals: list[float] = group["volume"].dropna().tolist()
                    if not l_vals or not v_vals:
                        continue
                    n = min(len(l_vals), len(v_vals))
                    l_min, l_max = min(l_vals), max(l_vals)
                    v_min, v_max = min(v_vals), max(v_vals)
                    l_mean_val = mean(l_vals)
                    v_mean_val = mean(v_vals)
                    l_std = stdev(l_vals) if len(l_vals) > 1 else 0
                    v_std = stdev(v_vals) if len(v_vals) > 1 else 0

                    tooltip: str = (
                        f"Time: {time_val.strftime('%Y-%m-%d %H:%M')}<br>"
                        f"Level: [{l_min:.2f}↓, {l_max:.2f}↑] ({l_mean_val:.2f} ± {l_std:.2f})<br>"
                        f"Volume: [{v_min:.2f}↓, {v_max:.2f}↑] ({v_mean_val:.2f} ± {v_std:.2f})<br>"
                        f"Number of data points: {n}"
                    )

                    data.append((time_val.to_pydatetime(), l_mean_val, tooltip))

                if not data:
                    plot_container.clear()
                    with plot_container:
                        ui.label("No data after aggregation.").classes("text-red-500")
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
                level_vals: list[float] = raw_df["level"].dropna().tolist()
                volume_vals: list[float] = raw_df["volume"].dropna().tolist()

                if level_vals and volume_vals:
                    n: int = min(len(level_vals), len(volume_vals))
                    l_min: float
                    l_max: float
                    l_min, l_max = min(level_vals), max(level_vals)
                    v_min: float
                    v_max: float
                    v_min, v_max = min(volume_vals), max(volume_vals)
                    l_mean_val: float = mean(level_vals)
                    v_mean_val: float = mean(volume_vals)
                    l_std: float = stdev(level_vals) if len(level_vals) > 1 else 0
                    v_std: float = stdev(volume_vals) if len(volume_vals) > 1 else 0

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
            granularity_input.on(
                "change", update_graph
            )  # Auto-update when granularity changes
            update_graph()


@ui.page("/")
def index() -> None:
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


def run(
    db_path: str = "data.db",
    host: str = "0.0.0.0",
    port: int = 8080,
    reload: bool = False,
) -> None:
    """Run the web application.

    Args:
        db_path: Path to the SQLite database file (default: "data.db")
        host: Host to bind the server to (default: "0.0.0.0")
        port: Port to bind the server to (default: 8080)
        reload: Enable hot reload for development (default: False)
    """
    global _repository
    _repository = WaterDataRepository(db_path)

    ui.run(
        host=host,
        port=port,
        title="WoodsGate Water Measurements",
        dark=False,
        native=False,
        show=False,
        reload=reload,
        uvicorn_reload_includes="*.py",
        uvicorn_reload_excludes=".*, .pyc, .pyo, .sw.*, ~*",
    )
