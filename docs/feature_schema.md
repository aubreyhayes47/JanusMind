# Action Feature Schema

This document describes the tensors emitted by `training/prepare_dataset.py` so that downstream agents can consume consistent inputs at inference time.

## Encoding Overview
- **Card vectors (52,):** Each position corresponds to a unique rank/suit combination ordered by suit (`s`, `h`, `d`, `c`) then rank (`2`–`A`). Values are binary indicators.
- **Numeric scalars (1,):** `stack`, `pot`, `to_call`, and `bet_targets` are divided by the big blind supplied to the encoder. They remain unbounded floats.
- **Action types (5,):** One-hot order: `fold`, `check`, `call`, `bet`, `raise`.

## Saved Artifacts
`prepare_dataset.py` writes three files to the requested output directory:
- `train.npz` – packed arrays for supervised learning.
- `val.npz` – held-out validation split using the same schema as `train.npz`.
- `metadata.json` – helper metadata for reproducibility.

### Array layout
Each `.npz` archive stores aligned arrays with the same leading dimension `N` (rows). Shapes are noted below:

| Key | Shape | Description |
| --- | --- | --- |
| `hole_cards` | `(N, 52)` | Binary indicators for the acting player's two hole cards. |
| `board_cards` | `(N, 52)` | Binary indicators for the public board at the time of the action. |
| `stacks` | `(N, 1)` | Remaining stack normalized by the big blind. |
| `pots` | `(N, 1)` | Current pot size normalized by the big blind. |
| `to_calls` | `(N, 1)` | Amount needed to call normalized by the big blind. |
| `action_types` | `(N, 5)` | One-hot encoded action label using the order above. |
| `bet_targets` | `(N, 1)` | Normalized bet/raise size; zeroed for non-bet actions. |

### Metadata fields
`metadata.json` includes the normalization parameters and ordering used during encoding:
- `big_blind` – float used to scale all chip amounts.
- `val_fraction` – proportion of rows reserved for validation.
- `num_samples` – total action rows observed across splits.
- `action_types` – ordered list of action labels for the one-hot encoding.
- `card_encoding` – rank/suit ordering and vector length.

## Inference Notes
- To encode new observations, construct 52-length binary vectors with the same rank/suit ordering and divide monetary values by the same big blind reference before forwarding into a model.
- When predicting a continuous bet size head, remember to multiply the model output by the big blind to recover chips.
- Non-betting actions should map to a `bet_targets` value of `0.0` to match the training convention.
