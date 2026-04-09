import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # GCP
    GCP_PROJECT_ID: str = os.environ["GCP_PROJECT_ID"]
    GCS_BUCKET: str = os.environ["GCS_BUCKET"]
    GCS_WAREHOUSE_PATH: str = os.environ["GCS_WAREHOUSE_PATH"]
    GOOGLE_APPLICATION_CREDENTIALS: str = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]

    # BigQuery
    BQ_DATASET: str = os.getenv("BQ_DATASET", "nyc_taxi_trust")
    BQ_LOCATION: str = os.getenv("BQ_LOCATION", "US")

    # Iceberg
    ICEBERG_CATALOG: str = os.getenv("ICEBERG_CATALOG", "nyc_taxi")
    ICEBERG_DATABASE: str = os.getenv("ICEBERG_DATABASE", "yellow_taxi")
    ICEBERG_TABLE: str = os.getenv("ICEBERG_TABLE", "trips")

    @property
    def iceberg_full_table(self) -> str:
        return f"{self.ICEBERG_CATALOG}.{self.ICEBERG_DATABASE}.{self.ICEBERG_TABLE}"

    # OpenAI
    OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Pipeline
    INGEST_TARGETS: list[str] = os.getenv(
        "INGEST_TARGETS", "2015-01,2017-01,2019-01,2022-01"
    ).split(",")

    # Sampling — how many rows to send to the LLM
    LLM_SAMPLE_SIZE: int = int(os.getenv("LLM_SAMPLE_SIZE", "500"))


settings = Settings()
