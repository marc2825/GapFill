#include "ui/review_session.hpp"

#include <algorithm>

namespace gap_assist {

ReviewSession::ReviewSession(std::vector<GapCandidate> gaps, RunMode mode)
    : gaps_(std::move(gaps)), mode_(mode) {
  initializeModeDefaults();
}

void ReviewSession::initializeModeDefaults() {
  for (auto& gap : gaps_) {
    if (!gap.suggestedColor.has_value()) {
      gap.apply = false;
      gap.status = ReviewStatus::MarkOnly;
      continue;
    }
    if (mode_ == RunMode::OneByOne) {
      gap.apply = false;
      gap.status = ReviewStatus::Unreviewed;
    } else if (gap.confidenceBand == ConfidenceBand::High) {
      gap.apply = true;
      gap.status = ReviewStatus::Apply;
    } else {
      gap.apply = false;
      gap.status = mode_ == RunMode::QuickFix ? ReviewStatus::MarkOnly
                                               : ReviewStatus::Unreviewed;
    }
  }
}

ReviewSummary ReviewSession::summary() const {
  ReviewSummary result;
  result.detected = gaps_.size();
  for (const auto& gap : gaps_) {
    if (gap.confidenceBand == ConfidenceBand::High) ++result.high;
    if (gap.confidenceBand == ConfidenceBand::Medium) ++result.medium;
    if (gap.confidenceBand == ConfidenceBand::Low) ++result.low;
    if (gap.status == ReviewStatus::Apply) ++result.apply;
    if (gap.status == ReviewStatus::Skip) ++result.skip;
    if (gap.status == ReviewStatus::MarkOnly) ++result.markOnly;
  }
  return result;
}

GapCandidate* ReviewSession::find(int gapId) {
  const auto found = std::find_if(gaps_.begin(), gaps_.end(),
                                  [&](const auto& gap) { return gap.id == gapId; });
  return found == gaps_.end() ? nullptr : &*found;
}

bool ReviewSession::setApply(int gapId, bool apply) {
  auto* gap = find(gapId);
  if (gap == nullptr || (apply && !gap->suggestedColor.has_value())) return false;
  gap->apply = apply;
  gap->status = apply ? ReviewStatus::Apply : ReviewStatus::Unreviewed;
  return true;
}

bool ReviewSession::skip(int gapId) {
  auto* gap = find(gapId);
  if (gap == nullptr) return false;
  gap->apply = false;
  gap->status = ReviewStatus::Skip;
  return true;
}

bool ReviewSession::markOnly(int gapId) {
  auto* gap = find(gapId);
  if (gap == nullptr) return false;
  gap->apply = false;
  gap->status = ReviewStatus::MarkOnly;
  return true;
}

void ReviewSession::applySelected(std::span<const int> ids) {
  for (const int id : ids) {
    auto* gap = find(id);
    if (gap != nullptr && gap->status == ReviewStatus::Unreviewed) setApply(id, true);
  }
}

void ReviewSession::skipSelected(std::span<const int> ids) {
  for (const int id : ids) {
    auto* gap = find(id);
    if (gap != nullptr && gap->status == ReviewStatus::Unreviewed) skip(id);
  }
}

void ReviewSession::applyHighConfidence() {
  applyAllRemainingHighConfidence();
}

void ReviewSession::applyAllRemainingHighConfidence() {
  for (auto& gap : gaps_) {
    if (gap.confidenceBand == ConfidenceBand::High &&
        gap.status == ReviewStatus::Unreviewed && gap.suggestedColor.has_value())
      setApply(gap.id, true);
  }
}

GapCandidate* ReviewSession::current() {
  return currentIndex_ < gaps_.size() ? &gaps_[currentIndex_] : nullptr;
}

const GapCandidate* ReviewSession::current() const {
  return currentIndex_ < gaps_.size() ? &gaps_[currentIndex_] : nullptr;
}

bool ReviewSession::next() {
  if (currentIndex_ + 1 >= gaps_.size()) return false;
  ++currentIndex_;
  return true;
}

bool ReviewSession::back() {
  if (currentIndex_ == 0) return false;
  --currentIndex_;
  return true;
}

bool ReviewSession::applyAndNext() {
  auto* gap = current();
  if (gap == nullptr || !setApply(gap->id, true)) return false;
  next();
  return true;
}

bool ReviewSession::skipAndNext() {
  auto* gap = current();
  if (gap == nullptr || !skip(gap->id)) return false;
  next();
  return true;
}

}  // namespace gap_assist
