"""Training pipeline for NearestRegionUNet."""

from __future__ import annotations

import json
import os
from types import SimpleNamespace

import torch
import torch.distributed as dist
import torch.nn as nn
import torch.nn.init as nninit
import torch.optim as optim
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm

from src.models.nearest_region import NearestRegionUNet
from src.utils.data_loader import create_batch_dataloaders
from src.utils.patch_utils import validate_model_crop_size


def initialize_weights(module: nn.Module):
    if isinstance(module, (nn.Conv2d, nn.ConvTranspose2d)):
        nninit.kaiming_normal_(module.weight, mode="fan_in", nonlinearity="relu")
        if module.bias is not None:
            nninit.zeros_(module.bias)

    elif isinstance(module, (nn.BatchNorm2d)):
        if module.weight is not None:
            nninit.ones_(module.weight)
        if module.bias is not None:
            nninit.zeros_(module.bias)

def _setup_distributed(args) -> SimpleNamespace:
    local_rank = int(os.environ.get("LOCAL_RANK", "0"))
    world_size = int(os.environ.get("WORLD_SIZE", "1"))
    distributed = world_size > 1

    if distributed:
        backend = args.backend
        if backend == "nccl" and not torch.cuda.is_available():
            backend = "gloo"
        dist.init_process_group(backend=backend)

    if torch.cuda.is_available() and args.device.startswith("cuda"):
        if distributed:
            torch.cuda.set_device(local_rank)
            device = torch.device(f"cuda:{local_rank}")
        else:
            device = torch.device(args.device)
    else:
        device = torch.device("cpu")

    return SimpleNamespace(
        distributed=distributed,
        local_rank=local_rank,
        world_size=world_size,
        device=device,
        is_rank0=(not distributed) or local_rank == 0,
    )

def _reduce_loss(loss_sum: float, sample_count: int, device: torch.device, distributed: bool) -> float:
    totals = torch.tensor([loss_sum, sample_count], dtype=torch.float64, device=device)
    if distributed:
        dist.all_reduce(totals, op=dist.ReduceOp.SUM)
    if totals[1].item() == 0:
        raise ValueError("Cannot calculate loss for an empty DataLoader")
    return (totals[0] / totals[1]).item()


def train_model(args) -> None:
    validate_model_crop_size(args.crop_size)
    state = _setup_distributed(args)

    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(os.path.join(args.output_dir, "checkpoints"), exist_ok=True)
    os.makedirs(os.path.join(args.output_dir, "samples"), exist_ok=True)

    writer = None
    if state.is_rank0:
        writer = SummaryWriter(os.path.join(args.output_dir, "logs"))
        print(f"Using device: {state.device}")

    # Create dataloaders: input is {'input': [B,2,H,W], 'target': [B,1,H,W]}
    train_loader, val_loader, train_sampler, _ = create_batch_dataloaders(
        args.data_dir,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        crop_size=args.crop_size,
        use_hdf5=args.use_hdf5,
    )

    # Implementation of Section 4.2.2: train the NearestRegionUNet model (Section 4.2.1) on the synthetic patch dataset.
    model = NearestRegionUNet(in_channels=2, out_channels=1).to(state.device)
    model.apply(initialize_weights)

    if state.distributed:
        model = DDP(model, device_ids=[state.local_rank] if state.device.type == "cuda" else None)

    # Loss function: for binary classification (output already has Sigmoid applied)
    criterion = nn.BCELoss()

    optimizer = optim.Adam(model.parameters(), lr=args.lr, betas=(0.5, 0.999), weight_decay=args.weight_decay)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="min", factor=0.5, patience=5)

    history = {"train_loss": [], "val_loss": []}

    best_val_loss = float("inf")
    patience_counter = 0

    for epoch in range(args.num_epochs):
        if state.distributed and train_sampler is not None:
            train_sampler.set_epoch(epoch)

        # ===========  TRAIN  =======================
        model.train()
        running_train_loss = 0.0
        train_sample_count = 0
        pbar = tqdm(
            train_loader,
            desc=f"[Train] epoch {epoch + 1}/{args.num_epochs}",
            disable=(not state.is_rank0),
        )

        for batch in pbar:
            inputs = batch["input"].to(state.device)
            targets = batch["target"].to(state.device)

            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()

            batch_size = inputs.size(0)
            running_train_loss += loss.item() * batch_size
            train_sample_count += batch_size
            pbar.set_postfix(loss=loss.item())

        train_loss = _reduce_loss(running_train_loss, train_sample_count, state.device, state.distributed)

        # ===========  VALIDATION  ===================
        model.eval()
        running_val_loss = 0.0
        val_sample_count = 0
        with torch.no_grad():
            for batch in val_loader:
                inputs = batch["input"].to(state.device)
                targets = batch["target"].to(state.device)
                outputs = model(inputs)
                loss = criterion(outputs, targets)
                batch_size = inputs.size(0)
                running_val_loss += loss.item() * batch_size
                val_sample_count += batch_size

        val_loss = _reduce_loss(running_val_loss, val_sample_count, state.device, state.distributed)

        if state.is_rank0:
            history["train_loss"].append(train_loss)
            history["val_loss"].append(val_loss)
            if writer is not None:
                writer.add_scalar("Loss/train", train_loss, epoch + 1)
                writer.add_scalar("Loss/val", val_loss, epoch + 1)
            print(f"Epoch {epoch + 1}: train={train_loss:.4f}, val={val_loss:.4f}")

        # ===========  Early-Stopping Check  ==========
        is_improved = torch.tensor([0], dtype=torch.uint8, device=state.device)
        if state.is_rank0 and val_loss < best_val_loss - 1e-6:  # min_delta
            best_val_loss = val_loss
            is_improved[0] = 1
            state_dict = model.module.state_dict() if state.distributed else model.state_dict()
            torch.save(state_dict, os.path.join(args.output_dir, "checkpoints", "best_model.pth"))
            print(f"best model saved (val_loss={val_loss:.4f})")

        if state.distributed:
            dist.broadcast(is_improved, src=0)

        # Update patience
        patience_counter = 0 if is_improved.item() else patience_counter + 1

        # ===========  LR Scheduler  ==============
        scheduler.step(val_loss)

        # ===========  Periodic Save  ======================
        if (epoch + 1) % args.save_interval == 0 and state.is_rank0:
            state_dict = model.module.state_dict() if state.distributed else model.state_dict()
            torch.save(state_dict, os.path.join(args.output_dir, "checkpoints", f"model_epoch_{epoch + 1}.pth"))

        # ===========  Early-Stop Triggered  ===============
        if patience_counter >= args.patience:
            if state.is_rank0:
                print(f"Early stopping at epoch {epoch + 1}")
            break

    if state.is_rank0:
        state_dict = model.module.state_dict() if state.distributed else model.state_dict()
        torch.save(state_dict, os.path.join(args.output_dir, "checkpoints", "final_model.pth"))
        with open(os.path.join(args.output_dir, "history.json"), "w") as f:
            json.dump(history, f)
        if writer is not None:
            writer.close()
        print(f"Training complete. Results saved to {args.output_dir}")

    if state.distributed and dist.is_initialized():
        dist.destroy_process_group()
