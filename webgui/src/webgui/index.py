from nicegui import ui

import pandas as pd

import plotly.express as px
from datetime import datetime, timedelta, date
from statistics import mean, stdev
from webgui.repository import WaterDataRepository
from webgui.postgress_db import SensorDataRepository

ACCENT: str = "#006400"

# Must match `tank_height` in woodsgate_collector/data_collector.py - used only
# to show a "% full" hint on the current-level card.
TANK_HEIGHT_M: float = 3.11
# Level below which the status card flags a low-water warning. Tune to taste.
LOW_LEVEL_WARNING_M: float = 0.5

# Global repository instances - will be initialized in run()
_repository: WaterDataRepository | None = None
_new_repository: SensorDataRepository | None = None


def _format_stat_html(label: str, mean_val: float, std_val: float, min_val: float, max_val: float) -> str:
    """Build a compact stats line with the headline number made to stand out.

    Renders as: "Label:  <big bold value>  ± std [min, max]" with the mean
    value emphasized (bold, larger, accent-colored) so it can be read at a
    glance, and the spread (± std / range) shown smaller and muted since it's
    secondary detail.
    """
    return (
        f'<span class="text-sm text-gray-500">{label}:</span> '
        f'<span class="text-2xl font-bold" style="color:{ACCENT}">{mean_val:.2f}</span> '
        f'<span class="text-xs text-gray-500">± {std_val:.2f} &nbsp;[{min_val:.2f}, {max_val:.2f}]</span>'
    )


def _format_current_value_html(label: str, value: float, color: str, extra: str = "") -> str:
    """Build a large, bold "current value" line for a status card."""
    extra_html = f' <span class="text-sm text-gray-500">{extra}</span>' if extra else ""
    return (
        f'<div class="text-sm text-gray-500">{label}</div>'
        f'<div class="text-3xl font-bold" style="color:{color}">{value:.2f}</div>'
        f'{extra_html}'
    )


def _time_ago_str(when: datetime) -> str:
    """Render a datetime as a short "X ago" string."""
    delta = datetime.now() - when
    seconds = delta.total_seconds()
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h ago"
    return f"{int(seconds // 86400)}d ago"


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


def create_pump_tab() -> None:
    if _repository is None:
        raise RuntimeError("Repository not initialized. Call run() first.")

    repository = _repository
    with ui.column().classes("w-full items-center"):
        # Current-status card: latest reading at a glance, independent of
        # whatever date range is selected in the chart card below.
        with ui.card().classes("w-full max-w-3xl"):
            ui.label("Current Status").classes("text-lg font-semibold mb-2")
            with ui.row().classes("w-full justify-around items-start"):
                status_level = ui.html()
                status_volume = ui.html()
            status_updated = ui.label().classes("text-xs text-gray-500 mt-2")

        def refresh_status_card() -> None:
            latest = repository.get_latest_measurement()
            if latest.empty:
                status_level.set_content("")
                status_volume.set_content("")
                status_updated.set_text("No measurements yet.")
                return

            row = latest.iloc[0]
            level = float(row["level"])
            volume = float(row["volume"])
            when: datetime = row["time"].to_pydatetime()

            is_low = level < LOW_LEVEL_WARNING_M
            level_color = "#b91c1c" if is_low else ACCENT
            pct_full = 100 * level / TANK_HEIGHT_M if TANK_HEIGHT_M else 0
            status_level.set_content(
                _format_current_value_html(
                    "Level", level, level_color, f"({pct_full:.0f}% full)"
                )
            )
            status_volume.set_content(
                _format_current_value_html("Volume", volume, ACCENT)
            )

            # Note: the collector only writes a new row when the level
            # actually changes, so a long gap here doesn't necessarily mean
            # the collector is down - it may just mean the level's been
            # steady. Only the low-level case is flagged as a real warning.
            status_updated.set_text(
                f"Last measurement: {when.strftime('%Y-%m-%d %H:%M')} ({_time_ago_str(when)})"
                + ("  •  LOW WATER LEVEL" if is_low else "")
            )
            status_updated.classes(
                replace="text-xs mt-2 font-semibold text-red-600"
                if is_low
                else "text-xs mt-2 text-gray-500"
            )

        with ui.card().classes("w-full max-w-3xl mt-4"):
            ui.label("Well Water Level Over Time").classes("text-2xl font-bold mb-4")

            plot_container = ui.element("div").classes("w-full mt-4")
            stats_container = ui.element("div").classes("w-full mt-4")

            with ui.row().classes("w-full justify-center gap-2"):
                update_button = ui.button("Update Graph").classes("mt-4")
                export_button = (
                    ui.button("Export CSV", icon="download")
                    .classes("mt-4")
                    .props("outline")
                )

            # Quick range presets
            with ui.row().classes("w-full justify-center gap-2 mt-2"):

                def set_range(range_start: date, range_end: date) -> None:
                    start_input.set_value(range_start.strftime("%Y-%m-%d"))
                    end_input.set_value(range_end.strftime("%Y-%m-%d"))
                    update_graph()

                def set_all_time() -> None:
                    earliest = repository.get_earliest_measurement()
                    range_start = (
                        earliest.iloc[0]["time"].date()
                        if not earliest.empty
                        else datetime.now().date()
                    )
                    set_range(range_start, datetime.now().date())

                today = datetime.now().date()
                ui.button(
                    "Today", on_click=lambda: set_range(today, today)
                ).props("dense flat size=sm")
                ui.button(
                    "7d", on_click=lambda: set_range(today - timedelta(days=7), today)
                ).props("dense flat size=sm")
                ui.button(
                    "30d", on_click=lambda: set_range(today - timedelta(days=30), today)
                ).props("dense flat size=sm")
                ui.button(
                    "90d", on_click=lambda: set_range(today - timedelta(days=90), today)
                ).props("dense flat size=sm")
                ui.button("All", on_click=set_all_time).props("dense flat size=sm")

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
                        global_stats_level = ui.html()
                        global_stats_volume = ui.html()
                        global_stats_count = ui.label().classes("text-xs text-gray-500")
                    with ui.column().classes("items-end"):
                        ui.label("Data Granularity")
                        granularity_input = ui.select(
                            ["minute", "hour", "day", "week", "month"],
                            value="day",
                        ).classes("w-48")
                        ui.label("Note: 'minute' auto-limited to 7 days").classes(
                            "text-xs text-gray-500 mt-1"
                        )

            def export_csv() -> None:
                start_date = _convert_ui_date_to_date(start_input.value)
                end_date = _convert_ui_date_to_date(end_input.value)
                export_df = repository.get_data_by_date_range(start_date, end_date)
                if export_df.empty:
                    ui.notify("No data to export for the selected range.", type="warning")
                    return
                csv_bytes = export_df.to_csv(index=False).encode("utf-8")
                ui.download(
                    csv_bytes,
                    filename=f"waterlevel_{start_date}_{end_date}.csv",
                    media_type="text/csv",
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
                    global_stats_level.set_content("")
                    global_stats_volume.set_content("")
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

                data: list[tuple[datetime, float, float, str]] = []
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

                    # Headline value (Level) bolded and first so it's the
                    # first thing the eye lands on; range shown compactly
                    # instead of separate ± / range lines, and Time/count
                    # demoted to a single trailing line.
                    tooltip: str = (
                        f"<b>Level: {l_mean_val:.2f}</b> ({l_min:.2f}–{l_max:.2f})<br>"
                        f"Volume: {v_mean_val:.2f} ({v_min:.2f}–{v_max:.2f})<br>"
                        f"{time_val.strftime('%Y-%m-%d %H:%M')} · n={n}"
                    )

                    data.append((time_val.to_pydatetime(), l_mean_val, v_mean_val, tooltip))

                if not data:
                    plot_container.clear()
                    with plot_container:
                        ui.label("No data after aggregation.").classes("text-red-500")
                    global_stats_level.set_content("")
                    global_stats_volume.set_content("")
                    global_stats_count.set_text("")
                    return

                times, levels, volumes, tooltips = zip(*data)
                fig.add_trace(
                    go.Scatter(
                        x=times,
                        y=levels,
                        mode="lines+markers",
                        hoverinfo="text",
                        text=tooltips,
                        name="Water Level",
                        line=dict(color=ACCENT),
                    )
                )
                # Volume plotted on its own axis for context; the tooltip on
                # the Level trace above already covers both values, so this
                # trace skips hover to avoid showing two overlapping tooltips.
                fig.add_trace(
                    go.Scatter(
                        x=times,
                        y=volumes,
                        mode="lines",
                        hoverinfo="skip",
                        name="Volume",
                        yaxis="y2",
                        line=dict(color="#94a3b8", dash="dot"),
                        opacity=0.7,
                    )
                )
                fig.add_hline(
                    y=LOW_LEVEL_WARNING_M,
                    line_dash="dot",
                    line_color="#dc2626",
                    annotation_text="Low level warning",
                    annotation_position="bottom right",
                )

                fig.update_layout(
                    xaxis_title="Time",
                    yaxis_title="Level",
                    yaxis=dict(range=[0, 3.3]),
                    yaxis2=dict(title="Volume", overlaying="y", side="right", showgrid=False),
                    title="Water Level Over Time",
                    margin=dict(l=20, r=20, t=40, b=20),
                    height=400,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0.5, xanchor="center"),
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

                    global_stats_level.set_content(
                        _format_stat_html("Level", l_mean_val, l_std, l_min, l_max)
                    )
                    global_stats_volume.set_content(
                        _format_stat_html("Volume", v_mean_val, v_std, v_min, v_max)
                    )
                    global_stats_count.set_text(f"n = {n} data points")
                else:
                    global_stats_level.set_content("No data")
                    global_stats_volume.set_content("")
                    global_stats_count.set_text("")

                refresh_status_card()

            update_button.on("click", update_graph)
            export_button.on("click", export_csv)
            granularity_input.on(
                "change", update_graph
            )  # Auto-update when granularity changes
            update_graph()

            # Keep the status card and chart fresh without requiring a
            # manual click - the status card is a cheap single-row query so
            # it refreshes more often than the full chart.
            ui.timer(60.0, refresh_status_card, immediate=False)
            ui.timer(300.0, update_graph, immediate=False)

def create_vvp_tab() -> None:
    if _new_repository is None:
        raise RuntimeError("Postgress Repository not initialized. Call run() first.")

    repository = _new_repository
    
    # Initial date range
    initial_start = datetime.now() - timedelta(days=7)
    initial_end = datetime.now()
    
    # Load initial data from all tables with date range
    t_data = repository.get_data_by_date_range("temperatures", initial_start, initial_end)
    alarms_data = repository.get_data_by_date_range("alarms", initial_start, initial_end)
    power_data = repository.get_data_by_date_range("power", initial_start, initial_end)
    pump_data = repository.get_data_by_date_range("pump", initial_start, initial_end)
    
    t_data_labels = t_data['name'].unique().tolist() if not t_data.empty else []
    alarms_labels = alarms_data['name'].unique().tolist() if not alarms_data.empty else []
    power_labels = power_data['name'].unique().tolist() if not power_data.empty else []
    pump_labels = pump_data['name'].unique().tolist() if not pump_data.empty else []
    
    # Create a consistent color map for each data series
    colors = px.colors.qualitative.Plotly + px.colors.qualitative.Set2
    color_map = {label: colors[i % len(colors)] for i, label in enumerate(t_data_labels)}
    
    with ui.column().classes("w-full items-center"):
        # Current-status card: latest reading per sensor/series, independent
        # of whatever date range is selected below.
        with ui.card().classes("w-full max-w-8xl"):
            ui.label("Current Status").classes("text-lg font-semibold mb-2")
            ui.label("Temperatures").classes("text-xs text-gray-500")
            status_temps = ui.html()
            ui.label("Power").classes("text-xs text-gray-500 mt-2")
            status_power = ui.html()
            status_alarms = ui.html().classes("mt-2")

        def _chips_html(df: pd.DataFrame) -> str:
            if df.empty:
                return '<span class="text-gray-500">No data</span>'
            return " ".join(
                f'<span class="mr-4"><span class="text-gray-500">{row["name"]}:</span> '
                f'<b style="color:{ACCENT}">{row["value"]:.1f}</b></span>'
                for _, row in df.iterrows()
            )

        def refresh_nibe_status() -> None:
            status_temps.set_content(_chips_html(repository.get_latest_per_name("temperatures")))
            status_power.set_content(_chips_html(repository.get_latest_per_name("power")))

            recent_alarms = repository.get_data_by_date_range(
                "alarms", datetime.now() - timedelta(hours=24), datetime.now()
            )
            if recent_alarms.empty:
                status_alarms.set_content(
                    '<span class="text-green-700 font-semibold">No alarms in the last 24h</span>'
                )
            else:
                last = recent_alarms.sort_values("timestamp", ascending=False).iloc[0]
                status_alarms.set_content(
                    f'<span class="text-red-600 font-semibold">{len(recent_alarms)} alarm(s) in the last 24h</span>'
                    f' <span class="text-gray-500">(latest: {last["name"]} at '
                    f'{last["timestamp"].strftime("%Y-%m-%d %H:%M")})</span>'
                )

        with ui.card().classes("w-full max-w-8xl mt-4"):
            ui.label("Nibe 360P Data").classes("text-2xl font-bold mb-4")

            # Compact date range filter with icon and menu
            with ui.row().classes("w-full justify-start items-center gap-2 mb-4"):
                ui.label("Date Range:").classes("text-sm font-semibold")

                # Display current date range
                date_display = ui.label(f"{initial_start.strftime('%Y-%m-%d')} to {initial_end.strftime('%Y-%m-%d')}").classes("text-sm")

                # Icon button that opens menu with date picker
                with ui.button(icon='calendar_month').props('flat dense'):
                    with ui.menu() as date_menu:
                        with ui.card().classes('p-4'):
                            ui.label('Select Date Range').classes('text-lg font-bold mb-2')
                            date_range = ui.date({
                                'from': initial_start.strftime("%Y-%m-%d"),
                                'to': initial_end.strftime("%Y-%m-%d")
                            }).props('range')

                            def apply_dates():
                                date_menu.close()
                                reload_all_data()

                            ui.button('Apply', on_click=apply_dates).classes('mt-2')

                def export_csv() -> None:
                    frames = []
                    for table_name, frame in (
                        ("temperatures", t_data),
                        ("alarms", alarms_data),
                        ("power", power_data),
                        ("pump", pump_data),
                    ):
                        if not frame.empty:
                            tagged = frame.copy()
                            tagged.insert(0, "table", table_name)
                            frames.append(tagged)

                    if not frames:
                        ui.notify("No data to export for the selected range.", type="warning")
                        return

                    combined = pd.concat(frames, ignore_index=True)
                    csv_bytes = combined.to_csv(index=False).encode("utf-8")
                    ui.download(
                        csv_bytes,
                        filename=f"nibe_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        media_type="text/csv",
                    )

                ui.button("Export CSV", icon="download", on_click=export_csv).props("outline dense")

            temp_checkboxes = {}
            alarms_checkboxes = {}
            power_checkboxes = {}
            pump_checkboxes = {}
            right_panel = None
            
            def reload_all_data():
                """Reload all data from repository with new date range"""
                nonlocal t_data, alarms_data, power_data, pump_data
                nonlocal t_data_labels, alarms_labels, power_labels, pump_labels
                
                range_value = date_range.value
                if not range_value or 'from' not in range_value or 'to' not in range_value:
                    return
                
                start = _convert_ui_date_to_date(range_value['from'])
                end = _convert_ui_date_to_date(range_value['to'])
                
                # Update display
                date_display.set_text(f"{start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}")
                
                # Reload data from repository
                t_data = repository.get_data_by_date_range("temperatures", start, end)
                alarms_data = repository.get_data_by_date_range("alarms", start, end)
                power_data = repository.get_data_by_date_range("power", start, end)
                pump_data = repository.get_data_by_date_range("pump", start, end)
                
                # Update labels
                t_data_labels = t_data['name'].unique().tolist() if not t_data.empty else []
                alarms_labels = alarms_data['name'].unique().tolist() if not alarms_data.empty else []
                power_labels = power_data['name'].unique().tolist() if not power_data.empty else []
                pump_labels = pump_data['name'].unique().tolist() if not pump_data.empty else []
                
                # Refresh current view
                update_temps_plot()
            
            def update_temps_plot():
                import plotly.graph_objs as go

                fig = go.Figure()
                y_max = None

                # Data is already filtered by date range from repository
                for label in t_data_labels:
                    if label in temp_checkboxes and temp_checkboxes[label].value:
                        sensor_data = t_data[t_data['name'] == label]
                        if sensor_data.empty:
                            continue

                        # Value bolded so it's the first thing that stands out
                        hover_text = [
                            f"{label}<br><b>Value: {row['value']:.2f}</b><br>Time: {row['timestamp']}"
                            for _, row in sensor_data.iterrows()
                        ]

                        fig.add_trace(go.Scatter(
                            x=sensor_data['timestamp'],
                            y=sensor_data['value'],
                            mode='lines+markers',
                            name=label,
                            line=dict(color=color_map.get(label, 'blue')),
                            marker=dict(color=color_map.get(label, 'blue')),
                            hovertext=hover_text,
                            hoverinfo='text'
                        ))
                        series_max = sensor_data['value'].max()
                        y_max = series_max if y_max is None else max(y_max, series_max)

                # Overlay alarm events as markers just above the highest
                # visible series, so you can correlate an alarm with what the
                # temperatures were doing at that moment.
                if y_max is not None and not alarms_data.empty:
                    alarm_y = y_max * 1.05 if y_max > 0 else 1
                    fig.add_trace(go.Scatter(
                        x=alarms_data['timestamp'],
                        y=[alarm_y] * len(alarms_data),
                        mode='markers',
                        marker=dict(symbol='triangle-down', color='#dc2626', size=11,
                                    line=dict(width=1, color='white')),
                        name='Alarms',
                        hovertext=[
                            f"{row['name']}<br>{row['timestamp']}"
                            for _, row in alarms_data.iterrows()
                        ],
                        hoverinfo='text',
                    ))

                fig.update_layout(
                    xaxis_title="Time",
                    yaxis_title="Value",
                    margin=dict(l=20, r=20, t=20, b=20),
                    height=350,
                    showlegend=True
                )

                right_panel.clear()
                with right_panel:
                    ui.plotly(fig).classes("w-full h-full")
            
            def show_filtered_table(data, checkboxes_dict, labels_list, title):
                # Data is already filtered by date range from repository
                # Filter data based on selected checkboxes
                selected_labels = [label for label in labels_list if label in checkboxes_dict and checkboxes_dict[label].value]
                
                if selected_labels:
                    filtered_data = data[data['name'].isin(selected_labels)].copy()
                    # Sort by name (ascending), then timestamp (descending)
                    if 'name' in filtered_data.columns and 'timestamp' in filtered_data.columns:
                        filtered_data = filtered_data.sort_values(by=['name', 'timestamp'], ascending=[True, False])
                else:
                    filtered_data = pd.DataFrame()  # Empty if nothing selected
                
                right_panel.clear()
                with right_panel:
                    if not filtered_data.empty:
                        with ui.scroll_area().classes('w-full h-full'):
                            # Convert dataframe copy and handle timestamps
                            data_copy = filtered_data.copy()
                            
                            # Convert all datetime/timestamp columns to strings
                            for col in data_copy.columns:
                                if pd.api.types.is_datetime64_any_dtype(data_copy[col]):
                                    data_copy[col] = data_copy[col].astype(str)
                            
                            # Hide id and register columns
                            columns_to_hide = ['id', 'register']
                            visible_columns = [col for col in data_copy.columns if col not in columns_to_hide]
                            
                            # Reorder columns: name, value, timestamp
                            column_order = ['name', 'value', 'timestamp']
                            ordered_columns = [col for col in column_order if col in visible_columns]
                            # Add any remaining columns that weren't in the specified order
                            ordered_columns.extend([col for col in visible_columns if col not in column_order])
                            
                            # Create a table
                            columns = [{'name': col, 'label': col.title(), 'field': col} for col in ordered_columns]
                            rows = data_copy[ordered_columns].to_dict('records')
                            
                            # Determine row key
                            if 'timestamp' in ordered_columns:
                                row_key = 'timestamp'
                            elif 'name' in ordered_columns:
                                row_key = 'name'
                            else:
                                # Add index as row key
                                for i, row in enumerate(rows):
                                    row['_index'] = i
                                columns.insert(0, {'name': '_index', 'label': 'Index', 'field': '_index'})
                                row_key = '_index'
                            
                            # Labels above the table
                            ui.label(title).classes('text-xl font-bold mb-2')
                            ui.label(f'Showing {len(filtered_data)} records ({len(selected_labels)} series selected)').classes('text-sm text-gray-600 mb-2')
                            
                            ui.table(
                                columns=columns,
                                rows=rows,
                                row_key=row_key
                            ).classes('w-full')
                    else:
                        ui.label(f'No data to display. Select items from the left panel.').classes('text-gray-500')
            
            with ui.splitter(value=20).classes('w-full h-96') as splitter:
                # Left side: grouped controls
                with splitter.before:
                    with ui.scroll_area().classes('w-full h-full'):
                        # Temperatures group - with checkboxes
                        temp_expansion = ui.expansion('Temperatures', icon='thermostat').classes('w-full')
                        with temp_expansion:
                            if t_data_labels:
                                def toggle_all_temps(value):
                                    for cb in temp_checkboxes.values():
                                        cb.set_value(value)
                                    update_temps_plot()
                                
                                with ui.row().classes('w-full gap-2 mb-2'):
                                    ui.button('Select All', on_click=lambda: toggle_all_temps(True)).props('dense flat size=sm')
                                    ui.button('Unselect All', on_click=lambda: toggle_all_temps(False)).props('dense flat size=sm')
                                
                                for label in t_data_labels:
                                    checkbox = ui.checkbox(label, value=True)
                                    checkbox.on_value_change(update_temps_plot)
                                    temp_checkboxes[label] = checkbox
                            else:
                                ui.label('No temperature data available').classes('text-sm text-gray-500')
                        
                        temp_expansion.on('click', lambda: update_temps_plot())
                        
                        # Alarms group - with checkboxes
                        alarms_expansion = ui.expansion('Alarms', icon='warning').classes('w-full')
                        with alarms_expansion:
                            if alarms_labels:
                                def toggle_all_alarms(value):
                                    for cb in alarms_checkboxes.values():
                                        cb.set_value(value)
                                    show_filtered_table(alarms_data, alarms_checkboxes, alarms_labels, 'Alarms')
                                
                                with ui.row().classes('w-full gap-2 mb-2'):
                                    ui.button('Select All', on_click=lambda: toggle_all_alarms(True)).props('dense flat size=sm')
                                    ui.button('Unselect All', on_click=lambda: toggle_all_alarms(False)).props('dense flat size=sm')
                                
                                for label in alarms_labels:
                                    checkbox = ui.checkbox(label, value=True)
                                    checkbox.on_value_change(lambda: show_filtered_table(alarms_data, alarms_checkboxes, alarms_labels, 'Alarms'))
                                    alarms_checkboxes[label] = checkbox
                            else:
                                ui.label('No alarm data available').classes('text-sm text-gray-500')
                        
                        alarms_expansion.on('click', lambda: show_filtered_table(alarms_data, alarms_checkboxes, alarms_labels, 'Alarms'))
                        
                        # Power group - with checkboxes
                        power_expansion = ui.expansion('Power', icon='power').classes('w-full')
                        with power_expansion:
                            if power_labels:
                                def toggle_all_power(value):
                                    for cb in power_checkboxes.values():
                                        cb.set_value(value)
                                    show_filtered_table(power_data, power_checkboxes, power_labels, 'Power Data')
                                
                                with ui.row().classes('w-full gap-2 mb-2'):
                                    ui.button('Select All', on_click=lambda: toggle_all_power(True)).props('dense flat size=sm')
                                    ui.button('Unselect All', on_click=lambda: toggle_all_power(False)).props('dense flat size=sm')
                                
                                for label in power_labels:
                                    checkbox = ui.checkbox(label, value=True)
                                    checkbox.on_value_change(lambda: show_filtered_table(power_data, power_checkboxes, power_labels, 'Power Data'))
                                    power_checkboxes[label] = checkbox
                            else:
                                ui.label('No power data available').classes('text-sm text-gray-500')
                        
                        power_expansion.on('click', lambda: show_filtered_table(power_data, power_checkboxes, power_labels, 'Power Data'))
                        
                        # Pump group - with checkboxes
                        pump_expansion = ui.expansion('Pump', icon='hvac').classes('w-full')
                        with pump_expansion:
                            if pump_labels:
                                def toggle_all_pump(value):
                                    for cb in pump_checkboxes.values():
                                        cb.set_value(value)
                                    show_filtered_table(pump_data, pump_checkboxes, pump_labels, 'Pump Data')
                                
                                with ui.row().classes('w-full gap-2 mb-2'):
                                    ui.button('Select All', on_click=lambda: toggle_all_pump(True)).props('dense flat size=sm')
                                    ui.button('Unselect All', on_click=lambda: toggle_all_pump(False)).props('dense flat size=sm')
                                
                                for label in pump_labels:
                                    checkbox = ui.checkbox(label, value=True)
                                    checkbox.on_value_change(lambda: show_filtered_table(pump_data, pump_checkboxes, pump_labels, 'Pump Data'))
                                    pump_checkboxes[label] = checkbox
                            else:
                                ui.label('No pump data available').classes('text-sm text-gray-500')
                        
                        pump_expansion.on('click', lambda: show_filtered_table(pump_data, pump_checkboxes, pump_labels, 'Pump Data'))
                
                # Right side: dynamic content area
                with splitter.after:
                    right_panel = ui.element("div").classes("w-full h-full")
            
            # Initial plot
            if t_data_labels:
                update_temps_plot()

    refresh_nibe_status()
    ui.timer(120.0, refresh_nibe_status, immediate=False)


@ui.page("/")
def index() -> None:
    ui.colors(primary=ACCENT)

    with ui.tabs().classes("w-full justify-center") as tabs:
        pump_tab = ui.tab("Waterlevel")
        temp_tab = ui.tab("Nibe 360P")

    with ui.tab_panels(tabs, value=pump_tab).classes("w-full"):
        with ui.tab_panel(pump_tab):
            create_pump_tab()

        with ui.tab_panel(temp_tab):
            create_vvp_tab()

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
    pwd_path: str = "password.txt",
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
    global _repository, _new_repository
    _repository = WaterDataRepository(db_path)
    _new_repository = SensorDataRepository(pwd_path)

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
