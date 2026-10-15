import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import RepeatedKFold

# ------------------------------------------------------------------
# Config (tune these to your data)
# ------------------------------------------------------------------
DATA_PATH = "data/Sales_Transactions.csv"
MODEL_PATH = Path("data/early_hit_model.pkl")
META_PATH = Path("data/early_hit_meta.json")

OBSERVE_DAYS = 7      # days used to build the features
TARGET_DAYS = 60      # fixed window used to define a "hit" (same for ALL products)
TOP_QUANTILE = 0.70   # hit = top 30% by quantity within the target window
MIN_GAP_DAYS = 0      # products first seen within this many days of the data start
                      # are treated as pre-existing (not real launches) and dropped
MIN_PRODUCTS = 30     # safety check

FEATURES = ["qty_7d", "sales_7d", "customers_7d"]

# ------------------------------------------------------------------
# 1. Load + detect launch date (T0)
# ------------------------------------------------------------------
df = pd.read_csv(DATA_PATH, parse_dates=["Order_Date"])

data_start = df["Order_Date"].min()
data_end = df["Order_Date"].max()

t0_df = (
    df.groupby("Product_ID")["Order_Date"].min().reset_index().rename(columns={"Order_Date": "T0"})
)

# ------------------------------------------------------------------
# 2. Keep only real launches with a full observation window
# ------------------------------------------------------------------
total_products = len(t0_df)

is_new_launch = t0_df["T0"] >= data_start + pd.Timedelta(days=MIN_GAP_DAYS)
has_full_window = (data_end - t0_df["T0"]).dt.days >= TARGET_DAYS - 1

kept = t0_df[is_new_launch & has_full_window]

print(f"Total products:                      {total_products}")
print(f"Dropped (likely pre-existing):       {(~is_new_launch).sum()}")
print(f"Dropped (not enough history):        {(is_new_launch & ~has_full_window).sum()}")
print(f"Kept for training:                   {len(kept)}")

if len(kept) < MIN_PRODUCTS:
    raise SystemExit(
        f"Only {len(kept)} products left. Reduce TARGET_DAYS or MIN_GAP_DAYS, "
        "or collect more data."
    )

df = df.merge(kept, on="Product_ID")  # inner merge keeps only kept products
df["days_since_launch"] = (df["Order_Date"] - df["T0"]).dt.days

# ------------------------------------------------------------------
# 3. Features: first 7 days only (days 0..6)
# ------------------------------------------------------------------
first_days = df[df["days_since_launch"] < OBSERVE_DAYS]

features = first_days.groupby("Product_ID").agg(
    qty_7d=("Quantity", "sum"),
    sales_7d=("Net_Sales_EGP", "sum"),
    customers_7d=("Customer_ID", "nunique"),
)

# ------------------------------------------------------------------
# 4. Target quantity over a FIXED window for every product
# ------------------------------------------------------------------
window = df[df["days_since_launch"] < TARGET_DAYS]
target_qty = window.groupby("Product_ID")["Quantity"].sum().rename("target_qty")

ml_data = features.join(target_qty, how="inner").reset_index(drop=True)

X = ml_data[FEATURES]
qty_target = ml_data["target_qty"]


def make_model():
    return RandomForestClassifier(
        n_estimators=100,
        max_depth=3,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=42,
    )


# ------------------------------------------------------------------
# 5. Repeated cross-validation
#    The hit threshold is computed from the TRAIN fold only (no leakage)
# ------------------------------------------------------------------
cv = RepeatedKFold(n_splits=5, n_repeats=10, random_state=42)

rows = []
for train_idx, test_idx in cv.split(X):
    threshold = qty_target.iloc[train_idx].quantile(TOP_QUANTILE)
    y_train = (qty_target.iloc[train_idx] >= threshold).astype(int)
    y_test = (qty_target.iloc[test_idx] >= threshold).astype(int)

    model = make_model().fit(X.iloc[train_idx], y_train)
    pred = model.predict(X.iloc[test_idx])

    # Baseline: a simple rule on qty_7d only
    qty_cut = X.iloc[train_idx]["qty_7d"].quantile(TOP_QUANTILE)
    base_pred = (X.iloc[test_idx]["qty_7d"] >= qty_cut).astype(int)

    for name, p in [("RandomForest", pred), ("Baseline (qty_7d rule)", base_pred)]:
        rows.append(
            {
                "model": name,
                "accuracy": accuracy_score(y_test, p),
                "precision_hit": precision_score(y_test, p, zero_division=0),
                "recall_hit": recall_score(y_test, p, zero_division=0),
                "f1_hit": f1_score(y_test, p, zero_division=0),
            }
        )

results = pd.DataFrame(rows).groupby("model").agg(["mean", "std"]).round(3)
print("\nCross-validation results (mean / std over 50 folds):")
print(results.T.to_string())

# ------------------------------------------------------------------
# 6. Final model on ALL data
# ------------------------------------------------------------------
final_threshold = float(qty_target.quantile(TOP_QUANTILE))
y_all = (qty_target >= final_threshold).astype(int)

final_model = make_model().fit(X, y_all)

print("\nClass balance (hit=1):", y_all.mean().round(2))
print("\nFeature importance:")
for name, imp in sorted(zip(FEATURES, final_model.feature_importances_), key=lambda t: -t[1]):
    print(f"  {name:<14} {imp:.3f}")

MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
joblib.dump(final_model, MODEL_PATH)

meta = {
    "observe_days": OBSERVE_DAYS,
    "target_days": TARGET_DAYS,
    "top_quantile": TOP_QUANTILE,
    "hit_threshold_qty": final_threshold,
    "n_products": int(len(ml_data)),
    "features": FEATURES,
}
META_PATH.write_text(json.dumps(meta, indent=2))

print(f"\nSaved model to {MODEL_PATH}")
print(f"Saved metadata to {META_PATH}")
