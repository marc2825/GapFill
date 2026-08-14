#pragma once

#include <vector>

#include "core/candidate_context.hpp"
#include "core/image_types.hpp"
#include "core/settings.hpp"

namespace gap_assist {

struct GeneratedOutputs {
  Image correctionLayer;
  Image highlightLayer;
  Image correctedComposite;
  std::size_t appliedCount{};
  std::size_t markedCount{};
};

class CorrectionOutputGenerator {
 public:
  [[nodiscard]] GeneratedOutputs generate(
      const Image& source, const std::vector<GapCandidate>& gaps,
      const Settings& settings, const CandidateContext& context,
      const SelectionMask* selection = nullptr,
      bool includeCorrectedComposite = true,
      const DetectionGeometry* geometry = nullptr) const;

 private:
  static void drawMarker(Image& image, const GapCandidate& gap, Rgba color);
};

}  // namespace gap_assist
