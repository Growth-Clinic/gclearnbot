from slack_bolt import App
from config.settings import Config
import logging

logger = logging.getLogger(__name__)

def init_slack_auth(app: App) -> None:
    """Initialize Slack authentication handlers"""
    
    @app.event("app_home_opened")
    def handle_app_home_opened(body, logger):
        """Handle when a user opens the app home"""
        try:
            user_id = body["event"]["user"]
            logger.info(f"App home opened by user: {user_id}")
        except Exception as e:
            logger.error(f"Error handling app home opened: {e}")

    @app.event("tokens_revoked")
    def handle_tokens_revoked(body, logger):
        """Handle when tokens are revoked"""
        try:
            user_id = body.get("event", {}).get("user")
            logger.warning(f"Tokens revoked for user: {user_id}")
        except Exception as e:
            logger.error(f"Error handling tokens revoked: {e}")

    @app.event("app_uninstalled")
    def handle_app_uninstalled(body, logger):
        """Handle when the app is uninstalled"""
        try:
            logger.warning("App was uninstalled from workspace")
        except Exception as e:
            logger.error(f"Error handling app uninstalled: {e}")