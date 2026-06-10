"""Nearest-region segmentation models."""

from __future__ import annotations

import torch.nn as nn

from .unet_blocks import UNetDown, UNetUp


class NearestRegionUNet(nn.Module):
    """
    [U-Net-based architecture]
    Input: line art mask & target region mask (2 channels),
    Output: nearest region mask (1 channel, binary probability map [0,1])
    """
    # Implementation of Section 4.2.1 / Figure 6.

    ### for 32x32
    def __init__(self, in_channels=2, out_channels=1):
        super().__init__()

        # Encoder: 4 stages (32x32 → ... → 2x2)
        self.down1 = UNetDown(in_channels, 64, normalize=False)  # 32x32 → 16x16
        self.down2 = UNetDown(64, 128)  # 16x16 → 8x8
        self.down3 = UNetDown(128, 256, dropout=0.5)  # 8x8   → 4x4
        self.down4 = UNetDown(256, 512, dropout=0.5)  # 4x4   → 2x2

        # Decoder: 3 stages + final upsampling (2x2 → ... → 32x32)
        self.up1 = UNetUp(512, 256, dropout=0.5)  # 2x2 → 4x4 + concat with down3
        self.up2 = UNetUp(512, 128)  # 4x4 → 8x8 + concat with down2
        self.up3 = UNetUp(256, 64)  # 8x8 → 16x16 + concat with down1
        self.final = nn.Sequential(
            nn.Upsample(scale_factor=2),  # 16x16 → 32x32
            nn.ZeroPad2d((1, 0, 1, 0)),  # Fine-tune size
            nn.Conv2d(128, out_channels, 4, padding=1),  # Final output (32x32)
            nn.Sigmoid(), # For binary probability map [0,1] output
        )

    def forward(self, input_mask):
        # input_mask: [B,2,32,32]
        height, width = input_mask.shape[-2:]
        if height % 16 != 0 or width % 16 != 0:
            raise ValueError(f"Input height and width must be multiples of 16, got {(height, width)}")

        d1 = self.down1(input_mask)  # [B,64,16,16]
        d2 = self.down2(d1)  # [B,128,8,8]
        d3 = self.down3(d2)  # [B,256,4,4]
        d4 = self.down4(d3)  # [B,512,2,2]

        u1 = self.up1(d4, d3)  # [B,512,4,4]
        u2 = self.up2(u1, d2)  # [B,256,8,8]
        u3 = self.up3(u2, d1)  # [B,128,16,16]
        output = self.final(u3)  # [B,1,32,32]
        return output
