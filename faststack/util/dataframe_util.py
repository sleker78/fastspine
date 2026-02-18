from typing import Any, Type

import pandas as pd
from pydantic import BaseModel
from sqlalchemy.engine.result import Row


def convert_to_df(results: Any) -> pd.DataFrame:
    """Converts SQLAlchemy results to a pandas DataFrame."""
    if hasattr(results, "keys"):
        rows = results.fetchall()
        return pd.DataFrame(rows, columns=results.keys())

    if isinstance(results, list) and results:
        if isinstance(results[0], Row):
            return pd.DataFrame(results, columns=results[0].keys())

        keys = results[0].keys() if isinstance(results[0], dict) else []
        return pd.DataFrame(results, columns=keys)

    raise ValueError("Unsupported result format for DataFrame conversion.")


def map_data_to_model(df: pd.DataFrame, model: Type[BaseModel]) -> list[BaseModel]:
    """Converts a pandas DataFrame to a list of Pydantic models.

    NaN values are replaced with None before instantiating the models.
    """
    df = df.replace({float("nan"): None})
    return [model(**row.to_dict()) for _, row in df.iterrows()]
