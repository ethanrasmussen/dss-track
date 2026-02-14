import math
from typing import Any
import numpy as np
from pandas import DataFrame

def sanitize_pre_api_resp(x: Any):
    if isinstance(x, DataFrame):
        return sanitize_pandas_df(x)
    return sanitize_for_json(x)


def sanitize_for_json(x: Any):
    # numpy scalars
    if np is not None and isinstance(x, (np.floating, np.integer)):
        x = x.item()

    # floats
    if isinstance(x, float):
        return x if math.isfinite(x) else None

    # dict / list / tuple
    if isinstance(x, dict):
        return {k: sanitize_for_json(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [sanitize_for_json(v) for v in x]

    return x

def sanitize_pandas_df(df):
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.where(df.notna(), None)  # NaN -> None
    return df.to_dict(orient="records")

