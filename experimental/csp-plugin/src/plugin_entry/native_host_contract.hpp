#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <exception>
#include <functional>
#include <optional>
#include <string>
#include <vector>

#include "core/image_types.hpp"

namespace gap_assist {

// Public, SDK-independent boundary for a native host adapter. Host SDK types,
// headers, constants, and artifacts must remain outside this public contract.

struct RgbaTile {
  Rect bounds;
  std::size_t rowStride{};
  std::size_t pixelStride{};
  std::array<std::size_t, 4> rgbaOffsets{};
  std::vector<std::uint8_t> bytes;
};

struct MaskTile {
  Rect bounds;
  std::size_t rowStride{};
  std::size_t pixelStride{};
  std::size_t valueOffset{};
  std::vector<std::uint8_t> bytes;
};

// Assemble absolute-coordinate host tiles into a top-left, document-sized
// plane. The host adapter must have color-managed the bytes to straight,
// 8-bit sRGB RGBA before calling this function. Transparent pixels are emitted
// outside a cropped plane. Missing, overlapping, or malformed coverage fails
// closed.
[[nodiscard]] Image assembleNormalizedRgbaPlane(
    Rect documentBounds, Rect planeBounds, const std::vector<RgbaTile>& tiles);

// Preserve host selection coverage exactly (including fractional 1..254
// values); pixels outside a cropped selection extent are zero.
[[nodiscard]] SelectionMask assembleSelectionMask(
    Rect documentBounds, Rect selectionBounds,
    const std::vector<MaskTile>& tiles);

struct SnapshotIdentity {
  std::uint64_t document{};
  std::uint64_t target{};
  std::uint64_t revision{};

  friend bool operator==(const SnapshotIdentity&, const SnapshotIdentity&) = default;
};

enum class CanonicalPixelEncoding { StraightRgba8Srgb };

struct ColorNormalizationRecord {
  std::string sourceColorSpace;
  std::string sourceProfile;
  CanonicalPixelEncoding outputEncoding{CanonicalPixelEncoding::StraightRgba8Srgb};
  bool outputHasStraightAlpha{true};
  std::string conversionEvidence;
};

struct CanonicalInputSnapshot {
  SnapshotIdentity identity;
  Rect documentBounds;
  Image coloring;
  Image lineArt;
  Image guide;
  DetectionGeometry geometry;
  std::optional<SelectionMask> selection;
  ColorNormalizationRecord colorNormalization;

  [[nodiscard]] static CanonicalInputSnapshot fromNormalizedRasters(
      SnapshotIdentity identity, Rect documentBounds, Image coloring,
      Image lineArt, Image guide,
      std::optional<SelectionMask> selection = std::nullopt,
      ColorNormalizationRecord colorNormalization = {
          "adapter-declared source space", "adapter-declared source profile",
          CanonicalPixelEncoding::StraightRgba8Srgb, true,
          "adapter-declared canonical sRGB conversion"});

  void validate() const;
};

struct NativeHostCapabilities {
  bool coloringInput{};
  bool lineInput{};
  bool guideInput{};
  bool selectionInput{};
  bool normalizedStraightRgba8Srgb{};
  bool cancellationPolling{};
  bool replaceablePreview{};
  bool atomicFinalMutation{};
  bool undoAndRedo{};

  [[nodiscard]] bool hasCanonicalInputContract() const noexcept;
  [[nodiscard]] bool hasFinalMutationContract() const noexcept;
};

class HostCancelled final : public std::exception {
 public:
  [[nodiscard]] const char* what() const noexcept override {
    return "Native host operation was cancelled.";
  }
};

struct CommitEvidence {
  bool exactlyOneUndoStep{};
  bool redoRestoresCommit{};
};

class NativeHostAdapter {
 public:
  virtual ~NativeHostAdapter() = default;

  [[nodiscard]] virtual NativeHostCapabilities capabilities() const = 0;
  [[nodiscard]] virtual CanonicalInputSnapshot acquireCanonicalInput(
      const std::function<bool()>& cancelRequested) = 0;
  [[nodiscard]] virtual bool snapshotStillCurrent(
      const SnapshotIdentity& identity) const = 0;
  [[nodiscard]] virtual bool cancellationRequested() const = 0;

  // A replacement must remain temporary and must not add an Undo entry.
  virtual void replacePreview(const SnapshotIdentity& identity,
                              const Image& pixels) = 0;
  virtual void discardPreview() noexcept = 0;

  // Final output is a two-phase mutation. Any exception, cancellation, or
  // stale snapshot before commit must be recoverable through abort.
  virtual void beginFinalMutation(const SnapshotIdentity& identity) = 0;
  virtual void stageFinalPixels(const Image& pixels) = 0;
  [[nodiscard]] virtual CommitEvidence commitFinalMutation() = 0;
  virtual void abortFinalMutation() noexcept = 0;
};

// Enforces fail-closed lifecycle rules around an SDK-specific adapter. This
// class deliberately does not run detection or prediction and therefore does
// not alter the frozen GapFill algorithms.
class NativeHostSession {
 public:
  explicit NativeHostSession(NativeHostAdapter& adapter) : adapter_(adapter) {}

  [[nodiscard]] CanonicalInputSnapshot acquire();
  void replacePreview(const CanonicalInputSnapshot& snapshot,
                      const Image& pixels);
  void cancelPreview() noexcept;
  void commit(const CanonicalInputSnapshot& snapshot, const Image& pixels);

 private:
  void ensureCurrentAndNotCancelled(
      const CanonicalInputSnapshot& snapshot) const;
  static void validateOutputDimensions(const CanonicalInputSnapshot& snapshot,
                                       const Image& pixels);

  NativeHostAdapter& adapter_;
};

}  // namespace gap_assist
