#include "plugin_entry/native_host_contract.hpp"

#include <algorithm>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <utility>

namespace gap_assist {
namespace {

[[nodiscard]] std::size_t checkedProduct(std::size_t left, std::size_t right,
                                         const char* message) {
  if (left != 0 && right > std::numeric_limits<std::size_t>::max() / left) {
    throw std::overflow_error(message);
  }
  return left * right;
}

[[nodiscard]] std::size_t checkedAdd(std::size_t left, std::size_t right,
                                     const char* message) {
  if (right > std::numeric_limits<std::size_t>::max() - left) {
    throw std::overflow_error(message);
  }
  return left + right;
}

void validatePositiveRect(Rect rect, const char* name) {
  if (rect.width <= 0 || rect.height <= 0) {
    throw std::invalid_argument(std::string(name) +
                                " must have positive dimensions.");
  }
}

[[nodiscard]] std::int64_t rectRight(Rect rect) {
  return static_cast<std::int64_t>(rect.x) + rect.width;
}

[[nodiscard]] std::int64_t rectBottom(Rect rect) {
  return static_cast<std::int64_t>(rect.y) + rect.height;
}

[[nodiscard]] bool contains(Rect outer, Rect inner) {
  return inner.x >= outer.x && inner.y >= outer.y &&
         rectRight(inner) <= rectRight(outer) &&
         rectBottom(inner) <= rectBottom(outer);
}

void validateExtent(Rect documentBounds, Rect planeBounds,
                    const std::vector<RgbaTile>& tiles) {
  validatePositiveRect(documentBounds, "Document bounds");
  if (planeBounds.width == 0 && planeBounds.height == 0) {
    if (!tiles.empty()) {
      throw std::invalid_argument("An empty plane cannot contain tiles.");
    }
    return;
  }
  validatePositiveRect(planeBounds, "Plane bounds");
  if (!contains(documentBounds, planeBounds)) {
    throw std::invalid_argument("Plane bounds are outside the document.");
  }
}

void validateExtent(Rect documentBounds, Rect planeBounds,
                    const std::vector<MaskTile>& tiles) {
  validatePositiveRect(documentBounds, "Document bounds");
  if (planeBounds.width == 0 && planeBounds.height == 0) {
    if (!tiles.empty()) {
      throw std::invalid_argument("An empty mask cannot contain tiles.");
    }
    return;
  }
  validatePositiveRect(planeBounds, "Mask bounds");
  if (!contains(documentBounds, planeBounds)) {
    throw std::invalid_argument("Mask bounds are outside the document.");
  }
}

[[nodiscard]] std::size_t coverageIndex(Rect extent, int absoluteX,
                                        int absoluteY) {
  const auto x = static_cast<std::size_t>(absoluteX - extent.x);
  const auto y = static_cast<std::size_t>(absoluteY - extent.y);
  return y * static_cast<std::size_t>(extent.width) + x;
}

[[nodiscard]] std::size_t requiredByteCount(int width, int height,
                                            std::size_t rowStride,
                                            std::size_t pixelStride,
                                            std::size_t lastOffset) {
  const auto lastPixel = checkedProduct(
      static_cast<std::size_t>(width - 1), pixelStride,
      "Tile pixel stride overflows addressable memory.");
  const auto rowBytes = checkedAdd(
      checkedAdd(lastPixel, lastOffset, "Tile channel offset overflows."), 1,
      "Tile byte count overflows.");
  if (rowStride < rowBytes) {
    throw std::invalid_argument("Tile row stride is too short.");
  }
  const auto precedingRows = checkedProduct(
      static_cast<std::size_t>(height - 1), rowStride,
      "Tile row stride overflows addressable memory.");
  return checkedAdd(precedingRows, rowBytes, "Tile byte count overflows.");
}

void requireCompleteCoverage(const std::vector<std::uint8_t>& coverage) {
  if (std::find(coverage.begin(), coverage.end(), std::uint8_t{0}) !=
      coverage.end()) {
    throw std::invalid_argument("Host tiles do not completely cover the plane.");
  }
}

void validateImageDimensions(const Image& image, Rect documentBounds,
                             const char* name) {
  if (image.width() != documentBounds.width ||
      image.height() != documentBounds.height) {
    throw std::invalid_argument(std::string(name) +
                                " dimensions do not match the document.");
  }
}

}  // namespace

Image assembleNormalizedRgbaPlane(Rect documentBounds, Rect planeBounds,
                                  const std::vector<RgbaTile>& tiles) {
  validateExtent(documentBounds, planeBounds, tiles);
  Image output(documentBounds.width, documentBounds.height, Rgba{});
  if (planeBounds.width == 0 && planeBounds.height == 0) return output;

  std::vector<std::uint8_t> coverage(
      checkedProduct(static_cast<std::size_t>(planeBounds.width),
                     static_cast<std::size_t>(planeBounds.height),
                     "Plane coverage size overflows."));

  for (const auto& tile : tiles) {
    validatePositiveRect(tile.bounds, "Tile bounds");
    if (!contains(planeBounds, tile.bounds)) {
      throw std::invalid_argument("Tile bounds are outside the plane.");
    }
    if (tile.pixelStride == 0) {
      throw std::invalid_argument("Tile pixel stride cannot be zero.");
    }
    const auto maximumOffset =
        *std::max_element(tile.rgbaOffsets.begin(), tile.rgbaOffsets.end());
    if (maximumOffset >= tile.pixelStride) {
      throw std::invalid_argument("RGBA channel offset is outside the pixel.");
    }
    auto sortedOffsets = tile.rgbaOffsets;
    std::sort(sortedOffsets.begin(), sortedOffsets.end());
    if (std::adjacent_find(sortedOffsets.begin(), sortedOffsets.end()) !=
        sortedOffsets.end()) {
      throw std::invalid_argument("RGBA channel offsets must be distinct.");
    }
    const auto required = requiredByteCount(
        tile.bounds.width, tile.bounds.height, tile.rowStride,
        tile.pixelStride, maximumOffset);
    if (tile.bytes.size() < required) {
      throw std::invalid_argument("Tile byte storage is truncated.");
    }

    for (int localY = 0; localY < tile.bounds.height; ++localY) {
      for (int localX = 0; localX < tile.bounds.width; ++localX) {
        const int absoluteX = tile.bounds.x + localX;
        const int absoluteY = tile.bounds.y + localY;
        const auto coverageOffset =
            coverageIndex(planeBounds, absoluteX, absoluteY);
        if (coverage[coverageOffset] != 0) {
          throw std::invalid_argument("Host tiles overlap.");
        }
        coverage[coverageOffset] = 1;

        const auto byteOffset =
            static_cast<std::size_t>(localY) * tile.rowStride +
            static_cast<std::size_t>(localX) * tile.pixelStride;
        output.at(absoluteX - documentBounds.x,
                  absoluteY - documentBounds.y) =
            Rgba{tile.bytes[byteOffset + tile.rgbaOffsets[0]],
                 tile.bytes[byteOffset + tile.rgbaOffsets[1]],
                 tile.bytes[byteOffset + tile.rgbaOffsets[2]],
                 tile.bytes[byteOffset + tile.rgbaOffsets[3]]};
      }
    }
  }
  requireCompleteCoverage(coverage);
  return output;
}

SelectionMask assembleSelectionMask(Rect documentBounds, Rect selectionBounds,
                                    const std::vector<MaskTile>& tiles) {
  validateExtent(documentBounds, selectionBounds, tiles);
  SelectionMask output(documentBounds.width, documentBounds.height, 0);
  if (selectionBounds.width == 0 && selectionBounds.height == 0) return output;

  std::vector<std::uint8_t> coverage(
      checkedProduct(static_cast<std::size_t>(selectionBounds.width),
                     static_cast<std::size_t>(selectionBounds.height),
                     "Mask coverage size overflows."));

  for (const auto& tile : tiles) {
    validatePositiveRect(tile.bounds, "Mask tile bounds");
    if (!contains(selectionBounds, tile.bounds)) {
      throw std::invalid_argument("Mask tile bounds are outside the mask.");
    }
    if (tile.pixelStride == 0 || tile.valueOffset >= tile.pixelStride) {
      throw std::invalid_argument("Mask value offset is outside the pixel.");
    }
    const auto required = requiredByteCount(
        tile.bounds.width, tile.bounds.height, tile.rowStride,
        tile.pixelStride, tile.valueOffset);
    if (tile.bytes.size() < required) {
      throw std::invalid_argument("Mask tile byte storage is truncated.");
    }

    for (int localY = 0; localY < tile.bounds.height; ++localY) {
      for (int localX = 0; localX < tile.bounds.width; ++localX) {
        const int absoluteX = tile.bounds.x + localX;
        const int absoluteY = tile.bounds.y + localY;
        const auto coverageOffset =
            coverageIndex(selectionBounds, absoluteX, absoluteY);
        if (coverage[coverageOffset] != 0) {
          throw std::invalid_argument("Host mask tiles overlap.");
        }
        coverage[coverageOffset] = 1;
        const auto byteOffset =
            static_cast<std::size_t>(localY) * tile.rowStride +
            static_cast<std::size_t>(localX) * tile.pixelStride;
        output.set(absoluteX - documentBounds.x, absoluteY - documentBounds.y,
                   tile.bytes[byteOffset + tile.valueOffset]);
      }
    }
  }
  requireCompleteCoverage(coverage);
  return output;
}

CanonicalInputSnapshot CanonicalInputSnapshot::fromNormalizedRasters(
    SnapshotIdentity identityValue, Rect bounds, Image coloringValue,
    Image lineArtValue, Image guideValue,
    std::optional<SelectionMask> selectionValue,
    ColorNormalizationRecord colorNormalizationValue) {
  CanonicalInputSnapshot result;
  result.identity = identityValue;
  result.documentBounds = bounds;
  result.coloring = std::move(coloringValue);
  result.lineArt = std::move(lineArtValue);
  result.guide = std::move(guideValue);
  result.geometry = normalizeLegacyRgbaGeometry(
      result.coloring, &result.lineArt, &result.guide);
  result.selection = std::move(selectionValue);
  result.colorNormalization = std::move(colorNormalizationValue);
  result.validate();
  return result;
}

void CanonicalInputSnapshot::validate() const {
  validatePositiveRect(documentBounds, "Snapshot document bounds");
  if (identity.document == 0 || identity.target == 0) {
    throw std::invalid_argument(
        "Snapshot document and target identities must be nonzero.");
  }
  validateImageDimensions(coloring, documentBounds, "Coloring");
  validateImageDimensions(lineArt, documentBounds, "Line");
  validateImageDimensions(guide, documentBounds, "Guide");
  geometry.validate();
  if (geometry.width() != documentBounds.width ||
      geometry.height() != documentBounds.height) {
    throw std::invalid_argument(
        "Normalized detection geometry dimensions do not match the document.");
  }
  const auto expected =
      normalizeLegacyRgbaGeometry(coloring, &lineArt, &guide);
  if (geometry.coloringGap.values() != expected.coloringGap.values() ||
      geometry.lineBoundary.values() != expected.lineBoundary.values() ||
      geometry.guideBoundary.values() != expected.guideBoundary.values()) {
    throw std::invalid_argument(
        "Normalized detection geometry does not match its source planes.");
  }
  if (selection.has_value() &&
      (selection->width() != documentBounds.width ||
       selection->height() != documentBounds.height)) {
    throw std::invalid_argument(
        "Selection dimensions do not match the document.");
  }
  if (colorNormalization.sourceColorSpace.empty() ||
      colorNormalization.sourceProfile.empty() ||
      colorNormalization.outputEncoding !=
          CanonicalPixelEncoding::StraightRgba8Srgb ||
      !colorNormalization.outputHasStraightAlpha ||
      colorNormalization.conversionEvidence.empty()) {
    throw std::invalid_argument(
        "Snapshot lacks canonical straight RGBA8 sRGB conversion evidence.");
  }
}

bool NativeHostCapabilities::hasCanonicalInputContract() const noexcept {
  return coloringInput && lineInput && guideInput && selectionInput &&
         normalizedStraightRgba8Srgb && cancellationPolling;
}

bool NativeHostCapabilities::hasFinalMutationContract() const noexcept {
  return atomicFinalMutation && undoAndRedo && cancellationPolling;
}

CanonicalInputSnapshot NativeHostSession::acquire() {
  if (!adapter_.capabilities().hasCanonicalInputContract()) {
    throw std::runtime_error(
        "Native host cannot provide the canonical Coloring/Line/Guide/Selection contract.");
  }
  auto snapshot = adapter_.acquireCanonicalInput(
      [this] { return adapter_.cancellationRequested(); });
  snapshot.validate();
  ensureCurrentAndNotCancelled(snapshot);
  return snapshot;
}

void NativeHostSession::replacePreview(const CanonicalInputSnapshot& snapshot,
                                       const Image& pixels) {
  if (!adapter_.capabilities().replaceablePreview) {
    throw std::runtime_error("Native host cannot replace temporary previews.");
  }
  snapshot.validate();
  validateOutputDimensions(snapshot, pixels);
  ensureCurrentAndNotCancelled(snapshot);
  try {
    adapter_.replacePreview(snapshot.identity, pixels);
  } catch (...) {
    adapter_.discardPreview();
    throw;
  }
}

void NativeHostSession::cancelPreview() noexcept { adapter_.discardPreview(); }

void NativeHostSession::commit(const CanonicalInputSnapshot& snapshot,
                               const Image& pixels) {
  const auto capabilities = adapter_.capabilities();
  if (!capabilities.hasFinalMutationContract()) {
    throw std::runtime_error(
        "Native host lacks atomic one-step Undo/Redo final mutation support.");
  }
  snapshot.validate();
  validateOutputDimensions(snapshot, pixels);
  ensureCurrentAndNotCancelled(snapshot);

  bool transactionOpen = false;
  try {
    adapter_.beginFinalMutation(snapshot.identity);
    transactionOpen = true;
    adapter_.stageFinalPixels(pixels);
    ensureCurrentAndNotCancelled(snapshot);
    const auto evidence = adapter_.commitFinalMutation();
    transactionOpen = false;
    if (!evidence.exactlyOneUndoStep || !evidence.redoRestoresCommit) {
      throw std::runtime_error(
          "Native host commit lacks one-step Undo and exact Redo evidence.");
    }
  } catch (...) {
    if (transactionOpen) adapter_.abortFinalMutation();
    throw;
  }
}

void NativeHostSession::ensureCurrentAndNotCancelled(
    const CanonicalInputSnapshot& snapshot) const {
  if (adapter_.cancellationRequested()) throw HostCancelled{};
  if (!adapter_.snapshotStillCurrent(snapshot.identity)) {
    throw std::runtime_error("Native host snapshot is stale.");
  }
}

void NativeHostSession::validateOutputDimensions(
    const CanonicalInputSnapshot& snapshot, const Image& pixels) {
  if (pixels.width() != snapshot.documentBounds.width ||
      pixels.height() != snapshot.documentBounds.height) {
    throw std::invalid_argument(
        "Native host output dimensions do not match the snapshot.");
  }
}

}  // namespace gap_assist
