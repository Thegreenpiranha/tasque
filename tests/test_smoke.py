"""Feature #1 smoke test: the app boots, shows its banner, and quits on `q`."""

from textual.widgets import Static

from tasque.app import TasqueApp


async def test_app_boots_and_shows_banner():
    app = TasqueApp()
    async with app.run_test():
        banner = app.query_one("#banner", Static)
        assert "Tasque" in str(banner.render())
        assert app.title == "Tasque"


async def test_quits_on_q():
    app = TasqueApp()
    async with app.run_test() as pilot:
        await pilot.press("q")
    assert app.return_code == 0
