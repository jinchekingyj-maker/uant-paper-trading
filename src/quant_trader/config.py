from decimal import Decimal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./paper_trading.db"
    default_account_id: str = "paper"
    initial_cash: Decimal = Decimal("100000")
    max_order_notional: Decimal = Decimal("25000")
    max_position_ratio: Decimal = Decimal("0.50")
    max_gross_exposure_ratio: Decimal = Decimal("1.00")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

