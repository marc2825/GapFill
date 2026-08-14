#include "core/correction_output.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <unordered_set>

namespace gap_assist {
namespace {

bool shouldApply(const GapCandidate& gap) {
  return gap.suggestedColor.has_value() && gap.apply &&
         gap.status == ReviewStatus::Apply;
}

bool shouldMark(const GapCandidate& gap, const Settings& settings) {
  if (shouldApply(gap))
    return gap.confidenceBand == ConfidenceBand::High &&
           settings.highlightHighConfidence;
  if (gap.status == ReviewStatus::Skip || gap.status == ReviewStatus::MarkOnly)
    return true;
  if (gap.confidenceBand == ConfidenceBand::Low ||
      gap.confidenceBand == ConfidenceBand::Medium)
    return true;
  return settings.highlightHighConfidence;
}

Rgba markerColor(const GapCandidate& gap) {
  if (gap.confidenceBand == ConfidenceBand::Low) return {255, 48, 48, 230};
  if (gap.confidenceBand == ConfidenceBand::Medium) return {255, 196, 0, 220};
  return {0, 210, 255, 150};
}

void validateCandidates(const Image& source, const std::vector<GapCandidate>& gaps,
                        const Settings& settings, const CandidateContext& context,
                        const SelectionMask* selection,
                        const DetectionGeometry* geometry) {
  validateCandidateContext(context, source, settings, selection, geometry);
  std::unordered_set<int> ids;
  std::unordered_set<std::uint32_t> occupied;
  for (const auto& gap : gaps) {
    if (!ids.insert(gap.id).second)
      throw std::invalid_argument("Candidate IDs must be unique.");
    if (gap.pixels.empty() || gap.area != gap.pixels.size())
      throw std::invalid_argument("Candidate area does not match its unique pixels.");

    int minX = std::numeric_limits<int>::max();
    int minY = std::numeric_limits<int>::max();
    int maxX = -1;
    int maxY = -1;
    std::uint64_t sumX = 0;
    std::uint64_t sumY = 0;
    std::unordered_set<std::uint32_t> local;
    for (const auto pixel : gap.pixels) {
      if (pixel >= source.size())
        throw std::invalid_argument("Candidate pixel index is outside the source.");
      if (!local.insert(pixel).second)
        throw std::invalid_argument("Candidate pixel indices must be unique.");
      if (!occupied.insert(pixel).second)
        throw std::invalid_argument("Candidate pixel sets must not overlap.");
      if (source.atIndex(pixel).a != 0)
        throw std::invalid_argument(
            "Candidate target is no longer a fully transparent Coloring pixel.");
      const int x = static_cast<int>(pixel % static_cast<std::uint32_t>(source.width()));
      const int y = static_cast<int>(pixel / static_cast<std::uint32_t>(source.width()));
      minX = std::min(minX, x);
      minY = std::min(minY, y);
      maxX = std::max(maxX, x);
      maxY = std::max(maxY, y);
      sumX += static_cast<std::uint64_t>(x);
      sumY += static_cast<std::uint64_t>(y);
    }
    const Rect expectedBox{minX, minY, maxX - minX + 1, maxY - minY + 1};
    if (gap.bbox.x != expectedBox.x || gap.bbox.y != expectedBox.y ||
        gap.bbox.width != expectedBox.width || gap.bbox.height != expectedBox.height)
      throw std::invalid_argument("Candidate bounding box does not match its pixels.");
    const double expectedX = static_cast<double>(sumX / gap.area);
    const double expectedY = static_cast<double>(sumY / gap.area);
    if (!std::isfinite(gap.centroid.x) || !std::isfinite(gap.centroid.y) ||
        std::abs(gap.centroid.x - expectedX) > 1e-9 ||
        std::abs(gap.centroid.y - expectedY) > 1e-9)
      throw std::invalid_argument("Candidate centroid does not match its pixels.");

    const auto& targets = candidateApplicationPixels(gap);
    if (targets.empty())
      throw std::invalid_argument("Candidate has no pixels in the application scope.");
    std::unordered_set<std::uint32_t> targetSet;
    for (const auto pixel : targets) {
      if (!targetSet.insert(pixel).second)
        throw std::invalid_argument("Candidate application pixels must be unique.");
      if (!local.contains(pixel))
        throw std::invalid_argument(
            "Candidate application pixels must be a subset of its full geometry.");
      const int x = static_cast<int>(pixel % static_cast<std::uint32_t>(source.width()));
      const int y = static_cast<int>(pixel / static_cast<std::uint32_t>(source.width()));
      if (settings.scope == Scope::SelectionOnly &&
          (selection == nullptr || !selection->selected(x, y))) {
        throw std::invalid_argument("Candidate target is outside the application scope.");
      }
    }
    if (settings.scope == Scope::WholeLayer && targets.size() != gap.pixels.size())
      throw std::invalid_argument(
          "Whole-layer candidates must apply to their complete geometry.");
  }
}

}  // namespace

GeneratedOutputs CorrectionOutputGenerator::generate(
    const Image& source, const std::vector<GapCandidate>& gaps,
    const Settings& settings, const CandidateContext& context,
    const SelectionMask* selection, bool includeCorrectedComposite,
    const DetectionGeometry* geometry) const {
  validateCandidates(source, gaps, settings, context, selection, geometry);
  GeneratedOutputs output{Image(source.width(), source.height()),
                          settings.createHighlightLayer
                              ? Image(source.width(), source.height())
                              : Image(),
                          includeCorrectedComposite ? source : Image(), 0, 0};
  for (const auto& gap : gaps) {
    if (shouldApply(gap)) {
      const auto color = *gap.suggestedColor;
      for (const auto pixel : candidateApplicationPixels(gap)) {
        output.correctionLayer.atIndex(pixel) = color;
        if (includeCorrectedComposite)
          output.correctedComposite.atIndex(pixel) = color;
      }
      ++output.appliedCount;
    }
    if (settings.createHighlightLayer && shouldMark(gap, settings)) {
      drawMarker(output.highlightLayer, gap, markerColor(gap));
      ++output.markedCount;
    }
  }
  return output;
}

void CorrectionOutputGenerator::drawMarker(Image& image, const GapCandidate& gap,
                                           Rgba color) {
  const int centerX = static_cast<int>(std::lround(gap.centroid.x));
  const int centerY = static_cast<int>(std::lround(gap.centroid.y));
  const int radius = std::max(3, static_cast<int>(std::ceil(std::sqrt(gap.area))) + 2);
  const int inner = std::max(0, radius - 2);
  const auto outerSquared = static_cast<std::int64_t>(radius) * radius;
  const auto innerSquared = static_cast<std::int64_t>(inner) * inner;
  for (int y = centerY - radius; y <= centerY + radius; ++y) {
    for (int x = centerX - radius; x <= centerX + radius; ++x) {
      if (x < 0 || y < 0 || x >= image.width() || y >= image.height()) continue;
      const int dx = x - centerX;
      const int dy = y - centerY;
      const auto distance = static_cast<std::int64_t>(dx) * dx +
                            static_cast<std::int64_t>(dy) * dy;
      if (distance <= outerSquared && distance >= innerSquared) image.at(x, y) = color;
    }
  }
  for (int offset = -2; offset <= 2; ++offset) {
    if (centerX + offset >= 0 && centerX + offset < image.width() && centerY >= 0 &&
        centerY < image.height())
      image.at(centerX + offset, centerY) = color;
    if (centerY + offset >= 0 && centerY + offset < image.height() && centerX >= 0 &&
        centerX < image.width())
      image.at(centerX, centerY + offset) = color;
  }
}

}  // namespace gap_assist
