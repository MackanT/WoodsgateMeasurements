from nicegui import ui


@ui.page("/")
def index():
    ui.button("click me!")


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(host="0.0.0.0", port=8080)
