"""PyTorch ResBlock MLP — 8-regime classifier (Kairos-v2 architecture).

Porta fedele del model di Kairos-v2:
  https://github.com/PVinh-Quant/Kairos-v2
  ml/trang_thai_thi_truong_ml/ml_model.py

Architettura:
  Input (80-dim: 18 features × 4 timeframe + 8 context)
  → Linear(80→256) + BatchNorm + GELU + Dropout
  → 3 × ResBlock(256, Dropout=0.3)
  → Linear(256→64) + BN + GELU + Dropout
  → Linear(64→8)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import polars as pl
import torch
import torch.nn as nn

from analytics.regime.ml_features import (
    FEATURE_NAMES,
    compute_all_features,
    compute_multi_tf_features,
)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ── 8 Regime Labels ──────────────────────────────────────────────────

REGIME_LABELS: list[str] = [
    "Dong_Bang",  # Congelato
    "Nen_Chat",  # Compressione
    "Dau_XH",  # Inizio uptrend
    "XH_Manh",  # Uptrend forte
    "Cao_Trao",  # Climax
    "Hoi_Quy",  # Regressione/ritraccio
    "Nhieu_Dong",  # Noisy/choppy
    "Quet_TK",  # Stop hunting
]


# ── Z-score Scaler (PyTorch, no sklearn dependency) ──────────────────


class MyTorchScaler:
    """Z-score scaler puro PyTorch (identico a Kairos-v2)."""

    def __init__(self) -> None:
        self.mean: torch.Tensor | None = None
        self.std: torch.Tensor | None = None

    def fit(self, x_tensor: torch.Tensor) -> None:
        self.mean = x_tensor.mean(dim=0).cpu()
        self.std = x_tensor.std(dim=0).cpu()
        self.std[self.std == 0] = 1e-7

    def transform(self, x_tensor: torch.Tensor) -> torch.Tensor:
        if self.mean is None:
            raise ValueError("Scaler non ancora fit — chiama .fit() prima")
        assert self.std is not None
        return (x_tensor - self.mean.to(x_tensor.device)) / self.std.to(x_tensor.device)

    def save(self, path: str) -> None:
        assert self.mean is not None and self.std is not None
        with open(path, "w") as f:
            json.dump({"mean": self.mean.tolist(), "std": self.std.tolist()}, f)

    def load(self, path: str) -> None:
        with open(path) as f:
            data = json.load(f)
        self.mean = torch.tensor(data["mean"])
        self.std = torch.tensor(data["std"])


# ── ResBlock ─────────────────────────────────────────────────────────


class ResBlock(nn.Module):
    """Residual block: Linear + BatchNorm + GELU + Dropout."""

    def __init__(self, dim: int, dropout_rate: float = 0.3) -> None:
        super().__init__()
        self.block = nn.Sequential(
            nn.Linear(dim, dim),
            nn.BatchNorm1d(dim),
            nn.GELU(),
            nn.Dropout(dropout_rate),
            nn.Linear(dim, dim),
            nn.BatchNorm1d(dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return nn.functional.gelu(x + self.block(x))


# ── TradingMLP ───────────────────────────────────────────────────────


class TradingMLP(nn.Module):
    """MLP per classificazione regime mercato (8 classi).

    Args:
        input_dim: Feature dimension (default 80).
        output_dim: Number of regime classes (default 8).
        hidden_dim: Hidden layer size (default 256).
        dropout_rate: Dropout probability (default 0.3).
    """

    def __init__(
        self,
        input_dim: int = 80,
        output_dim: int = 8,
        hidden_dim: int = 256,
        dropout_rate: float = 0.3,
    ) -> None:
        super().__init__()

        self.input_layer = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout_rate * 0.5),
        )

        self.res_blocks = nn.Sequential(
            ResBlock(hidden_dim, dropout_rate),
            ResBlock(hidden_dim, dropout_rate),
            ResBlock(hidden_dim, dropout_rate),
        )

        self.output_layer = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.BatchNorm1d(64),
            nn.GELU(),
            nn.Dropout(dropout_rate),
            nn.Linear(64, output_dim),
        )

        self._init_weights()

    def _init_weights(self) -> None:
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, mode="fan_in", nonlinearity="relu")
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        result: torch.Tensor = self.input_layer(x)
        result = self.res_blocks(result)
        out: torch.Tensor = self.output_layer(result)
        return out


# ── Feature vectorization ────────────────────────────────────────────

INPUT_DIM_SINGLE = len(FEATURE_NAMES)  # 18
INPUT_DIM_MULTI = 72  # 3 TF × 18 + 8 context + padding


def build_feature_vector(df: pl.DataFrame) -> torch.Tensor:
    """Compute 18 features and return latest row as tensor."""
    features = compute_all_features(df)
    last = features.row(-1, named=True)
    vals = [float(last.get(name, 0.0)) for name in FEATURE_NAMES]
    return torch.tensor(vals, dtype=torch.float32).unsqueeze(0)


def build_multi_tf_vector(
    df_1h: pl.DataFrame | None = None,
    df_4h: pl.DataFrame | None = None,
    df_1d: pl.DataFrame | None = None,
) -> torch.Tensor:
    """Compute 72-dim feature vector from up to 3 timeframes.

    Returns:
        (1, 72) tensor suitable for model inference.
    """
    vec = compute_multi_tf_features(df_1h, df_4h, df_1d)
    if vec is None:
        vec = np.zeros(INPUT_DIM_MULTI, dtype=np.float32)
    # Pad to 72 if needed
    if len(vec) < INPUT_DIM_MULTI:
        padded = np.zeros(INPUT_DIM_MULTI, dtype=np.float32)
        padded[: len(vec)] = vec
        vec = padded
    return torch.tensor(vec[:INPUT_DIM_MULTI], dtype=torch.float32).unsqueeze(0)


# ── Inference engine ────────────────────────────────────────────────


class RegimeClassifier:
    """Singleton wrapper: load model + scaler, predict regime.

    Usage::
        clf = RegimeClassifier()
        clf.load_or_init(input_dim=18)       # single TF (deprecated)
        clf.load_or_init(input_dim=72)       # multi TF (preferred)
    """

    def __init__(self, model_dir: str = "models/regime") -> None:
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.model_path = self.model_dir / "model_pytorch.pth"
        self.scaler_path = self.model_dir / "scaler_params.json"
        self.info_path = self.model_dir / "model_info.json"

        self.model: TradingMLP | None = None
        self.scaler: MyTorchScaler | None = None

    def _make_scaler(self) -> MyTorchScaler:
        """Create a fresh scaler instance."""
        return MyTorchScaler()

    def load_or_init(self, input_dim: int = 18) -> None:
        """Load saved model or initialise untrained."""
        if self.model_path.exists() and self.scaler_path.exists():
            self.model = TradingMLP(input_dim=input_dim).to(device)
            self.model.load_state_dict(
                torch.load(self.model_path, map_location=device, weights_only=True)
            )
            self.model.eval()
            self.scaler = MyTorchScaler()
            self.scaler.load(str(self.scaler_path))
            print(f"  RegimeClassifier: loaded from {self.model_path}")
        else:
            self.model = TradingMLP(input_dim=input_dim).to(device)
            self.scaler = MyTorchScaler()
            print(f"  RegimeClassifier: init untrained (input_dim={input_dim})")

    def predict(self, df: pl.DataFrame) -> tuple[str, float]:
        """Predict regime for the latest bar.

        Returns:
            (regime_label, softmax_confidence)
        """
        if self.model is None:
            return "Nhieu_Dong", 0.0

        x = build_feature_vector(df).to(device)
        self.model.eval()
        if self.scaler is not None and self.scaler.mean is not None:
            x = self.scaler.transform(x)

        with torch.no_grad():
            logits = self.model(x)
            probs = torch.softmax(logits, dim=1)
            pred_idx: int = int(probs.argmax(dim=1).item())
            conf = float(probs[0, pred_idx].item())

        label = REGIME_LABELS[pred_idx] if pred_idx < len(REGIME_LABELS) else "Nhieu_Dong"
        return label, round(conf, 4)

    def predict_multi_tf(
        self,
        df_1h: pl.DataFrame | None = None,
        df_4h: pl.DataFrame | None = None,
        df_1d: pl.DataFrame | None = None,
    ) -> tuple[str, float]:
        """Predict regime using multi-timeframe features (72-dim).

        Args:
            df_1h: 1-hour OHLCV DataFrame.
            df_4h: 4-hour OHLCV DataFrame.
            df_1d: 1-day OHLCV DataFrame.

        Returns:
            (regime_label, softmax_confidence)
        """
        if self.model is None:
            return "Nhieu_Dong", 0.0

        x = build_multi_tf_vector(df_1h, df_4h, df_1d).to(device)
        self.model.eval()
        if self.scaler is not None and self.scaler.mean is not None:
            x = self.scaler.transform(x)

        with torch.no_grad():
            logits = self.model(x)
            probs = torch.softmax(logits, dim=1)
            pred_idx = int(probs.argmax(dim=1).item())
            conf = float(probs[0, pred_idx].item())

        label = REGIME_LABELS[pred_idx] if pred_idx < len(REGIME_LABELS) else "Nhieu_Dong"
        return label, round(conf, 4)

    def train(
        self, df_list: list[pl.DataFrame], labels: list[int], epochs: int = 100, lr: float = 1e-4
    ) -> dict[str, list[float]]:
        """Train the classifier on historical data.

        Args:
            df_list: List of OHLCV DataFrames (one per sample).
            labels: List of integer regime labels (0-7).
            epochs: Number of training epochs.
            lr: Learning rate.

        Returns:
            Dict with 'loss' history.
        """
        if self.model is None:
            self.model = TradingMLP(input_dim=INPUT_DIM_SINGLE).to(device)
            self.scaler = MyTorchScaler()

        # Build feature matrix
        x_list: list[torch.Tensor] = []
        for df in df_list:
            x = build_feature_vector(df)
            x_list.append(x)
        x = torch.cat(x_list, dim=0)
        y = torch.tensor(labels, dtype=torch.long, device=device)

        # Fit scaler and transform
        assert self.scaler is not None
        self.scaler.fit(x)
        x_scaled = self.scaler.transform(x)

        # Training
        self.model.train()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        criterion = nn.CrossEntropyLoss()

        history: dict[str, list[float]] = {"loss": []}
        for epoch in range(epochs):
            optimizer.zero_grad()
            logits = self.model(x_scaled)
            loss = criterion(logits, y)
            loss.backward()
            optimizer.step()
            history["loss"].append(loss.item())

            if epoch > 0 and epoch % 20 == 0:
                acc = (logits.argmax(dim=1) == y).float().mean().item()
                print(f"  Epoch {epoch}: loss={loss.item():.4f} acc={acc:.2%}")

        # Save
        self.model.eval()
        torch.save(self.model.state_dict(), str(self.model_path))
        assert self.scaler is not None
        self.scaler.save(str(self.scaler_path))
        with open(self.info_path, "w") as f:
            json.dump(
                {
                    "input_dim": INPUT_DIM_SINGLE,
                    "output_dim": 8,
                    "feature_names": FEATURE_NAMES,
                    "epochs": epochs,
                    "final_loss": history["loss"][-1] if history["loss"] else 0.0,
                },
                f,
            )
        print(f"  Model saved to {self.model_path}")

        return history


__all__ = ["REGIME_LABELS", "RegimeClassifier", "ResBlock", "TradingMLP"]
