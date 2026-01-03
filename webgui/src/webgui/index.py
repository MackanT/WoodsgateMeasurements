from nicegui import ui

import pandas as pd

import plotly.express as px
from datetime import datetime, timedelta, date
from statistics import mean, stdev
from webgui.repository import WaterDataRepository
from webgui.postgress_db import SensorDataRepository

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
                        f"Level: {l_mean_val:.2f} ± {l_std:.2f}<br>"
                        f"Level Range: [{l_min:.2f}↓, {l_max:.2f}↑]<br>"
                        f"Volume: {v_mean_val:.2f} ± {v_std:.2f}<br>"
                        f"Volume Range: [{v_min:.2f}↓, {v_max:.2f}↑]<br>"
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
                        f"Level: {l_mean_val:.2f} ± {l_std:.2f} \t[{l_min:.2f}↓, {l_max:.2f}↑]"
                    )
                    global_stats_volume.set_text(
                        f"Volume: {v_mean_val:.2f} ± {v_std:.2f} \t[{v_min:.2f}↓, {v_max:.2f}↑]"
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
        with ui.card().classes("w-full max-w-8xl"):
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
                
                # Data is already filtered by date range from repository
                for label in t_data_labels:
                    if label in temp_checkboxes and temp_checkboxes[label].value:
                        sensor_data = t_data[t_data['name'] == label]
                        
                        # Create custom hover text with value on its own row
                        hover_text = [
                            f"{label}<br>Time: {row['timestamp']}<br>Value: {row['value']:.2f}"
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
