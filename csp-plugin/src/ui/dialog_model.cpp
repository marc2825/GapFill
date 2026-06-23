#include "ui/dialog_model.hpp"

#include <algorithm>

namespace gap_assist {

std::vector<ReviewRow> DialogModel::rows() const {
  std::vector<ReviewRow> result;
  result.reserve(session_.gaps().size());
  for (const auto& gap : session_.gaps()) {
    result.push_back({gap.apply, gap.id, gap.confidence, gap.confidenceBand,
                      gap.suggestedColor, gap.status, gap.bbox});
  }
  return result;
}

std::optional<GapDetail> DialogModel::detail(int gapId) const {
  const auto& gaps = session_.gaps();
  const auto found = std::find_if(gaps.begin(), gaps.end(),
                                  [&](const auto& gap) { return gap.id == gapId; });
  if (found == gaps.end()) return std::nullopt;
  return GapDetail{found->id,         found->bbox,       found->suggestedColor,
                   found->confidence, found->confidenceBand,
                   found->sourceOwnerId};
}

}  // namespace gap_assist
