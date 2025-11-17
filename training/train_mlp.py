"""Train a small MLP policy on encoded action datasets."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset


ACTION_KEY = "action_types"
BET_TARGET_KEY = "bet_targets"
NUMERIC_COLUMNS: Tuple[str, ...] = ("stacks", "pots", "to_calls")
CARD_COLUMNS: Tuple[str, ...] = ("hole_cards", "board_cards")


@dataclass
class NormalizationStats:
    """Mean/std pairs for each numeric scalar feature."""

    means: Dict[str, float]
    stds: Dict[str, float]

    @classmethod
    def from_arrays(cls, arrays: Dict[str, np.ndarray]) -> "NormalizationStats":
        means: Dict[str, float] = {}
        stds: Dict[str, float] = {}
        for key in NUMERIC_COLUMNS:
            values = arrays[key].astype(np.float32)
            means[key] = float(values.mean())
            std = float(values.std())
            stds[key] = std if std > 1e-6 else 1e-6
        return cls(means=means, stds=stds)

    def apply(self, tensor: torch.Tensor, key: str) -> torch.Tensor:
        mean = self.means[key]
        std = self.stds[key]
        return (tensor - mean) / std


class ActionDataset(Dataset[Dict[str, torch.Tensor]]):
    def __init__(
        self,
        arrays: Dict[str, np.ndarray],
        normalization: NormalizationStats,
    ) -> None:
        self.normalization = normalization
        self.hole_cards = torch.from_numpy(arrays["hole_cards"]).float()
        self.board_cards = torch.from_numpy(arrays["board_cards"]).float()
        self.stacks = torch.from_numpy(arrays["stacks"]).float()
        self.pots = torch.from_numpy(arrays["pots"]).float()
        self.to_calls = torch.from_numpy(arrays["to_calls"]).float()
        self.action_labels = torch.from_numpy(arrays[ACTION_KEY].argmax(axis=1)).long()
        self.bet_targets = torch.from_numpy(arrays[BET_TARGET_KEY]).float()

    def __len__(self) -> int:
        return self.action_labels.shape[0]

    def __getitem__(self, index: int) -> Dict[str, torch.Tensor]:
        features = [
            self.hole_cards[index],
            self.board_cards[index],
            self.normalization.apply(self.stacks[index], "stacks"),
            self.normalization.apply(self.pots[index], "pots"),
            self.normalization.apply(self.to_calls[index], "to_calls"),
        ]
        return {
            "features": torch.cat(features, dim=-1),
            "action": self.action_labels[index],
            "bet_target": self.bet_targets[index],
        }


def load_npz(path: Path) -> Dict[str, np.ndarray]:
    arrays = np.load(path)
    return {key: arrays[key] for key in arrays.files}


class ActionValueMLP(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int, num_actions: int) -> None:
        super().__init__()
        self.backbone = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(p=0.1),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )
        self.action_head = nn.Linear(hidden_dim, num_actions)
        self.bet_head = nn.Linear(hidden_dim, 1)

    def forward(self, features: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        hidden = self.backbone(features)
        return self.action_head(hidden), self.bet_head(hidden)


def _bet_mask(actions: torch.Tensor, bet_idx: int, raise_idx: int) -> torch.Tensor:
    return (actions == bet_idx) | (actions == raise_idx)


def train_epoch(
    model: ActionValueMLP,
    dataloader: DataLoader[Dict[str, torch.Tensor]],
    optimizer: torch.optim.Optimizer,
    device: torch.device,
    bet_loss_weight: float,
    bet_idx: int,
    raise_idx: int,
) -> Dict[str, float]:
    model.train()
    total_samples = 0
    loss_sum = 0.0
    ce_sum = 0.0
    mse_sum = 0.0
    correct = 0
    masked = 0

    for batch in dataloader:
        features = batch["features"].to(device)
        actions = batch["action"].to(device)
        bet_targets = batch["bet_target"].to(device)

        optimizer.zero_grad()
        logits, bet_pred = model(features)
        action_loss = F.cross_entropy(logits, actions)
        bet_mask = _bet_mask(actions, bet_idx=bet_idx, raise_idx=raise_idx)
        if bet_mask.any():
            bet_loss = F.mse_loss(bet_pred[bet_mask], bet_targets[bet_mask])
            masked += int(bet_mask.sum().item())
        else:
            bet_loss = torch.tensor(0.0, device=device)
        loss = action_loss + bet_loss_weight * bet_loss
        loss.backward()
        optimizer.step()

        batch_size = actions.shape[0]
        total_samples += batch_size
        loss_sum += float(loss.item()) * batch_size
        ce_sum += float(action_loss.item()) * batch_size
        mse_sum += float(bet_loss.item()) * batch_size
        correct += int((logits.argmax(dim=1) == actions).sum().item())

    return {
        "loss": loss_sum / total_samples,
        "action_loss": ce_sum / total_samples,
        "bet_loss": mse_sum / max(total_samples, 1),
        "accuracy": correct / total_samples,
        "bet_fraction": masked / max(total_samples, 1),
    }


def evaluate(
    model: ActionValueMLP,
    dataloader: DataLoader[Dict[str, torch.Tensor]],
    device: torch.device,
    bet_loss_weight: float,
    bet_idx: int,
    raise_idx: int,
) -> Dict[str, float]:
    model.eval()
    total_samples = 0
    loss_sum = 0.0
    ce_sum = 0.0
    mse_sum = 0.0
    correct = 0
    masked = 0

    with torch.no_grad():
        for batch in dataloader:
            features = batch["features"].to(device)
            actions = batch["action"].to(device)
            bet_targets = batch["bet_target"].to(device)
            logits, bet_pred = model(features)
            action_loss = F.cross_entropy(logits, actions)
            bet_mask = _bet_mask(actions, bet_idx=bet_idx, raise_idx=raise_idx)
            if bet_mask.any():
                bet_loss = F.mse_loss(bet_pred[bet_mask], bet_targets[bet_mask])
                masked += int(bet_mask.sum().item())
            else:
                bet_loss = torch.tensor(0.0, device=device)
            loss = action_loss + bet_loss_weight * bet_loss

            batch_size = actions.shape[0]
            total_samples += batch_size
            loss_sum += float(loss.item()) * batch_size
            ce_sum += float(action_loss.item()) * batch_size
            mse_sum += float(bet_loss.item()) * batch_size
            correct += int((logits.argmax(dim=1) == actions).sum().item())

    ev_proxy = -loss_sum / max(total_samples, 1)
    return {
        "loss": loss_sum / total_samples,
        "action_loss": ce_sum / total_samples,
        "bet_loss": mse_sum / max(total_samples, 1),
        "accuracy": correct / total_samples,
        "bet_fraction": masked / max(total_samples, 1),
        "ev_proxy": ev_proxy,
    }


def load_metadata(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_dataloaders(
    dataset_dir: Path,
    batch_size: int,
    normalization: NormalizationStats,
) -> Tuple[DataLoader[Dict[str, torch.Tensor]], DataLoader[Dict[str, torch.Tensor]]]:
    train_arrays = load_npz(dataset_dir / "train.npz")
    val_arrays = load_npz(dataset_dir / "val.npz")
    train_ds = ActionDataset(train_arrays, normalization=normalization)
    val_ds = ActionDataset(val_arrays, normalization=normalization)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size)
    return train_loader, val_loader


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a small MLP over encoded poker actions")
    parser.add_argument("dataset_dir", type=Path, help="Directory containing train.npz, val.npz, metadata.json")
    parser.add_argument("output_dir", type=Path, help="Directory to store model checkpoints and metadata")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--hidden-dim", type=int, default=256)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--bet-loss-weight", type=float, default=1.0, help="Weight for the bet/raise regression head")
    parser.add_argument("--seed", type=int, default=7, help="Random seed for reproducibility")
    parser.add_argument("--device", type=str, default="cpu", help="Torch device to use (cpu or cuda)")
    return parser.parse_args()


def save_artifacts(
    output_dir: Path,
    model: ActionValueMLP,
    normalization: NormalizationStats,
    metadata: Dict[str, object],
    action_types: List[str],
    best_metrics: Dict[str, float],
    config: argparse.Namespace,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), output_dir / "mlp_policy.pt")
    normalization_blob = {
        "big_blind": metadata.get("big_blind"),
        "action_types": action_types,
        "numeric_normalization": {
            key: {"mean": normalization.means[key], "std": normalization.stds[key]}
            for key in NUMERIC_COLUMNS
        },
        "feature_order": [*CARD_COLUMNS, *NUMERIC_COLUMNS],
        "model_config": {
            "hidden_dim": config.hidden_dim,
            "bet_loss_weight": config.bet_loss_weight,
        },
        "best_validation": best_metrics,
    }
    (output_dir / "normalization.json").write_text(
        json.dumps(normalization_blob, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    dataset_dir = args.dataset_dir
    metadata = load_metadata(dataset_dir / "metadata.json")
    action_types = [str(action).lower() for action in metadata.get("action_types", [])]
    if "bet" not in action_types or "raise" not in action_types:
        raise ValueError("metadata.json must list bet and raise action types")
    bet_idx = action_types.index("bet")
    raise_idx = action_types.index("raise")

    train_arrays = load_npz(dataset_dir / "train.npz")
    normalization = NormalizationStats.from_arrays(train_arrays)
    train_loader, val_loader = build_dataloaders(
        dataset_dir=dataset_dir, batch_size=args.batch_size, normalization=normalization
    )

    feature_dim = train_arrays["hole_cards"].shape[1] + train_arrays["board_cards"].shape[1] + len(NUMERIC_COLUMNS)
    num_actions = train_arrays[ACTION_KEY].shape[1]
    model = ActionValueMLP(input_dim=feature_dim, hidden_dim=args.hidden_dim, num_actions=num_actions)
    device = torch.device(args.device)
    model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate)

    best_val_ev = float("-inf")
    best_metrics: Dict[str, float] = {}
    for epoch in range(1, args.epochs + 1):
        train_metrics = train_epoch(
            model,
            train_loader,
            optimizer,
            device,
            args.bet_loss_weight,
            bet_idx,
            raise_idx,
        )
        val_metrics = evaluate(
            model,
            val_loader,
            device,
            args.bet_loss_weight,
            bet_idx,
            raise_idx,
        )
        print(
            f"Epoch {epoch:02d} | train loss {train_metrics['loss']:.4f} "
            f"acc {train_metrics['accuracy']:.3f} | val loss {val_metrics['loss']:.4f} "
            f"acc {val_metrics['accuracy']:.3f} ev_proxy {val_metrics['ev_proxy']:.4f}"
        )
        if val_metrics["ev_proxy"] > best_val_ev:
            best_val_ev = val_metrics["ev_proxy"]
            best_metrics = val_metrics
            save_artifacts(
                output_dir=args.output_dir,
                model=model,
                normalization=normalization,
                metadata=metadata,
                action_types=action_types,
                best_metrics=val_metrics,
                config=args,
            )


if __name__ == "__main__":
    main()
