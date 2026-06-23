#include "core/correction_output.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>

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

}  // namespace

GeneratedOutputs CorrectionOutputGenerator::generate(
    const Image& source, const std::vector<GapCandidate>& gaps,
    const Settings& settings, bool includeCorrectedComposite) const {
  GeneratedOutputs output{Image(source.width(), source.height()),
                          settings.createHighlightLayer
                              ? Image(source.width(), source.height())
                              : Image(),
                          includeCorrectedComposite ? source : Image(), 0, 0};
  for (const auto& gap : gaps) {
    if (shouldApply(gap)) {
      const auto color = *gap.suggestedColor;
      for (const auto pixel : gap.pixels) {
        if (pixel >= source.size()) continue;
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
