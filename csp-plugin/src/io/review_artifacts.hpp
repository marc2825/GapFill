#pragma once

#include <filesystem>
#include <vector>

#include "core/image_types.hpp"
#include "ui/review_session.hpp"

namespace gap_assist {

[[nodiscard]] Image renderReviewContactSheet(const Image& source,
                                             const std::vector<GapCandidate>& gaps,
                                             int columns = 4);
void writeGapManifest(const std::filesystem::path& path,
                      const ReviewSession& session, bool includeDebug = false);
void applyDecisionFile(const std::filesystem::path& path, ReviewSession& session);

}  // namespace gap_assist
