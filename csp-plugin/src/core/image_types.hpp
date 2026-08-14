#pragma once

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <optional>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace gap_assist {

struct Point {
  int x{};
  int y{};
};

struct PointF {
  double x{};
  double y{};
};

struct Rect {
  int x{};
  int y{};
  int width{};
  int height{};

  [[nodiscard]] int right() const noexcept { return x + width; }
  [[nodiscard]] int bottom() const noexcept { return y + height; }
  [[nodiscard]] bool empty() const noexcept { return width <= 0 || height <= 0; }
};

struct Rgba {
  std::uint8_t r{};
  std::uint8_t g{};
  std::uint8_t b{};
  std::uint8_t a{};

  friend bool operator==(const Rgba&, const Rgba&) = default;
};

class Image {
 public:
  Image() = default;
  Image(int width, int height, Rgba fill = {})
      : width_(width), height_(height), pixels_(checkedSize(width, height), fill) {}

  [[nodiscard]] int width() const noexcept { return width_; }
  [[nodiscard]] int height() const noexcept { return height_; }
  [[nodiscard]] std::size_t size() const noexcept { return pixels_.size(); }
  [[nodiscard]] bool empty() const noexcept { return pixels_.empty(); }

  [[nodiscard]] const Rgba& at(int x, int y) const {
    return pixels_.at(index(x, y));
  }
  [[nodiscard]] Rgba& at(int x, int y) { return pixels_.at(index(x, y)); }
  [[nodiscard]] const Rgba& atIndex(std::size_t index) const { return pixels_.at(index); }
  [[nodiscard]] Rgba& atIndex(std::size_t index) { return pixels_.at(index); }
  [[nodiscard]] const std::vector<Rgba>& pixels() const noexcept { return pixels_; }
  [[nodiscard]] std::vector<Rgba>& pixels() noexcept { return pixels_; }

  [[nodiscard]] std::size_t index(int x, int y) const {
    if (x < 0 || y < 0 || x >= width_ || y >= height_) {
      throw std::out_of_range("Image coordinate is outside the image.");
    }
    return static_cast<std::size_t>(y) * static_cast<std::size_t>(width_) +
           static_cast<std::size_t>(x);
  }

 private:
  static std::size_t checkedSize(int width, int height) {
    if (width < 0 || height < 0) {
      throw std::invalid_argument("Image dimensions cannot be negative.");
    }
    const auto result = static_cast<std::size_t>(width) * static_cast<std::size_t>(height);
    if (width != 0 && result / static_cast<std::size_t>(width) !=
                          static_cast<std::size_t>(height)) {
      throw std::overflow_error("Image dimensions overflow addressable memory.");
    }
    if (result > std::numeric_limits<std::uint32_t>::max()) {
      throw std::overflow_error(
          "Image has too many pixels for Gap Assist's 32-bit pixel indices.");
    }
    return result;
  }

  int width_{};
  int height_{};
  std::vector<Rgba> pixels_;
};

class SelectionMask {
 public:
  SelectionMask() = default;
  SelectionMask(int width, int height, std::uint8_t fill = 0)
      : width_(width), height_(height), values_(Image(width, height).size(), fill) {}

  [[nodiscard]] int width() const noexcept { return width_; }
  [[nodiscard]] int height() const noexcept { return height_; }
  [[nodiscard]] bool selected(int x, int y) const {
    return value(x, y) != 0;
  }
  [[nodiscard]] std::uint8_t value(int x, int y) const {
    if (x < 0 || y < 0 || x >= width_ || y >= height_) return 0;
    return values_[static_cast<std::size_t>(y) * width_ + x];
  }
  void set(int x, int y, std::uint8_t value) {
    if (x < 0 || y < 0 || x >= width_ || y >= height_) {
      throw std::out_of_range("Selection coordinate is outside the mask.");
    }
    values_[static_cast<std::size_t>(y) * width_ + x] = value;
  }
  [[nodiscard]] const std::vector<std::uint8_t>& values() const noexcept {
    return values_;
  }

 private:
  int width_{};
  int height_{};
  std::vector<std::uint8_t> values_;
};

// Binary, row-major, top-left-origin mask used only by pure detection geometry.
// A true Coloring value means canonical alpha-zero gap membership. True Line or
// Guide values are impassable boundaries. Raster/host threshold policy belongs
// in the conversion that creates these masks, not in GapDetector.
class BinaryMask {
 public:
  BinaryMask() = default;
  BinaryMask(int width, int height, bool fill = false);

  [[nodiscard]] int width() const noexcept { return width_; }
  [[nodiscard]] int height() const noexcept { return height_; }
  [[nodiscard]] std::size_t size() const noexcept { return values_.size(); }
  [[nodiscard]] bool value(int x, int y) const;
  [[nodiscard]] bool atIndex(std::size_t index) const;
  void set(int x, int y, bool value);
  [[nodiscard]] const std::vector<std::uint8_t>& values() const noexcept {
    return values_;
  }

 private:
  int width_{};
  int height_{};
  std::vector<std::uint8_t> values_;
};

struct DetectionGeometry {
  explicit DetectionGeometry(int width = 0, int height = 0)
      : coloringGap(width, height),
        lineBoundary(width, height),
        guideBoundary(width, height) {}

  BinaryMask coloringGap;
  BinaryMask lineBoundary;
  BinaryMask guideBoundary;

  [[nodiscard]] int width() const noexcept { return coloringGap.width(); }
  [[nodiscard]] int height() const noexcept { return coloringGap.height(); }
  [[nodiscard]] std::size_t size() const noexcept { return coloringGap.size(); }
  void validate() const;
};

// Canonical active-Coloring conversion: only alpha == 0 becomes membership.
[[nodiscard]] DetectionGeometry normalizeCanonicalColoringGeometry(
    const Image& coloring);

// Compatibility conversion for existing RGBA layer snapshots. Coloring remains
// exact-zero; Line/Guide keep the current any-nonzero-alpha acquisition rule.
// That boundary rasterization policy is empirical and deliberately outside the
// normalized detector contract.
[[nodiscard]] DetectionGeometry normalizeLegacyRgbaGeometry(
    const Image& coloring, const Image* lineArt = nullptr,
    const Image* guides = nullptr);

enum class Connectivity { Four = 4, Eight = 8 };
enum class ConfidenceBand { High, Medium, Low };
enum class ReviewStatus { Unreviewed, Apply, Skip, MarkOnly };
enum class RunMode { QuickFix, ReviewList, OneByOne };
enum class OutputMode { CorrectionLayer, OverwriteActiveLayer };
enum class Scope { WholeLayer, SelectionOnly };

struct GapCandidate {
  int id{};
  // Full canonical component used for enclosure, metadata, and prediction.
  std::vector<std::uint32_t> pixels;
  // Optional-selection application subset. Empty means the full component for
  // whole-layer and legacy/manually-built candidates, avoiding a duplicate copy.
  std::vector<std::uint32_t> applicationPixels;
  std::size_t area{};
  Rect bbox;
  PointF centroid;
  std::optional<Rgba> suggestedColor;
  double confidence{};
  ConfidenceBand confidenceBand{ConfidenceBand::Low};
  bool apply{};
  ReviewStatus status{ReviewStatus::Unreviewed};
  std::optional<int> sourceOwnerId;
  std::string debugInfo;
};

[[nodiscard]] inline const std::vector<std::uint32_t>& candidateApplicationPixels(
    const GapCandidate& gap) noexcept {
  return gap.applicationPixels.empty() ? gap.pixels : gap.applicationPixels;
}

[[nodiscard]] inline std::string toString(ConfidenceBand band) {
  switch (band) {
    case ConfidenceBand::High:
      return "high";
    case ConfidenceBand::Medium:
      return "medium";
    case ConfidenceBand::Low:
      return "low";
  }
  return "low";
}

[[nodiscard]] inline std::string toString(ReviewStatus status) {
  switch (status) {
    case ReviewStatus::Unreviewed:
      return "unreviewed";
    case ReviewStatus::Apply:
      return "apply";
    case ReviewStatus::Skip:
      return "skip";
    case ReviewStatus::MarkOnly:
      return "mark_only";
  }
  return "unreviewed";
}

}  // namespace gap_assist
